"""Casos reais de duplicidade (e de falsas duplicidades) para não regredir.

Rodar: python testes/test_duplicatas.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gerar_feed_site import agrupar_duplicatas  # noqa: E402

MESMA = [
    # Relatado no site: mesma apreensão pela Umuarama News e pelo G1.
    ('BPRv apreende 300 garrafas de vinho estrangeiro na PR-323, em Cruzeiro do Oeste',
     'Polícia apreende 300 garrafas de vinho em Cruzeiro do Oeste', 'PR', 'PR'),
    ('Polícia apreende mais de 1,3 tonelada de maconha em apartamento em Vila Velha',
     'Mais de uma tonelada de maconha é apreendida em apartamento de Vila Velha', 'ES', 'ES'),
    ('PRF apreende 4 mil maços de cigarros sem comprovação em Parnaíba',
     'Polícia apreende 4 mil maços de cigarros ilegais na BR-402, em Parnaíba', 'PI', 'PI'),
]
DIFERENTES = [
    ('Polícia apreende drogas em Curitiba', 'Polícia apreende armas em Curitiba', 'PR', 'PR'),
    ('PM prende três homens com drogas em Teresina', 'PM prende dois homens com drogas em Teresina', 'PI', 'PI'),
    ('PRF apreende 2 toneladas de maconha na BR-163 em Dourados',
     'PRF apreende 500 kg de cocaína na BR-163 em Dourados', 'MS', 'MS'),
    # Operação nacional da PF: mesmo título, estados diferentes.
    ('PF reprime crimes de abuso sexual infantojuvenil no Pará',
     'PF reprime crimes de exploração sexual infantojuvenil na internet no RS', 'PA', 'RS'),
]


def agrupa(a, b, ua, ub):
    itens = [{'i': 1, 't': a, 'f': 'Fonte A', 'd': '2026-11-14T10:00', 'uf': ua},
             {'i': 2, 't': b, 'f': 'Fonte B', 'd': '2026-11-14T15:00', 'uf': ub}]
    saida, _ = agrupar_duplicatas(itens)
    return len(saida) == 1


def main():
    erros = [f'deveria agrupar: {a!r} / {b!r}' for a, b, ua, ub in MESMA if not agrupa(a, b, ua, ub)]
    erros += [f'não deveria agrupar: {a!r} / {b!r}' for a, b, ua, ub in DIFERENTES if agrupa(a, b, ua, ub)]
    for e in erros:
        print('FALHOU:', e)
    print(f'{len(MESMA) + len(DIFERENTES) - len(erros)}/{len(MESMA) + len(DIFERENTES)} casos corretos')
    sys.exit(1 if erros else 0)


if __name__ == '__main__':
    main()
