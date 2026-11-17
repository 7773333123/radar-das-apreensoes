#!/usr/bin/env python3
"""Verificação (manual): veículos que bloqueiam a leitura automática das matérias publicam RSS aberto?

Para os ~250 veículos com mais notícias no acervo e sem feed cadastrado: testa uma matéria
(identificação honesta do Radar, sem disfarce) e os endereços comuns de RSS. Um RSS público é
o canal que o próprio site oferece para reaproveitamento; se o RSS também bloquear, respeitamos.
Grava rss_verificados.json (candidatos com foto/texto) e imprime o resumo.
"""
import json, re, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

UA = 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://www.radardasapreensoes.com.br)'
CAMINHOS = ['/feed/', '/rss', '/feed', '/rss.xml', '/feed/rss/', '/index.php/feed/', '/category/policia/feed/',
            '/policia/feed/', '/editoria/policia/feed/', '/rss/policia', '/feed/atom/']
OFICIAL = re.compile(r'\.(?:gov|jus|mp|leg|def)\.br$')
N = int(sys.argv[1]) if len(sys.argv) > 1 else 250


def get(url, limite=600_000):
    with urlopen(Request(url, headers={'User-Agent': UA, 'Accept': '*/*'}), timeout=12) as r:
        return r.status, r.read(limite)


def testar_feed(url):
    try:
        st, corpo = get(url)
        raiz = ET.fromstring(corpo)
    except Exception as e:
        return None
    itens = [el for el in raiz.iter() if el.tag.rsplit('}', 1)[-1] in ('item', 'entry')]
    if not itens:
        return None
    texto = corpo.decode('utf-8', 'replace')
    foto = bool(re.search(r'<(?:media:content|media:thumbnail|enclosure)[^>]+(?:url|href)=|<img\b|&lt;img', texto))
    integral = bool(re.search(r'content:encoded', texto)) and len(texto) / max(1, len(itens)) > 2500
    return {'url': url, 'itens': len(itens), 'foto': foto, 'texto_integral': integral}


def verificar(dominio, exemplo):
    try:
        st, _ = get(exemplo, 50_000)
        bloqueia = False
    except Exception as e:
        bloqueia = getattr(e, 'code', None) in (401, 403, 429, 503)
    feeds = []
    for c in CAMINHOS:
        f = testar_feed(f'https://{dominio}{c}')
        if f and all(f['url'].rstrip('/') != x['url'].rstrip('/') for x in feeds):
            feeds.append(f)
        if len(feeds) >= 2:
            break
    return {'dominio': dominio, 'bloqueia_materia': bloqueia, 'feeds': feeds}


ns = json.load(open('noticias.json'))['noticias']
cadastrados = set()
for arq, chave in (('feeds_estaduais.json', 'feeds'), ('feeds_descobertos.json', 'feeds')):
    for f in json.load(open(arq))[chave]:
        cadastrados.add((urlsplit(f['url']).hostname or '').removeprefix('www.'))
cont, exemplo = Counter(), {}
for n in ns:
    u = str(n.get('url_original') or '')
    if not u.startswith('http') or 'news.google' in u:
        continue
    h = urlsplit(u).hostname or ''
    if OFICIAL.search(h) or h.removeprefix('www.') in cadastrados:
        continue
    cont[h] += 1
    exemplo.setdefault(h, u)
alvos = [h for h, _ in cont.most_common(N)]
with ThreadPoolExecutor(12) as p:
    res = list(p.map(lambda h: verificar(h, exemplo[h]), alvos))
bloq = [r for r in res if r['bloqueia_materia']]
print(f'Veículos verificados: {len(res)}; bloqueiam a matéria: {len(bloq)}; '
      f'com RSS aberto: {sum(1 for r in res if r["feeds"])}; bloqueiam mas têm RSS aberto: {sum(1 for r in bloq if r["feeds"])}')
for r in sorted(res, key=lambda r: (not r['bloqueia_materia'], -cont[r['dominio']])):
    f = r['feeds'][0] if r['feeds'] else None
    print(f"{r['dominio'][:34]:34} notícias={cont[r['dominio']]:4} bloqueia={'sim' if r['bloqueia_materia'] else 'não'} "
          f"rss={'sim' if f else 'não'}" + (f" foto={'sim' if f['foto'] else 'não'} integral={'sim' if f['texto_integral'] else 'não'} {f['url']}" if f else ''))
json.dump(res, open('rss_verificados.json', 'w'), ensure_ascii=False, indent=1)
