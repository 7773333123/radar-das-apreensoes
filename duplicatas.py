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
    texto = unicodedata.normalize('NFKD', texto or '')
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
    return {nome for nome, padrao in MATERIAL_TITULO if re.search(r'\b(?:' + padrao + r')\b', t or '', re.I)}


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
        if len(especificas) >= 2 and jac >= 0.3:
            fortes += 1
            motivos.append('título específico na mesma cidade')
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
            SUSPEITAS.append({'nota': round(nota, 2), 'motivos': motivos,
                              'a': [itens[a]['i'], itens[a].get('f', ''), itens[a]['t']],
                              'b': [itens[b]['i'], itens[b].get('f', ''), itens[b]['t']]})
    SUSPEITAS.sort(key=lambda x: -x['nota'])
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

    def unir(a, b, regra):
        ra, rb = raiz(a), raiz(b)
        if ra == rb:
            return
        if len(ufs[ra] | ufs[rb]) > 1:  # veto: o grupo juntaria estados diferentes
            return
        pai[rb] = ra
        ufs[ra] |= ufs[rb]
        if motivos is not None:
            motivos.append((regra, a, b))

    pal = [palavras(it['t']) for it in itens]
    inf = [informativas(it['t']) for it in itens]
    qt = [quantidades_titulo(it['t']) for it in itens]
    nf = [numeros_fortes(it['t']) for it in itens]
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

    def especificas(a, b):
        """Palavras próprias em comum nos títulos (sem materiais, verbos e termos de regulação)."""
        for k in (a, b):
            if k not in _esp:
                _esp[k] = {w for w in palavras_proprias_foto(itens[k]['t']) if w not in REGULACAO}
        return _esp[a] & _esp[b]

    mats = [materiais_titulo(it['t']) for it in itens]
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
        if titulo and delta <= 1:
            unir(a, b, 'titulo')
        elif titulo and ((numero_forte and proprias) or foto or lead >= 0.3):
            unir(a, b, 'titulo+evidencia')
        elif lead >= 0.45:
            unir(a, b, 'abertura')
        elif foto and (proprias or _mesmas_quantidades(qs[a], qs[b])):
            unir(a, b, 'foto')
        elif delta <= 3 and mesmo_uf and _mesmas_quantidades(qs[a], qs[b]) and proprias:
            unir(a, b, 'fatos')
        elif delta <= 2 and _mesma_grande(qs[a], qs[b], 0.1) and mesmo_uf and especificas(a, b):
            # Grande apreensão do mesmo material com valor quase igual (arredondamento), mesmo
            # estado e uma palavra própria em comum (540 kg de cocaína != 600 kg de maconha).
            unir(a, b, 'grande-apreensao')
        elif delta <= 2 and proprias and _numero_raro(inf[a] & inf[b]):
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
