#!/usr/bin/env python3
"""Lê a página original das notícias e traz foto, resumo e, quando permitido, o texto.

Para cada notícia com link original (não Google Notícias):
  - fotos: a principal (og:image / JSON-LD) e as demais fotos do corpo da
    matéria (<figure> e imagens do texto), sem logos, ícones e "leia também";
  - resumo: og:description / description publicados pelo veículo;
  - texto integral: SOMENTE se a página declara licença Creative Commons que
    permite reprodução (ex.: portais gov.br, CC BY-ND 3.0). O texto é guardado
    sem alterações, com a licença, para ser exibido com crédito. Conteúdo com
    direitos reservados (jornais) fica só com resumo, foto e link.

Uso: python ler_materias.py --limite 400
"""
import argparse
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ARQUIVO = Path(__file__).resolve().parent / 'noticias.json'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://radar-das-apreensoes.vercel.app)',
    'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'pt-BR,pt;q=0.9',
}
# Licenças CC que permitem reproduzir o texto (sem "NãoComercial", por cautela).
LICENCA = re.compile(
    r'creativecommons\.org/licenses/(by|by-sa|by-nd)/[\d.]+|'
    r'Creative Commons Atribui[çc][ãa]o(?:-SemDeriva[çc][õo]es|-CompartilhaIgual)?\s*[\d.]*(?:\s*N[ãa]o Adaptada|\s*Internacional|\s*Brasil)?',
    re.I)
NAO_COMERCIAL = re.compile(r'N[ãa]oComercial|licenses/by-nc', re.I)
VERSAO = 2  # 2 = também coleta a galeria de fotos; notícias lidas na versão 1 são relidas
MAX_FOTOS = 12
NAO_FOTO = re.compile(r'logo|icon|icone|avatar|sprite|banner|placeholder|blank|pixel|spacer|loading|selo|'
                      r'whatsapp-share|/ads?/|publicidade|video\.glbimg|/x240/|\.svg(?:$|\?)|\.gif(?:$|\?)', re.I)
CONTATO = re.compile(r'^(?:Comunica[çc][ãa]o Social|Assessoria de|Ascom|Tel\.?:|E-?mail:|Fonte:|Fotos?:|@)', re.I)


class Metas(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.base = {}, ''

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'base' and a.get('href'):
            self.base = a['href']
        if tag == 'meta':
            chave = (a.get('property') or a.get('name') or a.get('itemprop') or '').lower()
            if chave and a.get('content') and chave not in self.meta:
                self.meta[chave] = a['content'].strip()


def valida(url):
    try:
        p = urlsplit(str(url).strip())
        return p.scheme in ('http', 'https') and bool(p.hostname) and 'news.google.com' not in p.hostname
    except (TypeError, ValueError):
        return False


def limpar(fragmento):
    texto = re.sub(r'<br\s*/?>', ' ', fragmento or '', flags=re.I)
    texto = re.sub(r'<[^>]+>', '', texto)
    return re.sub(r'\s+', ' ', html.unescape(texto)).strip()


def corpo_da_materia(pagina):
    """Parágrafos do corpo da matéria (Plone/gov.br, schema.org ou <article>)."""
    for padrao in (r'property="rnews:articleBody"[^>]*>(.*?)</div>\s*</div>',
                   r'itemprop="articleBody"[^>]*>(.*?)</(?:div|section|article)>',
                   r'<article\b[^>]*>(.*?)</article>'):
        m = re.search(padrao, pagina, re.S | re.I)
        if not m:
            continue
        paragrafos = [limpar(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', m.group(1), re.S | re.I)]
        paragrafos = [p for p in paragrafos if len(p) > 1 and not CONTATO.match(p)]
        if sum(len(p) for p in paragrafos) > 200:
            return paragrafos[:40]
    # Último recurso (só usado em páginas de licença aberta): o bloco da página
    # com mais texto em parágrafos — o corpo da matéria em quase todo CMS.
    melhor = []
    for bloco in re.findall(r'<(?:div|section|article)\b[^>]*>((?:(?!</?(?:div|section|article)\b).)*?)</(?:div|section|article)>',
                            pagina, re.S | re.I):
        paragrafos = [limpar(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', bloco, re.S | re.I)]
        paragrafos = [p for p in paragrafos if len(p) > 40 and not CONTATO.match(p)]
        if sum(map(len, paragrafos)) > sum(map(len, melhor)):
            melhor = paragrafos
    return melhor[:40] if sum(map(len, melhor)) > 400 else []


def melhor_do_srcset(srcset):
    """Escolhe a maior versão até ~1200 px de largura num srcset."""
    opcoes = []
    for parte in srcset.split(','):
        bits = parte.strip().split()
        if not bits:
            continue
        largura = int(bits[1][:-1]) if len(bits) > 1 and bits[1].endswith('w') and bits[1][:-1].isdigit() else 0
        opcoes.append((largura, bits[0]))
    if not opcoes:
        return ''
    ate = [o for o in opcoes if o[0] <= 1200]
    return max(ate or opcoes)[1]


def fotos_da_materia(pagina, base):
    """Fotos dentro de <figure> e do corpo do texto, na ordem em que aparecem."""
    trechos = re.findall(r'<figure\b.*?</figure>', pagina, re.S | re.I)
    for padrao in (r'property="rnews:articleBody"[^>]*>(.*?)</div>\s*</div>',
                   r'itemprop="articleBody"[^>]*>(.*?)</(?:div|section)>'):
        m = re.search(padrao, pagina, re.S | re.I)
        if m:
            trechos.append(m.group(1))
    fotos = []
    for trecho in trechos:
        for tag in re.findall(r'<(?:amp-)?img\b[^>]*>', trecho, re.I):
            atributos = dict((k.lower(), html.unescape(v)) for k, _, v in
                             re.findall(r'([\w:-]+)\s*=\s*(["\'])(.*?)\2', tag, re.S))
            url = (melhor_do_srcset(atributos.get('srcset') or atributos.get('data-srcset') or '')
                   or atributos.get('data-src') or atributos.get('src') or '')
            largura = atributos.get('width', '')
            if not url or url.startswith('data:') or NAO_FOTO.search(url):
                continue
            if largura.isdigit() and int(largura) < 200:
                continue
            fotos.append(urljoin(base, url))
    return fotos


def sem_repetir(urls):
    vistos, saida = set(), []
    for u in urls:
        chave = re.sub(r'[?#].*$', '', u).rsplit('/', 1)[-1].lower()  # mesmo arquivo em tamanhos diferentes
        if valida(u) and chave not in vistos:
            vistos.add(chave)
            saida.append(u)
    return saida[:MAX_FOTOS]


def imagem_jsonld(pagina, base):
    for bloco in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', pagina, re.S | re.I):
        try:
            pilha = [json.loads(html.unescape(bloco))]
        except ValueError:
            continue
        while pilha:
            item = pilha.pop()
            if isinstance(item, list):
                pilha.extend(item)
            elif isinstance(item, dict):
                tipo = item.get('@type')
                tipos = tipo if isinstance(tipo, list) else [tipo]
                if any(t in ('NewsArticle', 'Article', 'ReportageNewsArticle') for t in tipos):
                    img = item.get('image') or item.get('thumbnailUrl')
                    for c in (img if isinstance(img, list) else [img]):
                        c = c.get('url') if isinstance(c, dict) else c
                        if isinstance(c, str) and valida(urljoin(base, c)):
                            return urljoin(base, c)
                pilha.extend(v for v in item.values() if isinstance(v, (list, dict)))
    return ''


def ler(url, timeout):
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        if 'html' not in (r.headers.get('Content-Type') or '').lower():
            return {'erro': 'nao_html'}
        pagina = r.read(2_500_000).decode(r.headers.get_content_charset() or 'utf-8', 'replace')
        final = r.geturl()
    metas = Metas()
    metas.feed(pagina)
    base = urljoin(final, metas.base) if metas.base else final
    m = metas.meta
    resultado = {}
    for chave in ('og:image', 'og:image:url', 'og:image:secure_url', 'twitter:image', 'twitter:image:src'):
        if m.get(chave) and valida(urljoin(base, m[chave])):
            resultado['imagem'] = urljoin(base, html.unescape(m[chave]))
            break
    else:
        img = imagem_jsonld(pagina, base)
        if img:
            resultado['imagem'] = img
    resumo = m.get('og:description') or m.get('description') or m.get('twitter:description') or ''
    if resumo:
        resultado['resumo'] = limpar(resumo)[:1000]
    resultado['imagens'] = sem_repetir(([resultado['imagem']] if resultado.get('imagem') else []) +
                                       fotos_da_materia(pagina, base))
    if resultado['imagens'] and not resultado.get('imagem'):
        resultado['imagem'] = resultado['imagens'][0]
    licenca = LICENCA.search(pagina)
    if licenca and not NAO_COMERCIAL.search(pagina[max(0, licenca.start() - 300):licenca.end() + 300]):
        texto = corpo_da_materia(pagina)
        if texto:
            resultado['texto'] = texto
            resultado['licenca'] = limpar(licenca.group(0))
    return resultado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=1500, help='Páginas lidas por execução')
    ap.add_argument('--timeout', type=int, default=12)
    ap.add_argument('--trabalhadores', type=int, default=8)
    ap.add_argument('--max-tentativas', type=int, default=3)
    args = ap.parse_args()
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    pendentes = []
    for n in noticias:
        if not isinstance(n, dict) or int(n.get('materia_lida_v') or 0) >= VERSAO:
            continue
        url = n.get('url_original') if valida(n.get('url_original')) else (n.get('url') if valida(n.get('url')) else '')
        if url and int(n.get('tentativas_leitura') or 0) < args.max_tentativas:
            pendentes.append((n, url))
    # Mais recentes primeiro.
    pendentes.sort(key=lambda p: p[0].get('data_iso') or '', reverse=True)
    lote = pendentes[:max(0, args.limite)]
    print(f'Notícias com link original ainda não lidas: {len(pendentes)}; lendo agora: {len(lote)}', flush=True)
    fotos = textos = resumos = falhas = galerias = 0
    with ThreadPoolExecutor(max_workers=max(1, min(args.trabalhadores, 10))) as pool:
        tarefas = {pool.submit(ler, url, args.timeout): n for n, url in lote}
        for futuro in as_completed(tarefas):
            n = tarefas[futuro]
            try:
                r = futuro.result()
            except Exception as exc:  # rede, HTTP 4xx/5xx, página malformada
                r = {'erro': type(exc).__name__}
            if r.get('erro'):
                n['tentativas_leitura'] = int(n.get('tentativas_leitura') or 0) + 1
                n['leitura_fonte_status'] = 'erro_' + r['erro']
                falhas += 1
                continue
            n['materia_lida'] = time.strftime('%Y-%m-%d')
            n['materia_lida_v'] = VERSAO
            if r.get('imagens'):
                n['imagens'] = r['imagens']
                galerias += 1
            n['leitura_fonte_status'] = 'lida'
            if r.get('imagem') and not n.get('imagem_url'):
                n['imagem_url'] = r['imagem']
                n['imagem_status'] = 'metadados_da_fonte'
                fotos += 1
            if r.get('resumo') and not (n.get('descricao') or n.get('resumo')):
                n['resumo'] = r['resumo']
                resumos += 1
            if r.get('texto'):
                n['texto_integral'] = r['texto']
                n['licenca_texto'] = r['licenca']
                textos += 1
    if lote:
        tmp = ARQUIVO.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        tmp.replace(ARQUIVO)
    print(f'Lidas: {len(lote) - falhas}/{len(lote)}; fotos novas: {fotos}; resumos novos: {resumos}; '
          f'notícias com galeria: {galerias}; textos integrais (licença aberta): {textos}; falhas: {falhas}')


if __name__ == '__main__':
    main()
