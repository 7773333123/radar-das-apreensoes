#!/usr/bin/env python3
"""Coleta notícias de apreensões direto dos feeds RSS dos veículos (feeds_estaduais.json).

Diferente do Google Notícias, cada item desses feeds já traz:
  - o link original da matéria;
  - a fotografia publicada pela fonte;
  - o estado (feed regional).

Também "completa" notícias antigas do acervo que vieram pelo Google Notícias:
quando o título coincide, a notícia recebe o link original, a foto e a UF,
sem criar duplicata.

Uso: python coletar_feeds_estaduais.py
"""
from pagos import pago
import email.utils
import html
import json
import re
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQUIVO = PASTA / 'noticias.json'
FEEDS = PASTA / 'feeds_estaduais.json'
DESCOBERTOS = PASTA / 'feeds_descobertos.json'  # gerado por descobrir_feeds.py
SAUDE = PASTA / 'feeds_saude.json'  # falhas seguidas de cada feed (desliga os que morreram)
FALHAS_PARA_DESLIGAR = 12           # ~4 h de falha seguida na coleta rápida
NOVA_TENTATIVA_HORAS = 24           # feed desligado é testado de novo uma vez por dia
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://radar-das-apreensoes.vercel.app)'}
MEDIA = '{http://search.yahoo.com/mrss/}'
ATOM = '{http://www.w3.org/2005/Atom}'
# O título ou o subtítulo precisa tratar de apreensão, tráfico ou contrabando.
ASSUNTO = re.compile(
    r'apreen|apreend|tr[aá]fico de (?:drogas|armas|animais)|traficante|contrabando|descaminho|'
    r'lavagem de dinheiro|(?:preso|presa|presos|flagrad[oa]s?) com .{0,40}?'
    r'(?:drogas?|coca[ií]na|maconha|crack|haxixe|skunk|armas?|fuzil|fuzis|muni[çc][õo]es|pistolas?|rev[óo]lver)|'
    r'(?:toneladas?|quilos?|kg) de (?:drogas?|coca[ií]na|maconha|skunk|haxixe)|'
    r'madeira ilegal|garimpo ilegal|animais silvestres|cigarros contrabandeados',
    re.I)


def normalizar_titulo(t):
    t = unicodedata.normalize('NFKD', t or '')
    t = ''.join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r'\s+-\s+(g1|globo)\s*$', '', t)
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()


def baixar(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout) as r:
        return r.read()


def texto_limpo(fragmento):
    sem_tags = re.sub(r'<[^>]+>', ' ', fragmento or '')
    return re.sub(r'\s+', ' ', html.unescape(sem_tags)).strip()


def imagem_do_item(item):
    for tag in (MEDIA + 'content', MEDIA + 'thumbnail'):
        for el in item.iter(tag):
            url = el.get('url') or ''
            if url.startswith('http') and el.get('medium', 'image') == 'image':
                return url
    enc = item.find('enclosure')
    if enc is not None and (enc.get('type') or '').startswith('image') and enc.get('url'):
        return enc.get('url')
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', _filho(item, 'description', 'content', 'encoded'))
    return html.unescape(m.group(1)) if m else ''


def data_iso(valor):
    valor = (valor or '').strip()
    try:
        return email.utils.parsedate_to_datetime(valor).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:  # RSS 1.0 (dc:date) e Atom usam ISO 8601
        return datetime.fromisoformat(valor.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
    except ValueError:
        return ''


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _filho(item, *nomes):
    """Texto do primeiro filho com um dos nomes, ignorando o namespace."""
    for el in item:
        if _local(el.tag) in nomes:
            if _local(el.tag) == 'link' and el.get('href'):
                if el.get('rel', 'alternate') == 'alternate':
                    return el.get('href')
                continue
            return el.text or ''
    return ''


def ler_feed(feed):
    """Lê RSS 2.0, RSS 1.0 (RDF, usado pelo gov.br) e Atom."""
    raiz = ET.fromstring(baixar(feed['url']))
    itens = [el for el in raiz.iter() if _local(el.tag) in ('item', 'entry')]
    for item in itens:
        titulo = texto_limpo(_filho(item, 'title'))
        link = (_filho(item, 'link') or item.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about') or '').strip()
        resumo = texto_limpo(_filho(item, 'subtitle', 'summary'))
        corpo = texto_limpo(_filho(item, 'description', 'content', 'encoded'))
        if not titulo or not link.startswith('http'):
            continue
        if not ASSUNTO.search(titulo + ' ' + (resumo or corpo[:300])):
            continue
        quando = _filho(item, 'pubDate', 'date', 'published', 'updated')
        yield {
            'titulo': titulo,
            'url': link,
            'url_original': link,
            'url_original_status': 'feed_da_fonte',
            'fonte': feed.get('fonte') or feed['nome'],
            'dominio_fonte': re.sub(r'^https?://(www\.)?', '', link).split('/')[0],
            'data_publicacao': quando,
            'data_iso': data_iso(quando),
            'descricao': (resumo or corpo)[:800],
            'imagem_url': imagem_do_item(item),
            'imagem_status': 'feed_da_fonte',
            'uf': feed.get('uf') or '',
            'uf_fonte': feed.get('uf') or '',
            'origem_coleta': 'feed_rss_fonte',
            'leitura_fonte_status': 'pendente_leitura_original',
        }


# Agregadores que só republicam matérias de outros veículos: fica a versão original.
AGREGADORES = re.compile(r'(?:^|\.)(?:msn\.com|dailymotion\.com|yahoo\.com|flipboard\.com|newsbreak\.com|ground\.news|'
                         r'squid\.app|newsnow\.co\.uk|inoreader\.com|feedly\.com)$', re.I)


def agregador(url_ou_dominio):
    dominio = re.sub(r'^https?://', '', str(url_ou_dominio or '')).split('/')[0].lower()
    return bool(AGREGADORES.search(dominio))


def incorporar(noticias, resultados):
    """Acrescenta ao acervo os itens novos de cada (fonte, itens, erro); completa os já existentes.

    Usado pelos feeds dos veículos e pelos buscadores (buscadores.py).
    """
    por_url = {n.get('url_original') or n.get('url'): n for n in noticias if isinstance(n, dict)}
    por_titulo = {}
    for n in noticias:
        if isinstance(n, dict):
            por_titulo.setdefault(normalizar_titulo(n.get('titulo')), n)
    novas = completadas = falhas = 0
    for feed, itens, erro in resultados:
        if erro is not None:
            falhas += 1
            print(f'Falha em {feed["nome"]}: {type(erro).__name__}: {str(erro)[:120]}', flush=True)
            continue
        if itens:
            print(f'{feed["nome"]}: {len(itens)} notícias sobre apreensões', flush=True)
        for item in itens:
            if pago(item):  # veículo com conteúdo pago (pagos.py)
                continue
            if agregador(item['url']):
                continue
            if item['url'] in por_url:
                continue
            existente = por_titulo.get(normalizar_titulo(item['titulo']))
            if existente is not None:
                # Mesma matéria que chegou pelo Google Notícias: completa com dados da fonte.
                if not str(existente.get('url_original') or '').startswith('http') or \
                        'news.google.com' in str(existente.get('url_original')):
                    existente.setdefault('url_google_noticias', existente.get('url'))
                    existente['url_original'] = item['url']
                    existente['url_original_status'] = 'feed_da_fonte'
                for campo in ('imagem_url', 'imagem_status', 'uf_fonte', 'descricao'):
                    if item.get(campo) and not existente.get(campo):
                        existente[campo] = item[campo]
                if item['uf']:
                    existente['uf'] = item['uf']
                por_url[item['url']] = existente
                completadas += 1
                continue
            noticias.append(item)
            por_url[item['url']] = item
            por_titulo[normalizar_titulo(item['titulo'])] = item
            novas += 1
    return novas, completadas, falhas


def main():
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    feeds = json.loads(FEEDS.read_text(encoding='utf-8'))['feeds']
    if DESCOBERTOS.exists():
        conhecidos = {f['url'] for f in feeds}
        feeds += [f for f in json.loads(DESCOBERTOS.read_text(encoding='utf-8')).get('feeds', []) if f['url'] not in conhecidos]

    # Feeds que falham há muitas rodadas seguidas ficam de fora; uma vez por dia são testados de novo.
    saude = json.loads(SAUDE.read_text(encoding='utf-8')) if SAUDE.exists() else {}
    agora = datetime.now(timezone.utc)

    def desligado(feed):
        h = saude.get(feed['url']) or {}
        if int(h.get('falhas_seguidas') or 0) < FALHAS_PARA_DESLIGAR:
            return False
        try:
            ultima = datetime.fromisoformat(h.get('ultima_tentativa', ''))
        except ValueError:
            return False
        return (agora - ultima).total_seconds() < NOVA_TENTATIVA_HORAS * 3600

    pulados = [f for f in feeds if desligado(f)]
    feeds = [f for f in feeds if not desligado(f)]

    def tentar(feed):
        try:
            return feed, list(ler_feed(feed)), None
        except Exception as exc:  # feed fora do ar não interrompe a coleta
            return feed, [], exc

    # Baixa todos os feeds em paralelo; o processamento abaixo segue a ordem da lista.
    with ThreadPoolExecutor(max_workers=16) as pool:
        resultados = list(pool.map(tentar, feeds))
    novas, completadas, falhas = incorporar(noticias, resultados)
    for feed, itens, erro in resultados:
        h = saude.setdefault(feed['url'], {'nome': feed.get('nome', '')})
        h['ultima_tentativa'] = agora.isoformat(timespec='seconds')
        if erro is None:
            h['falhas_seguidas'] = 0
            h['ultimo_ok'] = h['ultima_tentativa']
        else:
            h['falhas_seguidas'] = int(h.get('falhas_seguidas') or 0) + 1
            h['ultimo_erro'] = f'{type(erro).__name__}: {str(erro)[:80]}'
    SAUDE.write_text(json.dumps(saude, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    if pulados:
        print(f'Feeds desligados por falha seguida (testados de novo a cada {NOVA_TENTATIVA_HORAS} h): {len(pulados)}')
    if novas or completadas:
        if isinstance(dados, dict):
            dados['noticias'] = noticias
            dados['total'] = len(noticias)
            dados['atualizado_em'] = datetime.now(timezone.utc).isoformat()
        tmp = ARQUIVO.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        tmp.replace(ARQUIVO)
    print(f'Feeds: {len(feeds)} ({falhas} com falha); novas: {novas}; '
          f'notícias antigas completadas com link/foto/UF: {completadas}; acervo: {len(noticias)}')
    if feeds and falhas == len(feeds):
        raise SystemExit('Nenhum feed respondeu.')


if __name__ == '__main__':
    main()
