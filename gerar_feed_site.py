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
No detalhe: s = resumo do Radar (frases próprias), f = ficha de fatos (resumo_fatos.py).
  o   outras fontes da mesma matéria: [[fonte, link, i], ...] (duplicatas agrupadas)
Resumo, trecho, texto integral e galeria ficam em det/<i // 100>.json, baixados ao abrir a notícia.
"""
import json
import re
import shutil
import unicodedata
from pathlib import Path

from localizar_uf import inferir_uf
from resumo_fatos import extrair
from contexto import resumo_ampliado
from estatisticas import MATERIAIS, ORGAOS_NOMES, enriquecer, exportar

PASTA = Path(__file__).resolve().parent
ORIGEM = PASTA / 'noticias.json'
DESTINO = PASTA / 'feed.json'
LINKS = PASTA / 'feed_links.json'
FONTES_JSON = PASTA / 'fontes.json'
DETALHES = PASTA / 'det'  # lotes de 100 notícias (antes: detalhes/, lotes de 1000)
LOTE = 100

# Tipos e relevância: classificar.py (regras próprias; ignora a classificação do coletor antigo).
from classificar import CATEGORIAS, REGRAS, relevante, categorias as classificar_categorias


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
    texto = ' '.join(str(n.get(k) or '') for k in ('descricao', 'resumo', 'trecho'))
    return classificar_categorias(titulo, texto)


PALAVRAS_VAZIAS = set('''para pela pelo pelos pelas com sem sobre apos após entre durante contra como mais menos
    que uma umas uns dos das nos nas aos este esta esse essa isso isto pode podem diz afirma'''.split())


def _normal(texto):
    texto = unicodedata.normalize('NFKD', texto or '')
    texto = ''.join(c for c in texto if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9]+', ' ', texto).strip()


# Palavras que aparecem em quase toda notícia policial: não ajudam a dizer se
# dois títulos falam do mesmo fato.
GENERICAS = set('''policia policias policial policiais militar militares civil federal rodoviaria
    apreende apreendem apreendeu apreendido apreendida apreendidos apreendidas apreensao apreensoes
    prende prendem prendeu preso presa presos presas prisao flagrante suspeito suspeitos suspeita
    homem mulher jovem jovens adolescente pessoas dupla trio operacao acao durante cerca mais
    droga drogas trafico traficante bairro cidade regiao estado'''.split())


def _palavras(texto):
    return {w for w in _normal(texto).split() if len(w) > 3 and w not in PALAVRAS_VAZIAS}


def _informativas(texto):
    """Palavras que identificam o fato: lugares, objetos, nomes e números (300, 1,3 t...)."""
    palavras = set()
    for w in _normal(texto).split():
        if w.isdigit():
            if len(w) >= 2 and w not in ('2024', '2025', '2026'):
                palavras.add(w)
        elif len(w) > 3 and w not in PALAVRAS_VAZIAS and w not in GENERICAS:
            palavras.add(w)
    return palavras


EXTENSO = {'um': '1', 'uma': '1', 'dois': '2', 'duas': '2', 'tres': '3', 'quatro': '4', 'cinco': '5', 'seis': '6',
           'sete': '7', 'oito': '8', 'nove': '9', 'dez': '10', 'onze': '11', 'doze': '12', 'treze': '13',
           'quatorze': '14', 'catorze': '14', 'quinze': '15', 'vinte': '20', 'trinta': '30', 'cem': '100'}


def _quantidades(texto):
    """Quantidades citadas no título, com números por extenso convertidos (uma -> 1)."""
    saida = set()
    for w in _normal(texto).split():
        if w.isdigit() and w not in ('2024', '2025', '2026'):
            saida.add(w.lstrip('0') or '0')
        elif w in EXTENSO:
            saida.add(EXTENSO[w])
    return saida


def mesma_materia(pa, pb, ia, ib, qa=frozenset(), qb=frozenset(), mesmo_uf=False):
    """pa/pb: palavras do título; ia/ib: palavras informativas; qa/qb: quantidades citadas."""
    if qa and qb and not (qa & qb):
        return False  # "três presos" e "dois presos" são fatos diferentes
    comum = len(pa & pb)
    if comum >= 4 and comum / len(pa | pb) >= 0.65:
        return True
    # Um título contido no outro: >= 75% das palavras informativas do mais curto
    # aparecem no mais longo (ex.: "300 garrafas de vinho em Cruzeiro do Oeste").
    # Só vale com o mesmo estado confirmado ou um número específico em comum
    # (a PF faz operações iguais em vários estados no mesmo dia).
    inf = len(ia & ib)
    numero_comum = bool(qa & qb) or any(w.isdigit() for w in ia & ib)
    return (inf >= 3 and inf / max(1, min(len(ia), len(ib))) >= 0.75 and (mesmo_uf or numero_comum)
            and (inf >= 4 or numero_comum))


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

    por_dia, palavras, normais, informativas, quantidades = {}, [], [], [], []
    for k, item in enumerate(itens):
        palavras.append(_palavras(item['t']))
        informativas.append(_informativas(item['t']))
        quantidades.append(_quantidades(item['t']))
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
            pa, ia = palavras[a], informativas[a]
            if len(pa) < 3:
                continue
            for b in vizinhos[a_pos + 1:]:
                ua, ub = itens[a].get('uf'), itens[b].get('uf')
                if ua and ub and ua != ub:
                    continue
                if not mesma_materia(pa, palavras[b], ia, informativas[b], quantidades[a], quantidades[b],
                                     mesmo_uf=bool(ua and ua == ub)):
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
            # Mantém a ordem da versão exibida (a 1ª é o selo) e acrescenta as das outras.
            principal['c'] = list(dict.fromkeys(principal.get('c', []) + outro.get('c', [])))
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


def juntar_fatos(lista):
    """Fatos da versão exibida, completados com os das outras versões da mesma notícia.

    Só preenche o que falta (não mistura listas, para não trazer ruído de outras
    páginas); os itens apreendidos de outra versão só entram se tiverem quantidade
    e a versão exibida não tiver.
    """
    lista = [f for f in lista if f]
    if not lista:
        return None
    junto = dict(lista[0])
    for f in lista[1:]:
        for k, v in f.items():
            if v and not junto.get(k):
                junto[k] = v
        tem_num = lambda fs: any(re.search(r'\d', x) for x in fs.get('apreendido', []))
        if tem_num(f) and not tem_num(junto):
            junto['apreendido'] = f['apreendido']
    return junto


def main():
    dados = json.loads(ORIGEM.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    fontes = json.loads(FONTES_JSON.read_text(encoding='utf-8')).get('fontes', []) if FONTES_JSON.exists() else []
    saida, links, ocultas, portugal = [], [''] * len(noticias), 0, 0
    detalhes = {}
    fatos_por_i = {}
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
        if not relevante(titulo):
            ocultas += 1
            continue
        cats = categorias(n, titulo)
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
        # Resumo do Radar: fatos da página original (ler_materias.py) ou, na falta
        # dela, do título e do resumo da fonte; redigido com frases próprias.
        fatos = n.get('fatos') or extrair(titulo, resumo)
        if fatos:
            fatos_por_i[i] = fatos
            detalhe['f'] = fatos
        # O que diz a fonte: abertura da reportagem (citação com crédito e link).
        trecho = str(n.get('trecho') or '').strip()
        if trecho and len(trecho) > len(resumo):
            detalhe['tr'] = trecho
        detalhes.setdefault(i // LOTE, {})[str(i)] = detalhe
        saida.append(item)
    antes = len(saida)
    saida, removidas = agrupar_duplicatas(saida)
    for lote in list(detalhes):
        for chave in [c for c in detalhes[lote] if int(c) in removidas]:
            del detalhes[lote][chave]
        if not detalhes[lote]:
            del detalhes[lote]
    # Quantidades, órgãos e rodovia só depois de agrupar as duplicatas: a versão
    # exibida usa os próprios fatos ou, se não tiver, os da fonte mais completa.
    for item in saida:
        candidatos = [fatos_por_i.get(item['i'])] + [fatos_por_i.get(o[2]) for o in item.get('o', [])]
        candidatos = [f for f in candidatos if f]
        if candidatos:
            enriquecer(item, max(candidatos, key=lambda f: (len(f.get('apreendido', [])), len(f))))
    # Resumo do Radar em parágrafos: fatos, quem atuou, base legal e outros veículos.
    for item in saida:
        fatos = juntar_fatos([fatos_por_i.get(item['i'])] + [fatos_por_i.get(o[2]) for o in item.get('o', [])])
        detalhes[item['i'] // LOTE][str(item['i'])]['s'] = resumo_ampliado(item, fatos)
    for lote in list(detalhes):
        for chave in [c for c, v in detalhes[lote].items() if not v]:
            del detalhes[lote][chave]
        if not detalhes[lote]:
            del detalhes[lote]
    saida.sort(key=lambda x: x.get('d', ''), reverse=True)
    feed = {
        'atualizado_em': dados.get('atualizado_em') if isinstance(dados, dict) else None,
        'categorias': CATEGORIAS,
        'orgaos': ORGAOS_NOMES,
        'materiais': {k: list(v) for k, v in MATERIAIS.items()},
        'total': len(saida),
        'noticias': saida,
    }
    DESTINO.write_text(json.dumps(feed, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    LINKS.write_text(json.dumps(links, separators=(',', ':')), encoding='utf-8')
    # Texto integral (só de licença aberta) e galeria de fotos, em lotes por índice.
    for antiga in ('textos', 'detalhes'):  # formatos anteriores
        shutil.rmtree(PASTA / antiga, ignore_errors=True)
    DETALHES.mkdir(exist_ok=True)
    for antigo in DETALHES.glob('*.json'):
        if int(antigo.stem) not in detalhes:
            antigo.unlink()
    for lote, conteudo in detalhes.items():
        (DETALHES / f'{lote}.json').write_text(json.dumps(conteudo, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    abertos = exportar(saida, CATEGORIAS, links, PASTA / 'dados')
    print(f'dados/: {abertos} notícias em CSV (dados abertos); '
          f'{sum(1 for x in saida if x.get("q"))} com quantidades')
    print(f'Duplicatas agrupadas: {antes - len(saida)}; notícias de Portugal excluídas: {portugal}')
    print(f'{DESTINO.name}: {len(saida)} notícias ({ocultas} sem relação com apreensões ocultadas), '
          f'{DESTINO.stat().st_size / 1e6:.1f} MB')
    print(f'{LINKS.name}: {LINKS.stat().st_size / 1e6:.1f} MB (carregado só ao abrir uma notícia)')
    print(f'det/: {sum(1 for v in detalhes.values() for d in v.values() if "p" in d)} textos integrais, '
          f'{sum(1 for v in detalhes.values() for d in v.values() if "g" in d)} galerias de fotos')


if __name__ == '__main__':
    main()
