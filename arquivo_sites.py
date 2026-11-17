#!/usr/bin/env python3
"""Coleta retroativa no arquivo dos próprios veículos (WordPress), mês a mês.

Boa parte dos portais regionais (sobretudo os da fronteira) usa WordPress, que tem uma
busca pública no próprio arquivo (/wp-json/wp/v2/posts?search=...&after=...&before=...).
Isso dá o link direto da matéria, a data, o título, o resumo e a foto de destaque, sem
depender do Google Notícias (que bloqueia buscas em volume).

Mesmos cuidados das outras coletas:
- robots.txt de cada site respeitado (recuperar_links._robots_permite);
- veículos pagos/bloqueados fora (pagos.py);
- só títulos sobre apreensões (classificar.relevante);
- duplicatas: mesma URL ou mesmo título já no acervo não entram de novo; as
  duplicatas entre veículos são agrupadas depois por duplicatas.py (texto, foto, operação, auditor);
- a matéria é lida depois por ler_materias.py (trecho, fotos, fatos) e só vai ao site
  com foto ou conteúdo (gerar_feed_site.py).

  python arquivo_sites.py --mes 2026-09 [--sites 400] [--tempo-max 2400]
O estado de cada domínio (é WordPress? bloqueia?) fica em arquivo_sites_estado.json.
"""
import argparse
import html
import json
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from classificar import relevante
from pagos import pago

RAIZ = Path(__file__).resolve().parent
ACERVO = RAIZ / 'noticias.json'
ESTADO = RAIZ / 'arquivo_sites_estado.json'
UA = 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://www.radardasapreensoes.com.br)'
# Termos da busca do WordPress (procura no título e no texto, por trecho de palavra).
TERMOS = ('apreens', 'apreende', 'contrabando', 'tráfico de drogas')
# Segunda passada (mês abaixo da meta): termos específicos que a busca geral perde.
TERMOS_EXTRA = ('maconha', 'cocaína', 'fuzil', 'cigarros', 'munições', 'skunk', 'descaminho', 'DOF', 'Gefron', 'BPFron')
POR_PAGINA = 100
MAX_PAGINAS = 4  # por termo e mês: até 400 matérias de um veículo num mês
TRAVA = threading.Lock()


def http_json(url, timeout=15):
    with urlopen(Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'}), timeout=timeout) as r:
        tipo = r.headers.get('Content-Type', '')
        corpo = r.read(6_000_000)
    if 'json' not in tipo:
        raise ValueError('não é JSON')
    return json.loads(corpo.decode('utf-8', 'replace'))


def permitido(base, caminho):
    try:
        from recuperar_links import _robots_permite
        return _robots_permite(base, caminho)
    except Exception:
        return False


def limpar(t):
    t = html.unescape(re.sub(r'<[^>]+>', ' ', str(t or '')))
    return re.sub(r'\s+', ' ', t).strip()


def normal(t):
    t = unicodedata.normalize('NFKD', t or '')
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in t if not unicodedata.combining(c)).lower()).strip()


def foto_destaque(post):
    try:
        midia = (post.get('_embedded') or {}).get('wp:featuredmedia') or []
        if midia and isinstance(midia[0], dict):
            tam = (midia[0].get('media_details') or {}).get('sizes') or {}
            for nome in ('large', 'medium_large', 'full'):
                if tam.get(nome, {}).get('source_url'):
                    return tam[nome]['source_url']
            return midia[0].get('source_url') or ''
    except Exception:
        pass
    return str(post.get('jetpack_featured_media_url') or '')


def buscar_site(fonte, inicio, fim, estado, termos=TERMOS):
    dominio = fonte['dominio'].lower().removeprefix('www.')
    info = estado.get(dominio, {})
    if info.get('wp') is False and info.get('testado', '') >= str(date.today().replace(day=1)):
        return []  # não é WordPress (testado neste mês)
    base = f'https://{fonte["dominio"]}'
    if not permitido(base, '/wp-json/wp/v2/posts'):
        with TRAVA:
            estado[dominio] = {'wp': False, 'motivo': 'robots', 'testado': str(date.today())}
        return []
    itens, vistos = [], set()
    for termo in termos:
        for pagina in range(1, MAX_PAGINAS + 1):
            params = {'search': termo, 'after': f'{inicio}T00:00:00', 'before': f'{fim}T00:00:00',
                      'per_page': POR_PAGINA, 'page': pagina, 'orderby': 'date', 'order': 'desc',
                      '_fields': 'link,date_gmt,date,title,excerpt,jetpack_featured_media_url,_links,_embedded',
                      '_embed': 'wp:featuredmedia'}
            try:
                posts = http_json(f'{base}/wp-json/wp/v2/posts?{urlencode(params)}')
            except Exception as exc:
                if pagina == 1 and termo == termos[0] and not info.get('wp'):
                    with TRAVA:
                        estado[dominio] = {'wp': False, 'motivo': type(exc).__name__, 'testado': str(date.today())}
                    return []
                break
            if not isinstance(posts, list):
                break
            with TRAVA:
                estado[dominio] = {'wp': True, 'testado': str(date.today())}
            for p in posts:
                link = str(p.get('link') or '')
                host = (urlparse(link).hostname or '').lower().removeprefix('www.')
                if not link or not (host == dominio or host.endswith('.' + dominio)) or link in vistos:
                    continue
                vistos.add(link)
                titulo = limpar((p.get('title') or {}).get('rendered'))
                if not titulo or not relevante(titulo):
                    continue
                data = str(p.get('date_gmt') or p.get('date') or '')
                n = {'titulo': titulo, 'url': link, 'url_original': link, 'url_original_status': 'arquivo_do_site',
                     'fonte': fonte.get('nome') or dominio, 'dominio_fonte': dominio, 'pagina_fonte': base,
                     'data_iso': (data[:19] + '+00:00') if data else '', 'origem_coleta': 'arquivo_wp',
                     'leitura_fonte_status': 'pendente_leitura_original'}
                resumo = limpar((p.get('excerpt') or {}).get('rendered'))
                if resumo:
                    n['descricao'] = resumo[:700]
                foto = foto_destaque(p)
                if foto.startswith('http'):
                    n['imagem_url'] = foto
                if not pago(n):
                    itens.append(n)
            if len(posts) < POR_PAGINA:
                break
            time.sleep(0.5)
    return itens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mes', required=True, help='AAAA-MM')
    ap.add_argument('--sites', type=int, default=2000, help='Máximo de sites nesta execução')
    ap.add_argument('--trabalhadores', type=int, default=10)
    ap.add_argument('--tempo-max', type=int, default=2400, help='Segundos no máximo')
    ap.add_argument('--extra', action='store_true', help='Segunda passada: termos específicos, só sites WordPress')
    args = ap.parse_args()
    ano, mes = map(int, args.mes.split('-'))
    inicio = f'{ano}-{mes:02d}-01'
    fim = f'{ano + (mes == 12)}-{1 if mes == 12 else mes + 1:02d}-01'
    fontes = json.loads((RAIZ / 'fontes.json').read_text(encoding='utf-8'))['fontes']
    estado = json.loads(ESTADO.read_text(encoding='utf-8')) if ESTADO.exists() else {}
    # Fronteira primeiro; depois os que já sabemos que são WordPress; depois os não testados.
    fontes = [f for f in fontes if f.get('dominio') and not pago({'dominio_fonte': f['dominio'], 'fonte': f.get('nome', '')})]
    fontes.sort(key=lambda f: (not f.get('fronteira'), not estado.get(f['dominio'].lower().removeprefix('www.'), {}).get('wp', False)))
    fontes = fontes[:args.sites]
    dados = json.loads(ACERVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    urls = {str(n.get('url_original') or n.get('url') or '').split('?')[0].rstrip('/') for n in noticias if isinstance(n, dict)}
    titulos = {(normal(n.get('titulo', ''))[:90], str(n.get('dominio_fonte') or '').removeprefix('www.'))
               for n in noticias if isinstance(n, dict)}
    limite = time.monotonic() + args.tempo_max
    novos, wp, sites_com_noticia = [], 0, 0
    with ThreadPoolExecutor(max_workers=args.trabalhadores) as pool:
        termos = TERMOS_EXTRA if args.extra else TERMOS
        if args.extra:  # segunda passada: só os sites que já sabemos ser WordPress
            fontes = [f for f in fontes if estado.get(f['dominio'].lower().removeprefix('www.'), {}).get('wp')]
        tarefas = {pool.submit(buscar_site, f, inicio, fim, estado, termos): f for f in fontes}
        for fut in as_completed(tarefas):
            try:
                itens = fut.result()
            except Exception:
                itens = []
            if itens:
                sites_com_noticia += 1
            for n in itens:
                chave_u = n['url'].split('?')[0].rstrip('/')
                chave_t = (normal(n['titulo'])[:90], n['dominio_fonte'])
                if chave_u in urls or chave_t in titulos:
                    continue
                urls.add(chave_u)
                titulos.add(chave_t)
                novos.append(n)
            if time.monotonic() > limite:
                print('Tempo esgotado; o restante fica para a próxima execução.', flush=True)
                for t in tarefas:
                    t.cancel()
                break
    wp = sum(1 for v in estado.values() if v.get('wp'))
    noticias.extend(novos)
    if isinstance(dados, dict):
        dados['total'] = len(noticias)
    tmp = ACERVO.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(ACERVO)
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=0, sort_keys=True), encoding='utf-8')
    com_foto = sum(1 for n in novos if n.get('imagem_url'))
    print(f'Arquivo dos sites {args.mes}: {len(fontes)} sites consultados; {wp} são WordPress; '
          f'{sites_com_noticia} com matérias no mês; {len(novos)} notícias novas ({com_foto} com foto).')


if __name__ == '__main__':
    main()
