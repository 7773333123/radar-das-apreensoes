#!/usr/bin/env python3
"""Diagnóstico (manual): o que um feed entrega agora e o que a coleta faz com cada item."""
import sys
sys.path.insert(0, '.')
from coletar_feeds_estaduais import ler_feed, baixar, ASSUNTO, _local, _filho, texto_limpo
from classificar import relevante
import xml.etree.ElementTree as ET

url = sys.argv[1]
bruto = baixar(url)
raiz = ET.fromstring(bruto)
itens = [el for el in raiz.iter() if _local(el.tag) in ('item', 'entry')]
print(f'Feed: {url} | {len(bruto)} bytes | {len(itens)} itens')
for it in itens:
    t = texto_limpo(_filho(it, 'title'))
    d = _filho(it, 'pubDate', 'date', 'published', 'updated')
    resumo = texto_limpo(_filho(it, 'subtitle', 'summary')) or texto_limpo(_filho(it, 'description', 'content', 'encoded'))[:300]
    print(f"{'COLETA' if ASSUNTO.search(t + ' ' + resumo) else '  fora'} relevante={'s' if relevante(t) else 'n'} {d[:25]:25} | {t[:110]}")
