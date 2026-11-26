#!/usr/bin/env python3
"""Vídeo oficial do YouTube ligado à notícia do mesmo fato (gerar_feed_site._video_do_canal), 26/11/2026."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gerar_feed_site import _video_do_canal, _palavras_video

def video(t, d):
    return {'yt': 'abcdefghijk', 't': t, 'd': d, 'orgao': 'PRF', '_p': _palavras_video(t), '_n': set()}

v = video('PRF | Da fiscalização na rodovia à desarticulação de uma fábrica de fuzis', '2026-11-25T20:14:00')
item = {'t': 'Polícia de SP fecha fábrica clandestina de peças para fuzis durante ação contra tráfico de armas',
        'd': '2026-11-25T15:03'}
outra = 'Ação conjunta com participação da PRF desarticula esquema de fabricação e envio de fuzis para Santa Catarina'
casos = [
    (_video_do_canal(item, [v], [outra]) is not None, 'fuzis: outra versão da mesma notícia liga o vídeo'),
    (_video_do_canal(item, [v]) is None, 'só o título exibido não basta (2 palavras)'),
    (_video_do_canal({'t': 'PM apreende maconha em fábrica abandonada de Londrina', 'd': '2026-11-25T10:00'}, [v]) is None,
     'outro fato não liga'),
    (_video_do_canal(dict(item, d='2026-11-20T10:00'), [v], [outra]) is None, 'mais de 2 dias de distância não liga'),
]
# Instagram oficial (26/11/2026): o vídeo liga do mesmo jeito e vai em 'ig' (reel/CODIGO), com o @ no crédito.
ig = dict(video('A Polícia Federal deflagrou a Operação Narcisus contra tráfico de drogas em Aracaju', '2026-11-25T17:04:00'),
          yt='', ig='reel/DgLBZ4BBthx', orgao='Polícia Federal (@pfsergipe)')
ig['uf'] = 'SE'
r = _video_do_canal({'t': 'PF deflagra Operação Narcisus contra tráfico de drogas em Aracaju', 'd': '2026-11-25T09:00', 'uf': 'SE'}, [ig])
casos.append((r == {'ig': ['reel/DgLBZ4BBthx'], 'vf': 'Polícia Federal (@pfsergipe)'}, 'Instagram: liga e usa a chave ig'))
# Conta estadual não liga notícia de outro estado (vídeo da PF/MA ligava a notícia de SP e do Acre).
ma = dict(video('A Polícia Federal realizou a incineração de aproximadamente 1,25 tonelada de drogas apreendidas', '2026-11-23T14:17:00'),
          yt='', ig='reel/DgFkv16R4Xg', orgao='Polícia Federal (@pf.maranhao)', uf='MA')
casos.append((_video_do_canal({'t': 'PM Rodoviária apreende mais de 1,2 tonelada de drogas entre carga de móveis', 'd': '2026-11-24T12:00',
                               'uf': 'SP'}, [ma]) is None, 'Instagram: conta do MA não liga notícia de SP'))
erros = [m for ok, m in casos if not ok]
for m in erros:
    print('FALHOU:', m)
print(f'{len(casos) - len(erros)}/{len(casos)} casos corretos')
sys.exit(1 if erros else 0)
