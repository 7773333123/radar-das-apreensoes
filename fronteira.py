#!/usr/bin/env python3
"""Notícias das regiões de fronteira: prioridade na coleta (leitura da matéria, link original).

Uma notícia é "de fronteira" quando vem de um site marcado com "fronteira" em fontes.json
(124 sites dos polos de polos_fronteira.json) ou quando o título cita um lugar dos polos.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

PASTA = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _dados():
    try:
        fontes = json.loads((PASTA / 'fontes.json').read_text(encoding='utf-8'))['fontes']
        dominios = {f['dominio'].lower().removeprefix('www.') for f in fontes if f.get('fronteira')}
        nomes = {str(f.get('nome') or '').strip().lower() for f in fontes if f.get('fronteira')} - {''}
    except (OSError, ValueError, KeyError):
        dominios, nomes = set(), set()
    try:
        polos = json.loads((PASTA / 'polos_fronteira.json').read_text(encoding='utf-8'))['polos']
        termos = sorted({t for p in polos for t in p['termos'] if len(t) > 3 and not re.match(r'^[A-Z]{2,}-?\d*$', t)}, key=len, reverse=True)
        lugares = re.compile(r'(?<![\wÀ-ÿ])(?:' + '|'.join(re.escape(t) for t in termos) + r')(?![\wÀ-ÿ])')
    except (OSError, ValueError, KeyError):
        lugares = None
    return dominios, nomes, lugares


def de_fronteira(n):
    """A notícia (do acervo) é de site ou de lugar de fronteira?"""
    dominios, nomes, lugares = _dados()
    for campo in ('url_original', 'url', 'dominio_fonte'):
        v = str(n.get(campo) or '')
        h = (urlsplit(v).hostname or '') if '://' in v else v
        h = h.lower().removeprefix('www.')
        if h and any(h == d or h.endswith('.' + d) for d in dominios):
            return True
    if str(n.get('fonte') or '').strip().lower() in nomes:
        return True
    return bool(lugares and lugares.search(str(n.get('titulo') or '')))
