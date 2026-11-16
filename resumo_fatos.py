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
    casas = 2 if abs(valor) < 100 and round(valor, 2) != round(valor, 1) else 1  # 1,25 t não vira 1,2 t
    return f'{valor:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


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
    ('joias', r'\bjoias\b'), ('mercúrio', r'merc[uú]rio'), ('ouro', r'\bouro\b'),
    ('dragas e balsas de garimpo', r'\bdragas?\b|\bbalsas?\b'), ('mercadorias irregulares', r'mercadorias?'),
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
    for k, parte in enumerate(fontes):  # o título manda; o resto só completa tipos novos
        for item in _itens(parte):
            if k == 2 and re.match(r'1 ', item):
                continue  # "um caminhão" no meio do texto quase nunca é item apreendido
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
    # Órgãos: título, resumo e só o começo do texto (o fim costuma citar a
    # delegacia para onde o caso foi levado, que não é quem fez a apreensão).
    inicio = '. '.join(f for f in (fontes[0], fontes[1], fontes[2][:700]) if f)
    inicio = re.sub(r'(?:encaminhad|conduzid|levad|apresentad)[oa]s?\s+(?:para|à|ao|a)\s+[^.]*', '', inicio)
    for nome, padrao in ORGAOS:
        if re.search(padrao, inicio):
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
    elif (PRESO_UM.search(titulo or '') or PRESO_UM.search(resumo or '')
          or re.search(r'\bpres[oa]s? em flagrante|recebeu voz de pris|foi pres[oa]\b|foram pres[oa]s\b', fontes[2][:2000], re.I)):
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
    fatos.update(detalhes(tudo))
    return fatos


# ---------- detalhes da ação (lidos do corpo da matéria; redigidos pelo Radar) ----------
COMO = [
    ('a partir de uma denúncia', r'den[uú]ncia'),
    ('durante uma fiscalização', r'fiscaliza[çc][ãa]o|\bblitz\b|barreira policial|posto de fiscaliza'),
    ('em uma abordagem', r'abordagem|abordad[oa]s?\b|abordaram|abordou'),
    ('durante patrulhamento', r'patrulhamento|\bronda\b|policiamento ostensivo'),
    ('após investigação', r'investiga[çc][ãa]o|investiga[çc][õo]es|trabalho de intelig[êe]ncia|monitoramento'),
    ('com apoio de cão farejador', r'c[ãa]o farejador|c[ãa]es farejadores|\bK-?9\b|faro do c[ãa]o'),
    ('com uso de escâner', r'esc[âa]ner|scanner|raio-?x'),
    ('após perseguição', r'persegui[çc][ãa]o|tentou fugir|empreendeu fuga|fugiu'),
]
ESCONDERIJO = [
    ('em um fundo falso', r'fundo falso|fundos falsos'),
    ('em um compartimento oculto', r'compartimento(?:s)? (?:oculto|falso|secreto|escondido|adaptado|preparado)'),
    ('no tanque de combustível', r'tanque de combust'),
    ('dentro de pneus', r'dentro (?:dos|de) pneus|\bestepe\b'),
    ('no porta-malas', r'porta-?malas'),
    ('na bagagem', r'\bbagage[mn]s?\b|\bmalas?\b'),
    ('em meio à carga', r'em meio (?:à|a) carga|misturad[oa]s? (?:à|a|com a) carga|sob a carga|entre a carga'),
    ('enterrado', r'enterrad[oa]s?'),
    ('em área de mata', r'\bmata\b|matagal|\bbeira de rio\b'),
    ('no corpo do suspeito', r'presos? ao corpo|junto ao corpo|amarrad[oa]s? ao corpo|nas roupas'),
]
VEICULOS = [('caminhão', r'caminh[ãa]o|carreta|bitrem|rodotrem'), ('ônibus', r'[ôo]nibus'),
            ('caminhonete', r'caminhonete|camionete|picape|pick-?up'), ('carro', r'\bcarro\b|autom[óo]vel|ve[íi]culo de passeio'),
            ('motocicleta', r'motocicleta|\bmoto\b'), ('van', r'\bvan\b'), ('embarcação', r'embarca[çc][ãa]o|\bbarco\b|lancha|balsa'),
            ('aeronave', r'aeronave|avi[ãa]o|monomotor|helic[óo]ptero')]
CRIMES = [
    ('tráfico de drogas', r'tr[áa]fico de (?:drogas|entorpecentes)|tr[áa]fico il[íi]cito'),
    ('associação para o tráfico', r'associa[çc][ãa]o (?:para o|ao) tr[áa]fico'),
    ('porte ilegal de arma de fogo', r'porte ilegal|porte de arma'),
    ('posse ilegal de arma de fogo', r'posse ilegal|posse irregular'),
    ('receptação', r'recepta[çc][ãa]o'),
    ('contrabando', r'contrabando'),
    ('descaminho', r'descaminho'),
    ('lavagem de dinheiro', r'lavagem de (?:dinheiro|capitais)'),
    ('organização criminosa', r'organiza[çc][ãa]o criminosa'),
    ('adulteração de sinal de veículo', r'adultera[çc][ãa]o de sinal'),
    ('crime ambiental', r'crime ambiental|crimes ambientais'),
]
PENAS = {  # pena prevista na lei para o crime principal (para contexto, não é condenação)
    'tráfico de drogas': 'O tráfico de drogas é previsto no artigo 33 da Lei de Drogas (Lei 11.343/2006), com pena de 5 a 15 anos de reclusão.',
    'associação para o tráfico': 'A associação para o tráfico (artigo 35 da Lei 11.343/2006) tem pena de 3 a 10 anos de reclusão.',
    'porte ilegal de arma de fogo': 'O porte ilegal de arma de fogo de uso permitido (artigo 14 do Estatuto do Desarmamento) tem pena de 2 a 4 anos; se a arma for de uso restrito, como fuzis, a pena é de 3 a 6 anos (artigo 16).',
    'posse ilegal de arma de fogo': 'A posse irregular de arma de fogo de uso permitido (artigo 12 do Estatuto do Desarmamento) tem pena de 1 a 3 anos de detenção.',
    'receptação': 'A receptação (artigo 180 do Código Penal) tem pena de 1 a 4 anos de reclusão.',
    'contrabando': 'O contrabando (artigo 334-A do Código Penal) tem pena de 2 a 5 anos de reclusão.',
    'descaminho': 'O descaminho (artigo 334 do Código Penal) tem pena de 1 a 4 anos de reclusão.',
    'lavagem de dinheiro': 'A lavagem de dinheiro (Lei 9.613/1998) tem pena de 3 a 10 anos de reclusão.',
    'organização criminosa': 'Integrar organização criminosa (Lei 12.850/2013) tem pena de 3 a 8 anos de reclusão.',
    'adulteração de sinal de veículo': 'A adulteração de sinal identificador de veículo (artigo 311 do Código Penal) tem pena de 3 a 6 anos de reclusão.',
}
LUGAR = r"([A-ZÁÉÍÓÚÂÊÔÃÕ][\wÀ-ÿ'’-]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕ][\wÀ-ÿ'’-]+){0,3}(?:\s*\([A-Z]{2}\)|/[A-Z]{2})?)"
ORIGEM = re.compile(r'(?:vind[oa]s?|(?:que )?(?:sa[íi]u|sa[íi]ram|partiu|partiram|vinha) d[eoa]s?|que seguia d[eoa]s?|procedente d[eoa]s?|oriund[oa]s? d[eoa]s?|saindo d[eoa]s?)\s+' + LUGAR)
DESTINO = re.compile(r'(?:com destino (?:a|ao|à|para)|que seguia para|seria levad[oa]s? para|levaria (?:a droga|a carga|o material)? ?para|iria para)\s+(?:o |a |os |as )?' + LUGAR)
ENCAMINHAMENTO = re.compile(r'(?:encaminhad|conduzid|levad|apresentad)[oa]s?\s+(?:para|à|ao|a)\s+(?:a\s+|o\s+)?'
                            r'((?:Delegacia|Central de Flagrantes?|Central de Polícia|Polícia Federal|Polícia Civil|Superintendência|Distrito Policial|DP|Plantão|Depol|Deic|Denarc|Unidade)[^.;,\n]{0,70})')
IDADE = re.compile(r'\b(\d{2}) anos\b')
PERIODO = re.compile(r'\b(madrugada|manhã|tarde|noite)\s+(?:dest[ae]|da|do|de)?\s*(?:última\s+)?'
                     r'(segunda|terça|quarta|quinta|sexta|sábado|domingo)(?:-feira)?', re.I)


def detalhes(texto):
    """Como foi a ação, onde estava o material, veículo, rota, crimes e encaminhamento."""
    d = {}
    t = texto or ''
    como = [rotulo for rotulo, p in COMO if re.search(p, t, re.I)]
    if como:
        d['como'] = como[:3]
    esc = [rotulo for rotulo, p in ESCONDERIJO if re.search(p, t, re.I)]
    if esc:
        d['esconderijo'] = esc[:2]
    for nome, p in VEICULOS:
        if re.search(p, t, re.I):
            d['veiculo'] = nome
            break
    m = ORIGEM.search(t)
    if m:
        d['origem'] = m.group(1).strip()
    m = DESTINO.search(t)
    if m and (not d.get('origem') or m.group(1).strip() != d['origem']):
        d['destino'] = m.group(1).strip()
    crimes = [nome for nome, p in CRIMES if re.search(p, t, re.I)]
    if crimes:
        d['crimes'] = crimes[:4]
    m = ENCAMINHAMENTO.search(t)
    if m:
        d['encaminhamento'] = re.sub(r'\s+', ' ', m.group(1)).strip(' -–')
    idades = []
    for m in IDADE.finditer(t[:3000]):
        v = int(m.group(1))
        if 12 <= v <= 90 and v not in idades:
            idades.append(v)
    if idades:
        d['idades'] = idades[:4]
    m = PERIODO.search(t[:1500])
    if m:
        dia = m.group(2).lower()
        d['periodo'] = f'{m.group(1).lower()} de {dia}' + ('' if dia in ('sábado', 'domingo') else '-feira')
    return d


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
