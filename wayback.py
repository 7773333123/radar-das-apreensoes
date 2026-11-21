#!/usr/bin/env python3
"""Coleta pelo Wayback Machine (archive.org): notícias de apreensão de anos antigos (2006-2016).

Muitas matérias daquela época sumiram dos sites (portais fechados, endereços trocados, arquivo
apagado) e o Google Notícias quase não as indexa. O archive.org guarda cópias. Para cada ano e cada
site (veículos cadastrados em fontes.json e portais oficiais antigos), consulta o índice do
archive.org (CDX) só com endereços que citam apreensão, drogas, armas ou contrabando; lê a cópia
arquivada (título, data, foto, resumo) e acrescenta ao acervo com o link da cópia arquivada.
O resto do caminho é o de sempre: leitura das matérias, fotos, duplicatas, regras do site.

Uso: python wayback.py --ano 2012 [--tempo-max 6000] [--por-dominio 150]
O cursor (wayback_cursor.json) guarda, por ano, até qual site já foi consultado.
"""
import argparse
import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from classificar import relevante
from coletar_feeds_estaduais import incorporar

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / 'noticias.json'
CURSOR_ANTIGO = RAIZ / 'wayback_cursor.json'  # antes de 21/11/2026: um cursor para todos os anos
FONTES = RAIZ / 'fontes.json'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; RadarApreensoes/1.0; acervo historico publico)'}
# Endereço (slug) com assunto de apreensão: filtro feito pelo próprio archive.org.
FILTRO_URL = r'.*(apreend|apreens|droga|maconha|cocain|trafic|arma|fuzil|muni[cç]|contraband|descaminho|crack|entorpecent|cigarro).*'
# Portais oficiais antigos (notas de PF, PRF, Receita, secretarias e polícias estaduais antes de 2015).
OFICIAIS = [
    ('Polícia Federal', 'dpf.gov.br', ''), ('Polícia Federal', 'pf.gov.br', ''),
    ('Polícia Rodoviária Federal', 'prf.gov.br', ''), ('Receita Federal', 'receita.fazenda.gov.br', ''),
    ('SSP-SP', 'ssp.sp.gov.br', 'SP'), ('Polícia Civil-SP', 'policiacivil.sp.gov.br', 'SP'),
    ('SESP-PR', 'seguranca.pr.gov.br', 'PR'), ('Polícia Civil-PR', 'policiacivil.pr.gov.br', 'PR'),
    ('Sejusp-MS', 'sejusp.ms.gov.br', 'MS'), ('Sesp-MT', 'sesp.mt.gov.br', 'MT'),
    ('SSP-BA', 'ssp.ba.gov.br', 'BA'), ('Sejusp-MG', 'seguranca.mg.gov.br', 'MG'),
    ('SSP-RS', 'ssp.rs.gov.br', 'RS'), ('SSP-SC', 'ssp.sc.gov.br', 'SC'), ('SSP-GO', 'ssp.go.gov.br', 'GO'),
    ('SDS-PE', 'sds.pe.gov.br', 'PE'), ('SSPDS-CE', 'sspds.ce.gov.br', 'CE'), ('Segup-PA', 'segup.pa.gov.br', 'PA'),
    ('SSP-AM', 'ssp.am.gov.br', 'AM'), ('Sesdec-RO', 'sesdec.ro.gov.br', 'RO'), ('SSP-DF', 'ssp.df.gov.br', 'DF'),
    ('Seseg-RJ', 'seseg.rj.gov.br', 'RJ'), ('Agência Brasil', 'agenciabrasil.ebc.com.br', ''),
]
LISTAGEM = re.compile(r'/(?:tag|tags|categoria|category|page|pagina|busca|search|autor|author|feed|rss)(?:/|$|\?)|\.(?:jpg|png|gif|pdf|css|js)(?:$|\?)', re.I)


def baixar(url, timeout=40):
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        return r.read(2_000_000).decode('utf-8', 'replace')


def lista_sites():
    """Portais oficiais primeiro; depois os veículos cadastrados, dos que mais publicaram apreensões."""
    sites = [(n, d, uf) for n, d, uf in OFICIAIS]
    vistos = {d for _, d, _ in sites}
    fontes = json.loads(FONTES.read_text(encoding='utf-8'))['fontes']
    fontes.sort(key=lambda f: -int(f.get('noticias_no_acervo') or 0))
    for f in fontes:
        d = str(f.get('dominio') or '').lower().removeprefix('www.')
        if d and d not in vistos and 'news.google' not in d:
            vistos.add(d)
            sites.append((f.get('nome') or d, d, f.get('uf') or ''))
    return sites


def capturas(dominio, ano, limite):
    """Endereços arquivados do site no ano, só os que citam apreensão (índice CDX do archive.org)."""
    url = (f'https://web.archive.org/cdx/search/cdx?url={quote(dominio)}/*&from={ano}&to={ano}&output=json'
           f'&fl=timestamp,original&filter=statuscode:200&filter=mimetype:text/html'
           f'&filter=original:{quote(FILTRO_URL)}&collapse=urlkey&limit={limite}')
    dados = json.loads(baixar(url, 60) or '[]')
    return [(ts, orig) for ts, orig in dados[1:] if not LISTAGEM.search(orig)]


def meta(pagina, *nomes):
    for nome in nomes:
        m = re.search(r'<meta[^>]+(?:property|name|itemprop)=["\']' + re.escape(nome) + r'["\'][^>]*content=["\']([^"\']+)', pagina, re.I) \
            or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name|itemprop)=["\']' + re.escape(nome) + r'["\']', pagina, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ''


def data_da_materia(pagina, original, ts):
    """Data de publicação: metadado da página, data no endereço (/2012/05/14/) ou a captura."""
    for valor in (meta(pagina, 'article:published_time', 'datePublished', 'pubdate', 'date', 'DC.date.issued'),
                  (re.search(r'"datePublished"\s*:\s*"([^"]+)"', pagina) or [None, ''])[1]):
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?', valor or '')
        if m:
            return f'{m[1]}-{m[2]}-{m[3]}T{m[4] or "12"}:{m[5] or "00"}:00+00:00'
    m = re.search(r'/(20\d{2}|19\d{2})/(\d{1,2})/(\d{1,2})/', original)
    if m:
        return f'{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}T12:00:00+00:00'
    return f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:00+00:00'


def ler_captura(nome, dominio, uf, ts, original, ano):
    pagina = baixar(f'https://web.archive.org/web/{ts}id_/{original}')
    titulo = meta(pagina, 'og:title', 'twitter:title') or html.unescape(
        re.sub(r'\s+', ' ', (re.search(r'<title[^>]*>(.*?)</title>', pagina, re.S | re.I) or [None, ''])[1])).strip()
    titulo = re.split(r'\s+[|–-]\s+(?=[^|–-]{2,40}$)', titulo)[0].strip()
    if not titulo or not relevante(titulo):
        return None
    quando = data_da_materia(pagina, original, ts)
    if not quando.startswith(str(ano)):
        return None  # captura de outro ano (matéria antiga ou nova) fica para o ano certo
    foto = meta(pagina, 'og:image', 'twitter:image')
    if foto.startswith('//'):
        foto = 'https:' + foto
    arquivada = f'https://web.archive.org/web/{ts}/{original}'
    return {
        'titulo': titulo[:300],
        'url': arquivada,
        'url_original': arquivada,
        'url_original_status': 'wayback',
        'url_site_original': original,
        'fonte': nome,
        'dominio_fonte': dominio,
        'data_publicacao': quando,
        'data_iso': quando,
        'descricao': meta(pagina, 'og:description', 'description')[:800],
        'imagem_url': f'https://web.archive.org/web/{ts}im_/{foto}' if foto.startswith('http') else '',
        'imagem_status': 'wayback' if foto else '',
        'uf': uf,
        'uf_fonte': uf,
        'origem_coleta': 'wayback',
        'leitura_fonte_status': 'pendente_leitura_original',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ano', type=int, required=True)
    ap.add_argument('--tempo-max', type=int, default=6000, help='segundos de coleta nesta execução')
    ap.add_argument('--por-dominio', type=int, default=150, help='endereços arquivados por site e ano')
    ap.add_argument('--max-sites', type=int, default=250, help='sites por ano: oficiais e os veículos que mais publicam')
    args = ap.parse_args()
    # Um cursor por ano (os anos rodam em paralelo, cada um num servidor): wayback_cursor_AAAA.json.
    CURSOR = RAIZ / f'wayback_cursor_{args.ano}.json'
    if CURSOR.exists():
        cursor = json.loads(CURSOR.read_text(encoding='utf-8'))
    else:
        antigo = json.loads(CURSOR_ANTIGO.read_text(encoding='utf-8')) if CURSOR_ANTIGO.exists() else {}
        cursor = {k: v for k, v in antigo.items() if k.startswith(str(args.ano))}
    sites = lista_sites()[:args.max_sites]
    por_dominio = {d: (n, d, u) for n, d, u in sites}
    ano = str(args.ano)
    k = int(cursor.get(ano, 0))
    adiados = cursor.setdefault(f'{ano}_adiados', [])  # índice indisponível na primeira tentativa
    segunda = cursor.get(f'{ano}_segunda')  # depois da lista inteira, os adiados de novo (uma vez)
    inicio = time.time()
    resultados, consultados = [], 0
    while time.time() - inicio < args.tempo_max:
        if k < len(sites):
            site, fase = sites[k], 'principal'
            k += 1
        else:
            if segunda is None:
                segunda, adiados[:] = list(adiados), []
            if not segunda:
                break
            site, fase = por_dominio.get(segunda.pop(0)), 'segunda'
            if not site:
                continue
        nome, dominio, uf = site
        consultados += 1
        # O índice do archive.org limita a velocidade (erro 429/503 ou conexão recusada): tenta de novo
        # com espera crescente; se ainda falhar, o site vai para o fim da fila do ano (não se perde).
        lista, erro = None, None
        for espera in (0, 20, 60, 180):
            time.sleep(espera)
            try:
                lista = capturas(dominio, args.ano, args.por_dominio)
                break
            except Exception as e:
                erro = e
        if lista is None:
            print(f'{dominio}: índice indisponível ({type(erro).__name__}: {str(erro)[:60]})'
                  f'{"; volta no fim do ano" if fase == "principal" else "; desistiu"}', flush=True)
            if fase == 'principal' and dominio not in adiados:
                adiados.append(dominio)
            continue
        itens, cortado = [], False
        for ts, original in lista:
            if time.time() - inicio > args.tempo_max:
                cortado = True
                break
            try:
                item = ler_captura(nome, dominio, uf, ts, original, args.ano)
            except Exception:
                item = None
            if item:
                itens.append(item)
            time.sleep(1)
        if cortado:  # site não terminou: a próxima execução recomeça nele
            if fase == 'principal':
                k -= 1
            else:
                segunda.insert(0, dominio)
        if lista:
            print(f'{dominio}: {len(lista)} endereços arquivados, {len(itens)} notícias de apreensão de {args.ano}', flush=True)
        resultados.append(({'nome': f'Wayback {dominio}'}, itens, None))
        time.sleep(4)  # respeita o limite do índice do archive.org
    cursor[ano] = k
    if segunda is not None:
        cursor[f'{ano}_segunda'] = segunda
    cursor[f'{ano}_fim'] = k >= len(sites) and segunda is not None and not segunda
    CURSOR.write_text(json.dumps(cursor, ensure_ascii=False, indent=1), encoding='utf-8')
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    novas, completadas, _ = incorporar(noticias, resultados)
    if novas or completadas:
        if isinstance(dados, dict):
            dados['total'] = len(noticias)
            dados['atualizado_em'] = datetime.now(timezone.utc).isoformat()
        ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Wayback {args.ano}: {consultados} sites consultados (até {k}/{len(sites)}); novas: {novas}; completadas: {completadas}')


if __name__ == '__main__':
    main()
