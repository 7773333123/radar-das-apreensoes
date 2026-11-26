"""Quantidade de outro fato não conta para a notícia (dono, 26/11/2026: os 579 kg de 2023 da PF em Cascavel
apareciam como apreensão do dia e ocupavam o topo da capa)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from resumo_fatos import sem_outros_fatos, extrair  # noqa: E402


def test_investigacao_de_outro_ano():
    t = ('A Polícia Federal deflagrou nesta quinta-feira (26/11/2026) a Operação Rastro Zero. A investigação teve '
         'início após uma prisão em flagrante no ano de 2023, que resultou na apreensão de, aproximadamente, 579 kg '
         'do entorpecente.')
    assert '579' not in sem_outros_fatos(t)
    assert '579' not in str(extrair('PF deflagra operação contra organização criminosa transnacional', '', t))


def test_apreensao_do_dia_continua():
    t = 'A PRF apreendeu 246 quilos de maconha nesta quinta-feira (26) em São José.'
    assert '246' in sem_outros_fatos(t)


if __name__ == '__main__':
    test_investigacao_de_outro_ano()
    test_apreensao_do_dia_continua()
    print('ok')
