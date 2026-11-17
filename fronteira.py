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


# Polos de fronteira de verdade (sem os corredores do interior e os portos), para o bloco
# "Fronteira" da página inicial.
CORREDORES = {'Leste de MS (divisa com SP)', 'Rotas fluviais e portos do Pará', 'Oeste paulista (corredor do PR e de MS)',
              'Corredor do Triângulo Mineiro e de Goiás', 'Portos de exportação'}


@lru_cache(maxsize=1)
def _polos_estritos():
    try:
        polos = json.loads((PASTA / 'polos_fronteira.json').read_text(encoding='utf-8'))['polos']
    except (OSError, ValueError, KeyError):
        return []
    saida = []
    for p in polos:
        if p['nome'] in CORREDORES:
            continue
        termos = sorted({t for t in p['termos'] if len(t) > 3 and not re.match(r'^[A-Z]{2,}-?\d*$', t)}, key=len, reverse=True)
        if termos:
            saida.append((p['nome'], p.get('uf', ''), re.compile(r'(?<![\wÀ-ÿ])(?:' + '|'.join(re.escape(t) for t in termos) + r')(?![\wÀ-ÿ])')))
    return saida


def polo_do_item(item):
    """Polo de fronteira de uma notícia do site (feed): pela cidade do fato ou pelo lugar no título, no mesmo estado."""
    texto = f"{item.get('cid', '')} {item.get('t', '')}"
    if prioridade_regional(item.get('cid', ''), item.get('t', ''), item.get('uf', '')) <= 8:
        return 'Foz do Iguaçu e Lago de Itaipu'
    for nome, uf, regex in _polos_estritos():
        if (not uf or not item.get('uf') or item.get('uf') == uf) and regex.search(texto):
            return nome
    return ''


# Prioridade regional (pedido do responsável, 17/11/2026): sempre Foz do Iguaçu, depois as cidades
# do Lago de Itaipu na ordem abaixo, depois as demais lindeiras e, por último, as outras fronteiras.
PRIORIDADE_CIDADES = [
    ('Foz do Iguaçu', 1), ('Guaíra', 2), ('Toledo', 3), ('Santa Helena', 4), ('Medianeira', 5),
    ('São Miguel do Iguaçu', 6), ('Itaipulândia', 7),
]
LINDEIROS = ['Santa Terezinha de Itaipu', 'Missal', "Diamante D'Oeste", 'Diamante do Oeste', 'São José das Palmeiras',
             'Entre Rios do Oeste', 'Pato Bragado', 'Marechal Cândido Rondon', 'Mercedes', 'Terra Roxa', 'Mundo Novo',
             'Lago de Itaipu', 'Ponte da Amizade']
_CIDADE_RE = [(re.compile(r'(?<![\wÀ-ÿ])' + re.escape(c) + r'(?![\wÀ-ÿ])', re.I), p) for c, p in PRIORIDADE_CIDADES]
_LINDEIRO_RE = re.compile(r'(?<![\wÀ-ÿ])(?:' + '|'.join(re.escape(c) for c in LINDEIROS) + r')(?![\wÀ-ÿ])', re.I)


def prioridade_regional(cidade='', titulo='', uf=''):
    """1 = Foz do Iguaçu ... 7 = Itaipulândia; 8 = demais lindeiras de Itaipu; 9 = outras fronteiras/demais."""
    if uf and uf not in ('PR', 'MS'):
        return 9
    for alvo in (cidade or '', titulo or ''):  # a cidade do fato vale antes de uma citação no título
        for regex, p in _CIDADE_RE:
            if regex.search(alvo) and (uf != 'MS'):
                return p
        if _LINDEIRO_RE.search(alvo):
            return 8
    return 9
