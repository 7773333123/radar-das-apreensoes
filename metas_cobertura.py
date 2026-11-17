#!/usr/bin/env python3
"""Meta mínima de notícias publicadas por mês (coleta retroativa e aviso de cobertura).

A coleta diária começou em out/2026; os meses anteriores são completados pela coleta
retroativa (retroativo.yml). Metas realistas pelo que a internet guarda de cada época.
"""


def meta_mes(ano):
    ano = int(ano)
    if ano >= 2026:
        return 2500
    if ano >= 2020:
        return 1500
    if ano >= 2015:
        return 800
    return 300


def publicadas_no_mes(feed, ym):
    return sum(1 for n in feed.get('noticias', []) if str(n.get('d') or '').startswith(ym))
