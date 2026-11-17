#!/usr/bin/env python3
"""Diagnóstico (manual): as fotos do site carregam fora do site de origem (sem Referer, como o navegador do leitor)?"""
import json, random, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
feed = json.load(open('feed-recente.json'))['noticias']
imgs = [n['img'] for n in feed if n.get('img')]
random.seed(1)
amostra = random.sample(imgs, min(N, len(imgs)))

def testar(u):
    try:
        with urlopen(Request(u, headers={'User-Agent': UA, 'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8'}), timeout=15) as r:
            tipo = r.headers.get('Content-Type', '')
            corpo = r.read(2048)
            ok = tipo.startswith('image/') and len(corpo) > 500
            return u, ('ok' if ok else f'nao_imagem:{tipo[:30]}')
    except Exception as e:
        return u, f'{type(e).__name__}:{getattr(e, "code", "")}'

with ThreadPoolExecutor(16) as p:
    res = list(p.map(testar, amostra))
c = Counter(s for _, s in res)
print(f'Amostra: {len(res)} fotos das notícias dos últimos 31 dias')
print('Resultado:', c.most_common())
falhas = Counter(urlsplit(u).hostname for u, s in res if s != 'ok')
print('Domínios com falha:', falhas.most_common(20))
print('http sem https entre as falhas:', sum(1 for u, s in res if s != 'ok' and u.startswith('http:')))
