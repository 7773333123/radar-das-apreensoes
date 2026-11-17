#!/usr/bin/env python3
"""Sondagem (manual): quais arquivos de notícias guardam anos antigos (2006-2019)?"""
import re, sys
from urllib.request import Request, urlopen

UA = {'User-Agent': 'Mozilla/5.0 (compatible; RadarApreensoes/1.0; pesquisa publica)'}
def get(url):
    try:
        with urlopen(Request(url, headers=UA), timeout=25) as r:
            return r.status, r.read(1_500_000).decode('utf-8', 'replace')
    except Exception as e:
        return type(e).__name__ + ':' + str(getattr(e, 'code', '')), ''

TESTES = []
for ano in (2008, 2012, 2016, 2019):
    TESTES += [
        (f'PF gov.br {ano}', f'https://www.gov.br/pf/pt-br/assuntos/noticias/{ano}/05'),
        (f'Receita gov.br {ano}', f'https://www.gov.br/receitafederal/pt-br/assuntos/noticias/{ano}/maio'),
        (f'PRF gov.br {ano}', f'https://www.gov.br/prf/pt-br/noticias/nacionais/{ano}'),
        (f'Wayback PF {ano}', f'https://web.archive.org/cdx/search/cdx?url=pf.gov.br/imprensa/noticias/*&from={ano}&to={ano}&limit=15&filter=statuscode:200'),
        (f'Wayback PF dpf {ano}', f'https://web.archive.org/cdx/search/cdx?url=dpf.gov.br/agencia/noticias/*&from={ano}&to={ano}&limit=15&filter=statuscode:200'),
        (f'Wayback PRF {ano}', f'https://web.archive.org/cdx/search/cdx?url=prf.gov.br/agencia/*&from={ano}&to={ano}&limit=15&filter=statuscode:200'),
        (f'Wayback Receita {ano}', f'https://web.archive.org/cdx/search/cdx?url=receita.fazenda.gov.br/Noticias/*&from={ano}&to={ano}&limit=15&filter=statuscode:200'),
    ]
TESTES += [
    ('Agência Brasil busca p0', 'https://agenciabrasil.ebc.com.br/busca?search_api_views_fulltext=apreens%C3%A3o'),
    ('Agência Brasil busca p300', 'https://agenciabrasil.ebc.com.br/busca?search_api_views_fulltext=apreens%C3%A3o&page=300'),
    ('Agência Brasil busca p900', 'https://agenciabrasil.ebc.com.br/busca?search_api_views_fulltext=apreens%C3%A3o&page=900'),
    ('Agência Brasil tag', 'https://agenciabrasil.ebc.com.br/tags/apreensao'),
    ('Wayback AgBr 2009', 'https://web.archive.org/cdx/search/cdx?url=agenciabrasil.ebc.com.br/*&from=2009&to=2009&limit=10&filter=original:.*apreen.*'),
]
for nome, url in TESTES:
    st, html = get(url)
    links = set(re.findall(r'href="([^"]+)"', html))
    apreen = [l for l in links if re.search(r'apreen|apreens|contraband|drog|maconha|cocain', l, re.I)]
    linhas = html.count('\n') if 'cdx' in url else 0
    anos = sorted(set(re.findall(r'/(20[01]\d)[-/]', ' '.join(links) + (html if 'cdx' in url else ''))))[:12]
    print(f'{nome:28} {st} links={len(links):4} apreensao={len(apreen):3} linhas_cdx={linhas:3} anos={anos}')
    for l in (apreen[:3] if apreen else (html.splitlines()[:3] if 'cdx' in url else [])):
        print('     ', l[:160])
