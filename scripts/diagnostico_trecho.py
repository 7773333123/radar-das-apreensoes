#!/usr/bin/env python3
"""Diagnóstico do 'O que diz a fonte': lê N matérias de imprensa e mostra o tamanho do trecho."""
import json, re, statistics, sys
sys.path.insert(0, '.')
import ler_materias as L

N = int(sys.argv[1]) if len(sys.argv) > 1 else 25
d = json.load(open('noticias.json'))
ns = d['noticias'] if isinstance(d, dict) else d
oficial = re.compile(r'\.(gov|jus|mp|leg|def)\.br$')
alvo = [n for n in sorted(ns, key=lambda n: n.get('data_iso') or '', reverse=True)
        if str(n.get('url_original', '')).startswith('http') and 'news.google' not in n['url_original']
        and not oficial.search(str(n.get('dominio_fonte') or ''))][:N]
pct = []
for n in alvo:
    try:
        r = L.ler(n['url_original'], 15)
    except Exception as e:
        print('ERRO', n['url_original'][:80], type(e).__name__); continue
    pag_paras = r.get('_paras', [])
    t, tt = r.get('trecho', ''), r.get('tamanho_texto') or 0
    if tt:
        pct.append(len(t) / tt)
    print(f"{(n.get('dominio_fonte') or '')[:30]:30} trecho {len(t):5} / texto {tt:5} = {len(t)/tt if tt else 0:4.0%}  {n['url_original'][:90]}")
    if tt and len(t) / tt < 0.6:
        print('   fim do trecho:', repr(t[-150:]))
if pct:
    print(f'\nMediana: {statistics.median(pct):.0%}  (n={len(pct)})')
