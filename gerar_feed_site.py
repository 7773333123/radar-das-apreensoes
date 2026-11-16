#!/usr/bin/env python3
"""Gera feed.json: versão enxuta de noticias.json usada pelo site.

noticias.json guarda todo o histórico de coleta (dezenas de MB, com
evidências de classificação, URLs do Google Notícias etc.). O navegador
só precisa de poucos campos por notícia; baixar o arquivo completo fazia
a página ficar presa em "CARREGANDO NOTÍCIAS...".
"""
import json
from pathlib import Path

ORIGEM = Path('noticias.json')
DESTINO = Path('feed.json')
# Links do Google Notícias têm ~400 caracteres cada e só são necessários
# quando o leitor abre uma notícia; ficam num arquivo à parte, carregado sob demanda.
LINKS = Path('feed_links.json')
CAMPOS = ('titulo', 'fonte', 'uf', 'descricao', 'resumo', 'imagem_url', 'status_revisao')


def enxugar(n):
    item = {k: n[k] for k in CAMPOS if n.get(k)}
    data = n.get('data_iso') or n.get('data_publicacao')
    if data:
        # O site só exibe a data (sem hora), mas mantém a hora para ordenar.
        item['data_iso'] = data
    url = n.get('url_original') or n.get('url') or n.get('url_google_noticias') or ''
    if url and 'news.google.com' not in url:
        item['url'] = url
    cats = [c for c in (n.get('categorias_identificadas') or []) if c != 'Não classificada']
    if cats:
        item['categorias_identificadas'] = cats
    return item


def main():
    dados = json.loads(ORIGEM.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    saida = {
        'atualizado_em': dados.get('atualizado_em') if isinstance(dados, dict) else None,
        'total': len(noticias),
        'noticias': [enxugar(n) for n in noticias],
    }
    links = [n.get('url_original') or n.get('url') or n.get('url_google_noticias') or '' for n in noticias]
    links = [u if 'news.google.com' in u else '' for u in links]
    DESTINO.write_text(json.dumps(saida, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    LINKS.write_text(json.dumps(links, separators=(',', ':')), encoding='utf-8')
    print(f'{DESTINO}: {len(noticias)} notícias, {DESTINO.stat().st_size / 1e6:.1f} MB')
    print(f'{LINKS}: {LINKS.stat().st_size / 1e6:.1f} MB (carregado só ao abrir uma notícia)')


if __name__ == '__main__':
    main()
