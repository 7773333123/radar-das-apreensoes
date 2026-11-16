#!/usr/bin/env python3
"""Gera feed.json, o arquivo enxuto que o site carrega.

noticias.json guarda todo o histórico bruto da coleta (dezenas de MB). Este
script produz, para o navegador, só o necessário e já limpo:

  - título sem o nome da fonte repetido no fim;
  - UF recalculada com evidência explícita (localizar_uf.py);
  - categorias canônicas (as não classificadas passam por regras de título);
  - notícias sem relação com apreensões ficam de fora do site (seguem no acervo);
  - link original quando existe; links longos do Google Notícias vão para
    feed_links.json, baixado só quando o leitor abre a notícia.

Formato de cada notícia em feed.json (chaves curtas para reduzir o tamanho):
  i   posição em noticias.json (índice em feed_links.json)
  t   título            f   fonte            d   data ISO (UTC)
  u   link original     img foto da fonte    r   resumo
  uf  sigla do estado   c   índices em "categorias"
"""
import json
import re
from pathlib import Path

from localizar_uf import inferir_uf

PASTA = Path(__file__).resolve().parent
ORIGEM = PASTA / 'noticias.json'
DESTINO = PASTA / 'feed.json'
LINKS = PASTA / 'feed_links.json'
FONTES_JSON = PASTA / 'fontes.json'

CATEGORIAS = [
    'Drogas e entorpecentes', 'Armas e munições', 'Contrabando e descaminho', 'Veículos',
    'Dinheiro e valores', 'Crimes ambientais', 'Medicamentos e produtos',
    'Operações patrimoniais', 'Outras apreensões',
]
REGRAS = [
    r'droga|tr[aá]fic|coca[ií]na|maconha|entorpecent|crack|haxixe|skunk|cannabis|ecstasy|lsd|pasta base',
    r'\barmas?\b|fuzil|fuzis|pistola|rev[oó]lver|muni[çc]|cartucho|explosiv|espingarda',
    r'contraband|descaminho|cigarros?|aduan|mercadorias? (?:irregular|il[ií]cit|estrangeir)',
    r've[ií]culos?|\bcarros?\b|caminh[ãa]o|caminh[õo]es|motocicleta|\bmotos?\b|embarca[çc]|aeronave|avi[ãa]o',
    r'dinheiro|em esp[ée]cie|\bouro\b|joias|numer[aá]rio|d[oó]lares|\bR\$',
    r'ambient|madeira|animais silvestres|aves silvestres|pesca ilegal|pescado|garimpo|min[eé]rio|desmatamento',
    r'medicamento|rem[eé]dio|anabolizante|falsificad|canetas? emagrecedora',
    r'bloqueio de bens|patrim[oô]nio|bens apreendidos|lavagem de dinheiro|sequestro de bens',
    r'apreens|apreend|confiscad|retid',
]
REGRAS = [re.compile(r, re.I) for r in REGRAS]
# Sem categoria e sem nenhum destes termos no título: não é notícia de apreensão.
RELEVANTE = re.compile(
    r'apreen|apreend|tr[aá]fic|contraband|descaminho|lavagem|drog|coca[ií]n|maconha|crack|haxixe|'
    r'skunk|entorpecent|\barmas?\b|fuzi|muni[çc]|pistola|rev[oó]lver|garimpo|madeira|pescado|'
    r'animais silvestres|cigarro|medicamento|anabolizante|confisc|opera[çc][ãa]o|pres[oa]s?\b|'
    r'flagrante|fac[çc][ãa]o|bloqueio de bens|sequestro de bens|prende|pris[ãa]o|mandados?|'
    r'ilegal|il[ií]cit|criminos|quadrilha|foragid', re.I)


def limpar_titulo(titulo, fonte):
    titulo = re.sub(r'\s+', ' ', str(titulo or '')).strip()
    fonte = str(fonte or '').strip()
    if fonte:
        sufixo = ' - ' + fonte
        while titulo.lower().endswith(sufixo.lower()) and len(titulo) > len(sufixo) + 10:
            titulo = titulo[:-len(sufixo)].rstrip()
    # Páginas gov.br: "Título — Polícia Federal", "Título — Receita Federal".
    titulo = re.sub(r'\s+—\s+[^—]{3,40}$', '', titulo)
    return titulo


def categorias(n, titulo):
    atuais = [c for c in (n.get('categorias_identificadas') or []) if c in CATEGORIAS]
    if not atuais:
        atuais = [CATEGORIAS[k] for k, regra in enumerate(REGRAS) if regra.search(titulo)]
        if len(atuais) > 1 and 'Outras apreensões' in atuais:
            atuais.remove('Outras apreensões')
    return [CATEGORIAS.index(c) for c in dict.fromkeys(atuais)]


def url_publica(valor):
    valor = str(valor or '').strip()
    return valor if re.match(r'https?://', valor) else ''


def main():
    dados = json.loads(ORIGEM.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    fontes = json.loads(FONTES_JSON.read_text(encoding='utf-8')).get('fontes', []) if FONTES_JSON.exists() else []
    saida, links, ocultas = [], [''] * len(noticias), 0
    for i, n in enumerate(noticias):
        if not isinstance(n, dict):
            continue
        fonte = str(n.get('fonte') or '').strip()
        titulo = limpar_titulo(n.get('titulo'), fonte)
        if not titulo:
            continue
        cats = categorias(n, titulo)
        if not cats and not RELEVANTE.search(titulo):
            ocultas += 1
            continue
        item = {'i': i, 't': titulo}
        if fonte:
            item['f'] = fonte
        data = n.get('data_iso') or ''
        if data:
            item['d'] = data[:16]  # AAAA-MM-DDTHH:MM
        url = next((u for u in (url_publica(n.get('url_original')), url_publica(n.get('url')))
                    if u and 'news.google.com' not in u), '')
        if url:
            item['u'] = url
        else:
            links[i] = url_publica(n.get('url_google_noticias') or n.get('url'))
        img = url_publica(n.get('imagem_url'))
        if img:
            item['img'] = img
        resumo = str(n.get('descricao') or n.get('resumo') or '').strip()
        if resumo:
            item['r'] = resumo[:300]
        uf = inferir_uf(n, fontes)
        if uf:
            item['uf'] = uf
        if cats:
            item['c'] = cats
        saida.append(item)
    saida.sort(key=lambda x: x.get('d', ''), reverse=True)
    feed = {
        'atualizado_em': dados.get('atualizado_em') if isinstance(dados, dict) else None,
        'categorias': CATEGORIAS,
        'total': len(saida),
        'noticias': saida,
    }
    DESTINO.write_text(json.dumps(feed, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    LINKS.write_text(json.dumps(links, separators=(',', ':')), encoding='utf-8')
    print(f'{DESTINO.name}: {len(saida)} notícias ({ocultas} sem relação com apreensões ocultadas), '
          f'{DESTINO.stat().st_size / 1e6:.1f} MB')
    print(f'{LINKS.name}: {LINKS.stat().st_size / 1e6:.1f} MB (carregado só ao abrir uma notícia)')


if __name__ == '__main__':
    main()
