#!/usr/bin/env python3
"""Confere com urllib.robotparser (regras Allow/Disallow completas) se o robots.txt permite ao Radar
ler a matéria de exemplo e o RSS de cada site em robots_conferir.json."""
import json
from urllib.robotparser import RobotFileParser
from urllib.request import Request, urlopen

UA = 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://www.radardasapreensoes.com.br)'
for c in json.load(open('robots_conferir.json')):
    d = c['dominio']
    rp = RobotFileParser()
    try:
        with urlopen(Request(f'https://{d}/robots.txt', headers={'User-Agent': UA}), timeout=10) as r:
            linhas = r.read(300_000).decode('utf-8', 'replace').splitlines()
        rp.parse(linhas)
    except Exception as e:
        print(f'{d:34} robots inacessível ({type(e).__name__}) -> permitido')
        continue
    materia = c.get('exemplo') or f'https://{d}/'
    ok_m = rp.can_fetch('RadarDasApreensoes', materia)
    ok_f = rp.can_fetch('RadarDasApreensoes', f'https://{d}/feed/')
    regra = [l for l in linhas if l.strip().lower().startswith(('user-agent', 'disallow: /'))][:6]
    print(f"{d:34} materia={'permitida' if ok_m else 'PROIBIDA'} rss={'permitido' if ok_f else 'PROIBIDO'} | {' ; '.join(x.strip() for x in regra)[:150]}")
