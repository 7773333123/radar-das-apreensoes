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
  i   identificador permanente da notícia (hash do link; não muda quando o acervo é reordenado)
  t   título            f   fonte            d   data ISO (UTC)
  u   link original     img foto da fonte    r   resumo
  uf  sigla do estado   c   índices em "categorias"
  x   1 quando há texto integral (licença aberta)    g   nº de fotos (quando > 1)
No detalhe: s = resumo do Radar (frases próprias), f = ficha de fatos (resumo_fatos.py).
  o   outras fontes da mesma matéria: [[fonte, link, i], ...] (duplicatas agrupadas)
feed_links.json: {i: link do Google Notícias} das que ainda não têm o link original.
Resumo, trecho, texto integral e galeria ficam em det/<i % 256>.json, baixados ao abrir a notícia.
"""
import json
import hashlib
import re
import shutil
import unicodedata
from pathlib import Path

from localizar_uf import inferir_uf
from resumo_fatos import extrair
from contexto import resumo_ampliado
from estatisticas import MATERIAIS, ORGAOS_NOMES, enriquecer, exportar, quantidades

PASTA = Path(__file__).resolve().parent
ORIGEM = PASTA / 'noticias.json'
DESTINO = PASTA / 'feed.json'
LINKS = PASTA / 'feed_links.json'
FONTES_JSON = PASTA / 'fontes.json'
DETALHES = PASTA / 'det'  # lotes de 100 notícias (antes: detalhes/, lotes de 1000)
LOTES = 256  # det/<i % LOTES>.json


def identificador(n):
    """Número permanente da notícia: hash do link (ou do título), igual em toda coleta."""
    return int(hashlib.sha1(chave_acervo(n).encode('utf-8')).hexdigest()[:13], 16) % 10**15

# Tipos e relevância: classificar.py (regras próprias; ignora a classificação do coletor antigo).
from mesclar_acervo import chave as chave_acervo
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


# Duplicatas: regras e métrica em duplicatas.py (texto, abertura, fatos e imagem).
from duplicatas import agrupar as _agrupar, mesma_materia, normal as _normal  # noqa: E402,F401


def agrupar_duplicatas(itens, motivos=None):
    return _agrupar(itens, motivos)


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
    saida, links, ocultas, portugal = [], {}, 0, 0
    usados = set()
    detalhes = {}
    fatos_por_i = {}
    fatos_titulo = {}
    for n in noticias:
        if not isinstance(n, dict):
            continue
        i = identificador(n)
        if i in usados:  # mesmo link registrado duas vezes no acervo
            continue
        usados.add(i)
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
        # Fatos do título e do resumo da fonte: os mais confiáveis para as
        # quantidades (o texto da página pode trazer números de outras matérias).
        do_titulo = extrair(titulo, resumo)
        if do_titulo:
            fatos_titulo[i] = do_titulo
        fatos = n.get('fatos') or do_titulo
        # Evidências para o agrupamento de duplicatas (removidas antes de gravar).
        if n.get('img_dhash') and n.get('img_dhash_url') == n.get('imagem_url'):
            item['_h'] = int(n['img_dhash'], 16)
        item['_lead'] = str(n.get('trecho') or resumo)[:600]
        if do_titulo:
            q = {k: v for k, v in quantidades(do_titulo).items() if k != 'val'}
            if q:
                item['_q'] = q
        if fatos:
            fatos_por_i[i] = fatos
            detalhe['f'] = fatos
        # O que diz a fonte: abertura da reportagem (citação com crédito e link).
        trecho = str(n.get('trecho') or '').strip()
        if trecho and len(trecho) > len(resumo):
            detalhe['tr'] = trecho
        detalhes.setdefault(i % LOTES, {})[str(i)] = detalhe
        saida.append(item)
    antes = len(saida)
    saida, removidas = agrupar_duplicatas(saida)
    for item in saida:
        for k in ('_h', '_lead', '_q'):
            item.pop(k, None)
    for lote in list(detalhes):
        for chave in [c for c in detalhes[lote] if int(c) in removidas]:
            del detalhes[lote][chave]
        if not detalhes[lote]:
            del detalhes[lote]
    # Quantidades, órgãos e rodovia só depois de agrupar as duplicatas: a versão
    # exibida usa os próprios fatos ou, se não tiver, os da fonte mais completa.
    for item in saida:
        ids = [item['i']] + [o[2] for o in item.get('o', [])]
        # Quantidades: primeiro as do título/resumo (desta versão ou das outras);
        # só sem nenhuma, as lidas na página. Órgãos e rodovia vêm da mais completa.
        com_numero = [fatos_titulo[k] for k in ids if k in fatos_titulo and quantidades(fatos_titulo[k])]
        candidatos = [f for f in [fatos_por_i.get(k) for k in ids] if f]
        if com_numero or candidatos:
            base = dict(max(candidatos, key=lambda f: (len(f.get('apreendido', [])), len(f)))) if candidatos else {}
            if com_numero:
                base['apreendido'] = com_numero[0].get('apreendido', [])
                if com_numero[0].get('valor'):
                    base['valor'] = com_numero[0]['valor']
                elif 'valor' in base:
                    del base['valor']
            enriquecer(item, base)
    # Resumo do Radar em parágrafos: fatos, quem atuou, base legal e outros veículos.
    for item in saida:
        fatos = juntar_fatos([fatos_por_i.get(item['i'])] + [fatos_por_i.get(o[2]) for o in item.get('o', [])])
        detalhes[item['i'] % LOTES][str(item['i'])]['s'] = resumo_ampliado(item, fatos)
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
