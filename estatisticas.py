#!/usr/bin/env python3
"""Quantidades normalizadas e dados abertos do Radar (usado por gerar_feed_site.py).

Converte as fichas de fatos (resumo_fatos.py) em números comparáveis:
  drogas em kg (cocaína, maconha, crack, haxixe/skunk, outras), armas e
  munições em unidades, valores em reais. Tudo é calculado DEPOIS de agrupar
  duplicatas, para a mesma apreensão não ser somada duas vezes.

Os números são "apreensões noticiadas": dependem de a notícia citar a
quantidade e não equivalem a estatísticas oficiais.
"""
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from resumo_fatos import ORGAOS

ORGAOS_NOMES = [nome for nome, _ in ORGAOS]
MATERIAIS = {  # código -> (rótulo, unidade)
    'coc': ('Cocaína e pasta base', 'kg'),
    'mac': ('Maconha', 'kg'),
    'skh': ('Skunk e haxixe', 'kg'),
    'cra': ('Crack', 'kg'),
    'dro': ('Outras drogas', 'kg'),
    'arm': ('Armas de fogo', 'un'),
    'fuz': ('Fuzis', 'un'),
    'mun': ('Munições', 'un'),
    'val': ('Valores citados', 'R$'),
}
_DROGA = [('coc', r'coca[ií]na|pasta[ -]base|cloridrato'), ('cra', r'\bcrack\b'),
          ('skh', r'sk[ua]nk|haxixe|supermaconha'), ('mac', r'maconha|cannabis|\berva\b'),
          ('dro', r'drogas?|entorpecentes?|subst[âa]ncias?|ecstasy|lsd|metanfetamina|k9')]
_ARMA = r'^(?:armas?(?: de fogo)?|pistolas?|rev[óo]lver(?:es)?|espingardas?|carabinas?|metralhadoras?|fuzis|fuzil|submetralhadoras?)$'
# Teto por notícia: acima disso é balanço, estimativa ou erro de leitura, não uma apreensão.
LIMITES = {'kg': 8_000, 'un': 20_000, 'R$': 5e10}
TETO = {'arm': 300, 'fuz': 100, 'mun': 20_000}
# Só entram nas somas notícias de uma apreensão concreta...
APREENSAO = re.compile(r'apreend|apreens|flagra|intercept|encontr|localiz|descobr|retid|confisc|'
                       r'pres[oa]s? com|carregad[oa] com|escondid|recolh|incinera', re.I)
# ...e não balanços, hipóteses, acusações ou fatos no exterior.
NAO_SOMAR = re.compile(r'\bbalan[çc]o\b|\btotal\b|acumulad|\bem (?:19|20)\d\d\b|\bno ano\b|\bdesde\b|'
                       r'\bpoderia\b|refinaria|seria(?:m)? capaz|\bcapaz de\b|estimad|acusad|suspeit[oa] de traficar|'
                       r'procurad|\bBol[ií]via\b|\bParaguai\b|\bCol[ôo]mbia\b|\bPeru\b|\bEUA\b|\bEuropa\b|'
                       r'\bmundo\b|\bONU\b|\bInterpol\b|\bem \d+ (?:anos|meses)\b|\bsemestre\b|\bmês\b|\bsemana\b|'
                       r'^em (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b|'
                       r'homenagead|incinera|incinerad|incinera[çc][ãa]o|destrui[çc][ãa]o de drogas|destr[óo]i\b|queima de drogas', re.I)


def _numero(texto):
    return float(texto.replace('.', '').replace(',', '.'))


def somavel(titulo):
    """A notícia descreve uma apreensão concreta (e não balanço/hipótese/exterior)?"""
    return bool(APREENSAO.search(titulo or '')) and not NAO_SOMAR.search(titulo or '')


def quantidades(fatos):
    """{'coc': kg, 'arm': n, ...} a partir de fatos['apreendido'] e fatos['valor']."""
    q = {}

    def somar(codigo, valor):
        unidade = MATERIAIS[codigo][1]
        if 0 < valor <= min(LIMITES[unidade], TETO.get(codigo, LIMITES[unidade])):
            q[codigo] = round(q.get(codigo, 0) + valor, 3)

    for item in (fatos or {}).get('apreendido', []):
        m = re.match(r'^([\d.,]+)\s+(.+)$', item)
        if not m:
            continue
        valor, resto = _numero(m.group(1)), m.group(2).lower()
        partes = resto.split(' de ', 1)
        unidade, material = (partes[0], partes[1]) if len(partes) == 2 else ('', resto)
        if unidade in ('kg', 'quilo', 'quilos', 'toneladas', 'tonelada', 'gramas', 'grama', 'g'):
            kg = valor * (1000 if unidade.startswith('tonelada') else 0.001 if unidade.startswith('g') else 1)
            for codigo, padrao in _DROGA:
                if re.search(padrao, material):
                    somar(codigo, kg)
                    break
        elif re.match(_ARMA, resto):
            somar('arm', valor)
            if resto.startswith('fuzi'):
                somar('fuz', valor)
        elif re.match(r'^muni[çc][õo]es|^cartuchos', resto):
            somar('mun', valor)
    valor = (fatos or {}).get('valor', '')
    m = re.match(r'R\$ ([\d.,]+)(?: (mil|milhão|milhões|bilhão|bilhões))?', valor)
    if m:
        mult = {'mil': 1e3, 'milhão': 1e6, 'milhões': 1e6, 'bilhão': 1e9, 'bilhões': 1e9}.get(m.group(2), 1)
        somar('val', _numero(m.group(1)) * mult)
    return q


def enriquecer(item, fatos):
    """Acrescenta ao item do feed: q (quantidades), ag (órgãos), rd (rodovia).

    q só existe para apreensões concretas (somavel); "val" (valores em R$) mistura
    mercadorias, bens bloqueados e fraudes, então vai como vq, fora das somas.
    """
    if not fatos:
        return
    q = quantidades(fatos) if somavel(item.get('t')) else {}
    if 'val' in q:
        item['vq'] = q.pop('val')
    if q:
        item['q'] = q
    ag = [ORGAOS_NOMES.index(o) for o in fatos.get('orgaos', []) if o in ORGAOS_NOMES]
    if ag:
        item['ag'] = ag
    if fatos.get('rodovia'):
        item['rd'] = fatos['rodovia']


CAMPOS_CSV = ['id', 'data', 'titulo', 'fonte', 'uf', 'categorias', 'orgaos', 'rodovia',
              'cocaina_kg', 'maconha_kg', 'skunk_haxixe_kg', 'crack_kg', 'outras_drogas_kg',
              'armas', 'fuzis', 'municoes', 'valor_rs', 'outras_fontes', 'link']
DICIONARIO = {
    'id': 'Identificador estável da notícia no acervo do Radar',
    'data': 'Data e hora de publicação (UTC), conferida na página original quando possível',
    'titulo': 'Título da notícia, sem o nome do veículo',
    'fonte': 'Veículo ou órgão que publicou a versão exibida',
    'uf': 'Estado identificado por evidência explícita (vazio quando incerto)',
    'categorias': 'Tipos de apreensão separados por "|"',
    'orgaos': 'Órgãos citados (PF, PRF, PM, PC...) separados por "|"',
    'rodovia': 'Rodovia citada (BR-xxx ou estadual)',
    'cocaina_kg': 'Cocaína e pasta base apreendidas, em kg, quando a notícia informa',
    'maconha_kg': 'Maconha apreendida, em kg',
    'skunk_haxixe_kg': 'Skunk e haxixe, em kg',
    'crack_kg': 'Crack, em kg',
    'outras_drogas_kg': 'Drogas não especificadas ou outras, em kg',
    'armas': 'Armas de fogo (inclui fuzis), em unidades',
    'fuzis': 'Fuzis, em unidades',
    'municoes': 'Munições, em unidades',
    'valor_rs': 'Maior valor em reais citado na notícia (mercadorias, bens ou dinheiro)',
    'outras_fontes': 'Outros veículos que publicaram a mesma matéria (duplicatas agrupadas)',
    'link': 'Endereço da reportagem original (ou do Google Notícias quando o original não foi resolvido)',
}


def exportar(itens, categorias, links, pasta):
    """Grava os dados abertos: CSV, JSON, dicionário e agregados mensais."""
    pasta.mkdir(exist_ok=True)
    linhas = []
    mensal = {}
    for x in sorted(itens, key=lambda y: y.get('d', '')):
        q = x.get('q', {})
        linhas.append({
            'id': x['i'], 'data': x.get('d', ''), 'titulo': x['t'], 'fonte': x.get('f', ''), 'uf': x.get('uf', ''),
            'categorias': '|'.join(categorias[c] for c in x.get('c', [])),
            'orgaos': '|'.join(ORGAOS_NOMES[a] for a in x.get('ag', [])), 'rodovia': x.get('rd', ''),
            'cocaina_kg': q.get('coc', ''), 'maconha_kg': q.get('mac', ''), 'skunk_haxixe_kg': q.get('skh', ''),
            'crack_kg': q.get('cra', ''), 'outras_drogas_kg': q.get('dro', ''), 'armas': q.get('arm', ''),
            'fuzis': q.get('fuz', ''), 'municoes': q.get('mun', ''), 'valor_rs': x.get('vq', ''),
            'outras_fontes': '|'.join(o[0] for o in x.get('o', [])),
            'link': x.get('u') or links.get(x['i'], ''),
        })
        mes = x.get('d', '')[:7]
        if mes:
            chave = (mes, x.get('uf', ''))
            m = mensal.setdefault(chave, {'noticias': 0, **{k: 0 for k in MATERIAIS}})
            m['noticias'] += 1
            for k, v in q.items():
                m[k] += v
            m['val'] += x.get('vq', 0)
    with open(pasta / 'noticias.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CSV)
        w.writeheader()
        w.writerows(linhas)
    with open(pasta / 'mensal_por_uf.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['mes', 'uf', 'noticias'] + [f'{MATERIAIS[k][0]} ({MATERIAIS[k][1]})' for k in MATERIAIS])
        for (mes, uf), m in sorted(mensal.items()):
            w.writerow([mes, uf, m['noticias']] + [round(m[k], 3) for k in MATERIAIS])
    (pasta / 'dicionario.json').write_text(json.dumps({
        'atualizado_em': datetime.now(timezone.utc).isoformat(),
        'licenca': 'Dados do Radar das Apreensões sob CC BY 4.0 (cite a fonte). Títulos e links pertencem aos veículos.',
        'campos': DICIONARIO,
        'materiais': {k: {'rotulo': r, 'unidade': u} for k, (r, u) in MATERIAIS.items()},
        'aviso': 'Contagens de notícias e quantidades citadas em notícias; não são estatísticas oficiais.',
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    return len(linhas)
