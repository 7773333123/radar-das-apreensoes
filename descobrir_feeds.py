#!/usr/bin/env python3
"""Procura o feed RSS/Atom de cada site cadastrado em fontes.json.

Para cada domínio: lê a página inicial e procura <link rel="alternate"
type="application/rss+xml">; se não houver, testa caminhos comuns (/feed,
/rss, /rss.xml...). Guarda em feeds_descobertos.json só feeds válidos e
ativos (com itens), que coletar_feeds_estaduais.py passa a ler.

Uso: python descobrir_feeds.py [--limite 1200] [--trabalhadores 24]
"""
import argparse
import html
import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

PASTA = Path(__file__).resolve().parent
FONTES = PASTA / 'fontes.json'
SAIDA = PASTA / 'feeds_descobertos.json'
FIXOS = PASTA / 'feeds_estaduais.json'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://radar-das-apreensoes.vercel.app)',
           'Accept': 'text/html,application/xhtml+xml,application/rss+xml,application/xml;q=0.9,*/*;q=0.8'}
CAMINHOS = ('/feed/', '/feed', '/rss', '/rss.xml', '/feed.xml', '/index.xml', '/rss/', '/feeds/posts/default',
            '/?feed=rss2', '/noticias/feed/', '/ultimas-noticias/feed/', '/RSS')
# Feeds só da editoria de polícia/segurança: muito mais matérias de apreensão por
# item do que o feed geral (que mistura esporte, política etc.).
CAMINHOS_POLICIA = ('/policia/feed/', '/category/policia/feed/', '/categoria/policia/feed/', '/editoria/policia/feed/',
                    '/policial/feed/', '/category/policial/feed/', '/seguranca/feed/', '/category/seguranca/feed/',
                    '/noticias/policia/feed/', '/cidades/policia/feed/', '/rss/policia', '/policia/rss',
                    '/category/seguranca-publica/feed/', '/seguranca-publica/feed/', '/category/noticias/policia/feed/')
LINK_POLICIA = re.compile(r'href=["\']([^"\']*/(?:category/|categoria/|editoria/)?(?:policia|policial|seguranca|seguranca-publica)/?)["\']', re.I)
LINK_RSS = re.compile(r'<link\b[^>]*type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', re.I)


def baixar(url, limite=1_500_000, timeout=10):
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        return r.geturl(), r.read(limite)


def itens_do_feed(conteudo):
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError:
        return 0
    return sum(1 for el in raiz.iter() if el.tag.rsplit('}', 1)[-1] in ('item', 'entry'))


def procurar(fonte):
    """Feed geral e, se houver, o da editoria de polícia (lista de 0 a 2 feeds)."""
    dominio = fonte['dominio']
    candidatos, policia = [], []
    for base in (f'https://{dominio}/', f'https://www.{dominio}/'):
        try:
            final, pagina = baixar(base, limite=600_000)
        except Exception:
            continue
        texto = pagina.decode('utf-8', 'replace')
        for tag in LINK_RSS.findall(texto):
            m = re.search(r'href=["\']([^"\']+)', tag)
            if m and 'comments' not in m.group(1).lower():
                candidatos.append(urljoin(final, html.unescape(m.group(1))))
        candidatos += [urljoin(final, c) for c in CAMINHOS]
        for m in LINK_POLICIA.findall(texto)[:3]:
            secao = urljoin(final, html.unescape(m)).rstrip('/')
            if dominio in secao:
                policia += [secao + '/feed/', secao + '/rss']
        policia += [urljoin(final, c) for c in CAMINHOS_POLICIA]
        break
    achados = []
    for lista, sufixo, minimo in ((candidatos, '', 5), (policia, ' (Polícia)', 3)):
        vistos = set()
        for url in lista:
            if url in vistos:
                continue
            vistos.add(url)
            try:
                final, conteudo = baixar(url)
            except Exception:
                continue
            n = itens_do_feed(conteudo)
            if n >= minimo and not any(a['url'] == final for a in achados):
                nome = (fonte.get('nome') or dominio) + sufixo
                achados.append({'nome': nome, 'fonte': fonte.get('nome') or dominio,
                                'uf': fonte.get('uf', ''), 'url': final, 'dominio': dominio, 'itens': n,
                                'editoria': 'policia' if sufixo else 'geral'})
                break
    return achados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=1200)
    ap.add_argument('--trabalhadores', type=int, default=24)
    args = ap.parse_args()
    fontes = json.loads(FONTES.read_text(encoding='utf-8'))['fontes']
    fixos = {re.sub(r'^https?://(www\.)?', '', f['url']).split('/')[0] for f in json.loads(FIXOS.read_text(encoding='utf-8'))['feeds']}
    fontes = [f for f in fontes if f['dominio'] not in fixos and f['dominio'] != 'gov.br'][:args.limite]
    print(f'Procurando feeds em {len(fontes)} sites...', flush=True)
    achados = []
    with ThreadPoolExecutor(max_workers=args.trabalhadores) as pool:
        for futuro in as_completed([pool.submit(procurar, f) for f in fontes]):
            try:
                achados += futuro.result() or []
            except Exception:
                pass
    achados.sort(key=lambda f: f['dominio'])
    SAIDA.write_text(json.dumps({'atualizado_em': datetime.now(timezone.utc).isoformat(),
                                 'sites_verificados': len(fontes), 'feeds': achados},
                                ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'Feeds encontrados: {len(achados)} de {len(fontes)} sites '
          f'({sum(1 for a in achados if a.get("editoria") == "policia")} de editoria de polícia) -> {SAIDA.name}')


if __name__ == '__main__':
    main()
