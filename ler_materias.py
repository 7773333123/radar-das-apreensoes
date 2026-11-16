#!/usr/bin/env python3
"""Lê a página original das notícias e traz foto, resumo e, quando permitido, o texto.

Para cada notícia com link original (não Google Notícias):
  - fotos: a principal (og:image / JSON-LD) e as demais fotos do corpo da
    matéria (<figure> e imagens do texto), sem logos, ícones e "leia também";
  - resumo: og:description / description publicados pelo veículo;
  - texto integral: SOMENTE se a página declara licença Creative Commons que
    permite reprodução (ex.: portais gov.br, CC BY-ND 3.0). O texto é guardado
    sem alterações, com a licença, para ser exibido com crédito. Conteúdo com
    direitos reservados (jornais) fica só com resumo, foto e link.

Uso: python ler_materias.py --limite 400
"""
import argparse
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ARQUIVO = Path(__file__).resolve().parent / 'noticias.json'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://radar-das-apreensoes.vercel.app)',
    'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'pt-BR,pt;q=0.9',
}
# Licenças CC que permitem reproduzir o texto (sem "NãoComercial", por cautela).
LICENCA = re.compile(
    r'creativecommons\.org/licenses/(by|by-sa|by-nd)/[\d.]+|'
    r'Creative Commons Atribui[çc][ãa]o(?:-SemDeriva[çc][õo]es|-CompartilhaIgual)?\s*[\d.]*(?:\s*N[ãa]o Adaptada|\s*Internacional|\s*Brasil)?',
    re.I)
NAO_COMERCIAL = re.compile(r'N[ãa]oComercial|licenses/by-nc', re.I)
VERSAO = 9  # 9 = fotos só da matéria (sem anúncios e chamadas); 2 = galeria; 3 = fatos; 4-5 = trecho; 6 = íntegra oficial; 7 = fatos do corpo; 8 = trecho proporcional e detalhes da ação. Versões anteriores são relidas
MAX_FOTOS = 12
NAO_FOTO = re.compile(r'logo|icon|icone|avatar|sprite|banner|placeholder|blank|pixel|spacer|loading|selo|'
                      r'whatsapp-share|/ads?/|publicidade|video\.glbimg|/x240/|\.svg(?:$|\?)|\.gif(?:$|\?)', re.I)
# Parágrafos que não fazem parte da reportagem (chamadas, assinatura, redes sociais).
RUIDO = re.compile(r'^(?:Leia (?:tamb[ée]m|mais)|Veja (?:tamb[ée]m|mais|o v[íi]deo)|Siga|Assine|Clique|Receba|Inscreva|'
                   r'Participe|Compartilhe|Acesse|Baixe|Entre (?:no|em) nosso|Publicidade|Continua (?:depois|ap[óo]s)|'
                   r'Foto:|Imagem:|Cr[ée]dito|Reprodu[çc][ãa]o|Por\s+\w+\s*$|Atualizad[oa]|Publicad[oa] em)', re.I)
# Citação proporcional (Lei 9.610/98, art. 46, III): a abertura da reportagem,
# até 1.500 caracteres e nunca mais que metade do texto original.
TRECHO_MIN, TRECHO_MAX, TRECHO_FRACAO = 600, 1500, 0.5
# Sites de órgãos públicos (polícias, secretarias, gov.br, Justiça, MP): notas
# oficiais feitas para divulgação, reproduzidas na íntegra com crédito.
OFICIAL = re.compile(r'\.(?:gov|jus|mp|leg|def)\.br$', re.I)
CONTATO = re.compile(r'^(?:Comunica[çc][ãa]o Social|Assessoria de|Ascom|Tel\.?:|E-?mail:|Fonte:|Fotos?:|@)', re.I)


class Metas(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.base = {}, ''

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'base' and a.get('href'):
            self.base = a['href']
        if tag == 'meta':
            chave = (a.get('property') or a.get('name') or a.get('itemprop') or '').lower()
            if chave and a.get('content') and chave not in self.meta:
                self.meta[chave] = a['content'].strip()


def valida(url):
    try:
        p = urlsplit(str(url).strip())
        return p.scheme in ('http', 'https') and bool(p.hostname) and 'news.google.com' not in p.hostname
    except (TypeError, ValueError):
        return False


def limpar(fragmento):
    texto = re.sub(r'<br\s*/?>', ' ', fragmento or '', flags=re.I)
    texto = re.sub(r'<[^>]+>', '', texto)
    return re.sub(r'\s+', ' ', html.unescape(texto)).strip()


def corpo_da_materia(pagina):
    """Parágrafos do corpo da matéria (Plone/gov.br, schema.org ou <article>)."""
    for padrao in (r'property="rnews:articleBody"[^>]*>(.*?)</div>\s*</div>',
                   r'itemprop="articleBody"[^>]*>(.*?)</(?:div|section|article)>',
                   r'<article\b[^>]*>(.*?)</article>'):
        m = re.search(padrao, pagina, re.S | re.I)
        if not m:
            continue
        paragrafos = [limpar(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', m.group(1), re.S | re.I)]
        paragrafos = [p for p in paragrafos if len(p) > 1 and not CONTATO.match(p)]
        if sum(len(p) for p in paragrafos) > 200:
            return paragrafos[:40]
    # Último recurso (só usado em páginas de licença aberta): o bloco da página
    # com mais texto em parágrafos — o corpo da matéria em quase todo CMS.
    melhor = []
    for bloco in re.findall(r'<(?:div|section|article)\b[^>]*>((?:(?!</?(?:div|section|article)\b).)*?)</(?:div|section|article)>',
                            pagina, re.S | re.I):
        paragrafos = [limpar(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', bloco, re.S | re.I)]
        paragrafos = [p for p in paragrafos if len(p) > 40 and not CONTATO.match(p)]
        if sum(map(len, paragrafos)) > sum(map(len, melhor)):
            melhor = paragrafos
    return melhor[:40] if sum(map(len, melhor)) > 400 else []


def corpo_estruturado(pagina):
    """Corpo da matéria preservando a edição do órgão: intertítulos ('## '), itens de lista ('• ')
    e parágrafos, na ordem original. Usado só para texto oficial ou de licença aberta."""
    regiao = regiao_da_materia(pagina)
    if not regiao:
        return []
    saida = []
    for m in re.finditer(r'<(p|h2|h3|h4|li|blockquote)\b[^>]*>(.*?)</\1>', regiao, re.S | re.I):
        tag, texto = m.group(1).lower(), limpar(m.group(2))
        if len(texto) < 2 or CONTATO.match(texto) or RUIDO.match(texto):
            continue
        if tag in ('h2', 'h3', 'h4'):
            saida.append('## ' + texto)
        elif tag == 'li':
            saida.append('• ' + texto)
        else:
            saida.append(texto)
    if sum(len(x) for x in saida if not x.startswith('## ')) < 200:
        return []
    while saida and saida[-1].startswith('## '):  # intertítulo solto no fim (ex.: "Leia também")
        saida.pop()
    return saida[:60]


def corpo_limpo(paragrafos):
    """Parágrafos da reportagem, sem chamadas, assinaturas e manchetes de outras matérias."""
    saida = []
    for p in paragrafos:
        p = p.strip()
        if not p or RUIDO.match(p) or CONTATO.match(p) or p.count('|') > 1:
            continue
        if not re.search(r'[.!?…:;)"”»]$', p):
            if len(saida) >= 2 and len(p) < 160:
                break  # lista de outras notícias no fim da página
            if len(p) < 160:
                continue
        saida.append(p)
    return saida if sum(map(len, saida)) >= 200 else []


def trecho_de_abertura(paragrafos):
    """Primeiros parágrafos da reportagem (o lide), para citação com crédito e link.

    Até TRECHO_MAX caracteres e no máximo TRECHO_FRACAO do texto da reportagem,
    sempre no fim de uma frase; o restante fica só no site de origem.
    """
    corpo = sum(len(p) for p in corpo_limpo(paragrafos)) or sum(len(p) for p in paragrafos)
    TRECHO_MAX = min(globals()['TRECHO_MAX'], int(corpo * TRECHO_FRACAO))
    TRECHO_MIN = min(globals()['TRECHO_MIN'], TRECHO_MAX)
    partes, total = [], 0
    for p in paragrafos[:15]:
        p = p.strip()
        if len(p) < 40 or RUIDO.match(p) or CONTATO.match(p) or p.count('|') > 1:
            continue
        # Parágrafo de reportagem termina em pontuação; sem ela é chamada para
        # outra matéria ("Internacional vence Flamengo..."): a reportagem acabou.
        if not re.search(r'[.!?…:;)"”»]$', p):
            if partes:
                break
            continue
        if total + len(p) > TRECHO_MAX:
            if total >= TRECHO_MIN:
                break
            frases = re.split(r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ“"])', p)
            corte = ''
            for f in frases:
                if total + len(corte) + len(f) + 1 > TRECHO_MAX:
                    break
                corte = (corte + ' ' + f).strip()
            if corte:
                partes.append(corte)
            break
        partes.append(p)
        total += len(p) + 2
        if total >= TRECHO_MAX:
            break
    texto = '\n\n'.join(partes)
    return texto if len(texto) >= min(200, TRECHO_MAX // 2) else ''


def melhor_do_srcset(srcset):
    """Escolhe a maior versão até ~1200 px de largura num srcset."""
    opcoes = []
    for parte in srcset.split(','):
        bits = parte.strip().split()
        if not bits:
            continue
        largura = int(bits[1][:-1]) if len(bits) > 1 and bits[1].endswith('w') and bits[1][:-1].isdigit() else 0
        opcoes.append((largura, bits[0]))
    if not opcoes:
        return ''
    ate = [o for o in opcoes if o[0] <= 1200]
    return max(ate or opcoes)[1]


# ---------- seleção de fotos: só as da própria matéria ----------
# Anúncios, cartões de "leia também", "mais lidas", vídeos recomendados e barras
# laterais também usam <figure>/<img>. Camadas de exclusão:
#  1. só a região da matéria (<article>/articleBody), cortada no primeiro bloco
#     de chamadas para outras matérias;
#  2. contêiner com classe/id de anúncio, recomendação ou barra lateral;
#  3. imagem dentro de link para outra página (miniatura de outra notícia);
#  4. domínio de publicidade/rastreamento, miniatura (150x150, thumb), ícone;
#  5. legenda/alt sem nenhuma relação com a matéria (ex.: foto de jogador).
CONTEINER_ALHEIO = re.compile(
    r'\b(?:ads?|adv|advert\w*|anuncio\w*|publicidade|banner\w*|sponsor\w*|patrocin\w*|dfp|gpt|teads|taboola|outbrain|'
    r'related\w*|relacionad\w*|recomend\w*|recommend\w*|mais-?lidas|most-?read|leia-?tamb\w*|veja-?tamb\w*|'
    r'saiba-?mais|sidebar|aside|widget\w*|newsletter|promo\w*|carousel-?news|ultimas|latest|trending|shopping|'
    r'video-?playlist|playlist|feed-?item|card-?news|outras-?noticias)\b', re.I)
FIM_DA_MATERIA = re.compile(
    r'<(?:div|section|aside|ul|h2|h3)\b[^>]*(?:class|id)="[^"]*(?:related|relacionad|recomend|recommend|mais-?lidas|'
    r'most-?read|leia-?tamb|veja-?tamb|outras-?noticias|taboola|outbrain|comments?|comentarios)[^"]*"'
    r'|>\s*(?:Leia (?:também|mais)|Veja também|Mais lidas|Notícias relacionadas|Últimas notícias|Você pode gostar)\s*<', re.I)
DOMINIO_ANUNCIO = re.compile(r'doubleclick|googlesyndication|googleadservices|adservice|adsystem|taboola|outbrain|teads|'
                             r'criteo|adnxs|rubiconproject|pubmatic|smartadserver|facebook\.com/tr|scorecardresearch|'
                             r'/ads?/|/banners?/|/publicidade/|/anuncios?/|/patrocin', re.I)
MINIATURA = re.compile(r'[-_](?:\d{2,3})x(?:\d{2,3})\.(?:jpe?g|png|webp)|/thumbs?/|[-_]thumb|/(?:50|75|100|120|150|160|180|200)x|'
                       r'/fit-in/(?:\d{2,3})x|w=(?:\d{2,3})\b(?!\d)', re.I)
ASSUNTO_ALHEIO = re.compile(r'futebol|jogador|campeonato|partida|gol\b|t[ée]cnico do|torcida|est[áa]dio|novela|cantor|'
                            r'cantora|show\b|reality|bbb\b|receita de|hor[óo]scopo|loteria|mega-?sena|cupom|oferta|promo[çc][ãa]o',
                            re.I)
POLICIAL = re.compile(r'pol[íi]cia|apreen|droga|maconha|coca[íi]na|arma|muni[çc]|presos?|pris[ãa]o|opera[çc][ãa]o|'
                      r've[íi]culo|carga|contrabando|PRF|PF|PM|PC|delegacia|fronteira|rodovia|BR-|viatura|suspeit', re.I)


def regiao_da_materia(pagina):
    """Trecho do HTML que contém a matéria, sem cabeçalho, barra lateral e chamadas finais."""
    for padrao in (r'itemprop="articleBody"[^>]*>', r'property="rnews:articleBody"[^>]*>', r'<article\b[^>]*>',
                   r'class="[^"]*(?:post-content|entry-content|materia-conteudo|content-text|article-body|news-body|texto)[^"]*"'):
        m = re.search(padrao, pagina, re.I)
        if m:
            inicio = m.start()
            fim = pagina.find('</article>', inicio)
            trecho = pagina[inicio:fim if fim > 0 else inicio + 200_000]
            corte = FIM_DA_MATERIA.search(trecho, 200)
            return trecho[:corte.start()] if corte else trecho
    return ''


def _palavras(texto):
    import unicodedata
    t = unicodedata.normalize('NFKD', texto or '')
    t = ''.join(c for c in t if not unicodedata.combining(c)).lower()
    return {w for w in re.findall(r'[a-z0-9]{4,}', t)}


def foto_alheia(url, contexto, legenda, titulo):
    """True se a imagem não é da matéria (anúncio, miniatura de outra notícia, assunto diferente)."""
    if not url or url.startswith('data:') or NAO_FOTO.search(url) or DOMINIO_ANUNCIO.search(url) or MINIATURA.search(url):
        return True
    if CONTEINER_ALHEIO.search(contexto):
        return True
    if legenda:
        if ASSUNTO_ALHEIO.search(legenda) and not POLICIAL.search(legenda):
            return True
        if titulo and len(_palavras(legenda)) >= 4 and not (_palavras(legenda) & _palavras(titulo)) and not POLICIAL.search(legenda):
            return True
    return False


def fotos_da_materia(pagina, base, titulo=''):
    """Fotos da própria matéria, na ordem em que aparecem (sem anúncios e chamadas)."""
    regiao = regiao_da_materia(pagina)
    if not regiao:
        return []  # sem a região da matéria identificada, fica só a foto principal (og:image)
    fotos = []
    # Pilha dos contêineres abertos em cada ponto (para saber o que envolve a imagem).
    pilha = []
    for m in re.finditer(r'<(/?)(div|section|aside|figure|li|ul|a|span|p)\b[^>]*>|<(?:amp-)?img\b[^>]*>', regiao, re.I):
        tag = m.group(0)
        if m.group(2):
            nome = m.group(2).lower()
            if m.group(1):
                for k in range(len(pilha) - 1, -1, -1):
                    if pilha[k][0] == nome:
                        del pilha[k:]
                        break
            elif not tag.endswith('/>'):
                pilha.append((nome, tag))
            continue
        atributos = dict((k.lower(), html.unescape(v)) for k, _, v in
                         re.findall(r'([\w:-]+)\s*=\s*(["\'])(.*?)\2', tag, re.S))
        url = (melhor_do_srcset(atributos.get('srcset') or atributos.get('data-srcset') or '')
               or atributos.get('data-src') or atributos.get('data-lazy-src') or atributos.get('src') or '')
        largura, altura = atributos.get('width', ''), atributos.get('height', '')
        if (largura.isdigit() and int(largura) < 300) or (altura.isdigit() and int(altura) < 200):
            continue
        contexto = ' '.join(t for _, t in pilha[-6:])
        # Imagem dentro de link para outra página = miniatura de outra notícia.
        link = next((t for n, t in reversed(pilha) if n == 'a'), '')
        destino = re.search(r'href="([^"]+)"', link)
        if destino and not re.search(r'\.(?:jpe?g|png|webp|gif)(?:\?|$)', destino.group(1), re.I):
            continue
        depois = regiao[m.end():m.end() + 800]
        legenda = ' '.join(filter(None, [atributos.get('alt', ''), atributos.get('title', ''),
                                         limpar((re.search(r'<figcaption\b[^>]*>(.*?)</figcaption>', depois, re.S | re.I) or [None, ''])[1])]))
        if foto_alheia(url, contexto + ' ' + atributos.get('class', ''), legenda, titulo):
            continue
        fotos.append(urljoin(base, url))
    return fotos


def sem_repetir(urls):
    vistos, saida = set(), []
    for u in urls:
        chave = re.sub(r'[?#].*$', '', u).rsplit('/', 1)[-1].lower()  # mesmo arquivo em tamanhos diferentes
        if valida(u) and chave not in vistos:
            vistos.add(chave)
            saida.append(u)
    return saida[:MAX_FOTOS]


def _iso(valor):
    try:
        d = datetime.fromisoformat(str(valor).strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone(timedelta(hours=-3)))  # horário de Brasília
    return d.astimezone(timezone.utc)


def data_publicacao(pagina, url):
    """Data em que a matéria foi publicada, segundo a própria página."""
    for padrao in (r'"datePublished"\s*:\s*"([^"]+)"',
                   r'<meta[^>]+(?:property|name|itemprop)=["\'](?:article:published_time|datePublished|publish-date|DC\.date\.issued)["\'][^>]+content=["\']([^"\']+)',
                   r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name|itemprop)=["\'](?:article:published_time|datePublished)["\']'):
        m = re.search(padrao, pagina, re.I)
        if m and _iso(m.group(1)):
            return _iso(m.group(1))
    m = re.search(r'class="documentPublished".{0,400}?(\d{2})/(\d{2})/(\d{4})\s*(\d{2})h(\d{2})', pagina, re.S)  # gov.br
    if m:
        dia, mes, ano, h, mi = m.groups()
        return _iso(f'{ano}-{mes}-{dia}T{h}:{mi}:00')
    m = re.search(r'/(20\d{2})/(\d{2})/(\d{2})/', url)
    if m:
        return _iso(f'{m.group(1)}-{m.group(2)}-{m.group(3)}T12:00:00')
    return None


def imagem_jsonld(pagina, base):
    for bloco in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', pagina, re.S | re.I):
        try:
            pilha = [json.loads(html.unescape(bloco))]
        except ValueError:
            continue
        while pilha:
            item = pilha.pop()
            if isinstance(item, list):
                pilha.extend(item)
            elif isinstance(item, dict):
                tipo = item.get('@type')
                tipos = tipo if isinstance(tipo, list) else [tipo]
                if any(t in ('NewsArticle', 'Article', 'ReportageNewsArticle') for t in tipos):
                    img = item.get('image') or item.get('thumbnailUrl')
                    for c in (img if isinstance(img, list) else [img]):
                        c = c.get('url') if isinstance(c, dict) else c
                        if isinstance(c, str) and valida(urljoin(base, c)):
                            return urljoin(base, c)
                pilha.extend(v for v in item.values() if isinstance(v, (list, dict)))
    return ''


def titulo_pagina(metas, pagina):
    t = metas.meta.get('og:title') or ''
    if not t:
        m = re.search(r'<title[^>]*>(.*?)</title>', pagina, re.S | re.I)
        t = limpar(m.group(1)) if m else ''
    return t


def ler(url, timeout):
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        if 'html' not in (r.headers.get('Content-Type') or '').lower():
            return {'erro': 'nao_html'}
        pagina = r.read(2_500_000).decode(r.headers.get_content_charset() or 'utf-8', 'replace')
        final = r.geturl()
    metas = Metas()
    metas.feed(pagina)
    base = urljoin(final, metas.base) if metas.base else final
    m = metas.meta
    resultado = {}
    for chave in ('og:image', 'og:image:url', 'og:image:secure_url', 'twitter:image', 'twitter:image:src'):
        if m.get(chave) and valida(urljoin(base, m[chave])):
            resultado['imagem'] = urljoin(base, html.unescape(m[chave]))
            break
    else:
        img = imagem_jsonld(pagina, base)
        if img:
            resultado['imagem'] = img
    resumo = m.get('og:description') or m.get('description') or m.get('twitter:description') or ''
    if resumo:
        resultado['resumo'] = limpar(resumo)[:1000]
    publicada = data_publicacao(pagina, final)
    if publicada and publicada.year >= 2000 and publicada <= datetime.now(timezone.utc) + timedelta(days=1):
        resultado['publicada'] = publicada.isoformat()
    resultado['imagens'] = sem_repetir(([resultado['imagem']] if resultado.get('imagem') else []) +
                                       fotos_da_materia(pagina, base, titulo_pagina(metas, pagina)))
    if resultado['imagens'] and not resultado.get('imagem'):
        resultado['imagem'] = resultado['imagens'][0]
    # Fatos objetivos do texto da página (só os dados; o texto não é guardado).
    # Só o corpo da matéria, e só o começo: a página inteira traz chamadas e
    # resumos de outras notícias, cujos números contaminavam as quantidades.
    paragrafos = [limpar(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', pagina, re.S | re.I)]
    corpo = corpo_limpo(corpo_da_materia(pagina))
    texto_pagina = ' '.join(corpo)[:3000]
    if texto_pagina:
        from resumo_fatos import extrair
        resultado['fatos'] = extrair(titulo_pagina(metas, pagina), m.get('og:description') or '', texto_pagina)
    base_trecho = corpo_da_materia(pagina) or [p for p in paragrafos if len(p) > 40]
    trecho = trecho_de_abertura(base_trecho)
    if trecho:
        resultado['trecho'] = trecho
        resultado['tamanho_texto'] = sum(len(p) for p in corpo_limpo(base_trecho)) or sum(map(len, base_trecho))
    licenca = LICENCA.search(pagina)
    if licenca and not NAO_COMERCIAL.search(pagina[max(0, licenca.start() - 300):licenca.end() + 300]):
        texto = corpo_limpo(corpo_da_materia(pagina))
        if texto:
            resultado['texto'] = texto
            resultado['licenca'] = limpar(licenca.group(0))
    elif OFICIAL.search(urlsplit(final).hostname or ''):
        # Nota oficial: reproduzida como o órgão editou (intertítulos, listas, parágrafos).
        texto = corpo_estruturado(pagina) or corpo_limpo(corpo_da_materia(pagina))
        if texto:
            resultado['texto'] = texto
            resultado['licenca'] = 'oficial'
            resultado['texto_v'] = 2
    return resultado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=1500, help='Páginas lidas por execução')
    ap.add_argument('--timeout', type=int, default=12)
    ap.add_argument('--trabalhadores', type=int, default=8)
    ap.add_argument('--max-tentativas', type=int, default=3)
    args = ap.parse_args()
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    pendentes = []
    for n in noticias:
        if not isinstance(n, dict):
            continue
        # Notas oficiais lidas antes da versão estruturada são relidas (texto como o órgão editou).
        oficial_antigo = n.get('licenca_texto') == 'oficial' and int(n.get('texto_v') or 0) < 2
        if int(n.get('materia_lida_v') or 0) >= VERSAO and not oficial_antigo:
            continue
        url = n.get('url_original') if valida(n.get('url_original')) else (n.get('url') if valida(n.get('url')) else '')
        if url and int(n.get('tentativas_leitura') or 0) < args.max_tentativas:
            pendentes.append((n, url))
    # Mais recentes primeiro.
    pendentes.sort(key=lambda p: p[0].get('data_iso') or '', reverse=True)
    lote = pendentes[:max(0, args.limite)]
    print(f'Notícias com link original ainda não lidas: {len(pendentes)}; lendo agora: {len(lote)}', flush=True)
    fotos = textos = resumos = falhas = galerias = datas = 0
    with ThreadPoolExecutor(max_workers=max(1, min(args.trabalhadores, 10))) as pool:
        tarefas = {pool.submit(ler, url, args.timeout): n for n, url in lote}
        for futuro in as_completed(tarefas):
            n = tarefas[futuro]
            try:
                r = futuro.result()
            except Exception as exc:  # rede, HTTP 4xx/5xx, página malformada
                r = {'erro': type(exc).__name__}
            if r.get('erro'):
                n['tentativas_leitura'] = int(n.get('tentativas_leitura') or 0) + 1
                n['leitura_fonte_status'] = 'erro_' + r['erro']
                falhas += 1
                continue
            n['materia_lida'] = time.strftime('%Y-%m-%d')
            n['materia_lida_v'] = VERSAO
            if r.get('publicada'):
                # A data da página prevalece sobre a da busca (o Google às vezes
                # informa a data de atualização ou de indexação).
                atual = _iso(n.get('data_iso') or '')
                nova = _iso(r['publicada'])
                if atual is None or abs((nova - atual).total_seconds()) > 36 * 3600:
                    n.setdefault('data_iso_busca', n.get('data_iso') or '')
                    n['data_iso'] = r['publicada']
                    n['data_conferida'] = 'corrigida_pela_pagina'
                    datas += 1
                else:
                    n['data_conferida'] = 'confirmada_pela_pagina'
            if r.get('imagens'):
                n['imagens'] = r['imagens']
                galerias += 1
            n['leitura_fonte_status'] = 'lida'
            if r.get('imagem') and not n.get('imagem_url'):
                n['imagem_url'] = r['imagem']
                n['imagem_status'] = 'metadados_da_fonte'
                fotos += 1
            if r.get('resumo') and not (n.get('descricao') or n.get('resumo')):
                n['resumo'] = r['resumo']
                resumos += 1
            if r.get('fatos'):
                n['fatos'] = r['fatos']
            if r.get('trecho'):
                n['trecho'] = r['trecho']
                n['tamanho_texto'] = r.get('tamanho_texto') or 0
            if r.get('texto'):
                n['texto_integral'] = r['texto']
                n['licenca_texto'] = r['licenca']
                if r.get('texto_v'):
                    n['texto_v'] = r['texto_v']
                textos += 1
    if lote:
        tmp = ARQUIVO.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        tmp.replace(ARQUIVO)
    print(f'Lidas: {len(lote) - falhas}/{len(lote)}; fotos novas: {fotos}; resumos novos: {resumos}; '
          f'notícias com galeria: {galerias}; datas corrigidas pela página: {datas}; textos integrais (licença aberta): {textos}; falhas: {falhas}')


if __name__ == '__main__':
    main()
