#!/usr/bin/env python3
"""Planilha de classificação (uso interno, não publicada no site).

Lê feed.json e det/ (gerados por gerar_feed_site.py) e grava um .xlsx com:
  - Notícias: uma linha por notícia (sem duplicatas): tipo, estado, cidade,
    produtos, quantidades normalizadas, órgãos, presos, operação, links;
  - Itens apreendidos: uma linha por produto citado (quantidade e unidade);
  - Resumo: totais e cobertura de cada campo.

  python scripts/exportar_planilha.py saida.xlsx
"""
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

RAIZ = Path(__file__).resolve().parent.parent
SITE = 'https://www.radardasapreensoes.com.br'
ESTADOS = {'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas', 'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal',
           'ES': 'Espírito Santo', 'GO': 'Goiás', 'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul', 'MG': 'Minas Gerais',
           'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná', 'PE': 'Pernambuco', 'PI': 'Piauí', 'RJ': 'Rio de Janeiro',
           'RN': 'Rio Grande do Norte', 'RS': 'Rio Grande do Sul', 'RO': 'Rondônia', 'RR': 'Roraima', 'SC': 'Santa Catarina',
           'SP': 'São Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins'}
# Tipo do produto (para a aba de itens), na ordem de prioridade.
PRODUTO = [
    ('Cocaína', r'coca[ií]na|pasta[ -]base|cloridrato'), ('Crack', r'\bcrack'), ('Skunk/haxixe', r'sk[ua]nk|haxixe|supermaconha'),
    ('Maconha', r'maconha|cannabis'), ('Drogas sintéticas', r'ecstasy|\blsd\b|metanfetamina|sint[ée]tic|comprimidos? de|k9|k2'),
    ('Drogas (outras)', r'drogas?|entorpecente|subst[âa]ncia'),
    ('Fuzis', r'fuzi[ls]'), ('Armas de fogo', r'armas?|pistolas?|rev[óo]lver|espingarda|carabina|metralhadora|garruch'),
    ('Munições', r'muni[çc]|cartucho'), ('Explosivos', r'explosiv|dinamite|granada|emuls'),
    ('Cigarros', r'cigarr|ma[çc]os?|narguil|ess[êe]ncia|vape|pod'), ('Bebidas', r'bebida|u[íi]sque|vinho|cerveja|vodka'),
    ('Medicamentos', r'medicament|rem[ée]dio|anabolizante|caneta|emagrecedor|ampola|comprimido'),
    ('Eletrônicos', r'eletr[ôo]nic|celular|smartphone|notebook|computador|tablet|videogame|fone'),
    ('Veículos', r've[íi]culo|carro|caminh[ãa]o|carreta|moto|[ôo]nibus|caminhonete|embarca[çc]|lancha|barco|aeronave|avi[ãa]o'),
    ('Dinheiro', r'dinheiro|reais|r\$|d[óo]lar|euro|c[ée]dula'), ('Ouro e joias', r'\bouro\b|joia|j[óo]ia'),
    ('Madeira', r'madeira|tora|m[³3]'), ('Animais', r'animal|animais|ave|p[áa]ssaro|peixe|pescado|tartaruga|jabuti'),
    ('Agrotóxicos', r'agrot[óo]xic|defensivo'), ('Mercadorias', r'mercadoria|produto|roupa|cal[çc]ado|perfume|brinquedo|pneu'),
]
UNIDADES = {'kg': 'kg', 'quilo': 'kg', 'quilos': 'kg', 'quilograma': 'kg', 'quilogramas': 'kg', 'tonelada': 't', 'toneladas': 't',
            'grama': 'g', 'gramas': 'g', 'g': 'g', 'litro': 'L', 'litros': 'L'}


def numero(t):
    t = t.strip()
    if re.fullmatch(r'\d+\.\d{1,2}', t):
        return float(t)
    try:
        return float(t.replace('.', '').replace(',', '.'))
    except ValueError:
        return None


def item_apreendido(texto):
    """'1,13 tonelada de cocaína' -> (1.13, 't', 'cocaína'); '320 sacas de café' -> (320, 'un', 'sacas de café')."""
    texto = str(texto).strip()
    m = re.match(r'^([\d.,]+)(?:\s+(mil|milhão|milhões))?\s+(.+)$', texto)
    if not m:
        return None, '', texto
    q = numero(m.group(1))
    if q is not None and m.group(2):
        q *= 1000 if m.group(2) == 'mil' else 1_000_000
    resto = m.group(3)
    partes = resto.split(' de ', 1)
    if len(partes) == 2 and partes[0].lower() in UNIDADES:
        return q, UNIDADES[partes[0].lower()], partes[1]
    return q, 'un', resto


def tipo_produto(texto):
    for nome, padrao in PRODUTO:
        if re.search(padrao, texto, re.I):
            return nome
    return 'Outros'


def main():
    saida = Path(sys.argv[1] if len(sys.argv) > 1 else 'classificacao_radar.xlsx')
    feed = json.loads((RAIZ / 'feed.json').read_text(encoding='utf-8'))
    cats, orgaos = feed['categorias'], feed.get('orgaos', [])
    det = {}
    for arq in glob.glob(str(RAIZ / 'det' / '*.json')):
        det.update(json.loads(Path(arq).read_text(encoding='utf-8')))
    links = json.loads((RAIZ / 'feed_links.json').read_text(encoding='utf-8')) if (RAIZ / 'feed_links.json').exists() else {}

    wb = Workbook()
    ws = wb.active
    ws.title = 'Notícias'
    cab = ['ID', 'Data', 'Título', 'Fonte', 'Tipo principal', 'Todos os tipos', 'UF', 'Estado', 'Cidade (local da apreensão)',
           'Produtos apreendidos', 'Cocaína (kg)', 'Maconha (kg)', 'Skunk/haxixe (kg)', 'Crack (kg)', 'Outras drogas (kg)',
           'Armas', 'Fuzis', 'Munições', 'Valor citado (R$)', 'Órgãos', 'Rodovia', 'Presos', 'Mandados', 'Operação',
           'Outros veículos que noticiaram', 'Link da matéria', 'Página no Radar']
    ws.append(cab)
    wi = wb.create_sheet('Itens apreendidos')
    wi.append(['ID da notícia', 'Data', 'UF', 'Cidade', 'Tipo do produto', 'Produto (como citado)', 'Quantidade', 'Unidade', 'Título'])
    cobertura = Counter()
    por_tipo, por_uf = Counter(), Counter()
    for n in feed['noticias']:
        d = det.get(str(n['i']), {})
        f = d.get('f') or {}
        q = n.get('q') or {}
        c = n.get('c') or [8]
        apreendido = f.get('apreendido') or []
        presos = f.get('presos') or (len(f.get('presos_iniciais') or []) or ('sim' if f.get('presos_texto') else ''))
        slug = re.sub(r'[^a-z0-9]+', '-', re.sub(r'[̀-ͯ]', '', __import__('unicodedata').normalize('NFD', n['t']).lower())).strip('-')
        slug = '-'.join(slug.split('-')[:12])
        linha = [
            str(n['i']), (n.get('d') or '').replace('T', ' '), n['t'], n.get('f', ''), cats[c[0]], ', '.join(cats[x] for x in c),
            n.get('uf', ''), ESTADOS.get(n.get('uf', ''), ''), n.get('cid', ''), '; '.join(apreendido),
            q.get('coc'), q.get('mac'), q.get('skh'), q.get('cra'), q.get('dro'), q.get('arm'), q.get('fuz'), q.get('mun'),
            n.get('vq'), ', '.join(orgaos[a] for a in n.get('ag', []) if a < len(orgaos)), n.get('rd', ''), presos,
            f.get('mandados', ''), f.get('operacao', ''), len(n.get('o') or []),
            n.get('u') or links.get(str(n['i'])) or '', f'{SITE}/noticia/{n["i"]}-{slug}',
        ]
        ws.append(linha)
        por_tipo[cats[c[0]]] += 1
        por_uf[n.get('uf') or '(sem estado)'] += 1
        for campo, ok in (('Estado', n.get('uf')), ('Cidade', n.get('cid')), ('Produto', apreendido), ('Quantidade', q or n.get('vq')),
                          ('Órgão', n.get('ag')), ('Presos', presos), ('Link da matéria', n.get('u'))):
            cobertura[campo] += bool(ok)
        for a in apreendido:
            qt, un, prod = item_apreendido(a)
            wi.append([str(n['i']), (n.get('d') or '')[:10], n.get('uf', ''), n.get('cid', ''), tipo_produto(prod), prod, qt, un, n['t']])

    total = len(feed['noticias'])
    wr = wb.create_sheet('Resumo', 0)
    wr.append(['Planilha de classificação — Radar das Apreensões'])
    wr.append([f'Gerada a partir do site em {feed.get("atualizado_em") or ""}. Uso interno. Quantidades são as citadas nas notícias (estimativas, não estatística oficial).'])
    wr.append([])
    wr.append(['Notícias (sem duplicatas)', total])
    wr.append(['Itens apreendidos (linhas)', wi.max_row - 1])
    wr.append([])
    wr.append(['Campo', 'Notícias com o campo', '% do total'])
    wr.append(['Tipo', total, 1])
    for campo in ('Estado', 'Cidade', 'Produto', 'Quantidade', 'Órgão', 'Presos', 'Link da matéria'):
        wr.append([campo, cobertura[campo], cobertura[campo] / total if total else 0])
    wr.append([])
    wr.append(['Tipo principal', 'Notícias'])
    for k, v in por_tipo.most_common():
        wr.append([k, v])
    wr.append([])
    wr.append(['Estado', 'Notícias'])
    for k, v in sorted(por_uf.items(), key=lambda x: -x[1]):
        wr.append([ESTADOS.get(k, k), v])
    for linha in wr.iter_rows():
        for cel in linha:
            if isinstance(cel.value, float) and 0 <= cel.value <= 1 and cel.column == 3:
                cel.number_format = '0%'
    wr['A1'].font = Font(bold=True, size=14)
    wr.column_dimensions['A'].width = 34
    wr.column_dimensions['B'].width = 20
    wr.column_dimensions['C'].width = 12

    titulo = PatternFill('solid', fgColor='B3261E')
    for folha, larguras in ((ws, [17, 17, 70, 22, 22, 30, 5, 18, 22, 50, 11, 11, 11, 10, 12, 8, 8, 10, 16, 30, 10, 8, 18, 22, 10, 45, 45]),
                            (wi, [17, 11, 5, 22, 18, 40, 12, 8, 70])):
        for k, w in enumerate(larguras, 1):
            folha.column_dimensions[get_column_letter(k)].width = w
        for cel in folha[1]:
            cel.font = Font(bold=True, color='FFFFFF')
            cel.fill = titulo
            cel.alignment = Alignment(vertical='center', wrap_text=True)
        folha.freeze_panes = 'A2'
        folha.auto_filter.ref = folha.dimensions
    wb.save(saida)
    print(f'{saida}: {total} notícias, {wi.max_row - 1} itens; cobertura: ' +
          ', '.join(f'{k} {100 * v / total:.0f}%' for k, v in cobertura.items()))


if __name__ == '__main__':
    main()
