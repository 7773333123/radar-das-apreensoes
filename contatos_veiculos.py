#!/usr/bin/env python3
"""Lista os e-mails de contato publicados pelos próprios veículos (para pedidos de parceria).

Lê a página inicial e as páginas usuais de contato/expediente de cada domínio e
extrai os e-mails que aparecem nelas. Só mostra (não grava nem envia nada).
Uso: python contatos_veiculos.py dominio1 dominio2 ...
"""
import html
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

CAMINHOS = ['/', '/contato', '/contato/', '/fale-conosco', '/fale-conosco/', '/expediente', '/expediente/',
            '/quem-somos', '/quem-somos/', '/sobre', '/anuncie', '/redacao']
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
IGNORAR = re.compile(r'\.(?:png|jpe?g|gif|webp|svg)$|sentry|wixpress|example\.|exemplo|seuemail|email@|@2x|domain\.com', re.I)
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36'}


def emails(dominio):
    achados = {}
    for base in (f'https://{dominio}', f'https://www.{dominio}'):
        for c in CAMINHOS:
            try:
                with urlopen(Request(base + c, headers=HEADERS), timeout=12) as r:
                    texto = html.unescape(r.read(800_000).decode('utf-8', 'replace'))
            except Exception:
                continue
            texto = texto.replace('[at]', '@').replace('(at)', '@')
            for e in EMAIL.findall(texto):
                e = e.lower().strip('.')
                if not IGNORAR.search(e):
                    achados.setdefault(e, c)
        if achados:
            break
    return dominio, achados


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=8) as pool:
        for dominio, achados in pool.map(emails, sys.argv[1:]):
            lista = ', '.join(f'{e} ({p})' for e, p in sorted(achados.items(), key=lambda x: ('redac' not in x[0], x[0])))
            print(f'{dominio}: {lista or "nenhum e-mail publicado encontrado"}', flush=True)
