#!/usr/bin/env python3
"""Avaliação criteriosa dos sites candidatos (candidatos_sites.json) — manual, no GitHub.

Para cada site, com a identificação honesta do Radar e no máximo ~8 acessos:
  1. robots.txt: o site proíbe robôs (Disallow: / para * ou para o Radar)? -> fica de fora;
  2. uma matéria: abre (sem 401/403/429/503)? tem paywall (marcas fortes: piano/tinypass,
     isAccessibleForFree=false, "exclusivo para assinantes", "assine para continuar lendo")?
  3. RSS público: primeiro o da editoria de polícia, depois o geral; itens, foto e texto completo.
Grava avaliacao_sites.json com o veredito de cada site: 'incluir', 'pago', 'bloqueia',
'robots' ou 'sem_rss' (gratuito e aberto, mas sem RSS: entra só na busca por site).
"""
import json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

UA = 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://www.radardasapreensoes.com.br)'
POLICIA = ['/category/policia/feed/', '/policia/feed/', '/editoria/policia/feed/', '/categoria/policia/feed/',
           '/category/seguranca/feed/', '/seguranca/feed/', '/category/seguranca-publica/feed/', '/category/policial/feed/',
           '/policial/feed/', '/rss/policia', '/feed/policia']
GERAL = ['/feed/', '/rss', '/rss.xml', '/feed', '/feed/rss/', '/index.xml', '/rss/ultimas-noticias', '/feed.xml']
PAYWALL = re.compile(r'piano\.io|tinypass\.com|"isAccessibleForFree"\s*:\s*"?(?:false|False)|exclusivo para assinantes|'
                     r'conte[úu]do exclusivo para assinante|assine para (?:continuar|ler|ter acesso)|para continuar lendo,? assine|'
                     r'class="[^"]*(?<!no-)paywall(?!-)[^"]*"', re.I)


def get(url, limite=800_000, timeout=12):
    with urlopen(Request(url, headers={'User-Agent': UA, 'Accept': '*/*', 'Accept-Language': 'pt-BR'}), timeout=timeout) as r:
        return r.status, r.read(limite).decode('utf-8', 'replace')


def robots_bloqueia(dominio, exemplo=''):
    """urllib.robotparser: regras Allow/Disallow completas, para o agente do Radar."""
    from urllib.robotparser import RobotFileParser
    try:
        _, txt = get(f'https://{dominio}/robots.txt', 300_000, 8)
    except Exception:
        return False
    rp = RobotFileParser()
    rp.parse(txt.splitlines())
    return not rp.can_fetch('RadarDasApreensoes', exemplo or f'https://{dominio}/')


def feed(url):
    try:
        _, txt = get(url, 1_500_000)
        raiz = ET.fromstring(txt.encode('utf-8'))
    except Exception:
        return None
    itens = [e for e in raiz.iter() if e.tag.rsplit('}', 1)[-1] in ('item', 'entry')]
    if len(itens) < 3:
        return None
    foto = bool(re.search(r'<(?:media:content|media:thumbnail|enclosure)[^>]+(?:url|href)=|<img\b|&lt;img', txt))
    integral = 'content:encoded' in txt and len(txt) / len(itens) > 2500
    return {'url': url, 'itens': len(itens), 'foto': foto, 'integral': integral}


def avaliar(c):
    d = c['dominio']
    r = {**c, 'veredito': '', 'feed': None, 'motivo': ''}
    if robots_bloqueia(d, c.get('exemplo', '')):
        r.update(veredito='robots', motivo='robots.txt proíbe o Radar')
        return r
    pagina = ''
    if c.get('exemplo'):
        try:
            _, pagina = get(c['exemplo'])
        except Exception as e:
            code = getattr(e, 'code', None)
            if code in (401, 403, 429, 503):
                r.update(veredito='bloqueia', motivo=f'matéria responde {code}')
    if not r['veredito'] and pagina and PAYWALL.search(pagina):
        r.update(veredito='pago', motivo=PAYWALL.search(pagina).group(0)[:60])
    base = f'https://{d}' if d.count('.') > 1 or d.startswith('www.') else f'https://www.{d}'
    achado = None
    m = re.search(r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)', pagina or '')
    candidatos = [base + p for p in POLICIA] + ([m.group(1)] if m and m.group(1).startswith('http') else []) + [base + p for p in GERAL]
    if base != f'https://{d}':
        candidatos += [f'https://{d}{p}' for p in ('/feed/', '/rss')]
    for u in candidatos:
        achado = feed(u)
        if achado:
            achado['editoria'] = 'policia' if any(x in u for x in ('polic', 'segur')) else 'geral'
            break
        time.sleep(0.15)
    r['feed'] = achado
    if not r['veredito']:
        r['veredito'] = 'incluir' if achado else 'sem_rss'
    if r['veredito'] == 'bloqueia' and achado:
        r['veredito'] = 'incluir'  # o próprio site oferece o RSS
        r['motivo'] += '; RSS aberto'
    return r


cands = json.load(open(sys.argv[2] if len(sys.argv) > 2 else 'candidatos_sites.json'))
N = int(sys.argv[1]) if len(sys.argv) > 1 else len(cands)
with ThreadPoolExecutor(16) as p:
    res = list(p.map(avaliar, cands[:N]))
json.dump(res, open('avaliacao_sites.json', 'w'), ensure_ascii=False, indent=1)
from collections import Counter
print('Vereditos:', Counter(r['veredito'] for r in res).most_common())
print('Feeds de polícia:', sum(1 for r in res if r['feed'] and r['feed']['editoria'] == 'policia'),
      '| com foto:', sum(1 for r in res if r['feed'] and r['feed']['foto']))
for r in res:
    f = r['feed'] or {}
    print(f"{r['veredito']:8} {r['noticias_12m']:4} {r['dominio'][:36]:36} {f.get('editoria',''):7} foto={'s' if f.get('foto') else 'n'} {f.get('url','')[:70]} {r['motivo']}")
