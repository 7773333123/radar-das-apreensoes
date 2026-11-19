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


# Casos com dias de diferença, abertura, fatos e foto: (item A, item B, deve agrupar?).
H = 0x9F3C5A7E1B2D4C68  # impressão digital de uma foto
LEAD = ('A Polícia Rodoviária Federal apreendeu na tarde desta quinta-feira mais de 60 quilos de skunk '
        'escondidos no porta-malas de um carro de passeio durante fiscalização no km 10 da BR-364, em Vilhena. '
        'O motorista, de 34 anos, foi preso em flagrante e encaminhado à Polícia Civil.')
AVANCADOS = [
    # Mesma foto (recomprimida: 3 bits de diferença), 4 dias depois, mesmo lugar.
    ({'t': 'PM apreende 4,5 toneladas de maconha e fuzil em Ourinhos', 'd': '2026-11-09', 'uf': 'SP', '_h': H},
     {'t': 'Carga com maconha e fuzil é apreendida em Ourinhos', 'd': '2026-11-13', 'uf': 'SP', '_h': H ^ 0b10101}, True),
    # Mesmo release (abertura igual), títulos bem diferentes, 2 dias depois.
    ({'t': 'PRF apreende mais de 60 kg de supermaconha em Vilhena', 'd': '2026-11-13', 'uf': 'RO', '_lead': LEAD},
     {'t': 'Motorista é preso com droga escondida no porta-malas', 'd': '2026-11-15', 'uf': 'RO', '_lead': LEAD}, True),
    # Mesmas quantidades e mesmo lugar, títulos diferentes.
    ({'t': 'DOF apreende 1,9 tonelada de maconha em caminhonete furtada na MS-166', 'd': '2026-10-29', 'uf': 'MS',
      '_q': {'mac': 1900.0}},
     {'t': 'Camionete furtada levava 1,9 t de maconha; DOF prende motorista na MS-166', 'd': '2026-10-28', 'uf': 'MS',
      '_q': {'mac': 1900.0}}, True),
    # Mesmo título-padrão, cidades diferentes (não é a mesma).
    ({'t': 'PCPR prende dois homens por tráfico de drogas durante operação em Jacarezinho', 'd': '2026-10-29', 'uf': 'PR'},
     {'t': 'PCPR prende dois homens por tráfico de drogas em Santo Antônio do Sudoeste', 'd': '2026-10-22', 'uf': 'PR'}, False),
    # Quantidades diferentes com decimais (16,5 x 36,5).
    ({'t': 'Receita Federal retém 16,5 quilos de cocaína em Paranaguá', 'd': '2026-08-17', 'uf': 'PR'},
     {'t': 'Receita Federal retém 36,5 quilos de cocaína em Paranaguá', 'd': '2026-08-12', 'uf': 'PR'}, False),
    # Mesma quantidade, cidades diferentes: só "quilos" em comum não basta.
    ({'t': 'Polícia Civil incinera 40 quilos de drogas em Barra do Choça', 'd': '2026-11-10', 'uf': 'BA', '_q': {'dro': 40.0}},
     {'t': 'PM apreende mais de 40 quilos de drogas em Irecê', 'd': '2026-11-09', 'uf': 'BA', '_q': {'dro': 40.0}}, False),
    # Mesmo número da rodovia não é quantidade em comum.
    ({'t': 'PRF apreende mais de 45 quilos de drogas na BR-277, em Santa Terezinha de Itaipu', 'd': '2026-11-11', 'uf': 'PR'},
     {'t': 'PRF apreende quase 105 quilos de pasta base na BR-277', 'd': '2026-11-09', 'uf': 'PR'}, False),
    # Foto padrão do site em notícias sem relação (aparece em várias): não agrupa.
    ({'t': 'Festa com drogas e homens armados é interrompida pela PM em Cariacica', 'd': '2026-11-15', 'uf': 'ES', '_h': H},
     {'t': 'Empresário suspeito de esconder drogas em açougue é preso em Alegre', 'd': '2026-11-13', 'uf': 'ES', '_h': H}, False),
    # Mesma foto em estados diferentes: veto.
    ({'t': 'PF deflagra operação contra tráfico em Belém', 'd': '2026-11-10', 'uf': 'PA', '_h': H},
     {'t': 'PF deflagra operação contra tráfico em Porto Alegre', 'd': '2026-11-10', 'uf': 'RS', '_h': H}, False),
    # Mesma grande apreensão com números arredondados (casos reais de nov/2026).
    ({'t': 'Polícia apreende 4,4 toneladas de cocaína e prende seis britânicos em SC', 'd': '2026-10-30', 'uf': 'SC',
      '_q': {'coc': 4400.0}},
     {'t': 'Seis estrangeiros do Reino Unido são presos com 4 toneladas de cocaína em SC', 'd': '2026-10-31', 'uf': 'SC',
      '_q': {'coc': 4000.0}}, True),
    ({'t': 'Polícia apreende 118 armas e mais de 4 mil munições em operação no ES', 'd': '2026-10-20', 'uf': 'ES',
      '_q': {'arm': 118.0, 'mun': 4000.0}},
     {'t': 'Mais de 100 armas e 4 mil munições são apreendidas em operação contra facção no ES', 'd': '2026-10-21', 'uf': 'ES',
      '_q': {'arm': 100.0, 'mun': 4000.0}}, True),
    # Duas grandes apreensões diferentes: estados diferentes não se juntam.
    ({'t': 'PRF apreende 1 tonelada de maconha em Dourados', 'd': '2026-10-20', 'uf': 'MS', '_q': {'mac': 1000.0}},
     {'t': 'PM apreende 1 tonelada de maconha em Cascavel', 'd': '2026-10-20', 'uf': 'PR', '_q': {'mac': 1000.0}}, False),
    # Mesmo estado, valores muito diferentes: não se juntam.
    ({'t': 'PRF apreende 2 toneladas de maconha na BR-163', 'd': '2026-10-20', 'uf': 'MS', '_q': {'mac': 2000.0}},
     {'t': 'DOF apreende 500 kg de maconha em Ponta Porã', 'd': '2026-10-21', 'uf': 'MS', '_q': {'mac': 500.0}}, False),
    # Grande apreensão no mesmo estado e dia, cada veículo cita uma cidade (caso real, 19/11/2026).
    ({'t': 'PRF e Polícia Militar apreendem mais de 1,3 tonelada de maconha após perseguição em Campo Grande',
      'd': '2026-11-19T13:45', 'uf': 'MS', '_q': {'mac': 1300.0}, '_cid': 'Campo Grande'},
     {'t': 'Motorista foge de bloqueio em Sidrolândia, mas acaba preso com 1,3 tonelada de maconha',
      'd': '2026-11-19T10:30', 'uf': 'MS', '_q': {'mac': 1300.0}, '_cid': 'Sidrolândia',
      '_lead': 'Apreensão de 1.389,3 quilos de maconha no Jardim Centenário, em Campo Grande.'}, True),
    # Cidades distantes que nenhuma das matérias cita: fatos diferentes (caso real, PR 11/09/2025).
    ({'t': 'PRF apreende mais de 1,6 tonelada de maconha em caminhão em Arapongas', 'd': '2025-09-11T10:00', 'uf': 'PR',
      '_q': {'mac': 1600.0}, '_cid': 'Arapongas', '_lead': 'A PRF abordou um caminhão na BR-369 em Arapongas.'},
     {'t': 'Polícia apreende mais de 1,6 tonelada de maconha em chácara em Nova Santa Rosa', 'd': '2025-09-11T15:00', 'uf': 'PR',
      '_q': {'mac': 1600.0}, '_cid': 'Nova Santa Rosa', '_lead': 'A droga estava em uma chácara na zona rural de Nova Santa Rosa.'}, False),
    # ...mas quantidades diferentes, material diferente ou dias distantes continuam separados.
    ({'t': 'PRF apreende 1,3 tonelada de maconha em Campo Grande', 'd': '2026-11-19T13:45', 'uf': 'MS', '_q': {'mac': 1300.0}},
     {'t': 'DOF apreende 500 kg de maconha em Ponta Porã', 'd': '2026-11-19T10:30', 'uf': 'MS', '_q': {'mac': 500.0}}, False),
    ({'t': 'PRF apreende 1,3 tonelada de maconha em Campo Grande', 'd': '2026-11-19T13:45', 'uf': 'MS', '_q': {'mac': 1300.0}},
     {'t': 'PF apreende 1,3 tonelada de cocaína em Corumbá', 'd': '2026-11-19T10:30', 'uf': 'MS', '_q': {'coc': 1300.0}}, False),
    ({'t': 'PRF apreende 1,3 tonelada de maconha em Campo Grande', 'd': '2026-11-19T13:45', 'uf': 'MS', '_q': {'mac': 1300.0}},
     {'t': 'Polícia apreende 1,3 tonelada de maconha em Dourados', 'd': '2026-11-14T10:30', 'uf': 'MS', '_q': {'mac': 1300.0}}, False),
    # Valor redondo (2 t) no mesmo estado e dia, cidades diferentes: fatos diferentes (MS, 08/07/2025).
    ({'t': 'PRF apreende 2 toneladas de maconha em caminhão na BR-158', 'd': '2025-07-08T10:00', 'uf': 'MS', '_q': {'mac': 2000.0}},
     {'t': 'Ônibus escolar é apreendido com mais de 2 toneladas de maconha em Ponta Porã', 'd': '2025-07-08T15:00', 'uf': 'MS',
      '_q': {'mac': 2000.0}}, False),
    # O mesmo, em notícias antigas sem a cidade do fato identificada: lugares dos títulos.
    ({'t': 'PRF apreende mais de 1,6 tonelada de maconha em caminhão em Arapongas', 'd': '2025-09-11T10:00', 'uf': 'PR',
      '_q': {'mac': 1600.0}},
     {'t': 'Polícia apreende mais de 1,6 tonelada de maconha em chácara em Nova Santa Rosa', 'd': '2025-09-11T15:00', 'uf': 'PR',
      '_q': {'mac': 1600.0}}, False),
    ({'t': 'PRF apreende 1,4 tonelada de maconha em Guia Lopes da Laguna (MS)', 'd': '2026-06-21T10:00', 'uf': 'MS', '_q': {'mac': 1400.0}},
     {'t': 'Polícia apreende 1,4 tonelada de maconha escondida em galões metálicos', 'd': '2026-06-21T15:00', 'uf': 'MS', '_q': {'mac': 1400.0}}, True),
    # Título quase idêntico, mesma cidade, 2 dias depois (republicação; caso real, 19/11/2026).
    ({'t': 'Adolescente suspeito de participar de invasão ao Complexo Vila Brasília é apreendido', 'd': '2026-11-19T09:52',
      'uf': 'RJ', '_cid': 'Volta Redonda'},
     {'t': 'Adolescente suspeito de participar de invasão à Vila Brasília é apreendido', 'd': '2026-11-17T20:37',
      'uf': 'RJ', '_cid': 'Volta Redonda'}, True),
    # Idem, com a cidade lida só num lado (citada nos dois títulos).
    ({'t': 'Adolescente suspeito de participar de invasão ao Complexo Vila Brasília é apreendido em Volta Redonda',
      'd': '2026-11-19T09:52', 'uf': 'RJ', '_cid': 'Volta Redonda'},
     {'t': 'Adolescente suspeito de participar de invasão à Vila Brasília é apreendido em Volta Redonda',
      'd': '2026-11-17T20:37', 'uf': 'RJ'}, True),
    # Título genérico na mesma cidade dias depois: fatos diferentes (caso real, 14 e 17/11/2026).
    ({'t': 'Homem é preso por tráfico de drogas em Passo Fundo', 'd': '2026-11-17', 'uf': 'RS', '_cid': 'Passo Fundo'},
     {'t': 'Homem é preso por tráfico de drogas no Centro de Passo Fundo', 'd': '2026-11-14', 'uf': 'RS', '_cid': 'Passo Fundo'}, False),
    ({'t': 'Guarda Municipal apreende drogas e mais de R$ 7 mil em Nova Serrana', 'd': '2026-11-01', 'uf': 'MG', '_cid': 'Nova Serrana'},
     {'t': 'Nova Serrana: Guarda Municipal apreende adolescente com drogas', 'd': '2026-10-30', 'uf': 'MG', '_cid': 'Nova Serrana'}, False),
    ({'t': 'POLÍCIA CIVIL PRENDE HOMEM CONDENADO POR TRÁFICO DE DROGAS EM SÃO LUÍS', 'd': '2026-11-09', 'uf': 'MA', '_cid': 'São Luís'},
     {'t': 'POLÍCIA CIVIL PRENDE HOMEM POR TRÁFICO DE DROGAS EM SÃO LUÍS', 'd': '2026-11-06', 'uf': 'MA', '_cid': 'São Luís'}, False),
    ({'t': 'Polícia Militar prende homem e apreende drogas na Zona Norte de Aracaju', 'd': '2026-09-24', 'uf': 'SE'},
     {'t': 'Polícia Militar prende homem por tráfico de drogas na Zona Norte de Aracaju', 'd': '2026-09-21', 'uf': 'SE'}, False),
    ({'t': 'PM apreende drogas e rádios comunicadores em comunidades de Campos', 'd': '2026-11-16', 'uf': 'RJ'},
     {'t': 'PM apreende drogas, loló e rádios comunicadores em comunidades de Campos', 'd': '2026-11-14', 'uf': 'RJ'}, False),
    ({'t': 'Polícia Civil deflagra operação contra tráfico de drogas e lavagem de dinheiro em Pernambuco e São Paulo', 'd': '2026-11-12', 'uf': 'PE'},
     {'t': 'Polícia Civil realiza operação contra tráfico de drogas e lavagem de dinheiro em Pernambuco e São Paulo', 'd': '2026-11-10', 'uf': 'PE', '_cid': 'Recife'}, False),
    # Mesma cidade, mesmo dia e o mesmo número no título (casos reais, 17-18/11/2026).
    ({'t': 'Casal é preso com 5 kg de derivado potente de maconha em rodovia em Martinópolis', 'd': '2026-11-18T19:01',
      'uf': 'SP', '_cid': 'Martinópolis', '_q': {'maconha': 5.0}},
     {'t': 'Casal é preso transportando 5,1 kg de maconha dry em Martinópolis', 'd': '2026-11-18T15:22',
      'uf': 'SP', '_cid': 'Martinópolis', '_q': {'maconha': 5.1}}, True),
    ({'t': 'Mulher é presa com mais de 25 kg de drogas e 755 comprimidos de ecstasy em SC', 'd': '2026-11-18T17:16',
      'uf': 'SC', '_cid': 'Palhoça'},
     {'t': 'Mulher de 24 anos é presa com mais de 25 quilos de drogas em Palhoça', 'd': '2026-11-18T12:52',
      'uf': 'SC', '_cid': 'Palhoça'}, True),
    ({'t': 'Homem usa adolescente de 15 anos para vender drogas e acaba preso pela Cavalaria', 'd': '2026-11-17T22:46',
      'uf': 'MT', '_cid': 'Barra do Bugres'},
     {'t': 'Homem é preso por usar adolescente de 15 anos para vender drogas', 'd': '2026-11-17T16:28',
      'uf': 'MT', '_cid': 'Barra do Bugres'}, True),
    # Quantidades diferentes (57 kg x 61 kg) na mesma cidade: não basta o número parecido.
    ({'t': 'FICCO apreende cerca de 57 kg de entorpecentes em Porto Velho', 'd': '2026-10-28', 'uf': 'RO',
      '_cid': 'Porto Velho', '_q': {'maconha': 57.0}},
     {'t': 'Motorista de ônibus e esposa são flagrados com mais de 61 kg de maconha em Porto Velho', 'd': '2026-10-27', 'uf': 'RO',
      '_cid': 'Porto Velho', '_q': {'maconha': 61.0}}, False),
    # Número de rodovia em comum não identifica o fato.
    ({'t': 'PRF apreende cocaína em carro na BR-163 em Sorriso', 'd': '2026-11-09', 'uf': 'MT', '_cid': 'Sorriso', '_q': {'cocaina': 3.0}},
     {'t': 'PRF apreende cocaína em caminhão na BR-163 em Sorriso', 'd': '2026-11-09', 'uf': 'MT', '_cid': 'Sorriso', '_q': {'cocaina': 40.0}}, False),
    # O mesmo link da matéria com títulos diferentes (o feed cortou a cidade; caso real, 18/11/2026).
    ({'t': 'Jovem é preso com mais de 1 kg de maconha em Nova Andradina', 'd': '2026-11-18T13:55', 'uf': 'MS',
      'u': 'https://www.radiojotafm.com.br/ivinhema/2026/11/18/jovem-e-preso-com-mais-de-1-kg-de-maconha.html'},
     {'t': 'Jovem é preso com mais de 1 kg de maconha', 'd': '2026-11-18T13:39', 'uf': 'MS',
      'u': 'https://radiojotafm.com.br/ivinhema/2026/11/18/jovem-e-preso-com-mais-de-1-kg-de-maconha.html?utm_source=rss'}, True),
    # O mesmo link com o estado mal lido num deles ("Rua Paraná" em São Carlos-SP).
    ({'t': 'Guarda Municipal localiza mandado de prisão em abordagem no Jardim Pacaembu', 'd': '2026-11-18', 'uf': 'SP',
      'u': 'https://regiaoemdestake.com.br/guarda-municipal-mandado-prisao-jardim-pacaembu-sao-carlos/'},
     {'t': 'Guarda Municipal encontra mandado de prisão em abordagem na Rua Paraná, em São Carlos', 'd': '2026-11-18', 'uf': 'PR',
      'u': 'https://regiaoemdestake.com.br/guarda-municipal-mandado-prisao-jardim-pacaembu-sao-carlos/'}, True),
    # O mesmo link em fatos diferentes, anos depois (o feed repetiu o link): não junta.
    ({'t': 'Duas mulheres são presas por tráfico de drogas em Pato Branco', 'd': '2026-11-16', 'uf': 'PR',
      'u': 'https://rbj.com.br/duas-mulheres-sao-presas-por-trafico-de-drogas-em-pato-branco-2/'},
     {'t': 'Três pessoas são presas por tráfico de drogas em Pato Branco', 'd': '2023-05-04', 'uf': 'PR',
      'u': 'https://rbj.com.br/duas-mulheres-sao-presas-por-trafico-de-drogas-em-pato-branco-2/'}, False),
    # Página genérica do veículo (seção) não é a mesma notícia.
    ({'t': 'PM prende homem por tráfico no Centro', 'd': '2026-11-18', 'uf': 'SP', 'u': 'https://site.com.br/policia/'},
     {'t': 'Mulher é presa com cocaína em ônibus', 'd': '2026-11-18', 'uf': 'SP', 'u': 'https://site.com.br/policia/'}, False),
    # Mesmo fato em veículos diferentes com nomes próprios raros em comum (caso real, 18/11/2026).
    ({'t': 'PF deflagra nova fase da operação sobre o desvio de emendas no filme Dark Horse', 'd': '2026-11-18'},
     {'t': 'Operação da PF mira desvio de emendas para filme “Dark Horse”', 'd': '2026-11-18'}, True),
    # O texto de um só lado cita "Operação Dark Horse": não anula os nomes em comum.
    ({'t': 'PF faz nova operação sobre suspeita de desvio de emendas ligada ao filme Dark Horse', 'd': '2026-11-18',
      '_lead': 'A Polícia Federal deflagrou nesta terça a nova fase da Operação Dark Horse.'},
     {'t': "PF faz nova operação sobre suspeita de desvio de emendas para filme 'Dark Horse'", 'd': '2026-11-18'}, True),
    ({'t': 'PF faz nova operação sobre suspeita de desvio de emendas ligada ao filme Dark Horse', 'd': '2026-11-18'},
     {'t': "Operação da Polícia Federal investiga desvio de emendas para o filme 'Dark Horse'", 'd': '2026-11-18'}, True),
    # Nomes de lugar ou facção em comum não bastam.
    ({'t': 'PRF apreende cocaína em carro na BR-277 em Foz do Iguaçu', 'd': '2026-11-18', 'uf': 'PR'},
     {'t': 'Receita apreende cocaína em ônibus na Ponte da Amizade em Foz do Iguaçu', 'd': '2026-11-18', 'uf': 'PR'}, False),
]


def agrupa_itens(a, b):
    itens = [dict(a, i=1, f='Fonte A'), dict(b, i=2, f='Fonte B')]
    saida, _ = agrupar_duplicatas(itens)
    return len(saida) == 1


def main():
    erros = [f'deveria agrupar: {a!r} / {b!r}' for a, b, ua, ub in MESMA if not agrupa(a, b, ua, ub)]
    for a, b, esperado in AVANCADOS:
        if agrupa_itens(a, b) != esperado:
            erros.append(f'{"deveria" if esperado else "não deveria"} agrupar: {a["t"]!r} / {b["t"]!r}')
    erros += [f'não deveria agrupar: {a!r} / {b!r}' for a, b, ua, ub in DIFERENTES if agrupa(a, b, ua, ub)]
    for e in erros:
        print('FALHOU:', e)
    total = len(MESMA) + len(DIFERENTES) + len(AVANCADOS)
    print(f'{total - len(erros)}/{total} casos corretos')
    sys.exit(1 if erros else 0)


if __name__ == '__main__':
    main()
