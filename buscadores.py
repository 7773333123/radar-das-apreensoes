#!/usr/bin/env python3
"""Buscadores alternativos ao Google Notícias: Bing Notícias e GDELT.

O Google Notícias traz ~90% das notícias e pode limitar as buscas automáticas a
qualquer momento. Estes buscadores rodam em paralelo para não depender dele:

- Bing Notícias (RSS de busca): mesmo tipo de filtro por assunto e LINK DIRETO da
  reportagem (sem a etapa de decodificar o link do Google).
- GDELT (projeto acadêmico gratuito que monitora notícias do mundo todo): link
  direto e foto; mais ruído, filtrado pelo classificador.

As consultas giram em rodízio (temas, estados e polos de fronteira) e cada item
entra com origem_coleta = 'bing_noticias' ou 'gdelt', para medir quanto cada
buscador acrescenta. Uso:
  python buscadores.py [--limite-bing 15] [--gdelt] [--teste]
"""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from classificar import relevante
from coletar_feeds_estaduais import ASSUNTO, data_iso, incorporar, texto_limpo

PASTA = Path(__file__).resolve().parent
ARQUIVO = PASTA / 'noticias.json'
ESTADO = PASTA / 'buscadores_cursor.json'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://www.radardasapreensoes.com.br)',
           'Accept': 'application/rss+xml,application/xml,application/json;q=0.9,*/*;q=0.8'}
TERMOS = '(apreensão OR apreende OR apreendido OR apreendidos OR contrabando OR "tráfico de drogas")'
TEMAS = ['apreensão maconha', 'apreensão cocaína', 'apreensão de armas fuzil', 'apreensão munições',
         'contrabando cigarros apreensão', 'PRF apreende', 'Polícia Federal apreende', 'Receita Federal apreende',
         'apreensão drogas rodovia', 'tráfico de drogas preso em flagrante', 'apreensão skunk', 'apreensão crack',
         'apreensão garimpo ilegal', 'apreensão madeira ilegal', 'apreensão medicamentos contrabandeados',
         'DOF apreende', 'Gefron apreende', 'FICCO apreende', 'Polícia Militar apreende drogas',
         'Polícia Civil apreende drogas']
ESTADOS = ['Acre', 'Alagoas', 'Amapá', 'Amazonas', 'Bahia', 'Ceará', 'Distrito Federal', 'Espírito Santo', 'Goiás',
           'Maranhão', 'Mato Grosso', 'Mato Grosso do Sul', 'Minas Gerais', 'Pará', 'Paraíba', 'Paraná', 'Pernambuco',
           'Piauí', 'Rio de Janeiro', 'Rio Grande do Norte', 'Rio Grande do Sul', 'Rondônia', 'Roraima',
           'Santa Catarina', 'São Paulo', 'Sergipe', 'Tocantins']


def baixar(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout) as r:
        return r.read()


def consultas_bing():
    lista = [f'{t}' for t in TEMAS] + [f'apreensão polícia {uf}' for uf in ESTADOS]
    try:
        polos = json.loads((PASTA / 'polos_fronteira.json').read_text(encoding='utf-8'))['polos']
        lista += ['apreensão ' + ' OR '.join(f'"{t}"' for t in p['termos'][:4]) for p in polos]
    except (OSError, ValueError, KeyError):
        pass
    return lista


def nomes_das_fontes():
    try:
        return {f['dominio']: (f.get('nome') or f['dominio'], f.get('uf', ''))
                for f in json.loads((PASTA / 'fontes.json').read_text(encoding='utf-8'))['fontes']}
    except (OSError, ValueError, KeyError):
        return {}


def dominio(url):
    return re.sub(r'^https?://(www\.)?', '', url).split('/')[0].lower()


def item(titulo, url, fonte, quando_iso, descricao, imagem, origem, fontes):
    dom = dominio(url)
    nome, uf = fontes.get(dom, (fonte or dom, ''))
    return {
        'titulo': titulo, 'url': url, 'url_original': url, 'url_original_status': origem,
        'fonte': fonte or nome, 'dominio_fonte': dom, 'data_publicacao': quando_iso, 'data_iso': quando_iso,
        'descricao': descricao[:800], 'imagem_url': imagem, 'imagem_status': origem if imagem else '',
        'uf': uf, 'uf_fonte': uf, 'origem_coleta': origem, 'leitura_fonte_status': 'pendente_leitura_original',
    }


def assunto_ok(titulo, descricao):
    return bool(ASSUNTO.search(titulo + ' ' + descricao[:300]) or relevante(titulo))


# ---------- Bing Notícias ----------
def link_direto_bing(link):
    """O Bing entrega bing.com/news/apiclick.aspx?...&url=<link da reportagem>."""
    if 'bing.com' in link:
        alvo = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query).get('url', [''])[0]
        return alvo if alvo.startswith('http') else ''
    return link


def buscar_bing(consulta, fontes):
    url = ('https://www.bing.com/news/search?' +
           urllib.parse.urlencode({'q': consulta, 'format': 'rss', 'setlang': 'pt-br', 'mkt': 'pt-BR', 'cc': 'BR',
                                   'qft': 'sortbydate="1"'}))
    raiz = ET.fromstring(baixar(url))
    saida = []
    for el in raiz.iter('item'):
        filhos = {c.tag.rsplit('}', 1)[-1].lower(): (c.text or '') for c in el}
        titulo = texto_limpo(filhos.get('title', ''))
        link = link_direto_bing(filhos.get('link', '').strip())
        descricao = texto_limpo(filhos.get('description', ''))
        if not titulo or not link or 'news.google.com' in link or not assunto_ok(titulo, descricao):
            continue
        imagem = filhos.get('image', '')
        saida.append(item(titulo, link, texto_limpo(filhos.get('source', '')), data_iso(filhos.get('pubdate', '')),
                          descricao, '' if 'bing.com/th' in imagem else imagem, 'bing_noticias', fontes))
    return saida


# ---------- GDELT ----------
def buscar_gdelt(consulta, fontes, janela='1d'):
    url = ('https://api.gdeltproject.org/api/v2/doc/doc?' +
           urllib.parse.urlencode({'query': f'{consulta} sourcecountry:BR sourcelang:por', 'mode': 'artlist',
                                   'maxrecords': 250, 'format': 'json', 'timespan': janela, 'sort': 'datedesc'}))
    texto = baixar(url, timeout=40).decode('utf-8', 'replace')
    if not texto.strip().startswith('{'):
        raise ValueError(texto[:120])  # o GDELT responde texto simples quando limita ou recusa a consulta
    saida = []
    for a in json.loads(texto).get('articles', []):
        titulo, link = texto_limpo(a.get('title', '')), a.get('url', '')
        if not titulo or not link.startswith('http') or not assunto_ok(titulo, ''):
            continue
        visto = a.get('seendate', '')  # 20261116T130000Z
        try:
            quando = datetime.strptime(visto, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            quando = ''
        saida.append(item(titulo, link, '', quando, '', a.get('socialimage', ''), 'gdelt', fontes))
    return saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite-bing', type=int, default=15, help='consultas ao Bing por execução (rodízio)')
    ap.add_argument('--gdelt', action='store_true', help='também consulta o GDELT')
    ap.add_argument('--teste', action='store_true', help='só mostra o que encontraria, sem gravar')
    args = ap.parse_args()
    fontes = nomes_das_fontes()
    cursor = json.loads(ESTADO.read_text(encoding='utf-8')) if ESTADO.exists() else {}
    lista = consultas_bing()
    inicio = cursor.get('bing', 0) % max(1, len(lista))
    escolhidas = [lista[(inicio + k) % len(lista)] for k in range(min(args.limite_bing, len(lista)))]
    resultados = []
    for consulta in escolhidas:
        try:
            resultados.append(({'nome': f'Bing: {consulta[:50]}'}, buscar_bing(consulta, fontes), None))
        except Exception as exc:
            resultados.append(({'nome': f'Bing: {consulta[:50]}'}, [], exc))
        time.sleep(1.5)
    if args.gdelt:
        # O GDELT indexa sem acento e limita a ~1 consulta a cada 5 s por IP: uma consulta ampla.
        consulta = '(apreende OR apreendeu OR apreendidos OR apreendida OR apreensao OR contrabando OR traficantes)'
        for tentativa in range(2):
            try:
                resultados.append(({'nome': 'GDELT'}, buscar_gdelt(consulta, fontes, '2d'), None))
                break
            except Exception as exc:
                if tentativa:
                    resultados.append(({'nome': 'GDELT'}, [], exc))
                time.sleep(20)
    total = sum(len(i) for _, i, _ in resultados)
    falhas = sum(1 for _, _, e in resultados if e is not None)
    print(f'Buscadores: {len(resultados)} consultas, {falhas} falhas, {total} itens sobre apreensões', flush=True)
    for fonte, itens, erro in resultados:
        if erro is not None:
            print(f'  falha em {fonte["nome"]}: {type(erro).__name__}: {str(erro)[:150]}')
        elif args.teste:
            print(f'  {fonte["nome"]}: {len(itens)}')
            for x in itens[:3]:
                print(f'     {x["data_iso"][:16]} | {x["fonte"]} | {x["titulo"][:80]} | {x["url"][:70]}')
    if args.teste:
        return
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    novas, completadas, _ = incorporar(noticias, resultados)
    if novas or completadas:
        if isinstance(dados, dict):
            dados['total'] = len(noticias)
            dados['atualizado_em'] = datetime.now(timezone.utc).isoformat()
        tmp = ARQUIVO.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        tmp.replace(ARQUIVO)
    cursor['bing'] = (inicio + len(escolhidas)) % max(1, len(lista))
    ESTADO.write_text(json.dumps(cursor), encoding='utf-8')
    print(f'Novas: {novas}; já existentes completadas (link direto, foto): {completadas}; acervo: {len(noticias)}')


if __name__ == '__main__':
    main()
