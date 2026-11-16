#!/usr/bin/env python3
"""Resumo do Radar: ficha de fatos e parágrafo próprio, sem IA e sem copiar texto.

Fatos não têm direito autoral; a redação do jornalista tem. Por isso este módulo
extrai só dados objetivos (o que foi apreendido e quanto, onde, quando, quem
atuou, presos, mandados, operação, valor) e escreve com frases do próprio Radar.
O texto original continua disponível pelo link da fonte.

Ordem de confiança: título > resumo da fonte > texto da página.
"""
import re
import unicodedata
from datetime import datetime

from localizar_uf import NOMES_ESTADOS, municipios_no_texto

MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto',
         'setembro', 'outubro', 'novembro', 'dezembro']
NUM = r'(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?'
EXTENSO = {'um': 1, 'uma': 1, 'dois': 2, 'duas': 2, 'três': 3, 'tres': 3, 'quatro': 4, 'cinco': 5, 'seis': 6,
           'sete': 7, 'oito': 8, 'nove': 9, 'dez': 10, 'onze': 11, 'doze': 12, 'treze': 13, 'quatorze': 14,
           'quinze': 15, 'vinte': 20, 'trinta': 30, 'cem': 100}
QTD = rf'(?P<q>{NUM}|{"|".join(EXTENSO)})(?:\s+(?P<mult>milhões|milhão|mil))?'

ORGAOS = [
    ('Polícia Rodoviária Federal', r'\bPRF\b|Pol[ií]cia Rodovi[aá]ria Federal'),
    ('Polícia Federal', r'\bPF\b|Pol[ií]cia Federal'),
    ('Receita Federal', r'Receita Federal'),
    ('Polícia Rodoviária Estadual', r'\bBPRv\b|\bPRE\b|Pol[ií]cia Rodovi[aá]ria Estadual|Comando Rodovi[aá]rio|\bCPRv\b'),
    ('Polícia Militar', r'\bPM(?:-?[A-Z]{2})?\b|Pol[ií]cia Militar|\bBOPE\b|\bROTAM\b|\bRotam\b|\bBPChoque\b|\bCPRaio\b|\bROCAM\b|\bBAEP\b|For[çc]a T[aá]tica'),
    ('Polícia Civil', r'\bPC(?:-?[A-Z]{2})?\b|Pol[ií]cia Civil|\bDENARC\b|\bDenarc\b|\bDRACO\b|\bDEIC\b|\bDHPP\b|\bDelegacia\b'),
    ('Polícia Penal', r'Pol[ií]cia Penal'),
    ('FICCO', r'\bFICCO\b'),
    ('Guarda Municipal', r'Guarda (?:Civil )?Municipal|\bGCM\b'),
    ('Ibama', r'\bIbama\b|\bIBAMA\b'),
    ('Ministério Público', r'Minist[ée]rio P[uú]blico|\bMP-?[A-Z]{2}\b|\bGAECO\b|\bGaeco\b'),
    ('Força Nacional', r'For[çc]a Nacional'),
    ('Marinha', r'\bMarinha\b'),
    ('Exército', r'\bEx[ée]rcito\b'),
]
UNIDADES = (r'toneladas?|tonelada|kg|quilos?|gramas?|g\b|tabletes?|porções|por[çc][õo]es|papelotes?|pinos?|pedras?|'
            r'pés|mudas|unidades|maços|ma[çc]os|pacotes|caixas|fardos|litros|garrafas|cabeças|sacas|sacos|m³|metros cúbicos')
MATERIAL = r'(?:de\s+)?(?P<mat>[a-zà-ú][a-zà-ú\- ]{2,40}?)(?=\s*(?:,|\.|;|\bem\b|\bna\b|\bno\b|\bnas\b|\bnos\b|\bdurante\b|\bapós\b|\bque\b|\bavaliad|\bescondid|\bapreendid|\bencontrad|\blocalizad|\bforam\b|\bé\b|\bsão\b|\bficou\b|\bdentro\b|\bpor\b|\bcom\b|\be\b|$))'
ITEM_PESO = re.compile(rf'{QTD}\s*(?P<u>{UNIDADES})\s+{MATERIAL}', re.I)
CONTAVEIS = (r'armas?(?: de fogo)?|fuzis|fuzil|pistolas?|rev[óo]lveres|rev[óo]lver|espingardas?|carabinas?|metralhadoras?|'
             r'muni[çc][õo]es|cartuchos|carregadores|granadas|explosivos|celulares|aparelhos celulares|ve[ií]culos|carros|'
             r'motocicletas?|motos?|caminh[õo]es|caminhão|carretas?|embarca[çc][õo]es|barcos?|aeronaves?|avi[õo]es|avião|'
             r'animais|aves|p[áa]ssaros|cigarros eletr[ôo]nicos|vapes?|medicamentos|canetas emagrecedoras')
ITEM_CONTAVEL = re.compile(rf'{QTD}\s+(?P<obj>{CONTAVEIS})\b', re.I)
VALOR = re.compile(r'R\$\s?(?P<v>' + NUM + r')(?:\s?(?P<m>milhões|milhão|mil|bilhões|bilhão|mi\b|bi\b))?', re.I)
Q_SIMPLES = rf'({NUM}|{"|".join(EXTENSO)})'
PRESOS = re.compile(rf'(?:pren(?:de|deu|dem)|deté[mn]|detém|detiveram|prisão de)\s+{Q_SIMPLES}\s+(?:pessoas?|homens?|mulheres?|suspeitos?|investigados?|jovens?|integrantes|membros)'
                    rf'|{Q_SIMPLES}\s+(?:pessoas?|homens?|mulheres?|suspeitos?|investigados?|jovens?|integrantes|membros)\s+(?:foram\s+|são\s+|é\s+)?(?:pres[oa]s|detid[oa]s)', re.I)
PRESO_UM = re.compile(r'\b(?:homem|mulher|motorista|jovem|suspeito|suspeita|condutor|passageiro|idoso|casal|dupla|trio)\b[^.]{0,40}?\b(?:é|foi|são|foram)\s+pres[oa]s?\b', re.I)
MANDADOS = re.compile(rf'{QTD}\s+mandados?(?:\s+de\s+(?P<tipo>busca(?: e apreensão)?|prisão))?', re.I)
OPERACAO = re.compile(r'\bOpera[çc][ãa]o\s+(?P<nome>(?:[A-ZÁ-Ú0-9][\wÀ-ÿ\'’-]*)(?:\s+(?:d[aeo]s?\s+)?[A-ZÁ-Ú0-9][\wÀ-ÿ\'’-]*){0,3})')
RODOVIA = re.compile(r'\b(?P<r>(?:BR|[A-Z]{2})-\d{2,3})\b')
GENERICO_MAT = re.compile(r'^(?:drogas?|entorpecentes?|material|produtos?|mercadorias?|itens|objetos?)$', re.I)


def _num(texto, mult=None):
    t = texto.lower()
    if t in EXTENSO:
        valor = float(EXTENSO[t])
    else:
        valor = float(t.replace('.', '').replace(',', '.'))
    if mult:
        valor *= 1_000 if mult.lower() == 'mil' else 1_000_000
    return valor


def _fmt(valor):
    if valor == int(valor):
        return f'{int(valor):,}'.replace(',', '.')
    return f'{valor:,.1f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _limpa_material(mat):
    mat = re.sub(r'\s+', ' ', mat).strip(' -').lower()
    mat = re.sub(r'^(?:de|da|do)\s+', '', mat)
    return mat


SEM_QTD = [  # itens citados sem quantidade: ainda informam o que foi apreendido
    ('fuzil', r'\bfuzil\b|\bfuzis\b'), ('armas de fogo', r'\barmas? de fogo\b|\barmas?\b'),
    ('munições', r'muni[çc][ãõa]o|muni[çc][õo]es'), ('cocaína', r'coca[ií]na'), ('maconha', r'maconha|skunk|sk[ua]nk'),
    ('crack', r'\bcrack\b'), ('drogas', r'\bdrogas?\b|entorpecentes?'), ('cigarros contrabandeados', r'cigarros?'),
    ('dinheiro', r'\bdinheiro\b|em esp[ée]cie'),
    ('celulares', r'celulares?'), ('medicamentos', r'medicamentos?|rem[ée]dios?|anabolizantes?|canetas? emagrecedoras?'),
    ('madeira ilegal', r'madeira'), ('animais silvestres', r'animais silvestres|aves silvestres|p[áa]ssaros'),
    ('joias', r'\bjoias\b'), ('mercadorias irregulares', r'mercadorias?'),
]


def _tipo(item):
    """Classe do item para não repetir (armas/arma de fogo, munições...)."""
    sem_num = re.sub(r'^[\d.,]+\s*(?:mil\s+)?', '', item.lower())
    for nome, padrao in SEM_QTD:
        if re.search(padrao, sem_num):
            return nome
    partes = sem_num.split(' de ', 1)
    return (partes[-1] if len(partes) > 1 else sem_num)[:6]


def _itens(texto):
    itens, vistos = [], set()
    for m in ITEM_PESO.finditer(texto):
        mat = _limpa_material(m.group('mat'))
        if len(mat) < 3 or mat.split()[0] in ('que', 'em', 'na', 'no', 'para'):
            continue
        q = _num(m.group('q'), m.group('mult'))
        unidade = m.group('u').lower().replace('quilos', 'kg').replace('quilo', 'kg')
        chave = (mat.split()[0][:6], unidade[:3])
        if chave in vistos:
            continue
        vistos.add(chave)
        itens.append(f'{_fmt(q)} {unidade} de {mat}')
    for m in ITEM_CONTAVEL.finditer(texto):
        obj = m.group('obj').lower()
        chave = (obj[:5], 'un')
        if chave in vistos:
            continue
        vistos.add(chave)
        itens.append(f'{_fmt(_num(m.group("q"), m.group("mult")))} {obj}')
    return itens


def _valor(texto):
    melhores = []
    for m in VALOR.finditer(texto):
        v = _num(m.group('v'))
        mult = (m.group('m') or '').lower()
        if mult in ('mil',):
            v *= 1_000
        elif mult in ('milhões', 'milhão', 'mi'):
            v *= 1_000_000
        elif mult in ('bilhões', 'bilhão', 'bi'):
            v *= 1_000_000_000
        if v >= 100:
            melhores.append(v)
    if not melhores:
        return ''
    v = max(melhores)
    if v >= 1_000_000_000:
        return f'R$ {_fmt(round(v / 1e9, 1))} bilhões'
    if v >= 1_000_000:
        return f'R$ {_fmt(round(v / 1e6, 1))} milhões' if v >= 2_000_000 else f'R$ {_fmt(round(v / 1e6, 1))} milhão'
    if v >= 1_000:
        return f'R$ {_fmt(round(v / 1e3, 1))} mil'
    return f'R$ {_fmt(v)}'


def extrair(titulo, resumo='', texto=''):
    """Fatos objetivos da notícia. Campos vazios ficam de fora."""
    fontes = [titulo or '', resumo or '', (texto or '')[:6000]]
    tudo = '. '.join(f for f in fontes if f)
    fatos = {}
    itens, tipos = [], set()
    for parte in fontes:  # o título manda; o resto só completa tipos novos
        for item in _itens(parte):
            if _tipo(item) not in tipos:
                tipos.add(_tipo(item))
                itens.append(item)
    for parte in fontes[:2]:  # itens citados sem quantidade (título e resumo)
        for nome, padrao in SEM_QTD:
            if nome not in tipos and re.search(padrao, parte, re.I):
                if nome == 'armas de fogo' and 'fuzil' in tipos and not re.search(r'\barmas?\b', parte, re.I):
                    continue
                tipos.add(nome)
                itens.append('um fuzil' if nome == 'fuzil' and not re.search(r'fuzis', parte, re.I) else nome)
    if 'drogas' in tipos and tipos & {'cocaína', 'maconha', 'crack'}:
        itens = [i for i in itens if i != 'drogas']
    # Genérico sem quantidade ("drogas") só fica se não houver nada mais específico.
    itens = [i for i in itens if re.search(r'\d', i) or not GENERICO_MAT.match(i)] or itens
    if itens:
        fatos['apreendido'] = itens[:6]
    orgaos = []
    for nome, padrao in ORGAOS:
        if re.search(padrao, tudo):
            orgaos.append(nome)
    if orgaos:
        fatos['orgaos'] = orgaos[:3]
    cidades = []
    for parte in (fontes[0], fontes[1], fontes[2][:1500]):
        for nome, uf in municipios_no_texto(parte):
            if (nome, uf) not in cidades:
                cidades.append((nome, uf))
    if cidades:
        fatos['cidades'] = [f'{n} ({u})' for n, u in cidades[:3]]
    rod = RODOVIA.search(titulo or '') or RODOVIA.search(resumo or '') or RODOVIA.search(texto or '')
    if rod and rod.group('r').split('-')[0] in ({'BR'} | set(NOMES_ESTADOS)):
        fatos['rodovia'] = rod.group('r')
    m = PRESOS.search(tudo)
    if m:
        grupos = [g for g in m.groups() if g]
        try:
            fatos['presos'] = int(_num(grupos[0]))
        except (ValueError, IndexError):
            pass
    elif PRESO_UM.search(titulo or '') or PRESO_UM.search(resumo or ''):
        fatos['presos_texto'] = 'houve prisão em flagrante' if 'flagrante' in tudo.lower() else 'houve prisão'
    m = MANDADOS.search(tudo)
    if m:
        try:
            fatos['mandados'] = f'{_fmt(_num(m.group("q"), m.group("mult")))} mandados' + (f' de {m.group("tipo")}' if m.group('tipo') else '')
        except ValueError:
            pass
    m = OPERACAO.search(tudo)
    if m and len(m.group('nome')) > 2:
        fatos['operacao'] = 'Operação ' + m.group('nome').strip()
    valor = _valor(tudo)
    if valor:
        fatos['valor'] = valor
    return fatos


ARTIGO = {'Receita Federal': 'a', 'Ibama': 'o', 'Ministério Público': 'o', 'Exército': 'o', 'FICCO': 'a',
          'Guarda Municipal': 'a', 'Força Nacional': 'a', 'Marinha': 'a'}
PREP_UF = {'AC': 'no', 'AL': 'em', 'AP': 'no', 'AM': 'no', 'BA': 'na', 'CE': 'no', 'DF': 'no', 'ES': 'no', 'GO': 'em',
           'MA': 'no', 'MT': 'em', 'MS': 'em', 'MG': 'em', 'PA': 'no', 'PB': 'na', 'PR': 'no', 'PE': 'em', 'PI': 'no',
           'RJ': 'no', 'RN': 'no', 'RS': 'no', 'RO': 'em', 'RR': 'em', 'SC': 'em', 'SP': 'em', 'SE': 'em', 'TO': 'no'}


def _com_artigo(orgao):
    return f"{ARTIGO.get(orgao, 'a')} {orgao}"


def _juntar(lista):
    return lista[0] if len(lista) == 1 else ', '.join(lista[:-1]) + ' e ' + lista[-1]


def _data_extenso(iso):
    try:
        d = datetime.fromisoformat(str(iso)[:10])
    except ValueError:
        return ''
    return f'{d.day} de {MESES[d.month - 1]} de {d.year}'


def redigir(fatos, fonte='', data_iso='', uf=''):
    """Parágrafo do Radar a partir dos fatos. Nunca copia frases da fonte."""
    if not fatos:
        return ''
    orgaos = fatos.get('orgaos', [])
    sujeito = _juntar([_com_artigo(o) for o in orgaos]) if orgaos else 'as forças de segurança'
    sujeito = sujeito[0].upper() + sujeito[1:]
    plural = len(orgaos) > 1 or not orgaos
    frases = []
    local = ''
    if fatos.get('cidades'):
        local = f' em {_juntar(fatos["cidades"])}'
    elif uf in NOMES_ESTADOS:
        local = f' {PREP_UF[uf]} {NOMES_ESTADOS[uf]}'
    if fatos.get('rodovia'):
        local += f', na rodovia {fatos["rodovia"]}'
    quando = _data_extenso(data_iso)
    quando = f', em notícia publicada em {quando}' if quando else ''
    itens = fatos.get('apreendido', [])
    if any(re.search(r'\d', i) for i in itens):
        verbo = 'apreenderam' if plural else 'apreendeu'
        frases.append(f'{sujeito} {verbo} {_juntar(itens)}{local}{quando}.')
    elif itens:  # sem quantidade: descreve sem afirmar o tamanho da apreensão
        verbo = 'participaram' if plural else 'participou'
        frases.append(f'{sujeito} {verbo} de uma ação envolvendo {_juntar(itens)}{local}{quando}.')
    else:
        verbo = 'realizaram' if plural else 'realizou'
        frases.append(f'{sujeito} {verbo} uma ação com apreensões{local}{quando}.')
    if fatos.get('operacao'):
        frases.append(f'A ação fez parte da {fatos["operacao"]}.')
    if fatos.get('mandados'):
        frases.append(f'Foram cumpridos {fatos["mandados"]}.')
    if fatos.get('presos'):
        n = fatos['presos']
        frases.append('Uma pessoa foi presa.' if n == 1 else f'{_fmt(n)} pessoas foram presas.')
    elif fatos.get('presos_texto'):
        frases.append(f'Segundo a reportagem, {fatos["presos_texto"]}.')
    if fatos.get('valor'):
        frases.append(f'Os valores citados chegam a {fatos["valor"]}.')
    if fonte:
        frases.append(f'As informações foram publicadas por {fonte}; a íntegra está no link da reportagem.')
    return ' '.join(frases)


if __name__ == '__main__':
    exemplos = [
        ('BPRv apreende 300 garrafas de vinho estrangeiro na PR-323, em Cruzeiro do Oeste',
         'Policiais do Batalhão de Polícia Rodoviária abordaram um carro e encontraram as garrafas sem nota fiscal. O motorista foi preso.'),
        ('PRF apreende 1,1 tonelada de maconha, 608 kg de cocaína e 10 pistolas na BR-163 em Dourados', ''),
        ('Operação Lado A: 71 kg de cocaína apreendidos na Grande Florianópolis; sete pessoas são presas', ''),
        ('PF deflagra Operação Metamorfo e cumpre 21 mandados de busca contra tráfico em Teresina', 'Bens avaliados em R$ 3,5 milhões foram bloqueados.'),
    ]
    for t, r in exemplos:
        f = extrair(t, r)
        print(f)
        print(' ->', redigir(f, 'G1', '2026-11-14T10:00:00', 'PR'))
        print()
