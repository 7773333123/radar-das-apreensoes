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
    # Mesmos fatos no texto, títulos diferentes (Foz do Iguaçu, 19/11/2026: o caso que o usuário mostrou).
    ({'t': 'PCPR apreende fuzil, pistola e drogas e prende quatro pessoas em Foz do Iguaçu', 'd': '2026-11-19T15:45',
      'uf': 'PR', '_cid': 'Foz do Iguaçu', '_fx': {'r': ['fuzil'], 'p': 4}},
     {'t': 'Polícia prende jovem em Foz do Iguaçu após ostentar armas na internet', 'd': '2026-11-19T21:49',
      'uf': 'PR', '_cid': 'Foz do Iguaçu', '_fx': {'r': ['fuzil'], 'p': 4}}, True),
    ({'t': 'Jovem de 18 anos ostenta armas nas redes sociais, vira alvo de operação e acaba preso com outras três pessoas no Paraná',
      'd': '2026-11-19T18:48', 'uf': 'PR', '_cid': 'Foz do Iguaçu', '_fx': {'r': ['fuzil'], 'i': [18]}},
     {'t': 'Jovem que ostentava armas nas redes é preso em operação no Paraná', 'd': '2026-11-19T19:01',
      'uf': 'PR', '_cid': 'Foz do Iguaçu', '_fx': {'r': ['fuzil'], 'p': 4, 'i': [18]}}, True),
    # Dois fuzis apreendidos na mesma cidade e dia, com número de presos diferente: fatos diferentes.
    ({'t': 'PM prende dois homens com fuzil no bairro Centro', 'd': '2026-11-19', 'uf': 'RJ', '_cid': 'Duque de Caxias',
      '_fx': {'r': ['fuzil'], 'p': 2}},
     {'t': 'Operação prende cinco suspeitos e apreende fuzil', 'd': '2026-11-19', 'uf': 'RJ', '_cid': 'Duque de Caxias',
      '_fx': {'r': ['fuzil'], 'p': 5}}, False),
    # Só o fuzil em comum, sem outro sinal: não basta.
    ({'t': 'Polícia encontra fuzil escondido em matagal', 'd': '2026-11-19', 'uf': 'MG', '_cid': 'Contagem', '_fx': {'r': ['fuzil']}},
     {'t': 'PM prende suspeito com fuzil após perseguição', 'd': '2026-11-19', 'uf': 'MG', '_cid': 'Contagem', '_fx': {'r': ['fuzil']}}, False),
    # A mesma foto recortada/com zoom (fotos_orb.py), títulos genéricos (casos reais, 18-19/11/2026).
    ({'t': 'Polícia Civil apreende revólver durante operação', 'd': '2026-11-18T18:52', 'uf': 'PR',
      'img': 'https://midiasudoeste.com.br/arquivos/noticias/32362/P7.jpg',
      '_mesma': ['https://i0.wp.com/ppnewsfb.com.br/wp-content/uploads/2026/11/Captura.png']},
     {'t': 'Polícia Civil prende homem por posse irregular de arma de fogo na zona rural de Francisco Beltrão',
      'd': '2026-11-18T18:10', 'uf': 'PR', '_cid': 'Francisco Beltrão',
      'img': 'https://i0.wp.com/ppnewsfb.com.br/wp-content/uploads/2026/11/Captura.png',
      '_mesma': ['https://midiasudoeste.com.br/arquivos/noticias/32362/P7.jpg']}, True),
    ({'t': 'Encheu a mesa da polícia! Jovem é preso com três tipos de drogas diferentes no Litoral do Paraná',
      'd': '2026-11-19T16:34', 'uf': 'PR', 'img': 'https://imagens.bandab.com.br/jovem.jpg', '_mesma': ['https://pcpr/b7d5.jpg']},
     {'t': 'PCPR e PCSC prendem homem por tráfico de drogas e apreendem maconha em Matinhos', 'd': '2026-11-19T16:54',
      'uf': 'PR', '_cid': 'Matinhos', 'img': 'https://pcpr/b7d5.jpg', '_mesma': ['https://imagens.bandab.com.br/jovem.jpg']}, True),
    # A mesma foto em cidades do fato diferentes: foto de arquivo, fatos diferentes.
    ({'t': 'PM apreende drogas em Londrina', 'd': '2026-11-19', 'uf': 'PR', '_cid': 'Londrina',
      'img': 'https://x/arquivo1.jpg', '_mesma': ['https://y/arquivo2.jpg']},
     {'t': 'PM apreende drogas em Maringá', 'd': '2026-11-19', 'uf': 'PR', '_cid': 'Maringá',
      'img': 'https://y/arquivo2.jpg', '_mesma': ['https://x/arquivo1.jpg']}, False),
    # Foto de banco de imagens (casada com muitas outras): não vale.
    ({'t': 'Polícia prende suspeito', 'd': '2026-11-19', 'uf': 'PR', 'img': 'https://x/viatura.jpg',
      '_mesma': ['https://y/v1.jpg', 'https://y/v2.jpg', 'https://y/v3.jpg', 'https://y/v4.jpg']},
     {'t': 'Homem é detido após denúncia', 'd': '2026-11-19', 'uf': 'PR', 'img': 'https://y/v1.jpg', '_mesma': ['https://x/viatura.jpg']}, False),
    # Foto idêntica, títulos diferentes (caso mostrado pelo usuário na página inicial, 19/11/2026).
    ({'t': 'PRF apreende quase 3,4 toneladas de maconha em duas cidades de MS', 'd': '2026-11-19T22:11', 'uf': 'MS',
      '_cid': 'Dourados', '_h': 0x1234567890abcdef, 'img': 'https://jd1/x.jpg', '_q': {'maconha': 3400.0}},
     {'t': 'PRF apreende mais de 3 toneladas de maconha em Dourados e na Capital', 'd': '2026-11-19T20:00', 'uf': 'MS',
      '_h': 0x1234567890abcdef, 'img': 'https://enfoque/y.jpg', '_q': {'maconha': 3000.0}}, True),
    # Foto idêntica em cidades do fato diferentes (foto de arquivo): não junta.
    ({'t': 'PM apreende drogas no Centro', 'd': '2026-11-19', 'uf': 'MS', '_cid': 'Dourados', '_h': 0x0f0f0f0f0f0f0f0f,
      'img': 'https://a/1.jpg'},
     {'t': 'PM prende suspeito com drogas', 'd': '2026-11-19', 'uf': 'MS', '_cid': 'Corumbá', '_h': 0x0f0f0f0f0f0f0f0f,
      'img': 'https://b/2.jpg'}, False),
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
    # Caso real (17/11/2026, MS): 2 t x 6 t de maconha; "duas cidades" não é quantidade de droga.
    ({'t': 'Polícia Militar Ambiental e Polícia Rodoviária Federal apreende mais de duas toneladas de maconha em caminhão carregado com carga de carvão',
      'd': '2026-11-17', 'uf': 'MS', '_q': {'mac': 2000.0}},
     {'t': 'PRF apreende mais de 6 toneladas de maconha em duas cidades de MS', 'd': '2026-11-17', 'uf': 'MS',
      '_q': {'mac': 6000.0}}, False),
    # "Mais de uma tonelada" é o mesmo fato que 1,4 tonelada (caso real, 22/10/2026).
    ({'t': 'Polícia Rodoviária encontra mais de 1,4 tonelada de maconha em carga de fraldas em Assis', 'd': '2026-10-22', 'uf': 'SP'},
     {'t': 'Polícia apreende mais de uma tonelada de maconha escondida em carga de fraldas em Assis', 'd': '2026-10-22', 'uf': 'SP'}, True),
    # Número por extenso em comum ("duas toneladas") não identifica o fato (MS, 17 x 19/11/2026).
    ({'t': 'PRF intercepta caminhonete furtada e apreende mais de duas toneladas de maconha', 'd': '2026-11-19',
      'uf': 'MS', '_q': {'mac': 2000.0}},
     {'t': 'Polícia Militar Ambiental e Polícia Rodoviária Federal apreende mais de duas toneladas de maconha em caminhão carregado com carga de carvão',
      'd': '2026-11-17', 'uf': 'MS', '_q': {'mac': 2000.0}}, False),
    # O nome do veículo no fim do título não é palavra em comum (Ponta Porã Informa, 17/11/2026).
    ({'t': 'PM apreende maconha da rodoviária de Ponta Porã - Ponta Porã Informa - Notícias de Ponta Porã/MS e Pedro',
      'f': 'Ponta Porã Informa', 'd': '2026-11-17', 'uf': 'MS'},
     {'t': 'DOF apreende quase 150 quilos de maconha em duas motos em Itahum - Ponta Porã Informa - Notícias de Ponta',
      'f': 'Ponta Porã Informa', 'd': '2026-11-16', 'uf': 'MS'}, False),
    # Nomes de lugar ou facção em comum não bastam.
    ({'t': 'PRF apreende cocaína em carro na BR-277 em Foz do Iguaçu', 'd': '2026-11-18', 'uf': 'PR'},
     {'t': 'Receita apreende cocaína em ônibus na Ponte da Amizade em Foz do Iguaçu', 'd': '2026-11-18', 'uf': 'PR'}, False),
]


def agrupa_itens(a, b):
    itens = [dict(a, i=1, f=a.get('f', 'Fonte A')), dict(b, i=2, f=b.get('f', 'Fonte B'))]
    saida, _ = agrupar_duplicatas(itens)
    return len(saida) == 1


def main():
    erros = [f'deveria agrupar: {a!r} / {b!r}' for a, b, ua, ub in MESMA if not agrupa(a, b, ua, ub)]
    for a, b, esperado in AVANCADOS:
        if agrupa_itens(a, b) != esperado:
            erros.append(f'{"deveria" if esperado else "não deveria"} agrupar: {a["t"]!r} / {b["t"]!r}')
    erros += [f'não deveria agrupar: {a!r} / {b!r}' for a, b, ua, ub in DIFERENTES if agrupa(a, b, ua, ub)]
    # Decisão "mesmo" do juiz vale para o par, não para os grupos: caso real de Sobral (20/11/2026),
    # prisão de homem de 27 anos com 1 kg (17/11) unida ao casal de 18 e 30 anos com 35 kg (14/11).
    from duplicatas import _grupos_coerentes
    sob = [{'t': 'PM apreende 35 kg de drogas e prende casal em Sobral', '_cid': 'Sobral', '_fx': {'i': [18, 30]},
            '_q': {'dro': 35.0}},
           {'t': 'PMCE prende suspeito de tráfico de drogas e apreende drogas em Sobral', '_cid': 'Sobral'},
           {'t': 'PMCE prende suspeito de tráfico durante ação em Sobral', '_cid': 'Sobral', '_fx': {'i': [27]}}]
    pai = {0: 0, 1: 1, 2: 1}  # 1 e 2 já unidas (mesma prisão de 17/11)
    if _grupos_coerentes(sob, [0, 1, 2], lambda k: pai[k], 0, 1):
        erros.append('juiz não deveria unir grupos contraditórios (Sobral: idades 18/30 x 27)')
    # Skank é maconha: 1 kg de skank (17/11) x 15,2 kg de maconha (18/11), Sobral.
    sk = [{'t': 'PM apreende 15,2 kg de maconha em tambor enterrado em Sobral', '_q': {'mac': 15.2}},
          {'t': 'Polícia Militar prende suspeito de tráfico de drogas e apreende drogas em Sobral'},
          {'t': 'PM prende suspeito de tráfico e apreende 1 kg de skank em Sobral', '_q': {'skh': 1.0}}]
    if _grupos_coerentes(sk, [0, 1, 2], lambda k: {0: 0, 1: 1, 2: 1}[k], 0, 1):
        erros.append('juiz não deveria unir 1 kg de skank a 15,2 kg de maconha (Sobral)')
    # Casal nos dois lados: cada jornal cita a idade de um dos dois (Dourados, 20/11/2026).
    casal = [{'t': 'Com bebê de 1 ano no carro, casal é preso transportando maconha e cocaína em Dourados', '_fx': {'i': [25]}},
             {'t': 'Casal é preso por tráfico de drogas com filho de 1 ano dentro do carro em Dourados', '_fx': {'i': [22]}}]
    if not _grupos_coerentes(casal, [0, 1], lambda k: k, 0, 1):
        erros.append('casal: idades diferentes de cada um não são contradição (Dourados)')
    if not _grupos_coerentes(sob, [0, 1], lambda k: k, 0, 1):
        erros.append('par sem contradição deveria poder ser unido pelo juiz')
    # Cidade grande (mais de 40 notícias em 3 dias): par com material e 2+ palavras em comum vai ao
    # juiz (Foz do Iguaçu, 20/11/2026: "5 mil maços de cigarros", PF e PM, dois veículos).
    import duplicatas as dup
    foz = [{'i': 900 + k, 't': f'Notícia {k} diferente em Foz do Iguaçu', 'f': f'V{k}', '_cid': 'Foz do Iguaçu', 'uf': 'PR'}
           for k in range(45)]
    foz += [{'i': 1, 't': 'PF e PM apreendem 5 mil maços de cigarros contrabandeados em Foz do Iguaçu', 'f': 'Portal 24 Horas',
             '_cid': 'Foz do Iguaçu', 'uf': 'PR'},
            {'i': 2, 't': 'Ação integrada entre PF e PM apreende cinco mil maços de cigarros em Foz do Iguaçu/PR', 'f': 'GOV.BR',
             '_cid': 'Foz do Iguaçu', 'uf': 'PR'}]
    dup.SUSPEITAS.clear()  # pares de testes anteriores (mesmos ids) não contam como "já enviados"
    antes = len(dup.SUSPEITAS)
    dup._mesma_cidade(foz, [100] * len(foz), lambda a, b, r: None, lambda k: k)
    novos = dup.SUSPEITAS[antes:]
    del dup.SUSPEITAS[antes:]
    if not any({p['a'][0], p['b'][0]} == {1, 2} for p in novos):
        erros.append('cidade grande: par dos 5 mil maços de cigarros em Foz deveria ir ao juiz')
    # Estado gravado na coleta antes da correção do cadastro: o cadastro do veículo vence
    # (O Hoje = GO; edição com estado no nome fica com o da coleta).
    from localizar_uf import inferir_uf
    cad = [{'dominio': 'ohoje.com', 'uf': 'GO'}, {'dominio': 'jornalopcao.com.br', 'uf': 'GO'}]
    if inferir_uf({'titulo': 'Caminhonete leva polícia a 165 kg de maconha em Anápolis', 'fonte': 'O Hoje',
                   'dominio_fonte': 'ohoje.com', 'uf_fonte': 'DF'}, cad) != 'GO':
        erros.append('cadastro do veículo deveria vencer o estado antigo da coleta (O Hoje = GO)')
    if inferir_uf({'titulo': 'Operação prende cinco pessoas em Paraíso', 'fonte': 'Jornal Opção | Tocantins',
                   'dominio_fonte': 'jornalopcao.com.br', 'uf_fonte': 'TO'}, cad) != 'TO':
        erros.append('edição estadual com o estado no nome deveria manter o estado (Jornal Opção | Tocantins)')
    # Estado mal lido numa das versões (24/11/2026): valor distintivo igual vai ao juiz mesmo com estados
    # diferentes (R$ 850 mil: Metrópoles=DF x PF=PI); palavra rara em comum também ("Fundeb": DF x AL).
    dup.SUSPEITAS.clear()
    pi = [{'i': 31, 't': 'PF faz operação no Piauí e no DF após homem ser flagrado com R$ 850 mil', 'f': 'Metrópoles', 'uf': 'DF'},
          {'i': 32, 't': 'PF deflagra operação após apreensão de R$ 850 mil no Piauí', 'f': 'Governo Federal', 'uf': 'PI'}]
    dup._mesmo_valor(pi, [100, 100], lambda a, b, r, forcar=False: None, lambda k: k)
    if not any({p['a'][0], p['b'][0]} == {31, 32} for p in dup.SUSPEITAS):
        erros.append('R$ 850 mil (DF x PI, estado mal lido) deveria ir ao juiz')
    dup.SUSPEITAS.clear()
    fu = [{'i': 41, 't': 'PF acha cofre recheado de dinheiro em operação contra desvio do Fundeb', 'f': 'Metrópoles', 'uf': 'DF'},
          {'i': 42, 't': 'PF faz operação contra suspeita de corrupção com dinheiro do Fundeb em Alagoas', 'f': 'todosegundo', 'uf': 'AL'}]
    dup._palavra_rara(fu, [100, 100], lambda a, b, r, forcar=False: None, lambda k: k)
    if not any({p['a'][0], p['b'][0]} == {41, 42} for p in dup.SUSPEITAS):
        erros.append('Fundeb (DF x AL): palavra rara em comum deveria ir ao juiz')
    dup.SUSPEITAS.clear()
    # "prendem motorista com 253 kg de maconha": apreensão concreta, a quantidade entra (24/11/2026).
    from estatisticas import somavel
    if not somavel('PMPR e PF prendem motorista com 253 kg de maconha na região de Umuarama'):
        erros.append('"prendem motorista com 253 kg" deveria contar como apreensão concreta')
    if somavel('Balanço: PM prende 40 pessoas com 2 toneladas de drogas no total do ano'):
        erros.append('balanço não deveria contar como apreensão concreta')
    # Cidade pequena: par só com o material em comum vai ao juiz (Vereda/BA, 20/11/2026).
    ver = [{'i': 11, 't': 'PM apreende 11 porções de cocaína em Vereda', 'f': 'informebaiano.com.br', '_cid': 'Vereda', 'uf': 'BA'},
           {'i': 12, 't': 'PMBA apreende 82 gramas de cocaína durante abordagem em Vereda', 'f': 'Itamaraju Notícias',
            '_cid': 'Vereda', 'uf': 'BA'}]
    antes = len(dup.SUSPEITAS)
    dup._mesma_cidade(ver, [100, 100], lambda a, b, r: None, lambda k: k)
    novos = dup.SUSPEITAS[antes:]
    del dup.SUSPEITAS[antes:]
    if not any({p['a'][0], p['b'][0]} == {11, 12} for p in novos):
        erros.append('cidade pequena: par de Vereda (11 porções x 82 gramas de cocaína) deveria ir ao juiz')
    # Versão exibida: fonte primária (órgão público) vence a reportagem mais completa; sem fonte
    # oficial, quem publicou primeiro vence (21/11/2026).
    from duplicatas import _pontos
    completa = {'x': 1, '_tr': 1, 'img': 'a.jpg', 'g': 5, 'u': 'https://jornal/x', 'uf': 'PR', 'r': 'resumo'}
    if not _pontos({'_ofi': 1, 'u': 'https://www.gov.br/pf/x'}) > _pontos(completa):
        erros.append('fonte primária (órgão público) deveria ser a versão exibida')
    if not _pontos({'u': 'https://a/x', 'img': 'a.jpg'}, primeiro=True) > _pontos({'u': 'https://b/x', 'img': 'b.jpg', 'r': 'r', 'uf': 'PR'}):
        erros.append('quem publicou primeiro deveria vencer a versão um pouco mais completa')
    if not _pontos({'_ofi': 1, '_bloq': True}) < _pontos({'u': 'https://b/x'}):
        erros.append('versão bloqueada (sem conteúdo) nunca deveria ser a exibida')
    # Matéria livre com texto integral vence quem publicou primeiro (íntegra exibida como antes).
    if not _pontos({'x': 1, 'u': 'https://agenciabrasil/x'}) > _pontos({'u': 'https://a/x', 'img': 'a.jpg', '_tr': 1, '_uff': 'PR', 'uf': 'PR'}, primeiro=True):
        erros.append('matéria livre com texto integral deveria vencer quem publicou primeiro')
    # Cidade grande, mesma quantidade do mesmo material no título: vai ao juiz (Foz, 115 kg de maconha).
    fz = [{'i': 950 + k, 't': f'Notícia {k} diferente em Foz do Iguaçu', 'f': f'W{k}', '_cid': 'Foz do Iguaçu', 'uf': 'PR'}
          for k in range(45)]
    fz += [{'i': 21, 't': 'Analistas-Tributários atuam na apreensão de 115 kg de maconha no Paraná', 'f': 'Sindireceita',
            '_cid': 'Foz do Iguaçu', 'uf': 'PR'},
           {'i': 22, 't': 'Receita Federal apreende 115 quilos de maconha em veículo na Ponte da Amizade', 'f': 'Portal 24 Horas',
            '_cid': 'Foz do Iguaçu', 'uf': 'PR'}]
    antes = len(dup.SUSPEITAS)
    dup._mesma_cidade(fz, [100] * (len(fz) - 1) + [101], lambda a, b, r: None, lambda k: k)
    novos = dup.SUSPEITAS[antes:]
    del dup.SUSPEITAS[antes:]
    if not any({p['a'][0], p['b'][0]} == {21, 22} for p in novos):
        erros.append('mesma quantidade do mesmo material na mesma cidade deveria ir ao juiz (115 kg, Foz)')
    # Revisão à mão "mesmo" une sempre (São Gonçalo/RJ, 21/11/2026: seguia duplicada).
    sg = [{'i': 123092859823200, 't': 'Homem é preso e fuzil é apreendido durante operação em São Gonçalo',
           'f': 'O Dia', 'd': '2026-11-21T21:22', 'uf': 'RJ'},
          {'i': 384017253153659, 't': 'PM prende suspeito com fuzil durante operação para capturar criminosos que atacaram viatura em São Gonçalo',
           'f': 'Povo na Rua', 'd': '2026-11-21T16:06', 'uf': 'RJ'}]
    if len(agrupar_duplicatas(sg)[0]) != 1:
        erros.append('par marcado "mesmo" na revisão à mão deveria ficar numa notícia só (São Gonçalo)')
    # Post de Facebook com manchete e texto colados: fica só a manchete (21/11/2026).
    from gerar_feed_site import titulo_de_post
    for post, manchete in [
            ('BRIGADA MILITAR PRENDE DOIS HOMENS POR TRÁFICO DE DROGAS EM SANTO ANTÔNIO DA PATRULHA A Brigada Militar de Santo',
             'BRIGADA MILITAR PRENDE DOIS HOMENS POR TRÁFICO DE DROGAS EM SANTO ANTÔNIO DA PATRULHA'),
            ('PM FLAGRA SUSPEITOS PREPARANDO MACONHA PARA VENDA EM SALINAS | Foi pro meio de denúncia que a Polícia',
             'PM FLAGRA SUSPEITOS PREPARANDO MACONHA PARA VENDA EM SALINAS'),
            ('Operação contra o tráfico prende suspeito em Itajaí e revela esquema que movimentou mais de R$ 65 milhões Uma operação interestadual de…',
             'Operação contra o tráfico prende suspeito em Itajaí e revela esquema que movimentou mais de R$ 65 milhões')]:
        if titulo_de_post(post) != manchete:
            erros.append(f'post de rede social deveria ficar só com a manchete: {titulo_de_post(post)!r}')
    # Republicação atrasada com o mesmo valor no título (O Antagonista, 3 dias depois do release
    # do Ibama, 22/11/2026): o par vai ao juiz.
    rp = [{'i': 31, 't': 'Ibama aplica R$ 226,8 mil em multas e apreende drone de R$ 197 mil no estado do Rio', 'f': 'temporealrj'},
          {'i': 32, 't': 'Ibama fiscaliza propriedades rurais, apreende drone de R$ 197 mil e aplica R$ 226 mil em multas', 'f': 'O Antagonista'}]
    antes = len(dup.SUSPEITAS)
    dup._mesmo_valor(rp, [100, 103], lambda a, b, r: None, lambda k: k)
    novos = dup.SUSPEITAS[antes:]
    del dup.SUSPEITAS[antes:]
    if not any({p['a'][0], p['b'][0]} == {31, 32} for p in novos):
        erros.append('mesmo valor no título até 7 dias deveria ir ao juiz (drone de R$ 197 mil, Ibama)')
    # Valor comum ("30 kg" em 16 notícias): o par do mesmo dia com o mesmo material ainda vai ao
    # juiz; outro material ou dias distantes, não (Campos 24Horas x Folha1, 22/11/2026).
    cm = [{'i': 41, 't': 'PM apreende 30 Kg de maconha em Campos; prejuízo de R$ 60 mil ao tráfico', 'f': 'Campos 24Horas'},
          {'i': 42, 't': 'PM apreende 30 kg de maconha em residência na Baixada Campista', 'f': 'Folha1'},
          {'i': 43, 't': 'Polícia apreende 30 kg de cocaína em carreta', 'f': 'X'}]
    cm += [{'i': 100 + k, 't': f'Polícia apreende 30 kg de drogas na cidade {k}', 'f': 'Y'} for k in range(14)]
    antes = len(dup.SUSPEITAS)
    dup._mesmo_valor(cm, [100, 100, 100] + [90] * 14, lambda a, b, r: None, lambda k: k)
    novos = dup.SUSPEITAS[antes:]
    del dup.SUSPEITAS[antes:]
    pares = [{p['a'][0], p['b'][0]} for p in novos]
    if {41, 42} not in pares:
        erros.append('valor comum ("30 kg"), mesmo dia e mesmo material deveria ir ao juiz (Campos)')
    if {41, 43} in pares or {42, 43} in pares:
        erros.append('valor comum com materiais diferentes (maconha x cocaína) não deveria ir ao juiz')
    # A MESMA FOTO com marca d'água (CAMPOS24HORAS) x limpa (Folha1), dHash a 26 bits, estado vazio:
    # as miniaturas desfocadas juntam (Campos/RJ, 22/11/2026). Miniaturas reais das duas fotos.
    mc = [{'i': 51, 't': 'PM apreende 30 Kg de maconha em Campos; prejuízo de R$ 60 mil ao tráfico', 'f': 'Campos 24Horas', 'd': '2026-11-22T12:30',
           'img': 'https://campos24horas.com.br/x.jpg', '_mini': ('v24:sqymqKqhlpigmpSRlaKppK2mn6Smnpebop2Xk5WiqqimoJmeoJuYnKKemZSVn6mqoJyZm5yamZyenJeSk5ykqJ6em5iYmZmZl5WOio+Wm56eoZ6Yk5WWk5CLg4OMj4+Rn6GdlI2OjoyLhXx/iYmFhJuel4+HhoiIiYR7fYSAfHuUlo2GgYGEhoiFfHp7dHJzjY2DfYCBg4WFhX12c2pqbomJfnyCg4ODgYF7dXBpam2KioOAhoeBfnt2dnd2cXFxj4+LhIWJgHdya3B9fXh5eJKSjoSBiH1waWVxgX55gIGPjo2CfIB4bGlreYV6doWHiIaHf3NxcG9zeISJeXmJh4B/f3loYGh2goeMinx/h3t7enZuXFZleoyPioN+gXxpd3ZtYlZWZHiNjX10eHdqWnNyaF1XW2RxgoJsZGtnXFdwcGlfXWBkZ3J1Y1xhXFlfbW9taGRkZWFlb2liYF1ia2twc3BraGZfXXB3bWhobnNqcXd2b2poX1t0gndwcnZ3', 'h43:tLOzsa2opKOmq6+vq6ehnZiSj5GaoaamoJqWlJORj42OkZeepKmqqqaioKmopqKdl5OUmaClpKGdmpeVlJWZoKWopqKenJybmZaTkZKVmqGora+uq6mcnJycmpmXl5iam5ubmpuampmanJ2dnp2en5+enJiVkpKSlJicoaWpq6urnZ6goqOjoZ+cmJSTlJeam5uampqXlJKPjo+OiYJ9fICHjZCRkJCQkJKUlp+ipKalo6GempWPiYeIjI+PjIiHiImKioeDfnh0c3iAiI2PjoqGg4GAgIGTmJyenZmTj4yKhoF8e32BgoOCgoWIio2MiYR+enh7f4SFgn13dXV3d3d1g4eNj4yEenJvcnh8fX59f4GEiImHhIGBhImLh352cXFxcGpiXFtgZmpra4aHiIiFgHt4eHyCiIyMioR+fH6Bg4F/fX5+f3x5dnR0c3Nyb21sbW9vb26SkpKTk5SUko2GgYCFjI+LgndycnZ2dG5lXVtfZ3J+hYiHhIB+fn9+fXp3lJSUk5GRko+Ge3N0fIiPjod6bmZjYmFgXV1haXN/iYyGe3BqbXaDi42JhYWFhYJ/gIWMjIZ9dW9ta2tra2tsb3F0eHp8foOLkpSOf3FpanOBkJeXj4h5e3x7eXd5fHt1a11RSkpPWGFseISMkZSTkZCRlJaUjIN+gIePkpCHemthdXh6e3hya2VgW1dSUFFVW2JnbXN+h5CZnJePhHlwa2xyeX+BfHNoXVVPS29wcnNxbWdhXFlYWVtdYGJkZWRkZmpyfIF9cWFTTExTXGNjXFNNTFFXXF9rbG5wcXFwbmxqaWhnZmVlZWZkYVtXV1xmb3JwamVjY2FfXFpaXWNpbnFyaWptcHR2eHh4dnRxbWtpaWlpaGRdVlFTYHWIj4uCe3Zyb29xdXd5eXh4dw==')},
          {'i': 52, 't': 'PM apreende 30 kg de maconha em residência na Baixada Campista', 'f': 'Folha1', 'd': '2026-11-22T05:43',
           'img': 'http://www.folha1.com.br/y.jpg', '_mini': ('v34:t7awq6mqp6amnpaWo7G4ure0raupp6OipJyUkp6ttLW0r6eoqKOdn6Oak5CYpq+vrqefo6SdmJyim5WRlKGrrKafmZ2fmpaboJuXkpKdqaufm5aYmpiYmpyZlZCQmaOom5uYlpWXmJeUkoyIjJKYnpydmpWRk5OQjYiBgIiMjJCcnZmSioqKiIaBeHqEhoKCmJmTjIOBgYGEf3V4gH15eJGRiYN9e31/goB3dXdxbm+JiH56e3t8gIGBeXFuZ2ZqhIJ5d35+fH9+fHdva2RlaYSCfHyCgnp7eHJvcXBramyJh4SAg4R4cm5kaXV1cXJzjImIgX+EdWljXml5dXB6fYqHhoB7fHBkYWJxfW9sf4V/fH17bWVjaHF4g4FucIOBeHV1cV9UXG+Bh4eAdHl8b3Nxa2NTTltziYyBd3V5bVpwbmRZT1BdcIaHcmdubVtObWxiV1NXXmh5emNZYl5SUWtrZl5bXV9ham9fWFxXVl5pbGxoZGJhXV5pZ2FfXGFpaG5ycWtmY11aZm1saWdrb2hwd3hxamdhW2JtcnJwcG9pc3x+dm5qZmBfaHN3c29saXaBg3x0b2xmYWVyd3NsaGt4hYiBenVwbGdocXRvaWVseYiMhoB6dXJubHBwa2ZibXmIj4uFfnl2c3BvbWdjX214iJGPiIJ9endyb2pkX1tsd4iSkYuEfnt5dG9oYVxZbHaHkpKMhX97eXVvZ19aVw==', 'h30:tra0sq6rqqmpqKelo6SlpqSgmpaUlJifp6+ztre3r62qpaKho6WkoZ6bmp2go6KemZWTkZKWnKSqra2toaCdmpiYmZqbmZiXmJmbnJuZl5ORj46QlJmfo6Wnm5ycm5qXlJGQkJGRkZCOjoyKhoJ/gISIioyMjY+QlZaXlZGMiYWCgYGBgYKCg4SCfnh1d3p9fHp3dnZ2iImIhH98fH1+fX18fX9/gIB/fHh0cnBua2hmZ2lqh4eGhIJ/f4CDg4B8eHZ2dXFta2tvcnNyb21ub3BwiomIhoeEgHx7fHp1bWlnZmRiZWx1enlybnB3foCAfnx7enp5dW1lYF9hZGluc3d7foGDgXpzcXV8fnt2cXFwbWlkXldRT1FYYW12f4eJhHx1cG9xc3FrY1pUa2xsamZhXVpZWVteYGNma3J1cWhgXF5gYF1ZWFhaaGpsb3Fwb2xpZmVjYl9cW15kaWtqaWhoZmVnaWxtZ2txd3x+fnp2cW5samdkYl9gY2htcnV1dHJwbm1saW52foWIiIWBfXl3dHJwb2xpZ2hscHN0cm5raGZka3B3f4eNj46Lh4SAfXt5eHZ1c3Fwb25taWZjYV9da250fYaOkpKQjImGgn98fHp5eHVyb2xpZGBcWllX')}]
    if len(agrupar_duplicatas(mc)[0]) != 1:
        erros.append("a mesma foto com marca d'água deveria juntar as notícias (30 kg de maconha em Campos)")
    # Foto diferente com o mesmo título-padrão não junta.
    md = [dict(mc[0]), dict(mc[1], _mini=(mc[0]['_mini'][0][::-1], ''))]
    md[1]['t'] = 'PM apreende 30 kg de maconha em Itaperuna'
    md[1]['i'] = 53
    if len(agrupar_duplicatas(md)[0]) != 2:
        erros.append('foto diferente e cidade diferente não deveriam juntar')
    # Origem do transporte não é o local do fato (Teresina/PI, 23/11/2026).
    from localizar_uf import inferir_uf
    for titulo, uf in [('Dois homens são presos com 52 tabletes de maconha em ônibus que vinha de São Paulo para Teresina', 'PI'),
                       ('PM apreende 42 armas de fogo escondidas em ônibus que vinha do Maranhão para Sorriso e prende três motoristas', 'MT'),
                       ('Carga com 24 kg de skunk vinda de São Paulo é interceptada em Fortaleza', 'CE'),
                       ('Polícia apreende drogas em São Paulo', 'SP')]:
        if inferir_uf({'titulo': titulo}) != uf:
            erros.append(f'estado do fato deveria ser {uf}: {titulo}')
    # Veículo de divisa sem estado cadastrado não aprende estado (Zap Catalão/GO noticia Araguari/MG).
    from localizar_uf import ufs_aprendidas
    zap = [{'titulo': f'PM prende suspeito em Catalão ({k})', 'dominio_fonte': 'zapcatalao.com.br'} for k in range(9)]
    zap.append({'titulo': 'PM apreende maconha em Araguari', 'dominio_fonte': 'zapcatalao.com.br'})
    divisa = [{'dominio': 'zapcatalao.com.br', 'uf': '', 'fronteira': 'Corredor do Triângulo Mineiro e de Goiás'}]
    if ufs_aprendidas(zap, divisa) or not ufs_aprendidas(zap, []):
        erros.append('veículo de divisa não deveria aprender estado (e veículo comum deveria)')
    if inferir_uf(zap[-1], divisa + ufs_aprendidas(zap, divisa)) != 'MG':
        erros.append('Araguari noticiada por veículo de Goiás deveria ficar em MG')
    # Foto com marca d'água na versão exibida: troca pela foto limpa da outra fonte (24/11/2026).
    mw = [dict(mc[0], img='https://a.com/carimbada.jpg', _marca=[], d='2026-11-20T10:00'),
          dict(mc[1], img='https://b.com/limpa.jpg', d='2026-11-20T11:00')]
    mw[0].pop('_ofi', None)
    juntas = agrupar_duplicatas(mw)[0]
    if len(juntas) != 1 or juntas[0].get('img') != 'https://b.com/limpa.jpg' or '_marca' in juntas[0]:
        erros.append("a versão exibida deveria trocar a foto com marca d'água pela foto limpa da outra fonte")
    mw2 = [dict(mc[0], img='https://a.com/carimbada.jpg', _marca=[], d='2026-11-20T10:00'),
           dict(mc[1], img='https://b.com/outra-carimbada.jpg', _marca=[], d='2026-11-20T11:00')]
    juntas = agrupar_duplicatas(mw2)[0]
    if len(juntas) != 1 or '_marca' not in juntas[0]:
        erros.append("sem foto limpa, a foto deveria seguir marcada (o gerador tira a foto)")
    # Português do texto redigido pelo Radar (24/11/2026): zero a dez por extenso, com concordância de gênero;
    # algarismo com unidade/valor; idade junto do sujeito ou em oração separada.
    from resumo_fatos import numerais_por_extenso, _idade_dos_presos
    for antes, depois in [('apreendeu 6 armas, 2 pistolas, 2 fuzis, 2 motos, 2 caminhões e 6 kg de maconha.',
                           'apreendeu seis armas, duas pistolas, dois fuzis, duas motos, dois caminhões e 6 kg de maconha.'),
                          ('Foi cumprido 1 mandado de prisão.', 'Foi cumprido um mandado de prisão.'),
                          ('O caso repercutiu: 5 veículos publicaram.', 'O caso repercutiu: cinco veículos publicaram.'),
                          ('R$ 2 mil, 2 t de soja, BR-2, 3ª vez, de 9 anos, 12 notícias', 'R$ 2 mil, 2 t de soja, BR-2, 3ª vez, de 9 anos, 12 notícias')]:
        if numerais_por_extenso(antes) != depois:
            erros.append(f'numerais por extenso: {numerais_por_extenso(antes)!r}')
    if numerais_por_extenso(_idade_dos_presos(2, [39])) != 'Duas pessoas foram presas; uma delas tem 39 anos.' \
            or _idade_dos_presos(2, [41, 39]) != '2 pessoas, de 39 e 41 anos, foram presas.':
        erros.append('idade dos presos: concordância/posição errada')
    from resumo_fatos import redigir
    if 'de em' in redigir({'orgaos': ['Polícia Civil'], 'apreendido': ['30 porções de'], 'cidades': ['Umuarama']}, '', '', 'PR'):
        erros.append('item cortado na extração não pode deixar preposição solta ("porções de em")')
    if 'de embaladas' in redigir({'orgaos': ['Polícia Militar'], 'apreendido': ['79 porções de embaladas']}, '', '', 'PE'):
        erros.append('adjetivo não leva "de": "79 porções embaladas"')
    # Foto de arquivo (antiga, de outro fato) troca pela foto real de outra fonte (24/11/2026, arsenal no DF).
    from gerar_feed_site import foto_de_arquivo
    from gerar_feed_site import pagina_de_arquivo
    if not pagina_de_arquivo('https://www.gov.br/receitafederal/pt-br/x/apreensao-generico_prancheta.jpg/view') \
            or pagina_de_arquivo('https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/novembro/receita-retem-1-tonelada'):
        erros.append('página de arquivo de imagem do portal não é notícia (e notícia do portal é)')
    if not foto_de_arquivo('https://cdn.x.com.br/wp-content/uploads/2025/12/09183337/op.jpg', '2026-11-24T07:04') \
            or foto_de_arquivo('https://x.com/uploads/images/2026/11/arsenal.jpg', '2026-11-24T15:01') \
            or foto_de_arquivo('https://x.com/foto.jpg', '2026-11-24T15:01'):
        erros.append('foto de arquivo: deveria reconhecer só a foto de mais de 2 meses antes da notícia')
    ar = [dict(mc[0], img='https://a.com/2025/12/arquivo.jpg', _arq=1, d='2026-11-20T10:00'),
          dict(mc[1], img='https://b.com/2026/11/real.jpg', d='2026-11-20T11:00')]
    ar[0].pop('_ofi', None)
    juntas = agrupar_duplicatas(ar)[0]
    if len(juntas) != 1 or juntas[0].get('img') != 'https://b.com/2026/11/real.jpg' or juntas[0].get('_arq'):
        erros.append('a versão exibida deveria trocar a foto de arquivo pela foto real da outra fonte')
    # Condenado citado pelo nome sem idade vira iniciais (24/11/2026).
    from resumo_fatos import anonimizar, nomes_dos_presos
    t = 'A 2ª Vara Criminal condenou Ellen Larissa de Oliveira Silva à pena de cinco anos'
    if 'Ellen' in anonimizar(t, nomes_dos_presos(t)):
        erros.append('nome de condenado deveria virar iniciais')
    t = 'A Vara condenou Vitor Hugo Alves à pena de seis anos de reclusão e Maelson do Carmo Silva a cinco anos'
    if 'Maelson' in anonimizar(t, nomes_dos_presos(t)):
        erros.append('segundo condenado da frase deveria virar iniciais')
    # "1 2 tonelada" (vírgula que virou espaço) = 1,2 t; "1 200 kg" = 1.200 kg (24/11/2026).
    from duplicatas import quantidades_titulo
    if quantidades_titulo('PM rodoviária apreende 1 2 tonelada de maconha') != quantidades_titulo('PM apreende mais de 1,2 tonelada de maconha'):
        erros.append('"1 2 tonelada" deveria ser 1,2 t')
    if '1200' not in quantidades_titulo('PF apreende 1 200 kg de cocaína'):
        erros.append('"1 200 kg" deveria ser 1.200 kg')
    for e in erros:
        print('FALHOU:', e)
    total = len(MESMA) + len(DIFERENTES) + len(AVANCADOS) + 33
    print(f'{total - len(erros)}/{total} casos corretos')
    sys.exit(1 if erros else 0)


if __name__ == '__main__':
    main()
