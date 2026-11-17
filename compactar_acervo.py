#!/usr/bin/env python3
"""Compacta noticias.json para o acervo de 20 anos caber no repositório.

- grava sem indentação (cerca de 10% menor);
- remove url_google_noticias quando é igual a url (~7 MB de links repetidos).
Só saem notícias de veículos com conteúdo pago (pagos.py). O GitHub recusa arquivos acima de 100 MB; o script
avisa a partir de 80 MB.
"""
import json
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent / 'noticias.json'


def main():
    antes = ARQUIVO.stat().st_size
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    # Veículos com conteúdo pago saem do acervo (decisão do responsável; pagos.py).
    from pagos import pago
    pagas = [n for n in noticias if isinstance(n, dict) and pago(n)]
    if pagas:
        noticias[:] = [n for n in noticias if not (isinstance(n, dict) and pago(n))]
        if isinstance(dados, dict):
            dados['total'] = len(noticias)
        print(f'Notícias de veículos pagos removidas do acervo: {len(pagas)}')
    for n in noticias:
        if isinstance(n, dict) and n.get('url_google_noticias') and n.get('url_google_noticias') == n.get('url'):
            del n['url_google_noticias']
    tmp = ARQUIVO.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(ARQUIVO)
    depois = ARQUIVO.stat().st_size
    print(f'noticias.json: {len(noticias)} notícias; {antes / 1e6:.1f} MB -> {depois / 1e6:.1f} MB')
    if depois > 80e6:
        print('AVISO: acervo acima de 80 MB; o GitHub recusa arquivos acima de 100 MB. '
              'Será preciso dividir noticias.json por ano.')


if __name__ == '__main__':
    main()
