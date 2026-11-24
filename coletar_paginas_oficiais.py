#!/usr/bin/env python3
"""Portais oficiais SEM feed (24/11/2026): lê a página de notícias do órgão e traz as matérias de apreensão.

Por quê: as fotos que jornais regionais carimbam com marca d'água costumam ser a foto que a própria
polícia divulgou. Com a nota oficial no acervo, a notícia ganha a foto limpa (e a fonte primária).
Pernambuco era o caso: o feed da PM-PE parou em abril/2026 e a SDS-PE não tem feed, mas as páginas
iniciais trazem as notícias.

Para cada página da lista: links do próprio domínio cujo texto fala de apreensão (ASSUNTO, o mesmo filtro
dos feeds), ainda não no acervo -> lê a matéria (ler_materias.ler) para a data, a foto e o texto oficial.
Sem data na página ou com mais de 10 dias: fica de fora (não entra notícia antiga com data de hoje).

  python coletar_paginas_oficiais.py
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from coletar_feeds_estaduais import ARQUIVO, ASSUNTO, baixar, incorporar, texto_limpo
from ler_materias import ler

RAIZ = Path(__file__).resolve().parent
PAGINAS = [
    {'nome': 'Polícia Militar (PE)', 'uf': 'PE', 'url': 'https://www.pm.pe.gov.br/'},
    {'nome': 'Secretaria de Defesa Social (PE)', 'uf': 'PE', 'url': 'https://www.sds.pe.gov.br/'},
]
DIAS = 10


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self._href, self._texto = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self._href, self._texto = dict(attrs).get('href'), []
        elif tag == 'img' and self._href is not None:
            self._texto.append(dict(attrs).get('alt') or '')

    def handle_data(self, data):
        if self._href is not None:
            self._texto.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self._href:
            texto = ' '.join(' '.join(self._texto).split())
            if texto:
                self.links.append((self._href, texto))
            self._href = None


def links_da_pagina(pagina):
    base = pagina['url']
    dominio = urlsplit(base).hostname.removeprefix('www.')
    p = Links()
    p.feed(baixar(base).decode('utf-8', 'replace'))
    vistos = {}
    for href, texto in p.links:
        url = urljoin(base, href).split('#')[0]
        host = (urlsplit(url).hostname or '').removeprefix('www.')
        if host != dominio or url.rstrip('/') == base.rstrip('/') or len(texto) < 25:
            continue
        if ASSUNTO.search(texto):
            vistos.setdefault(url, texto_limpo(texto))
    return list(vistos.items())


def main():
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    conhecidas = {n.get('url_original') or n.get('url') for n in noticias if isinstance(n, dict)}
    limite = datetime.now(timezone.utc) - timedelta(days=DIAS)
    resultados = []
    for pagina in PAGINAS:
        try:
            candidatos = [(u, t) for u, t in links_da_pagina(pagina) if u not in conhecidas]
        except Exception as erro:  # portal fora do ar não para a coleta
            resultados.append((pagina, [], erro))
            continue

        def materia(par):
            url, titulo = par
            try:
                return url, titulo, ler(url, 15)
            except Exception:
                return url, titulo, None
        itens = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            for url, titulo, r in pool.map(materia, candidatos[:30]):
                if not r or not r.get('publicada'):
                    continue
                quando = datetime.fromisoformat(r['publicada'])
                if quando < limite:
                    continue
                item = {
                    'titulo': titulo, 'url': url, 'url_original': url, 'url_original_status': 'pagina_oficial',
                    'fonte': pagina['nome'], 'dominio_fonte': urlsplit(url).hostname.removeprefix('www.'),
                    'data_publicacao': r['publicada'], 'data_iso': quando.isoformat(),
                    'descricao': r.get('resumo', '')[:800], 'imagem_url': r.get('imagem', ''),
                    'imagem_status': 'pagina_oficial', 'imagens': r.get('imagens', []),
                    'uf': pagina['uf'], 'uf_fonte': pagina['uf'], 'origem_coleta': 'pagina_oficial',
                    'leitura_fonte_status': 'lida', 'data_conferida': 'confirmada_pela_pagina',
                }
                for campo, chave in (('trecho', 'trecho'), ('fatos', 'fatos'), ('texto_integral', 'texto'),
                                     ('licenca_texto', 'licenca'), ('tamanho_texto', 'tamanho_texto')):
                    if r.get(chave):
                        item[campo] = r[chave]
                itens.append(item)
        print(f'{pagina["nome"]}: {len(candidatos)} links de apreensão novos; {len(itens)} dos últimos {DIAS} dias', flush=True)
        resultados.append((pagina, itens, None))
    novas, completadas, falhas = incorporar(noticias, resultados)
    if novas or completadas:
        if isinstance(dados, dict):
            dados['noticias'] = noticias
            dados['total'] = len(noticias)
        tmp = ARQUIVO.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        tmp.replace(ARQUIVO)
    print(f'Páginas oficiais sem feed: {len(PAGINAS)} ({falhas} com falha); novas: {novas}; completadas: {completadas}')


def diagnostico():
    """Mostra o que cada portal devolve (links, filtro de assunto, data e foto da matéria). Não grava."""
    for pagina in PAGINAS:
        print('=' * 70, pagina['url'], flush=True)
        try:
            html = baixar(pagina['url']).decode('utf-8', 'replace')
        except Exception as erro:
            print('  ERRO ao baixar:', repr(erro)[:300])
            continue
        p = Links()
        p.feed(html)
        print(f'  bytes {len(html)}; links {len(p.links)}; de apreensão: {len(links_da_pagina(pagina))}')
        for href, texto in p.links[:60]:
            if len(texto) >= 25:
                print('   ', 'A' if ASSUNTO.search(texto) else '-', urljoin(pagina['url'], href)[:90], '|', texto[:80])
        for url, titulo in links_da_pagina(pagina)[:5]:
            try:
                r = ler(url, 15) or {}
                print('  LER', url[:80], '| publicada', r.get('publicada'), '| imagem', bool(r.get('imagem')))
            except Exception as erro:
                print('  LER ERRO', url[:80], repr(erro)[:200])


if __name__ == '__main__':
    import sys
    diagnostico() if '--diagnostico' in sys.argv else main()
