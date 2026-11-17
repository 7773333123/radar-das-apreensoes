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

from localizar_uf import _ufs_no_texto, inferir_uf
from resumo_fatos import anonimizar, extrair, nomes_dos_presos
from contexto import resumo_secoes
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
from ler_materias import foto_alheia
from coletar_feeds_estaduais import agregador
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
TRECHO_VEICULO = {}
try:
    TRECHO_VEICULO = {k.lower().removeprefix('www.'): v for k, v in json.loads(
        (Path(__file__).resolve().parent / 'trecho_por_veiculo.json').read_text(encoding='utf-8')).get('veiculos', {}).items()}
except (OSError, ValueError):
    pass


def limitar_trecho(trecho, n):
    """Corta o trecho no limite pedido pelo veículo (fração da reportagem e/ou caracteres), no fim de uma frase."""
    if not trecho or not TRECHO_VEICULO:
        return trecho
    dom = str(n.get('dominio_fonte') or '').lower().removeprefix('www.')
    regra = next((v for k, v in TRECHO_VEICULO.items() if dom == k or dom.endswith('.' + k)), None)
    if not regra:
        return trecho
    regra = regra if isinstance(regra, dict) else {'fracao': regra}
    total = int(n.get('tamanho_texto') or 0) or int(len(trecho) / 0.7)
    limite = int(total * float(regra.get('fracao', 0.7)))
    if regra.get('max'):
        limite = min(limite, int(regra['max']))
    if limite <= 0:
        return ''
    if len(trecho) <= limite:
        return trecho
    corte = trecho[:limite]
    fim = max(corte.rfind('. '), corte.rfind('.\n'), corte.rfind('! '), corte.rfind('? '))
    return corte[:fim + 1].strip() if fim > 0 else ''


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


def _chave_foto(url):
    return re.sub(r'[?#].*$', '', url or '').lower()


def contar_fotos_repetidas(noticias, limite=3):
    contagem = {}
    for n in noticias:
        if isinstance(n, dict):
            for foto in set(_chave_foto(f) for f in (n.get('imagens') or [])[1:]):
                contagem[foto] = contagem.get(foto, 0) + 1
    return {f for f, c in contagem.items() if c >= limite}


def ajustar_instagram(n):
    """Post do Instagram: veículo = conta que publicou; título = 1ª frase; resumo sem curtidas."""
    n = dict(n)
    resumo = str(n.get('descricao') or n.get('resumo') or '')
    m = re.match(r'^(?:[\d.,]+ likes?, [\d.,]+ comments? - )?([\w.]+) (?:no|on) [^:]{3,40}: ?["“]?(.*?)["”]?\.?$', resumo, re.S)
    conta = m.group(1) if m else ''
    if m:
        n['descricao'] = m.group(2).strip()
        n['resumo'] = ''
    titulo = re.sub(r'\s*[-|]\s*Instagram\s*$', '', str(n.get('titulo') or ''))
    frase = re.split(r'(?<=[.!?])\s+|\s+[|•]\s+|[\u2063\u200b\n]', titulo.strip())[0]
    frase = re.sub(r'\s+', ' ', frase).strip(' :-')
    if len(frase) > 120:
        frase = frase[:120].rsplit(' ', 1)[0] + '…'
    n['titulo'] = frase
    return (f'{conta} (Instagram)' if conta else 'Instagram'), n


def relatorio_coleta(saida, origem_por_i, destino, dias=30):
    """Quanto cada origem (Google, feeds, Bing...) e cada veículo de feed acrescenta de
    notícias ÚNICAS (que nenhuma outra origem trouxe), depois de agrupar duplicatas."""
    from datetime import date, timedelta
    ultima = max((x.get('d', '') for x in saida), default='')
    if not ultima:
        return
    corte = (date.fromisoformat(ultima[:10]) - timedelta(days=dias)).isoformat()
    total, unicas, feeds_total, feeds_unicas = {}, {}, {}, {}
    for item in saida:
        if item.get('d', '') < corte:
            continue
        membros = [item['i']] + [o[2] for o in item.get('o', [])]
        origens = [origem_por_i.get(k, ('outra', '')) for k in membros]
        tipos = {o for o, _ in origens}
        for o in tipos:
            total[o] = total.get(o, 0) + 1
        if len(tipos) == 1:
            o = next(iter(tipos))
            unicas[o] = unicas.get(o, 0) + 1
        for o, fonte in origens:
            if o == 'feed_rss_fonte':
                feeds_total[fonte] = feeds_total.get(fonte, 0) + 1
                if len(tipos) == 1:
                    feeds_unicas[fonte] = feeds_unicas.get(fonte, 0) + 1
    rel = {
        'periodo': f'{corte} a {ultima[:10]}',
        'por_origem': {o: {'noticias': total[o], 'unicas': unicas.get(o, 0)} for o in sorted(total, key=lambda k: -total[k])},
        'feeds_que_mais_acrescentam': sorted(([f, feeds_unicas[f], feeds_total[f]] for f in feeds_unicas), key=lambda x: -x[1])[:40],
        'feeds_sem_noticia_unica': sorted(f for f in feeds_total if not feeds_unicas.get(f)),
    }
    destino.write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding='utf-8')
    print('Contribuição por origem (30 dias, notícias / únicas): ' +
          '; '.join(f'{o} {v["noticias"]}/{v["unicas"]}' for o, v in rel['por_origem'].items()))


def main():
    dados = json.loads(ORIGEM.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    fontes = json.loads(FONTES_JSON.read_text(encoding='utf-8')).get('fontes', []) if FONTES_JSON.exists() else []
    saida, links, ocultas, portugal = [], {}, 0, 0
    usados = set()
    origem_por_i = {}
    detalhes = {}
    fatos_por_i = {}
    fatos_titulo = {}
    # Anti-imagem: foto que aparece na galeria de 3+ notícias diferentes é de
    # anúncio, barra lateral ou chamada de outra matéria, não do fato.
    repetidas = contar_fotos_repetidas(noticias)
    # Mesmo "trecho" em matérias de títulos diferentes = a leitura pegou um bloco fixo do site.
    por_trecho = {}
    for n in noticias:
        if isinstance(n, dict) and n.get('trecho'):
            por_trecho.setdefault(_normal(str(n['trecho'])[:300]), set()).add(_normal(str(n.get('titulo') or ''))[:60])
    # Só é bloco fixo se, além de repetido, não tiver relação com os títulos (um comunicado
    # republicado por vários veículos repete o texto, mas fala do mesmo fato do título).
    from duplicatas import informativas
    trechos_repetidos = {t for t, titulos in por_trecho.items() if len(titulos) >= 2 and
                         sum(len(informativas(x) & informativas(t)) < 2 for x in titulos) > len(titulos) / 2}
    for n in noticias:
        if not isinstance(n, dict):
            continue
        i = identificador(n)
        if i in usados:  # mesmo link registrado duas vezes no acervo
            continue
        usados.add(i)
        fonte = str(n.get('fonte') or '').strip()
        if fonte == 'Instagram':
            fonte, n = ajustar_instagram(n)
        # Agregadores (MSN, Dailymotion, Yahoo...) só republicam outros veículos.
        if agregador(n.get('dominio_fonte') or n.get('url_original') or ''):
            continue
        # Origem da coleta, para o relatório de contribuição de cada fonte.
        origem_por_i[i] = ('google' if 'news.google.com' in str(n.get('url') or '') else
                           str(n.get('origem_coleta') or 'outra'), fonte)
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
        for k, foto in enumerate([n.get('imagem_url')] + list(n.get('imagens') or [])):
            foto = url_publica(foto)
            if not foto or foto in fotos:
                continue
            if k > 0 and (foto_alheia(foto, '', '', '') or _chave_foto(foto) in repetidas):
                continue  # galeria: só fotos da própria matéria
            fotos.append(foto)
        if fotos:
            item['img'] = fotos[0]
        if len(fotos) > 1:
            item['g'] = len(fotos)
        resumo = str(n.get('descricao') or n.get('resumo') or '').strip()
        # Imprensa: nome completo de preso vira iniciais no que o Radar exibe (resumo
        # e trecho da fonte). Notas oficiais ficam como o órgão publicou.
        oficial = n.get('licenca_texto') == 'oficial' or bool(re.search(r'\.(?:gov|jus|mp|leg|def)\.br$', str(n.get('dominio_fonte') or '')))
        nomes_presos = [] if oficial else nomes_dos_presos(resumo + '. ' + str(n.get('trecho') or ''))
        if nomes_presos:
            resumo = anonimizar(resumo, nomes_presos)
        if resumo:
            item['r'] = resumo[:700]  # resumo inteiro publicado pela fonte
        uf = inferir_uf(n, fontes)
        if uf:
            item['uf'] = uf
            # Estado escrito no título (forte) ou só o estado do veículo/resumo (fraco):
            # notícia nacional publicada por jornais de estados diferentes ainda pode ser duplicata.
            e, c, l = _ufs_no_texto(str(n.get('titulo') or ''), detalhado=True)
            item['_ufx'] = uf in (e | c | l)
        if cats:
            item['c'] = cats
        paragrafos = [str(p) for p in (n.get('texto_integral') or []) if str(p).strip()]
        detalhe = {}
        if paragrafos and n.get('licenca_texto'):
            item['x'] = 1
            detalhe.update(p=[anonimizar(x, nomes_presos) for x in paragrafos] if nomes_presos else paragrafos, l=str(n['licenca_texto']))
        if len(fotos) > 1:
            detalhe['g'] = fotos
        # Resumo do Radar: fatos da página original (ler_materias.py) ou, na falta
        # dela, do título e do resumo da fonte; redigido com frases próprias.
        # Fatos do título e do resumo da fonte: os mais confiáveis para as
        # quantidades (o texto da página pode trazer números de outras matérias).
        do_titulo = extrair(titulo, resumo)
        if not quantidades(do_titulo or {}) and n.get('trecho'):
            # Sem número no título/resumo: a abertura da reportagem (o lide) costuma trazê-lo.
            do_lide = extrair(titulo, resumo, str(n['trecho'])[:900])
            if quantidades(do_lide):
                do_titulo = do_lide
        if do_titulo:
            fatos_titulo[i] = do_titulo
        fatos = dict(n.get('fatos') or do_titulo or {})
        # Detalhes da ação (como, esconderijo, rota, crimes, encaminhamento...)
        # também a partir da abertura guardada, sem esperar a releitura da página.
        if isinstance(fatos.get('mandados'), str):
            fatos['mandados'] = re.sub(r'^1 mandados', '1 mandado', fatos['mandados'])
        trecho_salvo = str(n.get('trecho') or '')
        if trecho_salvo:
            for k, v in extrair(titulo, resumo, trecho_salvo).items():
                if k != 'apreendido' and v and not fatos.get(k):
                    fatos[k] = v
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
        # O que diz a fonte: 70% da reportagem (com crédito e link), ou o limite
        # do veículo em trecho_por_veiculo.json, se ele tiver pedido.
        trecho = limitar_trecho(str(n.get('trecho') or '').strip(), n)
        if trecho and _normal(trecho[:300]) in trechos_repetidos:
            trecho = ''  # bloco fixo do site (rodapé, "quem somos"), não a reportagem
        if nomes_presos:
            trecho = anonimizar(trecho, nomes_presos)
        if trecho and len(trecho) > len(resumo):
            detalhe['tr'] = trecho
            if n.get('tamanho_texto'):
                detalhe['tt'] = int(n['tamanho_texto'])
        detalhes.setdefault(i % LOTES, {})[str(i)] = detalhe
        saida.append(item)
    antes = len(saida)
    saida, removidas = agrupar_duplicatas(saida)
    for item in saida:
        for k in ('_h', '_lead', '_q', '_ufx'):
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
            if not com_numero:
                # Números lidos na página inteira não são confiáveis (outras matérias,
                # anúncios): sem número no título, resumo ou abertura, não há quantidade.
                base['apreendido'] = [a for a in base.get('apreendido', []) if not re.search(r'\d', a)]
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
        secoes = resumo_secoes(item, fatos)
        alvo = detalhes[item['i'] % LOTES][str(item['i'])]
        alvo['s'] = '\n\n'.join(t for _, t in secoes)
        alvo['sx'] = [list(x) for x in secoes]
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
    # Página inicial: só os últimos 31 dias (~1/4 do tamanho), para aparecer rápido;
    # o feed completo carrega em seguida, para busca e filtros por ano.
    ultima = max((x.get('d', '') for x in saida), default='')
    if ultima:
        from datetime import date, timedelta
        corte = (date.fromisoformat(ultima[:10]) - timedelta(days=31)).isoformat()
        def enxuto(x):  # a página inicial usa só o começo do resumo e o nome das outras fontes
            y = dict(x)
            if y.get('r'):
                y['r'] = y['r'][:220]
            if y.get('o'):
                y['o'] = [[o[0], '', o[2]] for o in y['o']]
            return y
        recente = dict(feed, noticias=[enxuto(x) for x in saida if x.get('d', '') >= corte], parcial=True)
        recente['total'] = len(recente['noticias'])
        (PASTA / 'feed-recente.json').write_text(json.dumps(recente, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
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
    relatorio_coleta(saida, origem_por_i, PASTA / 'dados' / 'coleta_relatorio.json')
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
