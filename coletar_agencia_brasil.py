#!/usr/bin/env python3
"""Acervo histórico pela Agência Brasil (EBC): páginas de assunto (tags), da mais nova para a mais antiga.

A Agência Brasil publica sob licença Creative Commons (atribuição), guarda notícias desde
os anos 2000 e cobre apreensões em todo o país. Cada execução avança algumas páginas por
assunto e guarda onde parou em agencia_cursor.json; quando um assunto acaba, recomeça
do início (pega o que foi publicado depois).

  python coletar_agencia_brasil.py --paginas 25
"""
import argparse
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from coletar_fontes_diretas import KEY, OBJECT, BAD, Anchors, published

RAIZ = Path(__file__).resolve().parent
ACERVO = RAIZ / 'noticias.json'
CURSOR = RAIZ / 'agencia_cursor.json'
BASE = 'https://agenciabrasil.ebc.com.br'
ASSUNTOS = ['apreensao', 'trafico-de-drogas', 'contrabando', 'drogas', 'cocaina', 'maconha', 'armas', 'policia-federal',
            'policia-rodoviaria-federal', 'receita-federal', 'trafico', 'narcotrafico', 'crack', 'crime-organizado',
            'fronteira', 'policia-civil', 'policia-militar', 'operacao-policial', 'armas-de-fogo', 'fuzis', 'municao',
            'cigarros', 'descaminho', 'lavagem-de-dinheiro', 'pcc', 'comando-vermelho', 'milicia', 'garimpo-ilegal',
            'trafico-de-animais', 'desmatamento', 'ibama', 'seguranca-publica', 'violencia', 'pf', 'prf']
NOTICIA = re.compile(r'^/[a-z-]+/noticia/(\d{4})-(\d{2})/[a-z0-9-]+$')
UA = {'User-Agent': 'Mozilla/5.0 (compatible; RadarApreensoes/1.0; pesquisa publica)'}


def get(url, timeout=20):
    with urlopen(Request(url, headers=UA), timeout=timeout) as r:
        return r.read(1_500_000).decode('utf-8', 'replace')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--paginas', type=int, default=25, help='páginas por assunto nesta execução')
    args = ap.parse_args()
    dados = json.loads(ACERVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    conhecidas = {n.get('url_original') or n.get('url') for n in noticias if isinstance(n, dict)}
    cursor = json.loads(CURSOR.read_text(encoding='utf-8')) if CURSOR.exists() else {}
    novas, anos = [], {}
    for assunto in ASSUNTOS:
        pagina = int(cursor.get(assunto, 0))
        anterior = None
        for _ in range(args.paginas):
            url = f'{BASE}/tags/{assunto}' + (f'?page={pagina}' if pagina else '')
            try:
                html_pag = get(url)
            except Exception as exc:
                print(f'{assunto} p{pagina}: {type(exc).__name__}')
                break
            p = Anchors()
            p.feed(html_pag)
            links = []
            for href, titulo in p.links:
                alvo = urljoin(BASE, html.unescape(href)).split('#')[0].split('?')[0]
                caminho = alvo.replace(BASE, '')
                if NOTICIA.match(caminho) and len(titulo) > 25:
                    links.append((alvo, titulo))
            chave = tuple(sorted(a for a, _ in links))
            if not links or chave == anterior:  # fim do assunto (ou paginação repetida)
                print(f'{assunto}: fim na página {pagina}; recomeça do início na próxima volta')
                pagina = 0
                break
            anterior = chave
            for alvo, titulo in links:
                if alvo in conhecidas or not (KEY.search(titulo) and OBJECT.search(titulo)) or BAD.search(titulo):
                    continue
                conhecidas.add(alvo)
                m = NOTICIA.match(alvo.replace(BASE, ''))
                novas.append((alvo, titulo, f'{m.group(1)}-{m.group(2)}'))
            pagina += 1
            time.sleep(0.4)
        cursor[assunto] = pagina
    for alvo, titulo, mes in novas:
        try:
            data = published(get(alvo))
        except Exception:
            data = ''
        data = data or f'{mes}-01T12:00:00+00:00'
        anos[data[:4]] = anos.get(data[:4], 0) + 1
        noticias.append({
            'titulo': titulo, 'url': alvo, 'url_original': alvo, 'url_original_status': 'fonte_direta',
            'fonte': 'Agência Brasil', 'dominio_fonte': 'agenciabrasil.ebc.com.br', 'origem_coleta': 'agencia_brasil',
            'data_iso': data, 'data_publicacao': data, 'leitura_fonte_status': 'pendente_leitura_original',
        })
        time.sleep(0.25)
    if novas:
        if isinstance(dados, dict):
            dados['noticias'] = noticias
            dados['total'] = len(noticias)
        tmp = ACERVO.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        tmp.replace(ACERVO)
    CURSOR.write_text(json.dumps(cursor, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'Agência Brasil: {len(novas)} notícias novas; por ano: {dict(sorted(anos.items()))}; cursor: {cursor}')


if __name__ == '__main__':
    main()
