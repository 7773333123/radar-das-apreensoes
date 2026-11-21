#!/usr/bin/env python3
"""Agrupa a mesma notícia publicada mais de uma vez (mesmo veículo ou vários).

Métrica: cada par de notícias recebe evidências independentes, e é a mesma
notícia quando uma regra forte é satisfeita sem nenhum veto.

Evidências
  T  título: palavras em comum (Jaccard) ou título contido no outro
     (palavras informativas: lugares, objetos, nomes, números);
  L  abertura/resumo da fonte: trechos de 5 palavras em comum (Jaccard);
  F  fatos: mesmas quantidades apreendidas (830 kg de maconha) no mesmo estado;
  I  imagem: impressão digital visual da foto (dHash, hash_imagens.py) a até
     8 bits de distância, ignorando fotos genéricas (logotipos, arte padrão);
  Δ  dias entre as publicações (até 7).

Regras (qualquer uma basta)
  1. título igual (mais de 25 letras), em qualquer data; ou o mesmo resumo da
     fonte (140 primeiras letras) com até 3 dias;
  2. T forte com até 1 dia de diferença (regra original);
  3. T forte com até 7 dias e mais uma evidência: o mesmo número (>= 10 ou
     com decimais) e um lugar/nome em comum, ou L >= 0,25, ou I;
  4. L >= 0,45 com até 7 dias (o mesmo release republicado);
  5. I com até 7 dias e mais uma evidência de texto: lugar/nome em comum ou
     a mesma quantidade;
  6. F com até 3 dias, mesmo estado e um lugar/nome em comum (não vale só
     "quilos" ou "maconha");
  7. grande apreensão (>= 300 kg de droga, 20 armas, 5 fuzis, 1.000 munições)
     do mesmo material com valores a até 20% (arredondamentos), até 4 dias,
     mesmo estado ou um lugar/nome em comum.

Vetos (prevalecem sobre tudo)
  - estados diferentes;
  - quantidades do título diferentes ("três presos" x "dois presos");
  - o grupo resultante juntaria estados diferentes (evita correntes A~B~C).
"""
import re
import unicodedata
from datetime import date
from functools import lru_cache

JANELA = 7
PALAVRAS_VAZIAS = set('''para pela pelo pelos pelas com sem sobre apos após entre durante contra como mais menos
    que uma umas uns dos das nos nas aos este esta esse essa isso isto pode podem diz afirma'''.split())
# Palavras de quase toda notícia policial: não ajudam a dizer se é o mesmo fato.
GENERICAS = set('''policia policias policial policiais militar militares civil federal rodoviaria
    apreende apreendem apreendeu apreendido apreendida apreendidos apreendidas apreensao apreensoes
    prende prendem prendeu preso presa presos presas prisao flagrante suspeito suspeitos suspeita
    homem mulher jovem jovens adolescente pessoas dupla trio operacao acao durante cerca mais
    droga drogas trafico traficante bairro cidade regiao estado'''.split())
EXTENSO = {'um': '1', 'uma': '1', 'dois': '2', 'duas': '2', 'tres': '3', 'quatro': '4', 'cinco': '5', 'seis': '6',
           'sete': '7', 'oito': '8', 'nove': '9', 'dez': '10', 'onze': '11', 'doze': '12', 'treze': '13',
           'quatorze': '14', 'catorze': '14', 'quinze': '15', 'vinte': '20', 'trinta': '30', 'cem': '100'}
ANOS = {str(a) for a in range(2000, 2031)}


# Sinônimos de manchete: o mesmo fato escrito por veículos diferentes ("moto" x "motocicleta").
SINONIMOS = {'motocicleta': 'moto', 'motocicletas': 'motos', 'automovel': 'carro', 'automoveis': 'carros',
             'caminhonetes': 'caminhonete', 'camionete': 'caminhonete', 'pickup': 'caminhonete',
             'municoes': 'municao', 'skank': 'skunk', 'cigarros': 'cigarro'}


def normal(texto):
    texto = texto or ''
    # Títulos e trechos curtos ficam em memória; textos longos (reportagem) são calculados na hora.
    return _normal(texto) if len(texto) <= 400 else _normal.__wrapped__(texto)


# Funções puras chamadas milhões de vezes por geração (as mesmas manchetes em cada par):
# o resultado fica em memória; quem recebe um conjunto recebe uma cópia.
@lru_cache(maxsize=300000)
def _normal(texto):
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(c for c in texto if not unicodedata.combining(c)).lower()
    return ' '.join(SINONIMOS.get(w, w) for w in re.sub(r'[^a-z0-9]+', ' ', texto).split())


def palavras(texto):
    return {w for w in normal(texto).split() if len(w) > 3 and w not in PALAVRAS_VAZIAS}


def informativas(texto):
    saida = {n for n in numeros(texto) if len(n.replace('.', '')) >= 2}
    for w in normal(texto).split():
        if not w.isdigit() and len(w) > 3 and w not in PALAVRAS_VAZIAS and w not in GENERICAS:
            saida.add(w)
    return saida


NUMERO = re.compile(r'\d+(?:[.,]\d+)*')
# Unidades e materiais: comuns a muitas notícias diferentes; não identificam o fato.
MATERIAIS = set('''quilos quilo kg toneladas tonelada gramas porcoes porcao tabletes tablete pinos pedras
    maconha cocaina skunk crack haxixe pasta base armas arma fogo municoes municao fuzil fuzis pistola pistolas
    revolver espingardas cigarros celulares veiculo veiculos carro caminhao carreta onibus moto motocicleta
    mercadorias dinheiro reais valor avaliada avaliado avaliadas avaliados mil milhao milhoes'''.split())
# Drogas/objetos citados no título: duas notícias com materiais diferentes e sem nenhum em
# comum (600 kg de maconha x 540 kg de cocaína) não são o mesmo fato.
MATERIAL_TITULO = [('maconha', r'maconha|skunk|supermaconha|haxixe|cannabis'), ('cocaina', r'coca[ií]na|pasta[ -]base|crack'),
                   ('armas', r'armas?|fuzis|fuzil|pistolas?|rev[óo]lver(?:es)?|espingardas?|muni[çc](?:[ãa]o|[õo]es)'),
                   ('cigarros', r'cigarros?|vapes?|ma[çc]os'), ('dinheiro', r'dinheiro|reais|d[óo]lares'),
                   ('medicamentos', r'medicamentos?|emagrecedor(?:es)?|anabolizantes?|canetas?'),
                   ('veiculos', r've[íi]culos?|carros?|caminh[ãa]o|carreta|caminhonete|motos?|motocicleta')]


def materiais_titulo(t):
    return set(_materiais_titulo(t or ''))


@lru_cache(maxsize=300000)
def _materiais_titulo(t):
    return frozenset(nome for nome, padrao in MATERIAL_TITULO if re.search(r'\b(?:' + padrao + r')\b', t, re.I))


def numeros(texto):
    """Números do título como valores: "1.500" -> 1500, "16,5" -> 16.5 (sem anos)."""
    saida = set()
    texto = texto or ''
    for m in NUMERO.finditer(texto):
        t = m.group(0)
        antes, depois = texto[max(0, m.start() - 4):m.start()], texto[m.end():m.end() + 1]
        # Rodovias (BR-277, MS-164) e ordinais (10º BPM) não são quantidades.
        if re.search(r'(?:\b[A-Z]{2,3}-|\bBR\s)$', antes) or depois in ('º', 'ª', '°'):
            continue
        if re.fullmatch(r'\d{1,3}(?:\.\d{3})+', t):
            t = t.replace('.', '')
        t = t.replace('.', '').replace(',', '.') if ',' in t else t
        try:
            v = float(t)
        except ValueError:
            continue
        if t in ANOS:
            continue
        mult = re.match(r'\s*(mil\b|milh[õo]es|milh[ãa]o|bilh[õo]es|bilh[ãa]o)', texto[m.end():m.end() + 12], re.I)
        if mult:  # "2,6 mil" = 2.600
            v *= 1e3 if mult.group(1).lower() == 'mil' else (1e6 if mult.group(1).lower().startswith('milh') else 1e9)
        saida.add(f'{v:g}')
    return saida


def quantidades_titulo(texto):
    """Quantidades citadas no título (números e por extenso: "uma" -> 1)."""
    return set(_quantidades_titulo(texto or ''))


@lru_cache(maxsize=300000)
def _quantidades_titulo(texto):
    saida = numeros(texto)
    for w in normal(texto).split():
        if w in EXTENSO:
            saida.add(EXTENSO[w])
    return saida


def compativeis(qa, qb):
    """Algum número de um título bate com o do outro (1,3 t ~ "uma tonelada"; 236 ~ "mais de 236")."""
    for x in qa:
        for y in qb:
            fx, fy = float(x), float(y)
            if int(fx) == int(fy) or abs(fx - fy) <= 0.1 * max(fx, fy):
                return True
    return False


def numeros_fortes(texto):
    """Números que identificam o fato: >= 10 ou com casas decimais (52 kg, 4,5 t)."""
    return {n for n in numeros(texto) if float(n) >= 10 or '.' in n}


def mesma_materia(pa, pb, ia, ib, qa=frozenset(), qb=frozenset(), mesmo_uf=False):
    """Evidência T (forte) entre dois títulos. pa/pb: palavras; ia/ib: informativas; qa/qb: quantidades."""
    if qa and qb and not compativeis(qa, qb):
        return False
    comum = len(pa & pb)
    if comum >= 4 and comum / len(pa | pb) >= 0.65:
        return True
    inf = len(ia & ib)
    numero_comum = (bool(qa and qb) and compativeis(qa, qb)) or any(w[0].isdigit() for w in ia & ib)
    return (inf >= 3 and inf / max(1, min(len(ia), len(ib))) >= 0.75 and (mesmo_uf or numero_comum)
            and (inf >= 4 or numero_comum))


# Operação com nome próprio ("3ª fase da Operação Lastro Oculto"): o nome identifica o fato.
OPERACAO_NOME = re.compile(r'\bOpera[çc][ãa]o\s+(?P<nome>[A-ZÁ-Ú][\wÀ-ÿ\'’-]*(?:\s+(?:d[aeo]s?\s+)?[A-ZÁ-Ú0-9][\wÀ-ÿ\'’-]*){0,3})')
FASE = re.compile(r'\b(\d{1,2})\s*[ªºa]?\s*fase\b|\b(primeira|segunda|terceira|quarta|quinta|sexta|s[ée]tima|oitava|nona|d[ée]cima)\s+fase\b', re.I)
FASE_EXTENSO = {'primeira': '1', 'segunda': '2', 'terceira': '3', 'quarta': '4', 'quinta': '5', 'sexta': '6',
                'setima': '7', 'sétima': '7', 'oitava': '8', 'nona': '9', 'decima': '10', 'décima': '10'}
# Palavras que não são nome de operação ("Operação Policial", "Operação Conjunta da PF").
NAO_NOME = set('''policial policiais conjunta integrada especial pf prf pm pc gaeco ficco dof bprv da do de em na no
    nesta neste nessa nesse contra que deflagrada realizada pcpr pmpr bpfron gefron receita'''.split())
# Operações permanentes: cada apreensão delas é um fato diferente.
PERMANENTES = set('''horus agata muralha fronteira sentinela verao carnaval tiradentes natal rodovida egide protetor
    oeste seguro brasil impacto saturacao narco divisas integrada finados feriado pascoa reveillon ano novo
    independencia proclamacao carnaval semana santa ferias escola segura'''.split())
JUDICIAL = re.compile(r'\b(?:justi[çc]a|juiz|ju[íi]za|TRF|STF|STJ|TJ[A-Z]{0,2}|anula|condena|absolv|r[ée]us?\b|den[úu]ncia|julgament|habeas|soltur|solto|liberad)', re.I)


def operacoes(texto):
    """{(nome normalizado, fase)} das operações citadas; fase '' quando não dita."""
    texto = texto or ''
    fases = set()
    for m in FASE.finditer(texto):
        fases.add(m.group(1) or FASE_EXTENSO.get(m.group(2).lower(), ''))
    fase = next(iter(fases)) if len(fases) == 1 else ''
    saida = set()
    for m in OPERACAO_NOME.finditer(texto):
        palavras_nome = normal(m.group('nome')).split()
        for k, w in enumerate(palavras_nome):  # "Hórus da PRF" = "Hórus"
            if k and w in ('da', 'do', 'de', 'das', 'dos') and k + 1 < len(palavras_nome) and palavras_nome[k + 1] in NAO_NOME:
                palavras_nome = palavras_nome[:k]
                break
        while palavras_nome and palavras_nome[-1] in ('da', 'do', 'de', 'das', 'dos'):
            palavras_nome.pop()
        if not palavras_nome or palavras_nome[0] in NAO_NOME or palavras_nome[0] in PERMANENTES:
            continue
        nome = ' '.join(palavras_nome)
        if len(nome) >= 4:
            saida.add((nome, fase))
    return saida


def _mini(texto):
    """'v12:<base64>' -> (12, bytes) ou None."""
    import base64
    try:
        tam, dados = texto.split(':', 1)
        return int(tam[1:]), base64.b64decode(dados)
    except (ValueError, AttributeError):
        return None


def _correlacao(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va < n * 100 or vb < n * 100:  # imagem quase lisa (fundo, logotipo, foto escura): não identifica
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) ** 0.5


def _melhor_encaixe(ma, mb, vertical):
    """Maior correlação entre duas miniaturas deslizando uma sobre a outra (recorte de
    cima/baixo ou dos lados da mesma foto). Sobreposição mínima: 40% da menor e 5 linhas."""
    (na, da), (nb, db) = ma, mb
    lado = 16
    if len(da) != na * lado or len(db) != nb * lado:
        return 0.0

    def faixa(dados, n, ini, fim):  # linhas (vertical) ou colunas (horizontal) ini..fim
        if vertical:
            return dados[ini * lado:fim * lado]
        return bytes(dados[r * n + c] for r in range(lado) for c in range(ini, fim))

    minimo = max(6, int(0.5 * min(na, nb)))
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:
        A = np.frombuffer(da, dtype=np.uint8).astype(np.float32).reshape(na, lado) if vertical else \
            np.frombuffer(da, dtype=np.uint8).astype(np.float32).reshape(lado, na).T
        B = np.frombuffer(db, dtype=np.uint8).astype(np.float32).reshape(nb, lado) if vertical else \
            np.frombuffer(db, dtype=np.uint8).astype(np.float32).reshape(lado, nb).T
        melhor = 0.0
        for desl in range(-(nb - minimo), na - minimo + 1):
            ia, ib = max(0, desl), max(0, -desl)
            tam = min(na - ia, nb - ib)
            if tam < minimo:
                continue
            x = A[ia:ia + tam].ravel()
            y = B[ib:ib + tam].ravel()
            x = x - x.mean()
            y = y - y.mean()
            vx, vy = float((x * x).sum()), float((y * y).sum())
            if vx < x.size * 100 or vy < y.size * 100:
                continue
            melhor = max(melhor, float((x * y).sum()) / (vx * vy) ** 0.5)
        return melhor
    melhor = 0.0
    for desl in range(-(nb - minimo), na - minimo + 1):
        ia, ib = max(0, desl), max(0, -desl)
        tam = min(na - ia, nb - ib)
        if tam < minimo:
            continue
        melhor = max(melhor, _correlacao(faixa(da, na, ia, ia + tam), faixa(db, nb, ib, ib + tam)))
    return melhor


def mesma_foto_recortada(ma, mb, limiar=0.95):
    """A mesma foto, mesmo recortada de outro jeito por cada veículo."""
    if not ma or not mb:
        return False
    for k, vertical in ((0, True), (1, False)):
        a, b = _mini(ma[k]), _mini(mb[k])
        if a and b and _melhor_encaixe(a, b, vertical) >= limiar:
            return True
    return False


def radical(w):
    """rodoviária/rodoviário/rodoviárias -> rodoviari (gênero e número)."""
    if len(w) > 5:
        w = re.sub(r'(?:as|os|es|a|o|s)$', '', w)
    return w


# ---------------------------------------------------------------------------
# Auditor de duplicatas: as regras acima exigem uma evidência forte; o auditor soma
# evidências fracas e independentes de cada par recente (título pelo radical, abertura
# da reportagem, foto, cidade do fato, órgão, quantidades, operação, horário) e junta
# quando a nota passa de JUNTAR. Pares entre DUVIDA e JUNTAR vão para SUSPEITAS
# (relatório para revisão), sem juntar.
JUNTAR = 5.0
DUVIDA = 4.0
SUSPEITAS = []
JUNTADAS = []  # diagnóstico: pares juntados pelo auditor e os motivos
# Decisões do juiz de IA (juiz_duplicatas.py) sobre os pares em dúvida: "mesmo" junta,
# "diferente" tira da lista de dúvidas. Chave: "<menor id>-<maior id>".
JUIZ = None


def decisoes_juiz():
    global JUIZ
    if JUIZ is None:
        try:
            import json as _json
            from pathlib import Path as _P
            JUIZ = {}
            # juiz_decisoes.json e um arquivo por juiz em paralelo (juiz_decisoes_<n>.json).
            # Para o mesmo par vale a decisão mais recente (o juiz revê as dúvidas a cada versão).
            for arq in sorted(_P(__file__).resolve().parent.glob('juiz_decisoes*.json')):
                for k, v in _json.loads(arq.read_text(encoding='utf-8')).get('decisoes', {}).items():
                    if k not in JUIZ or v.get('em', '') >= JUIZ[k].get('em', ''):
                        JUIZ[k] = v
        except Exception:
            JUIZ = {}
    return JUIZ


def chave_par(ia, ib):
    ia, ib = sorted((str(ia), str(ib)), key=lambda x: (len(x), x))
    return f'{ia}-{ib}'
VAZIAS_AUDITOR = PALAVRAS_VAZIAS | set('''policia policias policial policiais militar militares civil federal
    apreende apreendem apreendeu apreendido apreendida apreendidos apreendidas apreensao apreensoes
    prende prendem prendeu preso presa presos presas prisao suspeito suspeitos suspeita durante
    acao operacao cerca mais apos seguida estado cidade regiao bairro homem mulher jovem jovens dupla trio
    casal adolescente adolescentes menor menores pessoas individuo trafico drogas droga entorpecentes porte
    ilegal flagrante posse arma armas fogo municoes municao detido detida detidos conduzido abordagem
    ocorrencia denuncia anonima suspeita investigado investigada dois duas tres quatro cinco grande quantidade
    durante contra pela pelo para após tem sao foi foram tenta tentou acaba acabou termina terminou
    pm prf pf pc gcm bm dof pmce pmpr pcpr pmerj pmesp pmmg pmdf pcdf bope rotam choque forca tatica'''.split())


def radicais_titulo(texto):
    texto = re.sub(r'pol[ií]cia rodovi[aá]ria(?: federal| estadual)?', ' ', texto or '', flags=re.I)
    return {radical(w) for w in normal(texto).split() if len(w) > 2 and w not in VAZIAS_AUDITOR}


BAIRRO = re.compile(r'\b(?i:jardim|vila|bairro|conjunto|parque|residencial|loteamento|n[úu]cleo|setor)\s+((?:[A-ZÀ-Ý][\wÀ-ÿ]*\s*){1,3})')


def bairro(titulo):
    m = BAIRRO.search(titulo or '')
    return normal(m.group(1)) if m else ''


GENERICAS_FOTO = set('''esquema esquemas lavagem dinheiro contrabando descaminho investiga investigacao mira grupo
    organizacao criminosa criminosas faccao mandados mandado cumpre deflagra fase nova operacao conjunta integrada
    suspeito suspeitos envolvidos empresa empresas documentos ligam liga'''.split())


# Palavras de avisos de órgãos reguladores (Anvisa etc.): comuns a decisões diferentes.
REGULACAO = {radical(w) for w in '''anvisa determina proibe proibicao manda apreender apreensao comercializacao venda
    vendidos vendidas lotes produtos produto marcas marca populares internet suspende suspensao recolhimento
    uso irregular irregulares'''.split()}


MATERIAIS_RAD = None


def palavras_proprias_foto(titulo):
    global MATERIAIS_RAD
    if MATERIAIS_RAD is None:
        MATERIAIS_RAD = {radical(m) for m in MATERIAIS | GENERICAS_FOTO} | {'quil', 'tonelad', 'meia', 'cerca', 'mais'}
    return {w for w in radicais_titulo(titulo) if not w.isdigit() and w not in MATERIAIS_RAD}


def nomes_proprios(titulo):
    """Palavras com inicial maiúscula fora do começo do título (lugares, nomes), pelo radical.
    Siglas (PM, PRF) e órgãos ficam de fora; título todo em maiúsculas não conta."""
    palavras_t = re.findall(r"[A-Za-zÀ-ÿ][\wÀ-ÿ'’-]*", titulo or '')
    if not palavras_t or sum(w.isupper() for w in palavras_t) > len(palavras_t) / 2:
        return set()
    saida = set()
    for w in palavras_t[1:]:
        if w[0].isupper() and not w.isupper():
            nw = normal(w)
            if len(nw) > 2 and nw not in VAZIAS_AUDITOR and nw not in ('rodoviaria', 'receita', 'guarda', 'municipal', 'gaeco', 'ficco'):
                saida.add(radical(nw))
    return saida


_LUGARES = None
# Nomes próprios comuns que não identificam um fato (facções, países, regiões, meses).
NOMES_COMUNS = set('''comando vermelho primeiro capital terceiro puro brasil paraguai bolivia colombia peru argentina
uruguai venezuela china estados unidos europa africa norte sul nordeste sudeste centro oeste regiao metropolitana
janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro natal carnaval pascoa
operacao fase nova deus sao santa santo dom'''.split())


def lugares():
    """Radicais das palavras dos nomes de municípios e estados (não distinguem um fato de outro)."""
    global _LUGARES
    if _LUGARES is None:
        _LUGARES = set()
        try:
            import json as _json
            from pathlib import Path as _P
            mun = _json.loads((_P(__file__).resolve().parent / 'municipios.json').read_text(encoding='utf-8'))
            nomes = [c for lista in mun.values() for c in (lista if isinstance(lista, list) else list(lista))]
        except Exception:
            nomes = []
        estados = '''acre alagoas amapa amazonas bahia ceara distrito federal espirito santo goias maranhao mato grosso
        minas gerais para paraiba parana pernambuco piaui rio janeiro grande norte sul rondonia roraima santa catarina
        sao paulo sergipe tocantins'''.split()
        for nome in nomes + estados:
            for w in normal(str(nome)).split():
                if len(w) > 2:
                    _LUGARES.add(radical(w))
        global _MUNICIPIOS
        _MUNICIPIOS = frozenset(_LUGARES)
        _LUGARES |= {radical(w) for w in NOMES_COMUNS}
    return _LUGARES


_MUNICIPIOS = None


def municipios():
    """Radicais das palavras dos nomes de municípios e estados (sem os nomes comuns)."""
    lugares()
    return _MUNICIPIOS


LOCAL_ANTES = set('''no na nos nas em bairro conjunto residencial complexo beco comunidade morro favela vila jardim
parque loteamento setor presidio penitenciaria aldeia distrito rua avenida rodovia'''.split())


def nomes_raros(titulo):
    """Nomes próprios do título que identificam o fato (pessoa, empresa, filme), sem lugares:
    fora cidades/estados/países e nomes que vêm depois de "no", "na", "bairro", "complexo"..."""
    validos = nomes_proprios(titulo)
    if not validos:
        return set()
    saida, local, anterior = set(), False, ''
    for w in re.findall(r"[A-Za-zÀ-ÿ][\wÀ-ÿ'’-]*", titulo):
        nw = normal(w)
        if w[0].isupper():
            if not local and anterior not in ('',) and normal(anterior) in LOCAL_ANTES:
                local = True  # começa um nome de lugar
            if not local and radical(nw) in validos:
                saida.add(radical(nw))
        elif nw not in ('do', 'da', 'de', 'dos', 'das'):
            local = False  # palavra comum: termina a sequência de nome
        anterior = w
    return saida - lugares()


def _numero(w):
    try:
        return float(w)
    except ValueError:
        return None


def nota_par(a, b, ra, rb, inf_a, inf_b, qa, qb, sha, shb, ha, hb, gen_a, gen_b):
    # qa/qb: quantidades do título (conjuntos); as do item (_q, dicionário) vêm de a/b.
    """Nota de 'mesma notícia' e os motivos. None = veto (fatos incompatíveis)."""
    if qa and qb and not compativeis(qa, qb):
        return None, [], 0
    ca, cb = a.get('_cid'), b.get('_cid')
    if ca and cb and ca != cb:
        return None, [], 0  # cidades do fato diferentes: fatos diferentes
    ma, mb = materiais_titulo(a['t']), materiais_titulo(b['t'])
    if ma and mb and not (ma & mb):
        return None, [], 0  # materiais diferentes nos títulos
    ba, bb = bairro(a['t']), bairro(b['t'])
    if ba and bb and ba != bb:
        return None, [], 0  # bairros diferentes (Jardim São Manoel x Jardim Primavera)
    na_ = a['_np'] if '_np' in a else nomes_proprios(a['t'])
    nb_ = b['_np'] if '_np' in b else nomes_proprios(b['t'])
    if na_ and nb_ and not (na_ & nb_):
        return None, [], 0  # lugares/nomes diferentes nos títulos (Barra do Choça x Irecê)
    nota, motivos = 0.0, []
    palavras_proprias_foto('')  # garante MATERIAIS_RAD
    ra = {w for w in ra if w not in MATERIAIS_RAD}
    rb = {w for w in rb if w not in MATERIAIS_RAD}
    comuns = ra & rb
    jac = len(comuns) / max(1, len(ra | rb))
    fortes = 0  # evidências independentes e fortes; para juntar, ao menos duas
    if jac:
        nota += 5 * jac
        motivos.append(f'título {jac:.2f}')
        fortes += jac >= 0.35
    proprias = {w for w in comuns if not w.isdigit()}
    if proprias:
        nota += 0.6 * min(len(proprias), 3)
    if ca and ca == cb:
        nota += 1.5
        motivos.append('mesma cidade')
        # Mesma cidade + título parecido com ao menos duas palavras próprias em comum além
        # do nome da cidade (Idosa ... filho ... Unei): evidência forte.
        cidade = radicais_titulo(ca)
        especificas = {w for w in comuns if not w.isdigit() and w not in cidade}
        mesmo_veiculo = bool(a.get('f')) and a.get('f') == b.get('f')  # o mesmo site repete o padrão de título
        if len(especificas) >= 2 and jac >= 0.3 and not mesmo_veiculo:
            fortes += 1
            motivos.append('título específico na mesma cidade')
    # Dois ou mais nomes próprios raros em comum no título (filme "Dark Horse", nome de
    # empresa ou pessoa), fora cidades, estados, países e facções: o mesmo fato.
    nomes_r = nomes_raros(a['t']) & nomes_raros(b['t'])
    if nomes_r:  # nome de operação já conta como "mesma operação": não conta duas vezes
        # Só a operação citada nas duas (essa já conta como "mesma operação").
        ops_t = (a['_ops'] if '_ops' in a else {x for x, _ in operacoes(a['t'])}) & \
            (b['_ops'] if '_ops' in b else {x for x, _ in operacoes(b['t'])})
        nomes_r -= {radical(w) for x in ops_t for w in x.split()}
    if len(nomes_r) >= 2 and jac >= 0.5 and not (a.get('f') and a.get('f') == b.get('f')):
        nota += 1
        fortes += 1
        motivos.append('mesmos nomes próprios')
    numeros = {w for w in (inf_a & inf_b) if w[0].isdigit() and w not in ANOS and _numero(w) is not None
               and (_numero(w) >= 100 or _numero(w) != int(_numero(w)))}
    if numeros:
        nota += 2
        fortes += 1
        motivos.append('mesmo número')
        # Número incomum (decimal ou não redondo: 2,3 milhões, 734 munições) na mesma cidade:
        # duas evidências independentes do mesmo fato.
        if ca and ca == cb and any('.' in w or _numero(w) % 100 for w in numeros):
            fortes += 1
            motivos.append('número incomum na mesma cidade')
    aga, agb = set(a.get('_ag') or ()), set(b.get('_ag') or ())
    if aga and agb:
        nota += 0.7 if aga & agb else -0.7
    if a.get('_q') and b.get('_q') and _mesmas_quantidades(a['_q'], b['_q']):
        nota += 2.5
        motivos.append('mesmas quantidades')
        fortes += 1
    # Abertura igual no mesmo veículo costuma ser bloco fixo do site: não conta.
    lead = 0.0 if (a.get('f') and a.get('f') == b.get('f')) else jaccard(sha, shb)
    if lead >= 0.08:
        nota += min(3.0, 10 * lead)
        motivos.append(f'abertura {lead:.2f}')
        fortes += lead >= 0.12
    if ha is not None and hb is not None and not (gen_a or gen_b) and (ha ^ hb).bit_count() <= 10:
        nota += 3
        motivos.append('mesma foto')
        fortes += 1
    if (a.get('uf') and a.get('uf') == b.get('uf')) and (b.get('img') and b['img'] in (a.get('_iguais') or ())
                                                       or a.get('img') and a['img'] in (b.get('_iguais') or ())):
        nota += 3
        motivos.append('mesma foto recortada')
        fortes += 1
    opa = a['_ops'] if '_ops' in a else {x for x, _ in operacoes(a['t'] + ' . ' + a.get('_lead', ''))}
    opb = b['_ops'] if '_ops' in b else {x for x, _ in operacoes(b['t'] + ' . ' + b.get('_lead', ''))}
    if opa & opb:
        nota += 2
        motivos.append('mesma operação')
        fortes += 1
    elif opa and opb:
        nota -= 2  # operações com nomes diferentes
    motivos.append(f'{fortes} fortes')
    return nota, motivos, fortes


def titulo_sem_veiculo(it):
    """Título sem o nome do veículo acrescentado no fim (" - Fonte - slogan")."""
    t, f = it.get('t') or '', (it.get('f') or '').strip()
    if len(f) >= 4:
        k = t.find(' - ' + f)
        if k < 0:
            k = t.find(' | ' + f)
        if k > 20:
            return t[:k]
    return t


@lru_cache(maxsize=200000)
def _q_titulo(t):
    from estatisticas import quantidades
    from resumo_fatos import extrair
    return tuple(sorted((k, v) for k, v in quantidades(extrair(t)).items() if k != 'val'))


def q_titulo(t):
    """Quantidade por material citada só no título ({'mac': 2000.0}); o resumo fica de fora."""
    return dict(_q_titulo(t or ''))


def quantidades_em_conflito(qa, qb):
    """Quantidade do MESMO material muito diferente: 2 t x 6 t de maconha.
    Tolera 25%, e até 1,5 vez quando o menor é número redondo ("mais de uma tonelada" x
    1,4 tonelada; "mais de 100 armas" x 118 armas)."""
    qa, qb = _familia(qa), _familia(qb)
    for m in set(qa) & set(qb):
        menor, maior = sorted((qa[m], qb[m]))
        if maior - menor <= 0.25 * maior:
            continue
        if menor > 0 and _redondo(menor) and maior <= 1.5 * menor:
            continue
        return True
    return False


# Skunk/skank é maconha: 1 kg de skank x 15 kg de maconha é contradição (Sobral, 17 x 18/11/2026).
FAMILIA_MATERIAL = {'skh': 'mac'}


def _familia(q):
    saida = {}
    for k, v in (q or {}).items():
        f = FAMILIA_MATERIAL.get(k, k)
        saida[f] = max(saida.get(f, 0), v)
    return saida


def _redondo(v):
    """1, 2, 10, 100, 1.000, 2.000 (um algarismo significativo): número arredondado."""
    v = float(v)
    if v <= 0 or v != int(v):
        return False
    v = int(v)
    while v % 10 == 0:
        v //= 10
    return v < 10


_REVISAO = None


def revisao_manual():
    """Correções da revisão à mão (juiz_decisoes_revisao.json): par -> decisão."""
    global _REVISAO
    if _REVISAO is None:
        try:
            import json as _json
            from pathlib import Path as _P
            arq = _P(__file__).resolve().parent / 'juiz_decisoes_revisao.json'
            _REVISAO = _json.loads(arq.read_text(encoding='utf-8')).get('decisoes', {}) if arq.exists() else {}
        except Exception:
            _REVISAO = {}
    return _REVISAO


def veto_do_juiz(ga, gb):
    """A revisão à mão já decidiu que uma notícia de um grupo e uma do outro são fatos
    DIFERENTES: os grupos não se juntam por nenhum outro par (caso real: a apreensão de 153 kg
    num navio voltava a entrar no grupo da operação por outra matéria)."""
    juiz = revisao_manual()
    if not juiz:
        return False
    for x in ga:
        for y in gb:
            if juiz.get(chave_par(x.get('i'), y.get('i')), {}).get('v') == 'diferente':
                return True
    return False


_PLURAL = re.compile(r'(?i)\b(casal|dupla|trio|irm[aã]os|pai e filho|m[aã]e e filho|dois|duas|tr[eê]s|quatro|cinco)\b')


# Palavras que não identificam o fato (órgãos, números, ações genéricas) na busca por mesma cidade.
_GENERICAS_CIDADE = set('''pcpr pmpr pcsc pmsc pcdf pmdf pmce pcce pcrs pcmg pmmg rotam bpfron gaeco draco denarc
    deflagra deflagram investiga investigacao ilegal ilegais cidades cidade vale homens mulheres dupla casal suspeitos
    presos jovem jovens adolescentes adolescente faccionados faccao acao acoes operacao operacoes forca forcas
    seguranca integrada conjunta internacional interestadual crime crimes grupo mira esquema venda foragido
    investigados judiciais roubos furtos mandado mandados aberto anos prisao prisoes'''.split())


def _mesma_cidade(itens, dia, unir, raiz, dias=3, max_por_cidade=40):
    """Pares da mesma cidade do fato, até 1 dia de diferença, de veículos diferentes, com palavra
    específica do título em comum: vão ao juiz de IA; o "mesmo" do juiz une (grupo coerente)."""
    validos = [x for x in dia if x is not None]
    if not validos:
        return
    limite = max(validos) - dias
    juiz = decisoes_juiz()
    ja = {chave_par(p['a'][0], p['b'][0]) for p in SUSPEITAS}
    porcid = {}
    for k, it in enumerate(itens):
        if dia[k] is not None and dia[k] >= limite and it.get('_cid'):
            porcid.setdefault((it.get('uf'), it['_cid']), []).append(k)
    recentes = [k for k in range(len(itens)) if dia[k] is not None and dia[k] >= limite]
    genericas = set(AREAS_GENERICAS) | MATERIAIS | set(EXTENSO) | VAZIAS_AUDITOR | _GENERICAS_CIDADE
    for (uf, cid), ks in porcid.items():
        if len(ks) > max_por_cidade:
            continue  # cidade grande: muitas notícias diferentes no mesmo dia
        da_cidade = palavras(cid)
        for x in range(len(ks)):
            for y in range(x + 1, len(ks)):
                a, b = ks[x], ks[y]
                ia, ib = itens[a], itens[b]
                if raiz(a) == raiz(b) or ia.get('f') == ib.get('f') or abs(dia[a] - dia[b]) > 1:
                    continue
                comuns = {w for w in (informativas(ia['t']) & informativas(ib['t'])) - da_cidade - genericas if not w[0].isdigit()}
                if not comuns:
                    continue
                chave = chave_par(ia.get('i'), ib.get('i'))
                decisao = juiz.get(chave, {}).get('v')
                if decisao == 'mesmo':
                    if _grupos_coerentes(itens, recentes, raiz, a, b):
                        unir(a, b, 'mesma-cidade+juiz')
                elif decisao is None and chave not in ja:
                    ja.add(chave)
                    SUSPEITAS.append({'nota': 1.0, 'motivos': ['mesma cidade: ' + ', '.join(sorted(comuns)[:4])],
                                      'a': [ia['i'], ia.get('f', ''), ia['t'], ia.get('d', ''), ia.get('uf', ''),
                                            str(ia.get('_txt') or ia.get('_lead', ''))[:700], ia.get('_cid') or ''],
                                      'b': [ib['i'], ib.get('f', ''), ib['t'], ib.get('d', ''), ib.get('uf', ''),
                                            str(ib.get('_txt') or ib.get('_lead', ''))[:700], ib.get('_cid') or '']})


def _grupos_coerentes(itens, recentes, raiz, a, b):
    """Juntar os grupos de a e b não deixa duas notícias contraditórias no mesmo grupo
    (a decisão do juiz vale para o par, não para tudo o que já estava unido a cada um)."""
    ra, rb = raiz(a), raiz(b)
    ga = [itens[k] for k in recentes if raiz(k) == ra][:40]
    gb = [itens[k] for k in recentes if raiz(k) == rb][:40]
    # A cidade o juiz já confere (operações citam várias). Operação com nome (Cash Out, Rainha do
    # Sul...): muitas pessoas, idades e números de presos conforme a matéria; aí só a quantidade conta.
    if veto_do_juiz(ga, gb):
        return False
    pessoas = not any(it.get('_ops') for it in ga + gb)
    # Casal/dupla/trio nos dois grupos: cada jornal cita a idade de um deles (22 x 25 anos não
    # é contradição). Caso real: casal preso com bebê em Dourados (20/11/2026).
    plural = lambda g: any(_PLURAL.search(it.get('t') or '') or (it.get('_fx') or {}).get('p', 0) >= 2 for it in g)
    idades = pessoas and not (plural(ga) and plural(gb))
    for x in ga:
        for y in gb:
            if quantidades_em_conflito(x.get('_q'), y.get('_q')):
                return False
            fa, fb = x.get('_fx') or {}, y.get('_fx') or {}
            if pessoas and fa.get('p') and fb.get('p') and fa['p'] != fb['p']:
                return False
            if idades and fa.get('i') and fb.get('i') and not set(fa['i']) & set(fb['i']):
                return False
    return True


def auditar(itens, dia, inf, qt, sh, hs, unir, raiz, dias=None):
    """dias=None: o acervo inteiro (a coleta retroativa também passa pelo auditor)."""
    SUSPEITAS.clear()
    JUNTADAS.clear()
    validos = [d for d in dia if d is not None]
    if not validos:
        return
    limite = (max(validos) - dias) if dias else min(validos)
    recentes = [k for k in range(len(itens)) if dia[k] is not None and dia[k] >= limite]
    # O nome do veículo no título ("... - Ponta Porã Informa") não é palavra da notícia.
    rad = {k: radicais_titulo(itens[k]['t']) - radicais_titulo(itens[k].get('f', '')) for k in recentes}
    for k in recentes:  # características calculadas uma vez por notícia
        itens[k]['_ops'] = {x for x, _ in operacoes(itens[k]['t'] + ' . ' + itens[k].get('_lead', ''))}
        itens[k]['_np'] = nomes_proprios(itens[k]['t'])
    # Pares candidatos: mesmo dia (ou vizinho) e ao menos um radical próprio em comum.
    indice = {}
    for k in recentes:
        for r in rad[k]:
            if r not in MATERIAIS:
                indice.setdefault(r, []).append(k)
    pares = set()
    for r, lista in indice.items():
        if len(lista) > 150:
            continue
        lista.sort(key=lambda k: dia[k])
        for x in range(len(lista)):
            for y in range(x + 1, len(lista)):
                a, b = lista[x], lista[y]
                if dia[b] - dia[a] > 1:
                    break
                pares.add((min(a, b), max(a, b)))
    # Foto genérica (logotipo): a mesma impressão em muitas notícias.
    contagem = {}
    for k in recentes:
        if hs[k] is not None:
            contagem[hs[k]] = contagem.get(hs[k], 0) + 1
    for a, b in pares:
        if raiz(a) == raiz(b):
            continue
        ua, ub = itens[a].get('uf'), itens[b].get('uf')
        if ua and ub and ua != ub and itens[a].get('_ufx', True) and itens[b].get('_ufx', True):
            continue
        nota, motivos, fortes = nota_par(itens[a], itens[b], rad[a], rad[b], inf[a], inf[b], qt[a] or None, qt[b] or None,
                                 sh[a], sh[b], hs[a], hs[b], contagem.get(hs[a], 0) > 3, contagem.get(hs[b], 0) > 3)
        if nota is None:
            continue
        if dia[a] == dia[b]:
            nota += 0.3
        if nota >= JUNTAR and fortes >= 2:  # duas evidências fortes e independentes, no mínimo
            unir(a, b, 'auditor')
            JUNTADAS.append((round(nota, 2), motivos, itens[a].get('f', ''), itens[a]['t'], itens[b].get('f', ''), itens[b]['t']))
        elif nota >= DUVIDA:
            juiz = decisoes_juiz().get(chave_par(itens[a].get('i'), itens[b].get('i')), {})
            if juiz.get('v') == 'mesmo' and _grupos_coerentes(itens, recentes, raiz, a, b):
                # o juiz de IA leu as duas e confirmou (nos dois sentidos); e nenhuma notícia de um
                # grupo contradiz uma do outro (outra idade, outra cidade, outra quantidade...)
                unir(a, b, 'auditor')
                JUNTADAS.append((round(nota, 2), motivos + ['juiz IA'], itens[a].get('f', ''), itens[a]['t'],
                                 itens[b].get('f', ''), itens[b]['t']))
            elif juiz.get('v') != 'diferente':
                SUSPEITAS.append({'nota': round(nota, 2), 'motivos': motivos,
                                  'a': [itens[a]['i'], itens[a].get('f', ''), itens[a]['t'], itens[a].get('d', ''),
                                        itens[a].get('uf', ''), str(itens[a].get('_lead', ''))[:700], itens[a].get('_cid') or ''],
                                  'b': [itens[b]['i'], itens[b].get('f', ''), itens[b]['t'], itens[b].get('d', ''),
                                        itens[b].get('uf', ''), str(itens[b].get('_lead', ''))[:700], itens[b].get('_cid') or '']})
    # Os mais recentes primeiro (o que está na página inicial), depois a nota: o juiz de IA
    # julga nessa ordem.
    recente = (max(validos) - 3) if validos else 0
    def _prioridade(x):
        ka = dia_por_i.get(x['a'][0], 0)
        kb = dia_por_i.get(x['b'][0], 0)
        return (0 if max(ka, kb) >= recente else 1, -x['nota'])
    dia_por_i = {itens[k].get('i'): dia[k] for k in recentes}
    SUSPEITAS.sort(key=_prioridade)
    for k in recentes:
        itens[k].pop('_ops', None)
        itens[k].pop('_np', None)


def trechos(texto, n=5):
    """Trechos de 5 palavras seguidas (shingles) do começo do texto."""
    ws = normal(texto).split()[:120]
    return {' '.join(ws[k:k + n]) for k in range(max(0, len(ws) - n + 1))}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def _dia(item):
    try:
        return date.fromisoformat(item.get('d', '')[:10]).toordinal()
    except ValueError:
        return None


def _numero_do_fato(ta, tb, qa, qb, palavras_comuns, mesmo_dia=True):
    """O mesmo número identifica o fato nos dois títulos: quantidade do mesmo material a até 3%
    ou o mesmo número forte, sem contar rodovias e quilômetros (BR-116, km 30). A idade
    ("de 15 anos") só conta com mais palavras em comum."""
    if palavras_comuns < 2:
        return False
    if _quantidade_proxima(qa, qb):
        return True
    def nums(t):
        t = re.sub(r'\b[A-Z]{2,3}-\d+|(?i:\bkm\s?\d+)', ' ', t or '')
        idades = set(numeros(' '.join(re.findall(r'(\d+)\s+anos', t))))
        return numeros_fortes(t), idades
    (na, ia), (nb, ib) = nums(ta), nums(tb)
    comuns = na & nb
    if comuns - (ia & ib):
        return True
    return bool(comuns) and palavras_comuns >= 3 and mesmo_dia  # só a idade: no mesmo dia


def _quantidade_proxima(qa, qb):
    """O mesmo material com valor quase igual (até 3%: 5 kg ~ 5,1 kg) e nenhum divergente."""
    comuns = set(qa) & set(qb)
    return bool(comuns) and all(abs(qa[m] - qb[m]) <= 0.03 * max(qa[m], qb[m]) for m in comuns)


def _mesmas_quantidades(qa, qb):
    """F: ao menos uma quantidade relevante (>= 10) igual, e nenhuma divergente no mesmo material."""
    comuns = set(qa) & set(qb)
    if not comuns:
        return False
    for m in comuns:
        a, b = qa[m], qb[m]
        if abs(a - b) > 0.02 * max(a, b):
            return False
    return any(qa[m] >= 10 for m in comuns)


# Grandes apreensões: muitos veículos noticiam, cada um arredonda ("4 toneladas",
# "4,4 t", "mais de 100 armas" para 118). Mesmo material, valores a até 20% e
# grande o bastante para ser raro no mesmo estado na mesma semana.
GRANDE = {'coc': 300, 'mac': 300, 'skh': 300, 'cra': 100, 'dro': 300, 'arm': 20, 'fuz': 5, 'mun': 1000}


def cidades_conversam(a, b):
    """Mesma cidade, cidade não identificada em uma das duas, ou a cidade de uma aparece no
    título/abertura da outra (fato que envolve duas cidades vizinhas)."""
    ta = normal(f"{a.get('t', '')} {a.get('_lead', '')}")
    tb = normal(f"{b.get('t', '')} {b.get('_lead', '')}")
    ca, cb = a.get('_cid'), b.get('_cid')
    if ca and cb:
        return ca == cb or normal(ca) in tb or normal(cb) in ta
    # Sem a cidade do fato (notícias antigas): lugares/nomes dos títulos.
    lug = municipios()
    na, nb = nomes_proprios(a.get('t', '')) & lug, nomes_proprios(b.get('t', '')) & lug
    if na and nb and not (na & nb):
        ra = {radical(w) for w in ta.split()}
        rb = {radical(w) for w in tb.split()}
        return na <= rb or nb <= ra
    return True


def _valor_redondo(qa, qb):
    """Quantidades grandes e redondas (2 t, 3 t, 1,5 t, 20 fuzis) se repetem em fatos diferentes."""
    for m in set(qa) & set(qb):
        passo = 10 if m in ('arm', 'fuz', 'mun') else 500
        if qa[m] % passo == 0 or qb[m] % passo == 0:
            return True
    return False


def mesma_cidade(a, b):
    """A mesma cidade do fato (ou o mesmo município nos dois títulos)."""
    ca, cb = a.get('_cid'), b.get('_cid')
    if ca and cb:
        return ca == cb
    lug = municipios()
    return bool(nomes_proprios(a.get('t', '')) & nomes_proprios(b.get('t', '')) & lug)


def _mesma_grande(qa, qb, tolerancia=0.2, escala=1):
    for m in set(qa) & set(qb):
        a, b = qa[m], qb[m]
        if max(a, b) >= GRANDE.get(m, 10 ** 9) * escala and abs(a - b) <= tolerancia * max(a, b):
            return True
    return False


def _numero_raro(comuns):
    """Número com 3+ algarismos significativos (581, 234,4, 7.603): raro de repetir por acaso."""
    for w in comuns:
        if not w[0].isdigit():
            continue
        try:
            v = float(w)
        except ValueError:
            continue
        if 1900 <= v <= 2100 and v == int(v):
            continue  # ano
        sig = re.sub(r'e[+-]?\d+$', '', f'{v:.6g}').replace('.', '').strip('0')
        if len(sig) >= 3 and v >= 100:
            return True
    return False


def _pontos(item):
    """Qual versão mostrar: texto integral, fotos, link original, estado, resumo."""
    # Versão de veículo que bloqueia a leitura nunca é a exibida se houver outra.
    return (item.get('x', 0) * 8 + item.get('_tr', 0) * 6 + min(item.get('g', 1 if item.get('img') else 0), 5) * 2 +
            (3 if item.get('u') else 0) + (1 if item.get('uf') else 0) + (1 if item.get('r') else 0)
            - (100 if item.get('_bloq') else 0))


# Partes de cidade que não distinguem um fato (Zona Norte, Centro, Região Metropolitana...).
AREAS_GENERICAS = {radical(w) for w in 'zona norte sul leste oeste centro central regiao metropolitana interior litoral capital estado'.split()}
# Nomes dos estados (pelo radical): também não distinguem um fato.
AREAS_GENERICAS |= {radical(w) for w in '''acre alagoas amapa amazonas bahia ceara distrito federal espirito santo goias
    maranhao mato grosso minas gerais para paraiba parana pernambuco piaui rio janeiro grande norte rondonia roraima
    santa catarina sao paulo sergipe tocantins brasil'''.split()}


# Itens apreendidos raros o bastante para identificar o fato (junto com cidade e dia).
ITENS_RAROS = [(k, re.compile(r)) for k, r in (
    ('fuzil', r'\bfuzi[ls]\b'), ('metralhadora', r'metralhadora'), ('granada', r'\bgranadas?\b'),
    ('explosivo', r'explosiv|dinamite'), ('drone', r'\bdrones?\b'), ('aeronave', r'\b(avi[aã]o|avi[oõ]es|aeronaves?|helic[oó]pteros?)\b'),
    ('embarcacao', r'embarca[cç][aãoõ]|\blanchas?\b'), ('ouro', r'\bouro\b'), ('canhao', r'\bcanh[aã]o\b'),
    ('maquina_fuzil', r'fabrica.*arma|arma.*fabrica'))]


RADICAIS_ITENS_RAROS = {radical(w) for w in '''fuzil fuzis metralhadora granada granadas explosivo explosivos drone drones
    aviao avioes aeronave aeronaves helicoptero embarcacao lancha ouro canhao arma armas apreende apreensao preso presa'''.split()}


def fatos_auditor(fatos):
    """Resumo dos fatos para o auditor: itens raros apreendidos, número de presos e idades."""
    fatos = fatos or {}
    texto = normal(' '.join(str(x) for x in fatos.get('apreendido') or []))
    raros = sorted(k for k, r in ITENS_RAROS if r.search(texto))
    saida = {}
    if raros:
        saida['r'] = raros
    if isinstance(fatos.get('presos'), int) and fatos['presos'] > 0:
        saida['p'] = fatos['presos']
    if fatos.get('idades'):
        saida['i'] = sorted({int(x) for x in fatos['idades'] if str(x).isdigit()})
    return saida


def mesmos_fatos(fa, fb, radicais_comuns):
    """Fatos do texto batem: o mesmo item raro apreendido (fuzil, granada, avião...), nada
    contraditório (número de presos, idades) e mais um sinal: o mesmo número de presos (2 ou
    mais), a mesma idade ou 2+ palavras do título em comum."""
    if not fa or not fb or not set(fa.get('r') or ()) & set(fb.get('r') or ()):
        return False
    if fa.get('p') and fb.get('p') and fa['p'] != fb['p']:
        return False
    if fa.get('i') and fb.get('i') and not set(fa['i']) & set(fb['i']):
        return False
    return ((fa.get('p') or 0) >= 2 and fa.get('p') == fb.get('p')) or bool(set(fa.get('i') or ()) & set(fb.get('i') or ())) \
        or radicais_comuns >= 2


def link_da_materia(u):
    """Endereço normalizado de uma matéria; vazio para endereços genéricos (página inicial,
    seções, buscas, agregadores), que não identificam uma notícia."""
    m = re.match(r'(?i)^(?:https?://)?(?:www\d?\.)?([^/?#]+)(/[^?#]*)?', str(u or '').strip())
    if not m:
        return ''
    host, caminho = m.group(1).lower(), (m.group(2) or '').rstrip('/')
    if host.startswith('news.google.') or len(caminho) < 20 or caminho.count('/') < 1:
        return ''
    if re.search(r'(?i)/(tag|tags|categoria|category|busca|search|page|author|autor|feed)(/|$)', caminho):
        return ''
    if not re.search(r'[a-z0-9]-[a-z0-9]|\d{4,}', caminho.lower()):
        return ''  # sem slug nem identificador numérico: provavelmente uma seção
    return host + caminho.lower()


def agrupar(itens, motivos=None):
    """Retorna (itens sem duplicatas, ids removidos). Campos temporários lidos:
    _h (dHash int), _lead (abertura/resumo), _q ({material: quantidade}).
    motivos: lista opcional que recebe (regra, a, b) de cada união (diagnóstico)."""
    n = len(itens)
    pai = list(range(n))
    # Só o estado escrito no título conta para o veto (o do veículo pode ser de outro estado).
    ufs = [{it['uf']} if it.get('uf') and it.get('_ufx', True) else set() for it in itens]

    def raiz(k):
        while pai[k] != k:
            pai[k] = pai[pai[k]]
            k = pai[k]
        return k

    # Veto da revisão à mão: notícias conferidas como fatos DIFERENTES nunca ficam no mesmo grupo,
    # por nenhuma regra nem cadeia de uniões. (O "diferente" do juiz de IA não entra: em
    # operações grandes ele separa ângulos da mesma notícia e dividiria grupos certos.)
    diferentes = {}
    for chave_d, dec in revisao_manual().items():
        if dec.get('v') == 'diferente' and '-' in chave_d:
            x, y = chave_d.split('-', 1)
            diferentes.setdefault(x, set()).add(y)
            diferentes.setdefault(y, set()).add(x)
    vetados = [{str(it.get('i'))} if str(it.get('i')) in diferentes else set() for it in itens]

    def unir(a, b, regra, forcar=False):
        ra, rb = raiz(a), raiz(b)
        if ra == rb:
            return
        if len(ufs[ra] | ufs[rb]) > 1 and not forcar:  # veto: o grupo juntaria estados diferentes
            return
        if vetados[ra] and vetados[rb] and any(diferentes[x] & vetados[rb] for x in vetados[ra]):
            return  # veto do juiz
        pai[rb] = ra
        ufs[ra] |= ufs[rb]
        vetados[ra] |= vetados[rb]
        if motivos is not None:
            motivos.append((regra, a, b))

    # Título sem o nome do veículo no fim ("... - Ponta Porã Informa - Notícias de Ponta Porã/MS"):
    # o sufixo igual não é palavra em comum entre duas notícias do mesmo site.
    tt = [titulo_sem_veiculo(it) for it in itens]
    pal = [palavras(t) for t in tt]
    inf = [informativas(t) for t in tt]
    qt = [quantidades_titulo(t) for t in tt]
    nf = [numeros_fortes(t) for t in tt]
    nor = [normal(it['t']) for it in itens]
    dia = [_dia(it) for it in itens]
    sh = [trechos(it.get('_lead', '')) if len(it.get('_lead', '')) >= 150 else set() for it in itens]
    hs = [it.get('_h') for it in itens]
    qs = [it.get('_q') or {} for it in itens]

    # Regra 1: título idêntico.
    por_titulo = {}
    for k, t in enumerate(nor):
        if len(t) > 25:
            if t in por_titulo:
                unir(por_titulo[t], k, 'titulo-igual')
            else:
                por_titulo[t] = k

    # Regra 1b: o mesmo endereço da matéria (sem http/www, parâmetros e barra final) é a mesma
    # notícia, ainda que o título tenha mudado (o veículo editou ou o feed cortou a cidade).
    por_link = {}
    for k, it in enumerate(itens):
        lk = link_da_materia(it.get('u'))
        if lk:
            if lk in por_link:
                o = por_link[lk]
                perto = dia[o] is not None and dia[k] is not None and abs(dia[o] - dia[k]) <= 7
                parecidos = len(pal[o] & pal[k]) >= 0.8 * max(1, len(pal[o] | pal[k]))
                if perto or parecidos:  # link repetido em fato antigo e diferente: feed errou o link
                    unir(o, k, 'mesmo-link', forcar=True)  # o estado de um deles pode ter sido mal lido
            else:
                por_link[lk] = k

    # Candidatos: pares a até 7 dias que dividem palavra informativa, trecho de
    # abertura ou foto parecida (índices invertidos; evita comparar todos com todos).
    candidatos = set()

    def indexar(chaves_por_item, max_df):
        indice = {}
        for k, chaves in enumerate(chaves_por_item):
            if dia[k] is None:
                continue
            for c in chaves:
                indice.setdefault(c, []).append(k)
        for lista in indice.values():
            if len(lista) > max_df:
                continue  # palavra comum demais: não discrimina
            lista.sort(key=lambda k: dia[k])
            for x in range(len(lista)):
                for y in range(x + 1, len(lista)):
                    a, b = lista[x], lista[y]
                    if dia[b] - dia[a] > JANELA:
                        break
                    candidatos.add((a, b) if a < b else (b, a))

    indexar(inf, 400)
    for m, minimo in GRANDE.items():
        grandes = sorted((k for k in range(n) if dia[k] is not None and qs[k].get(m, 0) >= minimo * 0.8), key=lambda k: dia[k])
        for x in range(len(grandes)):
            for y in range(x + 1, len(grandes)):
                a, b = grandes[x], grandes[y]
                if dia[b] - dia[a] > 4:
                    break
                candidatos.add((a, b) if a < b else (b, a))
    indexar(sh, 60)
    # Fotos: comparação por janela de datas (só itens com impressão digital).
    com_foto = sorted((k for k in range(n) if hs[k] is not None and dia[k] is not None), key=lambda k: dia[k])
    pares_foto, sem_relacao = {}, {}
    for x in range(len(com_foto)):
        a = com_foto[x]
        for y in range(x + 1, len(com_foto)):
            b = com_foto[y]
            if dia[b] - dia[a] > JANELA:
                break
            d = (hs[a] ^ hs[b]).bit_count()
            if d <= 8:
                par = (a, b) if a < b else (b, a)
                pares_foto[par] = d
                if not (inf[a] & inf[b]):
                    sem_relacao[a] = sem_relacao.get(a, 0) + 1
                    sem_relacao[b] = sem_relacao.get(b, 0) + 1
    # Foto genérica: a mesma imagem em 2+ notícias sem nenhuma palavra em comum
    # (logotipo do veículo, arte padrão da polícia...). Não serve como evidência.
    # Mesmo endereço de foto (sem parâmetros) conta como a mesma imagem.
    por_url = {}
    for k, it in enumerate(itens):
        u = (it.get('img') or '').split('?')[0]
        if u and 'logo' not in u.lower() and dia[k] is not None:
            por_url.setdefault(u, []).append(k)
    for lista in por_url.values():
        for x in range(len(lista)):
            for y in range(x + 1, len(lista)):
                a, b = sorted((lista[x], lista[y]))
                if abs(dia[a] - dia[b]) <= JANELA:
                    pares_foto[(a, b)] = 0
                    if not (inf[a] & inf[b]):
                        sem_relacao[a] = sem_relacao.get(a, 0) + 1
                        sem_relacao[b] = sem_relacao.get(b, 0) + 1
    generica = {k for k, v in sem_relacao.items() if v >= 2}
    candidatos.update(pares_foto)
    # Mesmo resumo da fonte (primeiros 140 caracteres) com até 3 dias.
    # Só entre veículos diferentes, e não vale resumo repetido em muitas notícias (descrição
    # fixa do site, como "Correio da Cidade: notícias de Conselheiro Lafaiete...").
    por_resumo = {}
    for k, it in enumerate(itens):
        r = normal(it.get('r', ''))[:140]
        if len(r) >= 80 and dia[k] is not None:
            por_resumo.setdefault(r, []).append(k)
    for r, lista in por_resumo.items():
        if len(lista) < 2 or len(lista) > 12 or len({itens[k].get('f', '') for k in lista}) < 2:
            continue
        if len({normal(itens[k]['t'])[:40] for k in lista}) > 0.5 * len(lista) and len({itens[k].get('f', '') for k in lista}) < len(lista) / 2:
            continue  # muitos títulos diferentes no mesmo veículo: é descrição fixa
        for x in range(len(lista)):
            for y in range(x + 1, len(lista)):
                j, k = lista[x], lista[y]
                if itens[j].get('f') != itens[k].get('f') and abs(dia[j] - dia[k]) <= 3:
                    unir(j, k, 'resumo-igual')

    _esp = {}

    def mesma_cid(a, b):
        # Cidade do fato lida nos dois; se faltar num deles, o mesmo município citado nos dois títulos.
        ca, cb = itens[a].get('_cid'), itens[b].get('_cid')
        if ca and cb:
            return ca == cb
        return mesma_cidade(itens[a], itens[b])

    def marca_comum(a, b):
        # Algo que distingue o fato nos dois títulos além da cidade: nome próprio (bairro,
        # operação, pessoa) ou número forte. Títulos genéricos ("Homem é preso por tráfico
        # em X") dias depois costumam ser fatos diferentes.
        if nf[a] & nf[b]:
            return True
        comuns = nomes_proprios(itens[a]['t']) & nomes_proprios(itens[b]['t'])
        cidade = set(AREAS_GENERICAS)
        for k in (a, b):
            cidade |= radicais_titulo(itens[k].get('_cid') or '')
        if not (itens[a].get('_cid') or itens[b].get('_cid')):
            cidade |= comuns & lugares()  # cidade só citada no título: o nome dela não distingue
        return bool(comuns - cidade)

    def _radicais_fato(a, b):
        # Radicais do título em comum, sem a cidade, o estado e partes genéricas.
        cidade = set(AREAS_GENERICAS)
        for k in (a, b):
            cidade |= radicais_titulo(itens[k].get('_cid') or '')
        cidade |= RADICAIS_ITENS_RAROS  # o próprio item raro já conta como fato
        return (radicais_titulo(itens[a]['t']) & radicais_titulo(itens[b]['t'])) - cidade

    def _jac_titulo(a, b):
        return len(pal[a] & pal[b]) / max(1, len(pal[a] | pal[b]))

    def especificas(a, b):
        """Palavras próprias em comum nos títulos (sem materiais, verbos e termos de regulação)."""
        for k in (a, b):
            if k not in _esp:
                _esp[k] = {w for w in palavras_proprias_foto(itens[k]['t']) if w not in REGULACAO}
        return _esp[a] & _esp[b]

    mats = [materiais_titulo(t) for t in tt]
    for a, b in candidatos:
        if mats[a] and mats[b] and not (mats[a] & mats[b]):
            continue  # materiais diferentes nos títulos
        ua, ub = itens[a].get('uf'), itens[b].get('uf')
        if ua and ub and ua != ub:
            # Estados diferentes escritos nos títulos: fatos diferentes. Se um deles é só o
            # estado do veículo (notícia nacional), segue, mas sem contar como mesmo estado.
            if itens[a].get('_ufx', True) and itens[b].get('_ufx', True):
                continue
            ua = ub = None
            uf_fraco = True
        else:
            uf_fraco = False
        if qt[a] and qt[b] and not compativeis(qt[a], qt[b]):
            continue
        if quantidades_em_conflito(q_titulo(tt[a]), q_titulo(tt[b])):
            continue  # 2 t x 6 t de maconha ("duas cidades" não é quantidade de droga)
        if dia[a] is None or dia[b] is None:
            continue
        delta = abs(dia[a] - dia[b])
        mesmo_uf = bool(ua and ua == ub)
        foto = (a, b) in pares_foto and a not in generica and b not in generica
        # Mesmo veículo: a abertura igual costuma ser bloco fixo do site ("Conteúdos copiados...
        # devem conter os créditos"), não a reportagem. Só vale entre veículos diferentes.
        mesmo_veiculo = bool(itens[a].get('f')) and itens[a].get('f') == itens[b].get('f')
        lead = 0.0 if mesmo_veiculo else jaccard(sh[a], sh[b])
        # Palavras em comum que identificam o fato (lugar, nome, objeto específico).
        proprias = {w for w in inf[a] & inf[b] if not w[0].isdigit() and w not in MATERIAIS}
        numero_forte = bool(nf[a] and nf[b] and compativeis(nf[a], nf[b]))
        titulo = len(pal[a]) >= 3 and mesma_materia(pal[a], pal[b], inf[a], inf[b], qt[a], qt[b], mesmo_uf)
        if titulo and delta <= 3 and mesma_cid(a, b) and _jac_titulo(a, b) >= 0.8 and (delta <= 1 or marca_comum(a, b)):
            # Título quase idêntico, mesma cidade do fato, até 3 dias (republicação tardia).
            unir(a, b, 'titulo-cidade')
        elif titulo and delta <= 1:
            unir(a, b, 'titulo')
        elif titulo and ((numero_forte and proprias) or foto or lead >= 0.3):
            unir(a, b, 'titulo+evidencia')
        elif lead >= 0.45:
            unir(a, b, 'abertura')
        elif foto and (proprias or _mesmas_quantidades(qs[a], qs[b])):
            unir(a, b, 'foto')
        elif (delta <= 3 and mesmo_uf and _mesmas_quantidades(qs[a], qs[b])
              and (proprias if delta <= 1 else proprias - set(EXTENSO))):
            # Dias diferentes: número por extenso em comum ("duas" toneladas) não identifica o fato.
            unir(a, b, 'fatos')
        elif (delta <= 1 and not mesmo_veiculo and itens[a].get('_cid') and itens[a].get('_cid') == itens[b].get('_cid')
              and qt[a] and qt[b] and _numero_do_fato(itens[a]['t'], itens[b]['t'], qs[a], qs[b],
                                                        len({w for w in pal[a] & pal[b] if not w[0].isdigit()}),
                                                        delta == 0)):
            # Mesma cidade do fato (lida nos dois), mesmo dia e o mesmo número no título
            # (5 kg ~ 5,1 kg; 25 kg; "adolescente de 15 anos"): o mesmo fato em veículos diferentes.
            unir(a, b, 'cidade-numero')
        elif (delta <= 1 and not mesmo_veiculo and itens[a].get('_cid') and itens[a].get('_cid') == itens[b].get('_cid')
              and mesmos_fatos(itens[a].get('_fx'), itens[b].get('_fx'), len(_radicais_fato(a, b)))):
            # Mesma cidade do fato, mesmo dia e os mesmos fatos no texto (item raro apreendido e o
            # mesmo número de presos ou a mesma idade): títulos diferentes do mesmo fato (Foz do
            # Iguaçu, 19/11/2026: "PCPR apreende fuzil... prende quatro" x "Jovem ostenta armas...").
            unir(a, b, 'cidade-fatos')
        elif delta <= 2 and _mesma_grande(qs[a], qs[b], 0.1) and mesmo_uf and especificas(a, b):
            # Grande apreensão do mesmo material com valor quase igual (arredondamento), mesmo
            # estado e uma palavra própria em comum (540 kg de cocaína != 600 kg de maconha).
            unir(a, b, 'grande-apreensao')
        elif delta <= 1 and mesmo_uf and _mesma_grande(qs[a], qs[b], 0.05, 4) and (
                mesma_cidade(itens[a], itens[b]) if _valor_redondo(qs[a], qs[b]) else cidades_conversam(itens[a], itens[b])):
            # Apreensão muito grande (>= 4x o mínimo: 1,2 t de droga, 80 armas, 20 fuzis...) do mesmo
            # material, com o mesmo valor (5%), no mesmo estado e no mesmo dia: o mesmo fato, mesmo
            # que cada veículo cite uma cidade (perseguição de Sidrolândia a Campo Grande) — desde
            # que o texto de uma cite a cidade da outra (Arapongas x Nova Santa Rosa: fatos diferentes).
            unir(a, b, 'grande-apreensao-uf')
        elif delta <= 2 and proprias and not uf_fraco and _numero_raro(inf[a] & inf[b]):
            # (Não vale entre estados diferentes: "127 mandados" da Operação Panóptico, PR, x
            # Operação Tentáculos, MS, no mesmo dia, 19/11/2026.)
            # Mesmo número incomum no título ("R$ 581 milhões", "7.603 kg") + palavra própria.
            unir(a, b, 'numero-raro')
        elif uf_fraco and delta <= 1 and len(especificas(a, b)) >= 3 and len(proprias) >= 0.5 * min(len(inf[a]), len(inf[b])):
            # Notícia nacional (Anvisa, Receita, PF) publicada por jornais de vários estados.
            unir(a, b, 'nacional')
        elif delta <= 2 and not (ua and ub) and _mesma_grande(qs[a], qs[b], 0.05, 4) and especificas(a, b):
            # Estado não identificado em uma das versões: só valor quase igual,
            # em até 2 dias, e muito grande (>= 4x o mínimo: 1,2 t, 80 armas...).
            unir(a, b, 'grande-apreensao')

    # Mesma foto recortada de outro jeito por cada veículo (o dHash não acha recortes):
    # hash_imagens.py compara as fotos (mesmo dia, estado e palavra própria no título) e
    # guarda os pares em img_iguais; aqui só se confirma data, estado e quantidades.
    por_foto = {}
    for k, it in enumerate(itens):
        if it.get('img'):
            por_foto.setdefault(it['img'], []).append(k)
    for a, it in enumerate(itens):
        for url in it.get('_iguais') or ():
            for b in por_foto.get(url, ()):
                if a == b or raiz(a) == raiz(b) or dia[a] is None or dia[b] is None or abs(dia[a] - dia[b]) > 1:
                    continue
                ua, ub = it.get('uf'), itens[b].get('uf')
                if not (ua and ub and ua == ub):
                    continue  # mesmo estado, nos dois (a foto sozinha já juntou fatos de fora do país)
                if qt[a] and qt[b] and not compativeis(qt[a], qt[b]):
                    continue
                # E uma palavra própria em comum nos títulos (não vale "esquema", "lavagem"...).
                if not palavras_proprias_foto(it['t']) & palavras_proprias_foto(itens[b]['t']):
                    continue
                unir(a, b, 'foto-recortada')

    # FOTO IDÊNTICA (impressão digital a até 4 bits): o mesmo fato com qualquer título (caso
    # real de 19/11/2026: "PRF apreende quase 3,4 toneladas de maconha em duas cidades de MS" x
    # "PRF apreende mais de 3 toneladas de maconha em Dourados e na Capital", a mesma foto).
    # Mesmo estado, até 1 dia, veículos diferentes, foto não genérica e nada contraditório.
    for (a, b), d in pares_foto.items():
        if d > 4 or a in generica or b in generica or raiz(a) == raiz(b):
            continue
        ia, ib = itens[a], itens[b]
        if dia[a] is None or dia[b] is None or abs(dia[a] - dia[b]) > 1:
            continue
        if not (ia.get('uf') and ia.get('uf') == ib.get('uf')):
            continue
        if ia.get('f') and ia.get('f') == ib.get('f'):
            continue
        if mats[a] and mats[b] and not (mats[a] & mats[b]):
            continue
        if qt[a] and qt[b] and not compativeis(qt[a], qt[b]):
            continue
        fa, fb = ia.get('_fx') or {}, ib.get('_fx') or {}
        if (fa.get('p') and fb.get('p') and fa['p'] != fb['p']) or \
                (fa.get('i') and fb.get('i') and not set(fa['i']) & set(fb['i'])):
            continue
        if ia.get('_cid') and ib.get('_cid') and ia['_cid'] != ib['_cid']:
            continue
        unir(a, b, 'foto-identica')

    # A MESMA FOTO com recorte, zoom ou outro tamanho (fotos_orb.py: pontos característicos em
    # comum). Caso real de 19/11/2026: veículos republicam o comunicado da polícia com a foto
    # dela e títulos genéricos ("Polícia Civil apreende revólver durante operação"). Vale com:
    # mesmo estado nos dois, até 2 dias, veículos diferentes, nada contraditório (materiais,
    # quantidades, presos, idades) e foto que não seja de banco de imagens (casada com no
    # máximo 3 outras fotos).
    # Foto genérica: casada com 4+ notícias no total (contando todos os lados) não vale.
    parceiros = {}  # foto -> outras fotos casadas com ela (distintas, nos dois sentidos)
    for it in itens:
        for u in it.get('_mesma') or ():
            if it.get('img') and u != it['img']:
                parceiros.setdefault(u, set()).add(it['img'])
                parceiros.setdefault(it['img'], set()).add(u)
    casadas = {u: len(v) for u, v in parceiros.items()}
    for a, it in enumerate(itens):
        mesmas = it.get('_mesma') or ()
        if not mesmas or len(mesmas) > 3 or casadas.get(it.get('img'), 0) > 3:
            continue
        for url in mesmas:
            if casadas.get(url, 0) > 3:
                continue
            for b in por_foto.get(url, ()):
                if a == b or raiz(a) == raiz(b) or dia[a] is None or dia[b] is None or abs(dia[a] - dia[b]) > 2:
                    continue
                ob = itens[b]
                if len(ob.get('_mesma') or ()) > 3:
                    continue
                if not (it.get('uf') and it.get('uf') == ob.get('uf')):
                    continue
                if it.get('f') and it.get('f') == ob.get('f'):
                    continue  # o mesmo veículo reusa foto de arquivo em matérias diferentes
                if mats[a] and mats[b] and not (mats[a] & mats[b]):
                    continue
                if qt[a] and qt[b] and not compativeis(qt[a], qt[b]):
                    continue
                fa, fb = it.get('_fx') or {}, ob.get('_fx') or {}
                if fa.get('p') and fb.get('p') and fa['p'] != fb['p']:
                    continue
                if fa.get('i') and fb.get('i') and not set(fa['i']) & set(fb['i']):
                    continue
                ca, cb = it.get('_cid'), ob.get('_cid')
                if ca and cb and ca != cb:
                    continue
                unir(a, b, 'mesma-foto')

    # Mesma operação com nome próprio, mesma fase (quando dita), até 1 dia: o mesmo fato,
    # mesmo com títulos e fotos diferentes (grande operação: muitos veículos no mesmo dia).
    # Operação permanente (Hórus, Ágata, Fronteira; ou nome visto em 4+ dias sem fase)
    # não serve: cada apreensão dela é um fato.
    por_op = {}
    for k, it in enumerate(itens):
        if dia[k] is None:
            continue
        for nome, fase in operacoes(it['t'] + ' . ' + it.get('_lead', '')):
            por_op.setdefault(nome, []).append((dia[k], fase, k))
    for nome, lista in por_op.items():
        lista.sort()
        # Nome que aparece em 4+ dias sem fase: operação permanente, não identifica o fato.
        if len({d for d, f, _ in lista if not f}) >= 4:
            continue
        for x in range(len(lista)):
            for y in range(x + 1, len(lista)):
                da, fa, a = lista[x]
                db, fb, b = lista[y]
                if db - da > 1:
                    break
                if a == b or (fa and fb and fa != fb):
                    continue
                ua, ub = itens[a].get('uf'), itens[b].get('uf')
                if ua and ub and ua != ub:
                    continue
                # Uma palavra própria em comum nos títulos (lugar, alvo, objeto): a matéria geral da
                # operação e a de uma prisão isolada dela em outra cidade não são a mesma notícia.
                if not {w for w in inf[a] & inf[b] if not w[0].isdigit() and w not in MATERIAIS}:
                    continue
                # Desdobramento na Justiça é outra notícia.
                if bool(JUDICIAL.search(itens[a]['t'])) != bool(JUDICIAL.search(itens[b]['t'])):
                    continue
                unir(a, b, 'operacao')

    # Auditor (notícias dos últimos dias): nota somando todas as evidências do par.
    # Coleta rápida: só os últimos dias (RADAR_AUDITOR_DIAS); as demais coletas, o acervo inteiro.
    import os
    auditar(itens, dia, inf, qt, sh, hs, unir, raiz, int(os.environ.get('RADAR_AUDITOR_DIAS') or 0) or None)
    # Motor de evidências (motor_evidencias.py): placar com texto completo, foto e fatos nos
    # pares que as regras deixaram separados; une os certos e manda os duvidosos ao juiz de IA.
    try:
        from motor_evidencias import aplicar as _motor
        _motor(itens, dia, unir, raiz, int(os.environ.get('RADAR_AUDITOR_DIAS') or 0) or None, SUSPEITAS, decisoes_juiz())
    except Exception as erro:  # o motor nunca derruba a geração do site
        print(f'Motor de evidências com erro (site gerado sem ele): {erro!r}')
    # Revisor da página inicial: passada exaustiva nos últimos 3 dias (todos os pares do estado).
    try:
        from motor_evidencias import revisar_vitrine as _revisor
        _revisor(itens, dia, unir, raiz, 3)
    except Exception as erro:
        print(f'Revisor da página inicial com erro (site gerado sem ele): {erro!r}')
    # Mesma cidade, até 1 dia, palavra específica em comum: o juiz de IA lê o par (notícias
    # curtas de cidade pequena não somam pontos para as regras nem para o motor).
    try:
        _mesma_cidade(itens, dia, unir, raiz)
    except Exception as erro:
        print(f'Busca por mesma cidade com erro (site gerado sem ela): {erro!r}')

    grupos = {}
    for k in range(n):
        grupos.setdefault(raiz(k), []).append(k)
    saida, removidas = [], set()
    for membros in grupos.values():
        membros.sort(key=lambda k: _pontos(itens[k]), reverse=True)
        principal = itens[membros[0]]
        outras, vistas = [], {principal.get('f', '')}
        for k in sorted(membros[1:], key=lambda k: itens[k].get('d', '')):
            outro = itens[k]
            removidas.add(outro['i'])
            for campo in ('uf', 'img', 'r'):
                if outro.get(campo) and not principal.get(campo):
                    principal[campo] = outro[campo]
            # Mantém a ordem da versão exibida (a 1ª é o selo) e acrescenta as das outras.
            principal['c'] = list(dict.fromkeys(principal.get('c', []) + outro.get('c', [])))
            if not principal['c']:
                del principal['c']
            if outro.get('f', '') not in vistas and not outro.get('_bloq'):
                vistas.add(outro.get('f', ''))
                outras.append([outro.get('f', 'Outra fonte'), outro.get('u', ''), outro['i']])
        if outras:
            principal['o'] = outras[:8]
        saida.append(principal)
    return saida, removidas
