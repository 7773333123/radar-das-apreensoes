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
import os
import hashlib
import re
import shutil
import unicodedata
from pathlib import Path

from pagos import pago
from fronteira import polo_do_item, prioridade_regional
from localizar_uf import _ufs_no_texto, cidade_do_fato, inferir_uf
from resumo_fatos import LUGAR, droga_pelo_nome
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


# Trajeto da carga ou do preso: "seguia para Curitiba", "vinda de Ponta Porã", "com destino a São Paulo".
# Essas cidades não são o local da apreensão: ficam fora da cidade da notícia, do resumo e da busca.
TRAJETO = re.compile(r'(?:com destino (?:a|ao|à|para)|destinad[oa]s? (?:a|ao|à|para)|que seguia(?:m)? (?:para|de)|seguia(?:m)? (?:para|de)|'
                     r'seguiria(?:m)? para|seria(?:m)? levad[oa]s? (?:para|a|ao|à)|levaria(?:m)? [^.;]{0,25}?para|iria(?:m)? para|rumo a|'
                     r'a caminho de|em dire[çc][ãa]o a|vind[oa]s? d[eoa]s?|vinha(?:m)? d[eoa]s?|sa[íi]d[oa]s? d[eoa]s?|que sa[íi]u d[eoa]s?|'
                     r'partiu d[eoa]s?|procedente d[eoa]s?|oriund[oa]s? d[eoa]s?|saindo d[eoa]s?|trazid[oa]s? d[eoa]s?|'
                     r'transportad[oa]s? d[eoa]s?|levad[oa]s? d[eoa]s?|transportad[oa]s? (?:para|até))'
                     r'\s+(?:o |a |os |as )?' + LUGAR)
SEM_TRAJETO = re.compile(r'\s+(?:que\s+)?(?:seguiria|seguia|iria|com destino|destinad|vind[oa]s?|vinha|sa[íi]d[oa]s? d|levad[oa]s? para|'
                         r'seria(?:m)? levad|rumo a|procedente|oriund)', re.I)
# Leitura antiga que pegou conectivo no lugar do material: '74 tabletes de e foi'.
MATERIAL_QUEBRADO = re.compile(r'^[\d.,]+\s+\S+\s+(?:d[aeo]s?\s+)?(?:e|ou|foi|foram|que|em|no|na|com|para|por|a|o|os|as|mesm[ao]s?|dess[ae]s?|dest[ae]s?|tal|tais)\b', re.I)
DEPOIS_PARA = re.compile(r'\s+(?:para|até|com destino a)\s+(?:o |a |os |as )?' + LUGAR)


def cidades_de_trajeto(*textos):
    vistos = []
    for t in textos:
        for m in TRAJETO.finditer(t or ''):
            lugares = [m.group(1)]
            seguinte = DEPOIS_PARA.match(t, m.end())  # "de São Paulo para Alagoas"
            if seguinte:
                lugares.append(seguinte.group(1))
            for lugar in lugares:
                lugar = re.sub(r'\s*(?:\([A-Z]{2}\)|/[A-Z]{2})$', '', lugar).strip()
                if lugar and lugar not in vistos:
                    vistos.append(lugar)
    return vistos


CORTE_FONTE = re.compile(r'\s*(?:\[\s*(?:…|\.\.\.)\s*\]|\(\s*(?:…|\.\.\.)\s*\)|…|\.{3,}|(?:Leia|Saiba|Veja) mais\W*|Continue lendo\W*|Ler mais\W*)\s*$', re.I)
FIM_FRASE = re.compile(r'[.!?](?:["”»’)\]]*)(?=\s|$)')
PALAVRA_SOLTA = re.compile(r'\b(?:a|o|as|os|e|de|da|do|das|dos|em|no|na|nos|nas|com|para|por|pelo|pela|que|um|uma|ao|à|aos|às|se|sua|seu|mais|entre|sobre|após|até)$', re.I)


def fechar_frase(texto):
    """Nunca termina no meio: corta na última frase completa ("... com […]" -> frase anterior).

    Sem nenhuma frase completa, devolve o texto só se ele já for uma frase inteira
    (termina sem reticências e sem palavra solta); senão, ''.
    """
    t = re.sub(r'<[^>]+>', ' ', texto or '')
    t = re.sub(r'(?:The post|O post)\s.*?(?:first appeared on|apareceu primeiro em)\s+[^.]*\.?', ' ', t, flags=re.I | re.S)
    t = re.sub(r'\s+', ' ', t).strip()
    if not t:
        return ''
    cortado = bool(CORTE_FONTE.search(t))
    t = CORTE_FONTE.sub('', t).strip()
    if re.search(r'[.!?]["”»’)\]]*$', t) and not cortado:
        return t
    fins = list(FIM_FRASE.finditer(t))
    if fins and fins[-1].end() >= 20:
        return t[:fins[-1].end()].strip()
    if not cortado and len(t) >= 60 and not PALAVRA_SOLTA.search(t):
        return t + '.'
    return ''


TAMANHO_SOLTO = re.compile(r'\bde\s+(?:médi|pequen|grand|maior|menor)\w*\s+(?:(?:de|da|do|das|dos)\s+)?', re.I)
MESMA = re.compile(r'\b(?:d[aeo]s?\s+)?mesm[ao]s?\s+(?:substância|droga|material|entorpecente)\b', re.I)


def arrumar_itens(itens):
    """Tira o tamanho solto ("de médias") e troca "da mesma substância" pelo material anterior."""
    saida, anterior = [], ''
    for a in itens:
        a = TAMANHO_SOLTO.sub('de ', str(a)).replace('de de ', 'de ').strip()
        if MESMA.search(a):
            if not anterior:
                continue
            a = MESMA.sub(f'de {anterior}', a).replace('de de ', 'de ')
        m = re.match(r'^[\d.,]+\s+\S+\s+de\s+(.+)$', a)
        if m:
            anterior = m.group(1)
        saida.append(re.sub(r'\s+', ' ', a))
    # "7 kg de droga" + "maconha" (citada sem quantidade) = "7 kg de maconha".
    soltas = [x for x in saida if re.fullmatch(r'(?:maconha|coca[íi]na|crack|skunk|haxixe|pasta[ -]base(?: de coca[íi]na)?)', x, re.I)]
    genericas = [x for x in saida if re.fullmatch(r'[\d.,]+\s+(?:kg|quilos?|toneladas?|gramas?)\s+d[ae]s?\s+(?:drogas?|entorpecentes?)', x, re.I)]
    if len(soltas) == 1 and len(genericas) == 1:
        novo = re.sub(r'd[ae]s?\s+(?:drogas?|entorpecentes?)$', 'de ' + soltas[0].lower(), genericas[0])
        saida = [novo if x == genericas[0] else x for x in saida if x != soltas[0]]
    return saida


def _tamanho(item):
    """Tamanho da apreensão no tipo principal: kg de droga, armas, ou valor em R$."""
    q = item.get('q') or {}
    tipo = (item.get('c') or [8])[0]
    if tipo == 0:
        return sum(q.get(k, 0) for k in ('coc', 'mac', 'skh', 'cra', 'dro'))
    if tipo == 1:
        return q.get('arm', 0) or q.get('mun', 0) / 1000
    return item.get('vq', 0) or 0


def contexto_das_noticias(itens):
    """Para o 'Por que importa': posição no estado e no país (30 dias), polo de fronteira, notícias na cidade (12 meses)."""
    from bisect import bisect_left
    from datetime import datetime, timedelta
    def dia(it):
        try:
            return datetime.fromisoformat(it['d'][:16])
        except (KeyError, ValueError):
            return None
    try:
        polos = json.loads((Path(__file__).resolve().parent / 'polos_fronteira.json').read_text(encoding='utf-8'))['polos']
    except (OSError, ValueError, KeyError):
        polos = []
    ctx = {}
    grupos = {}
    for it in itens:
        d, t = dia(it), _tamanho(it)
        tipo0 = (it.get('c') or [8])[0]
        # Só entra no ranking apreensão relevante: 10 kg de droga, 2 armas, R$ 100 mil.
        minimo = {0: 10, 1: 2}.get(tipo0, 100_000)
        if d and t >= minimo:
            tipo = (it.get('c') or [8])[0]
            grupos.setdefault(('BR', tipo), []).append((d, t, it['i']))
            if it.get('uf'):
                grupos.setdefault((it['uf'], tipo), []).append((d, t, it['i']))
    for chave, lista in grupos.items():
        lista.sort()
        datas = [x[0] for x in lista]
        for d, t, i in lista:
            ini = bisect_left(datas, d - timedelta(days=30))
            fim = bisect_left(datas, d + timedelta(minutes=1))
            janela = [x[1] for x in lista[ini:fim]]
            rank = 1 + sum(1 for v in janela if v > t)
            c = ctx.setdefault(i, {})
            if chave[0] == 'BR':
                c['rank_br'], c['total_br'] = rank, len(janela)
            else:
                c['rank_uf'], c['total_uf'] = rank, len(janela)
    por_cidade = {}
    for it in itens:
        d = dia(it)
        if d and it.get('cid') and it.get('uf'):
            por_cidade.setdefault((it['uf'], it['cid']), []).append(d)
    for v in por_cidade.values():
        v.sort()
    for it in itens:
        d = dia(it)
        c = ctx.setdefault(it['i'], {})
        if d and it.get('cid') and it.get('uf'):
            datas = por_cidade[(it['uf'], it['cid'])]
            c['cidade_12m'] = bisect_left(datas, d) - bisect_left(datas, d - timedelta(days=365))
        alvo = f"{it.get('cid', '')} {it.get('t', '')}"
        for polo in polos:
            if polo.get('uf') == it.get('uf') and any(re.search(r'(?<!\w)' + re.escape(t) + r'(?!\w)', alvo) for t in polo.get('termos', [])):
                c['polo'] = polo['nome']
                break
    return ctx


def limpar_rede_social(texto):
    """Tira hashtags, emojis e chamadas de post ("Clique no link da bio", "De #cidade para o mundo")."""
    if not texto or ('#' not in texto and 'link da bio' not in texto.lower()):
        return texto
    t = re.sub(r'(?i)\bclique no link da bio\b[^.!?]*|\bleia no\s+#\S+|\bde\s+#\S+\s+para o mundo', ' ', texto)
    t = re.sub(r'#\w+', ' ', t)
    t = re.sub(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip(' ·|-')
    return t if not t or t[-1] in '.!?…' else t + '.'


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


from duplicatas import agrupar as _agrupar, fatos_auditor, mesma_materia, normal as _normal  # noqa: E402,F401


from datetime import datetime as _dt, timedelta as _td, timezone as _tz  # noqa: E402
RECENTE_AUDITORIA = (_dt.now(_tz.utc) - _td(days=5)).isoformat()[:10]
# Análise antes da publicação: notícia das últimas 6 h com foto ainda não analisada (dHash e
# recorte, hash_imagens.py) espera a análise para não entrar no site como duplicata.
PENDENTE_DESDE = (_dt.now(_tz.utc) - _td(hours=6)).isoformat()[:19]
from fotos_orb import MIN_COBERTURA as MIN_COBERTURA_FOTO, MIN_PONTOS as MIN_PONTOS_FOTO, foto_util  # noqa: E402
BLOQUEIO_LEITURA = re.compile(r'^(?:erro_HTTPError|http_4\d\d|texto_insuficiente|nao_html|erro_nao_html|.*robots.*|.*bloque.*|.*paywall.*)$')


def leitura_bloqueada(n):
    """A página do veículo não pode ser lida (bloqueio, erro definitivo, sem texto), ou o
    link original não foi achado depois de todas as tentativas."""
    status = str(n.get('leitura_fonte_status') or '')
    if BLOQUEIO_LEITURA.match(status):
        return True
    try:
        tentativas = int(n.get('tentativas_url_original_v2') or 0)
    except (TypeError, ValueError):
        tentativas = 0
    sem_link = not url_publica(n.get('url_original')) or 'news.google.com' in str(n.get('url_original'))
    return sem_link and tentativas >= 3


def agrupar_duplicatas(itens, motivos=None):
    return _agrupar(itens, motivos)


_PAGINA_SITE = re.compile(r'(?i)^(resultados? (?:para|da busca|de pesquisa)|busca:|tag:|categoria:'
                          r'|tudo sobre(?::|.*-\s*p[aá]gina\s+\d)|arquivos\s*#)')
_VERBO = re.compile(r'(?i)\b(é|são|foi|foram|apreend\w*|prend\w*|pres[oa]s?|encontrad\w*|achad\w*|recolhid\w*)\b')


def nao_e_noticia(titulo):
    """Página de busca, etiqueta ou arquivo do site ("Tag: ...", "Arquivos #Draco",
    "Arquivos tráfico de drogas em X"), e não uma notícia. "Arquivos de abuso sexual são
    apreendidos..." é notícia (tem verbo)."""
    t = (titulo or '').strip()
    if _PAGINA_SITE.match(t):
        return True
    return bool(re.match(r'(?i)^arquivos\s', t)) and not _VERBO.search(t)


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


# Imagem que não é foto do fato: logotipo do órgão (gov.br/pf/logo.png), arte padrão do
# veículo para compartilhamento, avatar. Não vai como foto; outra versão da notícia ou a
# foto buscada na matéria entra no lugar.
CAPA_GENERICA = re.compile(r'(?:^|[/_-])(?:logo|logotipo|brasao|default|og-?image|share|avatar|placeholder|'
                           r'thumb_\d+x\d+_agbrasil|default-meta-image|sem-?imagem|no-?image)[\w.-]*(?:\.(?:png|jpe?g|webp|svg)|$)|'
                           r'/api/og-image|/thumb\.php$|/img$|/(?:None|null|undefined)$', re.I)


BLOCO_FIXO = re.compile(
    r'^(?:\s*(?:Conte[úu]dos? copiados?[^.]*?cr[ée]ditos?[^.]*\.|Nos adicione como fonte preferencial[^.]*\.|'
    r'Siga (?:o|a|nosso|nossa)[^.]{0,80}(?:WhatsApp|Instagram|Google|canal)[^.]*\.|'
    r'(?:Receba|Participe)[^.]{0,80}WhatsApp[^.]*\.|Ou[çc]a (?:a|esta) (?:not[íi]cia|mat[ée]ria)[^.]*\.|'
    r'Clique aqui[^.]*\.|Publicidade\.?|Continua (?:depois|ap[óo]s) (?:da|a) publicidade\.?))+', re.I)


def limpar_bloco_fixo(texto):
    return BLOCO_FIXO.sub('', texto or '').strip()


def contar_capas_genericas(noticias, limite=6):
    """Capa (imagem principal) repetida em 6+ notícias de 3+ dias: arte padrão, não foto do fato.
    Também: o MESMO veículo usando a mesma imagem em 3+ notícias de títulos diferentes, em 3+
    dias diferentes (foto de arquivo da GCM, arte de categoria do portal)."""
    vistas, por_site = {}, {}
    for n in noticias:
        if isinstance(n, dict) and n.get('imagem_url'):
            chave = _chave_foto(str(n['imagem_url']))
            dia = str(n.get('data_iso') or '')[:10]
            vistas.setdefault(chave, []).append(dia)
            site = str(n.get('dominio_fonte') or n.get('fonte') or '').lower().removeprefix('www.')
            por_site.setdefault((chave, site), []).append((dia, str(n.get('titulo') or '')[:60].lower()))
    genericas = {f for f, dias in vistas.items() if len(dias) >= limite and len(set(dias)) >= 3}
    for (f, _), lista in por_site.items():
        if len({t for _, t in lista}) >= 3 and len({d for d, _ in lista if d}) >= 3:
            genericas.add(f)
    return genericas


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
    # Acervo em partes (acervo.py): a parte "quente" gera só as notícias recentes (e as sem
    # data); as mais antigas estão na parte do ano delas, que gera o próprio pedaço do site.
    import acervo
    if acervo.parte_baixada() == 'quente' and (acervo.ponteiro().get('partes') or {}):
        corte = acervo.corte_quente()
        antes_corte = len(noticias)
        noticias = [n for n in noticias if not isinstance(n, dict) or not n.get('data_iso') or str(n['data_iso'])[:10] >= corte]
        print(f'Parte quente: {len(noticias)} notícias desde {corte} ({antes_corte - len(noticias)} antigas ficam com a parte do ano)')
    # Comparação de fotos por recorte/zoom ativa (fotos_orb.py já analisou fotos recentes): só
    # então a notícia nova espera a análise da foto (se o passo falhar, nada fica retido).
    ORB_ATIVO = any(isinstance(n, dict) and n.get('img_orb2') and str(n.get('data_iso') or '')[:19] >= PENDENTE_DESDE
                    for n in noticias)
    fontes = json.loads(FONTES_JSON.read_text(encoding='utf-8')).get('fontes', []) if FONTES_JSON.exists() else []
    saida, links, ocultas, portugal, pagas = [], {}, 0, 0, 0
    usados = set()
    origem_por_i = {}
    detalhes = {}
    fatos_por_i = {}
    fatos_titulo = {}
    # Anti-imagem: foto que aparece na galeria de 3+ notícias diferentes é de
    # anúncio, barra lateral ou chamada de outra matéria, não do fato.
    repetidas = contar_fotos_repetidas(noticias)
    capas_genericas = contar_capas_genericas(noticias)
    # Avisos fixos dos sites no começo do texto lido ("Conteúdos copiados ... devem conter os
    # devidos créditos", "Nos adicione como fonte preferencial no Google"): não são a reportagem.
    for n in noticias:
        if isinstance(n, dict) and n.get('trecho'):
            limpo = limpar_bloco_fixo(str(n['trecho']))
            if limpo != n['trecho']:
                n['trecho'] = limpo
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
        # Veículos com conteúdo pago (assinatura) ficam fora do site: pagos.py.
        if pago(n):
            pagas += 1
            continue
        titulo = limpar_titulo(n.get('titulo'), fonte)
        if not titulo:
            continue
        # Páginas de busca, etiqueta e arquivo dos sites não são notícias ("Busca: ...", "Tag: ...",
        # "Tudo sobre: ...", "Arquivos #Draco ...").
        if nao_e_noticia(titulo) or not relevante(titulo):
            ocultas += 1
            continue
        cats = categorias(n, titulo)
        # Veículo quase sempre é o transporte do que foi apreendido ("maconha em carro"):
        # só é o tipo principal quando não há outro tipo.
        if cats and cats[0] == 3 and any(c not in (3, 8) for c in cats):
            cats = [c for c in cats if c != 3] + [3]
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
            # Endereço corrompido na origem: "https://pm.am.gov.brhttps://pm.am.gov.br/foto.jpg".
            if isinstance(foto, str) and foto.rfind('http', 8) > 0:
                foto = foto[foto.rfind('http', 8):]
            foto = url_publica(foto)
            if not foto or foto in fotos:
                continue
            sem_param = foto.split('?')[0]
            if (CAPA_GENERICA.search(sem_param) and not re.search(r'-c-default\.', sem_param)) or _chave_foto(foto) in capas_genericas:
                continue  # logotipo/arte padrão: não é foto do fato
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
        resumo = limpar_rede_social(resumo)
        if resumo:
            item['r'] = fechar_frase(resumo[:700] + ('…' if len(resumo) > 700 else ''))  # sem frase cortada
            if not item['r']:
                del item['r']
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
        if fatos.get('apreendido'):  # "substância análoga à maconha" -> "maconha" (fichas antigas também)
            fatos['apreendido'] = [droga_pelo_nome(str(a)) for a in fatos['apreendido']]
        if fatos.get('apreendido'):  # "90 pedras de médias de crack, 280 pedras de pequenas da mesma substância"
            fatos['apreendido'] = arrumar_itens(fatos['apreendido'])
        if fatos.get('apreendido'):  # fichas antigas: trajeto colado no material
            fatos['apreendido'] = list(dict.fromkeys(SEM_TRAJETO.split(str(a))[0].strip(' ,;') for a in fatos['apreendido']
                                                     if not MATERIAL_QUEBRADO.search(str(a))))
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
            if n.get('img_iguais') and fotos and fotos[0] == url_publica(n.get('imagem_url')):  # não vale logotipo
                item['_iguais'] = list(n['img_iguais'])
        # A mesma foto com recorte/zoom/outro tamanho (fotos_orb.py): pares com pontos em comum.
        # Só pares da versão 2 (pontos espalhados pela foto, não só na marca d'água/brasão):
        # a versão 1 casava fotos diferentes com o mesmo logotipo do site ou brasão da polícia.
        if n.get('img_mesma') and fotos and fotos[0] == url_publica(n.get('imagem_url')):
            item['_mesma'] = [u for u, k in n['img_mesma'].items()
                              if isinstance(k, list) and len(k) > 1 and k[0] >= MIN_PONTOS_FOTO and k[1] >= MIN_COBERTURA_FOTO]
        item['_lead'] = str(n.get('trecho') or resumo)[:600]
        item['_txt'] = str(n.get('trecho') or resumo or '')[:2500]  # texto para o motor de evidências
        if (n.get('imagem_url') and not n.get('img_dhash') and int(n.get('img_dhash_tentativas') or 0) < 2
                and str(data or '')[:19] >= PENDENTE_DESDE):
            item['_pend'] = 1  # foto ainda não analisada (duas falhas de download liberam)
        elif (ORB_ATIVO and foto_util(n.get('imagem_url')) and n.get('uf') and not n.get('img_orb2')
              and int(n.get('img_orb_falhas') or 0) < 2 and str(data or '')[:19] >= PENDENTE_DESDE):
            item['_pend'] = 1  # foto ainda não comparada por recorte/zoom (fotos_orb.py)
        if do_titulo:
            q = {k: v for k, v in quantidades(do_titulo).items() if k != 'val'}
            if q:
                item['_q'] = q
        if fatos:
            fatos_por_i[i] = fatos
            detalhe['f'] = fatos
        # Evidências do auditor de duplicatas (só notícias recentes): cidade do fato e órgãos.
        if data and data[:10] >= RECENTE_AUDITORIA:
            rota_aud = cidades_de_trajeto(titulo, resumo) + [x for x in ((fatos or {}).get('origem'), (fatos or {}).get('destino')) if x]
            cid_aud = cidade_do_fato(uf or '', titulo, resumo, (fatos or {}).get('cidades', ()), rota_aud)
            if cid_aud:
                item['_cid'] = cid_aud
            if (fatos or {}).get('orgaos'):
                item['_ag'] = list(fatos['orgaos'])
            fx = fatos_auditor({**(do_titulo or {}), **(fatos or {})})
            if fx:
                item['_fx'] = fx
        # O que diz a fonte: 70% da reportagem (com crédito e link), ou o limite
        # do veículo em trecho_por_veiculo.json, se ele tiver pedido.
        trecho = limitar_trecho(limpar_rede_social(str(n.get('trecho') or '').strip()), n)
        if trecho and _normal(trecho[:300]) in trechos_repetidos:
            trecho = ''  # bloco fixo do site (rodapé, "quem somos"), não a reportagem
        if nomes_presos:
            trecho = anonimizar(trecho, nomes_presos)
        if trecho and len(trecho) > len(resumo):
            trecho = fechar_frase(trecho)
            if trecho:
                detalhe['tr'] = trecho
                if n.get('tamanho_texto'):
                    detalhe['tt'] = int(n['tamanho_texto'])
        if detalhe.get('tr'):
            item['_tr'] = 1
        # Veículo que não libera a leitura (bloqueio, erro, página sem texto) ou link original
        # nunca encontrado: sem conteúdo para mostrar, a notícia não vai ao site. Se outro
        # veículo publicou o mesmo fato, a versão dele é a exibida (duplicatas.py).
        if not (detalhe.get('tr') or item.get('x')) and leitura_bloqueada(n):
            item['_bloq'] = True
        detalhes.setdefault(i % LOTES, {})[str(i)] = detalhe
        saida.append(item)
    antes = len(saida)
    textos_por_i = {it['i']: (it.get('t', ''), it.get('r', ''), it.get('uf', '')) for it in saida}  # cidade de outras versões
    if os.environ.get('RADAR_DUMP_ITENS'):  # diagnóstico: itens antes do agrupamento (motor de evidências)
        Path(os.environ['RADAR_DUMP_ITENS']).write_text(json.dumps(saida, ensure_ascii=False, default=list), encoding='utf-8')
    saida, removidas = agrupar_duplicatas(saida)
    # Relatório do auditor: pares em dúvida (não juntados), para revisão periódica.
    from duplicatas import SUSPEITAS, JUNTADAS
    # Fila do juiz: primeiro os pares com notícia em espera (até 6 h), depois os dos últimos 3
    # dias (página inicial), depois o placar (regras e motor juntos).
    tres_dias = (_dt.now(_tz.utc) - _td(days=3)).isoformat()[:19]

    def _prioridade_juiz(par):
        nova = max(str(par['a'][3])[:19], str(par['b'][3])[:19])
        return (0 if nova >= PENDENTE_DESDE else 1 if nova >= tres_dias else 2, -float(par.get('nota') or 0))
    SUSPEITAS.sort(key=_prioridade_juiz)
    (PASTA / 'duplicatas_suspeitas.json').write_text(json.dumps({
        'gerado_em': _dt.now(_tz.utc).isoformat(timespec='seconds'),
        'juntadas_pelo_auditor': len(JUNTADAS), 'suspeitas': SUSPEITAS[:600]}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'Auditor de duplicatas: {len(JUNTADAS)} pares juntados; {len(SUSPEITAS)} em dúvida (duplicatas_suspeitas.json)')
    from motor_evidencias import REVISOR_LOG
    (PASTA / 'revisor_vitrine.json').write_text(json.dumps({'gerado_em': _dt.now(_tz.utc).isoformat(timespec='seconds'),
        'corrigidas': len(REVISOR_LOG), 'pares': REVISOR_LOG[:300]}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'Revisor da página inicial: {len(REVISOR_LOG)} duplicatas corrigidas (revisor_vitrine.json)')
    bloqueadas = [it for it in saida if it.get('_bloq')]
    saida = [it for it in saida if not it.get('_bloq')]
    removidas |= {it['i'] for it in bloqueadas}
    antes -= len(bloqueadas)
    print(f'Sem conteúdo publicável (veículo bloqueia a leitura ou link não encontrado): {len(bloqueadas)} fora do site')
    # Análise antes da publicação: notícia recente cuja foto ainda não passou pela comparação de
    # imagens fica fora até a próxima rodada (se já foi agrupada com outra versão, sai normalmente).
    pendentes = [it for it in saida if it.get('_pend') and not it.get('o')]
    if pendentes:
        saida = [it for it in saida if not (it.get('_pend') and not it.get('o'))]
        removidas |= {it['i'] for it in pendentes}
        antes -= len(pendentes)
    print(f'Aguardando a análise da foto (duplicatas por imagem): {len(pendentes)} fora do site até a próxima rodada')
    # Espera pelo juiz de IA (pedido do usuário, 20/11/2026): notícia NOVA em dúvida com outra
    # (par em duplicatas_suspeitas.json que o juiz ainda não leu) só entra no site depois da
    # decisão: se for o mesmo fato, entra já unida; se diferente, entra sozinha. Limite de 6 h
    # (PENDENTE_DESDE): depois disso é publicada mesmo sem decisão. Retém só a mais nova do par
    # e só se ela ainda estiver sozinha (sem outras versões já unidas).
    from duplicatas import chave_par as _chave, decisoes_juiz as _decisoes
    _juiz = _decisoes()
    sozinhas = {it['i'] for it in saida if not it.get('o')}
    em_espera = set()
    for par in SUSPEITAS:
        a, b = par['a'], par['b']
        if (_juiz.get(_chave(a[0], b[0])) or {}).get('v'):
            continue  # o juiz já leu (incerto: publica; mesmo/diferente já aplicados)
        nova = a if str(a[3]) >= str(b[3]) else b
        if str(nova[3])[:19] >= PENDENTE_DESDE and nova[0] in sozinhas:
            em_espera.add(nova[0])
    if em_espera:
        saida = [it for it in saida if it['i'] not in em_espera]
        removidas |= em_espera
        antes -= len(em_espera)
    (PASTA / 'espera_juiz.json').write_text(json.dumps({'gerado_em': _dt.now(_tz.utc).isoformat(timespec='seconds'),
        'em_espera': len(em_espera)}, ensure_ascii=False), encoding='utf-8')
    print(f'Em espera pelo juiz de IA (dúvida com outra notícia, até 6 h): {len(em_espera)} fora do site por enquanto')
    # Padrão do site: nenhuma notícia sem foto E sem conteúdo (trecho da reportagem ou texto
    # integral). Fica no acervo e entra no site assim que a leitura trouxer foto ou trecho
    # (de qualquer versão da mesma notícia: o agrupamento já copiou a foto de outra fonte).
    def tem_conteudo(it):
        d = detalhes.get(it['i'] % LOTES, {}).get(str(it['i']), {})
        return bool(it.get('img') or it.get('x') or d.get('tr'))
    vazias = [it for it in saida if not tem_conteudo(it)]
    if vazias:
        saida = [it for it in saida if tem_conteudo(it)]
        removidas |= {it['i'] for it in vazias}
        antes -= len(vazias)
    print(f'Sem foto e sem conteúdo (aguardando leitura): {len(vazias)} fora do site')
    for item in saida:
        for k in ('_h', '_iguais', '_lead', '_q', '_ufx', '_tr', '_bloq', '_cid', '_ag', '_pend', '_fx', '_mesma', '_txt'):
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
    # Resumo do Radar em parágrafos: fatos, por que importa, quem atuou, entenda e outros veículos.
    for item in saida:  # cidade antes do contexto (o contexto conta notícias por cidade)
        if not item.get('cid'):
            f0 = juntar_fatos([fatos_por_i.get(item['i'])] + [fatos_por_i.get(o[2]) for o in item.get('o', [])]) or {}
            rota0 = cidades_de_trajeto(item.get('t', ''), item.get('r', '')) + [x for x in (f0.get('origem'), f0.get('destino')) if x]
            c0 = cidade_do_fato(item.get('uf', ''), item.get('t', ''), item.get('r', ''), f0.get('cidades', ()), rota0)
            if c0:
                item['cid'] = c0
    contexto = contexto_das_noticias(saida)
    for item in saida:
        fatos = juntar_fatos([fatos_por_i.get(item['i'])] + [fatos_por_i.get(o[2]) for o in item.get('o', [])])
        # Município do fato (filtro e páginas por cidade).
        trajeto = cidades_de_trajeto(item.get('t', ''), item.get('r', ''))
        rota = trajeto + [x for x in ((fatos or {}).get('origem'), (fatos or {}).get('destino')) if x]
        cid = cidade_do_fato(item.get('uf', ''), item.get('t', ''), item.get('r', ''), (fatos or {}).get('cidades', ()), rota)
        if not cid and item.get('o'):
            # A versão exibida (ex.: nota oficial "no Paraná") não cita a cidade: vale a cidade
            # que a maioria das outras versões da mesma notícia cita.
            from collections import Counter as _C
            votos = _C()
            for o in item['o']:
                t_o, r_o, uf_o = textos_por_i.get(o[2], ('', '', ''))
                if uf_o == item.get('uf'):
                    c_o = cidade_do_fato(uf_o, t_o, r_o, (), cidades_de_trajeto(t_o, r_o))
                    if c_o:
                        votos[c_o] += 1
            if votos:
                cid = votos.most_common(1)[0][0]
        trajeto = [x for x in trajeto if x != cid]
        if trajeto:
            item['rt'] = trajeto[:4]  # a busca do site ignora essas cidades
        if cid:
            item['cid'] = cid
        polo = polo_do_item(item)  # bloco "Fronteira" da página inicial
        if polo:
            item['fr'] = polo
            item['frp'] = prioridade_regional(item.get('cid', ''), item.get('t', ''), item.get('uf', ''))  # 1 = Foz
        # Resumo e ficha ("Onde") citam só o local da apreensão, nunca a cidade da
        # delegacia, da moradia ou da origem/destino da carga.
        alvo = detalhes[item['i'] % LOTES][str(item['i'])]
        if fatos:
            fatos = dict(fatos)
            if cid:
                fatos['cidades'] = [f"{cid} ({item['uf']})"]
            else:
                fatos.pop('cidades', None)
            if isinstance(alvo.get('f'), dict):
                alvo['f'] = dict(alvo['f'])
                if cid:
                    alvo['f']['cidades'] = fatos['cidades']
                else:
                    alvo['f'].pop('cidades', None)
        secoes = resumo_secoes(item, fatos, contexto.get(item['i']))
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
    print(f'Duplicatas agrupadas: {antes - len(saida)}; notícias de Portugal excluídas: {portugal}; de veículos pagos: {pagas}')
    print(f'{DESTINO.name}: {len(saida)} notícias ({ocultas} sem relação com apreensões ocultadas), '
          f'{DESTINO.stat().st_size / 1e6:.1f} MB')
    print(f'{LINKS.name}: {LINKS.stat().st_size / 1e6:.1f} MB (carregado só ao abrir uma notícia)')
    print(f'det/: {sum(1 for v in detalhes.values() for d in v.values() if "p" in d)} textos integrais, '
          f'{sum(1 for v in detalhes.values() for d in v.values() if "g" in d)} galerias de fotos')


if __name__ == '__main__':
    main()
