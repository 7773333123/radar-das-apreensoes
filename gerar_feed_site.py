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
  x   1 quando há texto integral (licença aberta)    g   nº de fotos (quando > 1)
  o   outras fontes da mesma matéria: [[fonte, link, i], ...] (duplicatas agrupadas)
Texto integral e galeria ficam em detalhes/<i // 1000>.json, baixados ao abrir a notícia.
"""
import json
import re
import shutil
import unicodedata
from pathlib import Path

from localizar_uf import inferir_uf

PASTA = Path(__file__).resolve().parent
ORIGEM = PASTA / 'noticias.json'
DESTINO = PASTA / 'feed.json'
LINKS = PASTA / 'feed_links.json'
FONTES_JSON = PASTA / 'fontes.json'
DETALHES = PASTA / 'detalhes'
LOTE = 1000

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


PALAVRAS_VAZIAS = set('''para pela pelo pelos pelas com sem sobre apos após entre durante contra como mais menos
    que uma umas uns dos das nos nas aos este esta esse essa isso isto pode podem diz afirma'''.split())


def _normal(texto):
    texto = unicodedata.normalize('NFKD', texto or '')
    texto = ''.join(c for c in texto if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9]+', ' ', texto).strip()


def _palavras(texto):
    return {w for w in _normal(texto).split() if len(w) > 3 and w not in PALAVRAS_VAZIAS}


def _pontos(item):
    """Qual versão da matéria mostrar: texto integral, fotos, link original, estado."""
    return (item.get('x', 0) * 8 + min(item.get('g', 1 if item.get('img') else 0), 5) * 2 +
            (3 if item.get('u') else 0) + (1 if item.get('uf') else 0) + (1 if item.get('r') else 0))


def _data(dia):
    from datetime import date
    return date.fromisoformat(dia)


def agrupar_duplicatas(itens):
    """Une a mesma matéria publicada mais de uma vez (mesma fonte ou veículos diferentes).

    Duplicata = título igual, ou >= 65% das palavras em comum (mínimo 4), publicada
    com até 1 dia de diferença e sem estados conflitantes. Mantém a versão mais
    completa e guarda as demais em 'o' ("Também noticiado por").
    """
    pai = list(range(len(itens)))

    def raiz(k):
        while pai[k] != k:
            pai[k] = pai[pai[k]]
            k = pai[k]
        return k

    por_dia, palavras, normais = {}, [], []
    for k, item in enumerate(itens):
        palavras.append(_palavras(item['t']))
        normais.append(_normal(item['t']))
        dia = item.get('d', '')[:10]
        if dia:
            por_dia.setdefault(dia, []).append(k)
    por_titulo = {}
    for k, t in enumerate(normais):  # título idêntico: mesma matéria, mesmo sem data
        if len(t) > 25:
            if t in por_titulo:
                pai[raiz(k)] = raiz(por_titulo[t])
            else:
                por_titulo[t] = k
    # Texto repetido: mesmo resumo (primeiros 140 caracteres) ou mesma foto,
    # publicados com até 3 dias de diferença, são a mesma matéria republicada.
    for campo, tamanho in (('r', 140), ('img', None)):
        vistos = {}
        for k, item in enumerate(itens):
            valor = item.get(campo, '')
            valor = _normal(valor)[:tamanho] if tamanho else valor.split('?')[0]
            if (tamanho and len(valor) < 80) or not valor or 'logo' in valor.lower():
                continue
            dia = item.get('d', '')[:10]
            anterior = vistos.get(valor)
            if anterior is not None:
                dia_ant = itens[anterior].get('d', '')[:10]
                if dia and dia_ant and abs((_data(dia) - _data(dia_ant)).days) <= 3:
                    pai[raiz(k)] = raiz(anterior)
            vistos[valor] = k
    dias = sorted(por_dia)
    for posicao, dia in enumerate(dias):
        atuais = por_dia[dia]
        vizinhos = atuais + (por_dia[dias[posicao + 1]] if posicao + 1 < len(dias) else [])
        for a_pos, a in enumerate(atuais):
            pa = palavras[a]
            if len(pa) < 4:
                continue
            for b in vizinhos[a_pos + 1:]:
                pb = palavras[b]
                comum = len(pa & pb)
                if comum < 4 or comum / len(pa | pb) < 0.65:
                    continue
                ua, ub = itens[a].get('uf'), itens[b].get('uf')
                if ua and ub and ua != ub:
                    continue
                pai[raiz(b)] = raiz(a)
    grupos = {}
    for k in range(len(itens)):
        grupos.setdefault(raiz(k), []).append(k)
    saida, removidas = [], set()
    for membros in grupos.values():
        membros.sort(key=lambda k: _pontos(itens[k]), reverse=True)
        principal = itens[membros[0]]
        outras, vistas = [], {principal.get('f', '')}
        for k in membros[1:]:
            outro = itens[k]
            removidas.add(outro['i'])
            for campo in ('uf', 'img', 'r'):
                if outro.get(campo) and not principal.get(campo):
                    principal[campo] = outro[campo]
            principal['c'] = sorted(set(principal.get('c', [])) | set(outro.get('c', [])))
            if not principal['c']:
                del principal['c']
            if outro.get('f', '') not in vistas:
                vistas.add(outro.get('f', ''))
                outras.append([outro.get('f', 'Outra fonte'), outro.get('u', ''), outro['i']])
        if outras:
            principal['o'] = outras[:8]
        saida.append(principal)
    return saida, removidas


def url_publica(valor):
    valor = str(valor or '').strip()
    return valor if re.match(r'https?://', valor) else ''


def main():
    dados = json.loads(ORIGEM.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    fontes = json.loads(FONTES_JSON.read_text(encoding='utf-8')).get('fontes', []) if FONTES_JSON.exists() else []
    saida, links, ocultas, portugal = [], [''] * len(noticias), 0, 0
    detalhes = {}
    for i, n in enumerate(noticias):
        if not isinstance(n, dict):
            continue
        fonte = str(n.get('fonte') or '').strip()
        # Notícias de Portugal (o Google Notícias em português mistura os dois países).
        if str(n.get('dominio_fonte') or '').lower().endswith('.pt'):
            portugal += 1
            continue
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
        fotos = []
        for foto in [n.get('imagem_url')] + list(n.get('imagens') or []):
            foto = url_publica(foto)
            if foto and foto not in fotos:
                fotos.append(foto)
        if fotos:
            item['img'] = fotos[0]
        if len(fotos) > 1:
            item['g'] = len(fotos)
        resumo = str(n.get('descricao') or n.get('resumo') or '').strip()
        if resumo:
            item['r'] = resumo[:700]  # resumo inteiro publicado pela fonte
        uf = inferir_uf(n, fontes)
        if uf:
            item['uf'] = uf
        if cats:
            item['c'] = cats
        paragrafos = [str(p) for p in (n.get('texto_integral') or []) if str(p).strip()]
        detalhe = {}
        if paragrafos and n.get('licenca_texto'):
            item['x'] = 1
            detalhe.update(p=paragrafos, l=str(n['licenca_texto']))
        if len(fotos) > 1:
            detalhe['g'] = fotos
        if detalhe:
            detalhes.setdefault(i // LOTE, {})[str(i)] = detalhe
        saida.append(item)
    antes = len(saida)
    saida, removidas = agrupar_duplicatas(saida)
    for lote in list(detalhes):
        for chave in [c for c in detalhes[lote] if int(c) in removidas]:
            del detalhes[lote][chave]
        if not detalhes[lote]:
            del detalhes[lote]
    saida.sort(key=lambda x: x.get('d', ''), reverse=True)
    feed = {
        'atualizado_em': dados.get('atualizado_em') if isinstance(dados, dict) else None,
        'categorias': CATEGORIAS,
        'total': len(saida),
        'noticias': saida,
    }
    DESTINO.write_text(json.dumps(feed, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    LINKS.write_text(json.dumps(links, separators=(',', ':')), encoding='utf-8')
    # Texto integral (só de licença aberta) e galeria de fotos, em lotes por índice.
    shutil.rmtree(PASTA / 'textos', ignore_errors=True)  # formato anterior
    DETALHES.mkdir(exist_ok=True)
    for antigo in DETALHES.glob('*.json'):
        if int(antigo.stem) not in detalhes:
            antigo.unlink()
    for lote, conteudo in detalhes.items():
        (DETALHES / f'{lote}.json').write_text(json.dumps(conteudo, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Duplicatas agrupadas: {antes - len(saida)}; notícias de Portugal excluídas: {portugal}')
    print(f'{DESTINO.name}: {len(saida)} notícias ({ocultas} sem relação com apreensões ocultadas), '
          f'{DESTINO.stat().st_size / 1e6:.1f} MB')
    print(f'{LINKS.name}: {LINKS.stat().st_size / 1e6:.1f} MB (carregado só ao abrir uma notícia)')
    print(f'detalhes/: {sum(1 for v in detalhes.values() for d in v.values() if "p" in d)} textos integrais, '
          f'{sum(1 for v in detalhes.values() for d in v.values() if "g" in d)} galerias de fotos')


if __name__ == '__main__':
    main()
