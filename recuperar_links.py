#!/usr/bin/env python3
"""Recupera links de origem do Google Notícias, preservando o acervo."""
import argparse
import base64
import html
import json
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, unquote
from urllib.request import Request, urlopen

ARQUIVO = Path(__file__).resolve().parent / 'noticias.json'
BLOQUEADOS = ('google.com', 'googleusercontent.com', 'googleapis.com', 'gstatic.com', 'youtube.com')
HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36', 'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.7'}

def valida(url):
    if not isinstance(url, str): return False
    try:
        p = urlparse(html.unescape(url).strip())
        h = (p.hostname or '').lower()
        return p.scheme in ('http', 'https') and bool(h) and not any(h == d or h.endswith('.'+d) for d in BLOQUEADOS)
    except ValueError: return False

def fetch(url, data=None, timeout=10):
    headers = dict(HEADERS)
    if data is not None: headers['Content-Type'] = 'application/x-www-form-urlencoded;charset=UTF-8'
    with urlopen(Request(url, data=data, headers=headers), timeout=timeout) as r:
        return r.geturl(), r.read(350000).decode('utf-8', 'replace')

def codigo_embutido(url):
    try:
        token = urlparse(url).path.rstrip('/').split('/')[-1]
        raw = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4))
        for m in re.finditer(rb'https?://[^\x00-\x20\x7f"\'<>]+', raw):
            candidate = m.group().decode('utf-8', 'ignore')
            if valida(candidate): return candidate
    except Exception: pass
    return ''

def url_no_html(page):
    patterns = [r'<link\b(?=[^>]*\brel=["\']canonical["\'])(?=[^>]*\bhref=["\']([^"\']+))',
                r'<meta\b(?=[^>]*\bproperty=["\']og:url["\'])(?=[^>]*\bcontent=["\']([^"\']+))']
    for pattern in patterns:
        for m in re.finditer(pattern, page, re.I):
            candidate = html.unescape(m.group(1))
            if valida(candidate): return candidate
    return ''

def google_rpc(url):
    token = urlparse(url).path.rstrip('/').split('/')[-1]
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,}', token): return '', 'codigo_invalido'
    try:
        _, page = fetch('https://news.google.com/rss/articles/'+token+'?hl=pt-BR&gl=BR&ceid=BR:pt-419')
        # O Google alterna aspas, escapes e serialização de atributos.
        normalized = html.unescape(page).replace('\\"', '"')
        ident = re.search(r'data-n-a-id\s*=\s*["\']([^"\']+)', normalized)
        sign = re.search(r'data-n-a-sg\s*=\s*["\']([^"\']+)', normalized)
        if not ident or not sign:
            return '', 'assinatura_ausente'+('_id' if ident else '_sem_id')+('_sg' if sign else '_sem_sg')+('_html' if '<html' in page.lower() else '_outro')
        # Estrutura garturlreq: id e assinatura pertencem ao mesmo vetor interno.
        request = ['garturlreq', [['pt-BR','BR',['FINANCE_TOP_INDICES','WEB_TEST_1_0_0'],None,None,1,1,'BR:pt-419',None,180,None,None,None,None,None,0,None,None,[1608992183,723341000]], 'pt-BR','BR',1,[2,3,4,8],1,0,'655000234',0,0,None,0], ident.group(1), sign.group(1)]
        body = json.dumps([[['Fbv4je', json.dumps(request, separators=(',',':')), None, 'generic']]], separators=(',',':'))
        _, response = fetch('https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je', urlencode({'f.req':body}).encode())
        # A resposta é JSON aninhado. URLs externas só são aceitas se aparecem no resultado RPC.
        for candidate in re.findall(r'https?://[^\\"\s<>\[\]]+', response):
            candidate = html.unescape(candidate.rstrip('\\,;'))
            if valida(candidate): return candidate, 'recuperada_rpc'
        for candidate in re.findall(r'https?:\\/\\/[^"\s<>\[\]]+', response):
            candidate = candidate.replace('\\/', '/')
            if valida(candidate): return candidate, 'recuperada_rpc'
        return '', 'rpc_sem_url'
    except Exception as exc:
        return '', 'rpc_'+type(exc).__name__

def resolver(url):
    embedded = codigo_embutido(url)
    if embedded: return embedded, 'recuperada_codigo'
    for key in ('url','u','q','target'):
        for candidate in parse_qs(urlparse(url).query).get(key, []):
            if valida(candidate): return candidate, 'recuperada_parametro'
    # Tenta também o decodificador mantido pela comunidade, quando instalado.
    try:
        from googlenewsdecoder import gnewsdecoder
        decoded = gnewsdecoder(url, interval=0)
        if isinstance(decoded, dict):
            candidate = decoded.get('decoded_url') or decoded.get('url') or ''
            if decoded.get('status') and valida(candidate):
                return candidate, 'recuperada_decoder'
    except Exception as exc:
        if os.getenv('RADAR_DIAGNOSTICO') == '1':
            print('Decodificador:', type(exc).__name__, str(exc)[:140], flush=True)
    candidate, status = google_rpc(url)
    if candidate: return candidate, status
    try:
        destination, page = fetch(url)
        if valida(destination): return destination, 'recuperada_redirecionamento'
        candidate = url_no_html(page)
        if candidate: return candidate, 'recuperada_canonical'
    except Exception as exc:
        return '', status+'+http_'+type(exc).__name__
    return '', status

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=int(os.getenv('LIMITE_DECODIFICACAO','60')))
    ap.add_argument('--trabalhadores', type=int, default=4)
    ap.add_argument('--diagnostico', action='store_true', help='Exibe amostra de erros sem revelar dados privados')
    args = ap.parse_args()
    if not ARQUIVO.exists(): raise SystemExit('noticias.json ausente; nada alterado')
    data = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    news = data.get('noticias') if isinstance(data,dict) else data
    if not isinstance(news,list): raise SystemExit('Formato inválido; nada alterado')
    pending=[]; existing=0
    for article in news:
        if not isinstance(article,dict): continue
        if valida(article.get('url_original')): existing+=1; continue
        url = article.get('url_google_noticias') or article.get('url') or ''
        if valida(url):
            article['url_original']=url; article['url_original_status']='direta'; existing+=1
        elif isinstance(url,str) and 'news.google.com/' in url:
            pending.append((article,url))
    pending.sort(key=lambda x: (x[0].get('url_original_status') not in ('aguardando_resolucao',None,''), x[0].get('url_original_status','')))
    batch=pending[:max(0,args.limite)]
    print(f'Acervo: {len(news)}; links originais: {existing}; pendentes: {len(pending)}; tentativas: {len(batch)}', flush=True)
    successes=0; errors=Counter()
    with ThreadPoolExecutor(max_workers=max(1,min(args.trabalhadores,6))) as pool:
        futures={pool.submit(resolver,url):(article,url) for article,url in batch}
        for future in as_completed(futures):
            article,url=futures[future]
            try: original,status=future.result()
            except Exception as exc: original,status='', 'erro_'+type(exc).__name__
            article.setdefault('url_google_noticias',url)
            if original and valida(original):
                article['url_original']=original
                article['url_original_status']=status
                article['leitura_fonte_status']='pendente_leitura_original'
                successes+=1
            else:
                article['url_original_status']=status
                errors[status]+=1
    if batch:
        temp=ARQUIVO.with_suffix('.json.tmp')
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(ARQUIVO)
    print(f'Recuperados: {successes}/{len(batch)}; falhas: {dict(errors)}; acervo preservado: {len(news)}',flush=True)
    if batch and not successes: print('AVISO: nenhuma URL recuperada. Consulte os códigos de falha acima.',flush=True)
    if args.diagnostico: print('Diagnóstico:',dict(errors),'| notícias preservadas:',len(news),flush=True)

if __name__=='__main__': main()
