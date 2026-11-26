#!/usr/bin/env python3
"""Regra do dono (26/11/2026): "semelhante a maconha", "análogo a maconha" contam como MACONHA (idem outras drogas)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from resumo_fatos import extrair
from estatisticas import quantidades

casos = [
    ('Receita Federal retém mais de 830 kg de substância análoga à maconha durante abordagem', {'mac': 830.0}),
    ('PRF apreende 50 kg de material semelhante a maconha', {'mac': 50.0}),
    ('PM apreende 40 kg de produto análogo a maconha', {'mac': 40.0}),
    ('PRF apreende 1 tonelada de droga similar à maconha', {'mac': 1000.0}),
    ('PC prende homem com cerca de 2,5 quilos de droga análoga à cocaína', {'coc': 2.5}),
]
erros = [(t, quantidades(extrair(t, ''))) for t, esp in casos if quantidades(extrair(t, '')) != esp]
for t, q in erros:
    print('FALHOU:', t, q)
print(f'{len(casos) - len(erros)}/{len(casos)} casos corretos')
sys.exit(1 if erros else 0)
