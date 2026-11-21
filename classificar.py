#!/usr/bin/env python3
"""Classificação automática: a notícia é de apreensão? De qual tipo?

Regras próprias, decididas pelo título (a manchete diz do que trata a
matéria) e, se o título não bastar para o tipo, pelo início do resumo/texto.
Não usa a classificação do coletor antigo, que errava muito.

Relevância (sem revisão manual):
- FORTE no título (apreende, cocaína, fuzil, contrabando...): entra;
- MÉDIO (tráfico, armas, operação, mandados...) junto de um verbo de ação
  policial (prende, cumpre, deflagra...) e sem assunto alheio (morte sem
  apreensão, clima, política, esporte): entra;
- o resto fica fora do site (continua guardado no acervo).
"""
import re

CATEGORIAS = [
    'Drogas e entorpecentes', 'Armas e munições', 'Contrabando e descaminho', 'Veículos',
    'Dinheiro e valores', 'Crimes ambientais', 'Medicamentos e produtos',
    'Operações patrimoniais', 'Outras apreensões',
]
REGRAS = [re.compile(r, re.I) for r in [
    # 0 drogas
    r'\bdrogas?\b|tr[aá]fico de drogas|\btraficantes?\b|\btr[aá]fico\b(?! de (?:animais|pessoas|armas|influ[eê]ncia|[oó]rg[ãa]os))|'
    r'coca[ií]na|maconha|entorpecent|\bcrack\b|haxixe|skunk|cannabis|ecstasy|\blsd\b|pasta base|'
    r'\bpinos?\b|papelotes?|tabletes?|lança-perfume|\bk9\b|metanfetamina|\bmdma\b|sint[ée]tic[oa]s?\b',
    # 1 armas
    r'\barmas?\b|armamentos?|fuzil|fuzis|pistolas?|rev[oó]lver|rev[oó]lveres|muni[çc][ãaõo]|cartuchos?|'
    r'explosiv|espingardas?|carabinas?|metralhadoras?|submetralhadora|granadas?|simulacros?',
    # 2 contrabando
    r'contraband|descaminho|cigarros?(?! eletr)|cigarros? eletr[ôo]nicos?|vapes?\b|aduan|'
    r'mercadorias? (?:irregular|il[ií]cit|estrangeir|sem nota)|sem nota fiscal|vinhos?\b|eletr[ôo]nicos? (?:importad|estrangeir)|'
    r'pneus (?:importad|contraband)|agrot[oó]xicos? (?:contraband|il[ei]g)',
    # 3 veículos
    r've[ií]culos?|\bcarros?\b|caminh[ãa]o|caminh[õo]es|carretas?|motocicletas?|\bmotos?\b|caminhonetes?|'
    r'embarca[çc]|lanchas?|aeronaves?|avi[ãa]o|avi[õo]es|helic[oó]ptero|desmanche|clonad|adulterad',
    # 4 dinheiro
    r'dinheiro|em esp[ée]cie|\bouro\b|joias|numer[aá]rio|d[oó]lares|\beuros\b|\bpix\b|criptomoeda|bitcoin',
    # 5 ambiental
    r'ambient|madeira|animais silvestres|aves silvestres|p[áa]ssaros|pesca (?:ilegal|predat)|pescado|'
    r'garimpo|merc[uú]rio|min[eé]rio|desmatamento|\bca[çc]a\b|ca[çc]ador|jabutis?|tartarugas?|carv[ãa]o|'
    r'palmito|queimada criminosa|extra[çc][ãa]o ilegal|dragas?\b|balsas? de garimpo|rinha',
    # 6 medicamentos e produtos
    r'medicamento|rem[eé]dio|anabolizante|falsificad|canetas? emagrecedoras?|tirzepatida|semaglutida|'
    r'ozempic|mounjaro|ampolas|cosm[ée]ticos?|bebidas? (?:falsificad|adulterad)|produtos? (?:falsificad|pirata|sem registro)|'
    r'pirataria|piratas?\b|alimentos? (?:impr[óo]pri|vencid|estragad)|carne (?:impr[óo]pria|clandestina)',
    # 7 patrimonial
    r'bloqueio de bens|bloqueia(?:m)? (?:bens|r\$|contas)|sequestro de bens|lavagem de dinheiro|'
    r'bens (?:apreendidos|bloqueados)|im[óo]veis (?:sequestrad|bloquead)|patrim[ôo]nio',
    # 8 outras
    r'apreens|apreend|confisc|retid',
]]

FORTE = re.compile(
    r'apreen|apreend|confisc|coca[ií]n|maconha|\bcrack\b|haxixe|skunk|entorpecent|pasta base|ecstasy|'
    r'fuzil|fuzis|muni[çc][ãaõo]|pistolas?\b|rev[oó]lver|armas? de fogo|arsenal|contraband|descaminho|'
    r'tr[aá]fico de drogas|lavagem de dinheiro|bloqueio de bens|sequestro de bens|garimpo ilegal|'
    r'desmanche|ponto de (?:venda de drogas|tr[aá]fico)|boca de fumo|estufa de maconha|p[ée]s de maconha|'
    r'tabletes|papelotes|pinos de|(?:encontr|localiz|achad|flagr)\w* (?:\w+ )?(?:armas?|drogas?|fuzil|fuzis|muni[çc])|'
    r'canetas? emagrecedoras?', re.I)
MEDIO = re.compile(
    r'tr[aá]fic|\bdrogas?\b|\barmas?\b|armament|opera[çc][ãa]o|mandados?|flagrante|fac[çc][ãa]o|quadrilha|'
    r'organiza[çc][ãa]o criminosa|cigarros?|medicamentos?|anabolizante|madeira|pescado|animais silvestres|'
    r'garimpo|merc[uú]rio|ve[ií]culos? (?:roubad|furtad|clonad|adulterad)|receptação|explosiv|'
    r'mercadorias?|ouro|dinheiro', re.I)
ACAO = re.compile(
    r'combat|\bpren(?:de|dem|deu|deram)\b|\bpres[oa]s?\b|\bpris[ãa]o|\bpris[õo]es|\bdetid|cumpr|deflagr|desarticul|'
    r'flagr|captur|apreend|apreens|\bfecha\b|\bfecham\b|desmont|estour|intercept|localiz|encontr|recuper|'
    r'\bpega\b|\bpegam\b|\bflagra\b|\bbloque|\bretira de circula|\bincinera|\bdestr[oó]i|erradic|'
    r'opera[çc][ãa]o|abordag|\bPRF\b|\bPF\b|\bPM\b|\bPC\b|Pol[ií]cia|Receita Federal|Ibama|Gaeco|FICCO|BOPE|Rotam|Denarc', re.I)
# Assuntos que não são apreensão (quando não há termo FORTE no título).
ALHEIO = re.compile(
    r'\bmorr(?:e|em|eu|eram)\b|\bmort[oa]s?\b|assassinad|assassinato|homic[ií]dio|feminic[ií]dio|esfaquead|facadas|'
    r'baleado|atropel|acidente|afogad|desaparecid|sequestrad[oa]\b|estupro|abuso sexual|pornografia|'
    r'tempestade|chuvas?\b|previs[ãa]o do tempo|clima\b|temperatura|calor|frio\b|'
    r'elei[çc]|candidat|vereador|prefeit[oa]|deputad|senador|governador|ministro|\bSTF\b|\bSTJ\b|projeto de lei|'
    r'maioridade penal|\bprojeto\b|\bPEC\b|pesquisa|levantamento|estudo|ranking|[íi]ndice|aumentam|diminuem|cresce|caem\b|'
    r'futebol|campeonato|\bjogo\b|torcida|show\b|festival|concurso|vestibular|\benem\b|vagas|edital|licita[çc]|'
    r'inaugura|cerim[ôo]nia|homenag|formatura|curso|palestra|f[óo]rum|semin[áa]rio|centro cultural|'
    r'golpe|estelionato|fraude|furto de celular|briga|discuss[ãa]o|viol[êe]ncia dom[ée]stica|maria da penha',
    re.I)


# "Apreensão" no sentido de preocupação ("agenda econômica gera apreensão no mercado", "clima de
# apreensão", "apreensivos"): não é apreensão policial. Pedido do dono do site, 21/11/2026: não entra.
_APREENSAO_SENTIMENTO = re.compile(
    r'(?:\b(?:gera|geram|gerou|gerando|causa|causam|causou|causando|provoca|provocam|provocou|desperta|despertam|'
    r'despertou|traz|trazem|trouxe|aumenta|aumentou|eleva|elevou|cria|criou|há|houve|clima|momentos?|dias?|horas?|'
    r'noite|madrugada|tens[ãa]o|medo|expectativa|misto|sensa[çc][ãa]o|onda|ar|preocupa[çc][ãa]o|ansiedade|'
    r'sob|em meio [àa]|entre)\s+(?:de\s+|e\s+|a\s+|muita\s+|grande\s+|forte\s+)?apreens[ãa]o\b(?!\s+(?:de|da|do|das|dos|recorde)\b))'
    r'|\bapreens[ãa]o\s+(?:no|na|nos|nas|do|da|dos|das|entre|em)\s+(?:o\s+|a\s+)?(?:mercados?(?!\s+municipal)|bolsas?|investidores|'
    r'setor|agro|produtores|empres[aá]rios|moradores|pais|torcedores|torcida|familiares|fam[ií]lias|comunidade|popula[çc][ãa]o|'
    r'servidores|eleitores|governo|planalto|congresso|câmara|oposi[çc][ãa]o|aliados)\b'
    r'|(?<!busca e )\bapreens[ãa]o\s+(?:sobre|quanto|diante)\b|\bapreensiv[oa]s?\b', re.I)


def apreensao_sentimento(titulo):
    """Título em que "apreensão" é preocupação, sem outro termo forte de apreensão policial."""
    if not _APREENSAO_SENTIMENTO.search(titulo):
        return False
    return not FORTE.search(_APREENSAO_SENTIMENTO.sub(' ', titulo))


def relevante(titulo):
    if apreensao_sentimento(titulo):
        return False
    if FORTE.search(titulo):
        return True
    return bool(MEDIO.search(titulo) and ACAO.search(titulo) and not ALHEIO.search(titulo))


def categorias(titulo, texto=''):
    """Índices em CATEGORIAS; o primeiro é o tipo citado primeiro no título."""
    def achados(t):
        pos = {}
        for k, regra in enumerate(REGRAS[:8]):
            m = regra.search(t)
            if m:
                pos[k] = m.start()
        return sorted(pos, key=pos.get)
    cats = achados(titulo)
    if not cats and re.search(r'Receita Federal|\bRFB\b|importad|roupas|perfumes|produtos eletr', titulo, re.I):
        cats = [2]  # Receita apreendendo mercadorias = contrabando/descaminho
    if not cats and re.search(r'R\$\s?[\d.,]+\s*(?:mil|milh)', titulo, re.I):
        cats = [4]
    if not cats and texto:
        cats = achados(texto[:500])[:2]
    return cats or ([8] if REGRAS[8].search(titulo + ' ' + texto[:300]) else [8])


if __name__ == '__main__':
    casos = [
        ('Fórum em SP discute soluções urbanas e o futuro das cidades inteligentes', None),
        ('Semana começa com alerta de tempestade e ventos para 19 estados e o DF', None),
        ('Adolescente é morto a facadas em Montenegro', None),
        ('Área dominada por tráfico e milícia no RJ é praticamente igual a uma capital brasileira', None),
        ('Redução da maioridade penal ameaça ampliar poder das facções nos presídios', None),
        ('Polícia apreende mercúrio e fecha garimpo ilegal que pertenceria a detento; dois são presos', 5),
        ('PRF apreende 120 ampolas de tirzepatida introduzidas ilegalmente no país em Seberi', 6),
        ('Polícia Civil apreende caminhão e prende dois suspeitos por estelionato e receptação em Sarandi', 3),
        ('Operação Gerência cumpre três mandados de prisão preventiva em Charqueadas', 8),
        ('PRF apreende 1,1 tonelada de maconha e 10 pistolas na BR-163', 0),
        ('BPRv apreende 300 garrafas de vinho estrangeiro na PR-323', 2),
        ('Homem morre em confronto com a PM após apreensão de drogas', 0),
        ('PF deflagra operação contra lavagem de dinheiro do tráfico e bloqueia R$ 20 milhões', 7),
        # "Apreensão" = preocupação: fora do site (21/11/2026).
        ('A agenda econômica de Lula gera apreensão no mercado financeiro', None),
        ('Clima de apreensão toma conta de moradores após ataques', None),
        ('Investidores apreensivos com juros', None),
        ('PMSE apreende drogas e dinheiro durante ação policial no Mercado Municipal de Lagarto', 0),
        ('Apreensão de drogas no mercado municipal leva dois à prisão', 0),
        ('Bolsas da Ásia fecham em baixa com apreensão sobre IA', None),
        ('Receita realiza quatro abordagens com apreensão na Ponte da Amizade', 8),
        ('Polícia Federal cumpre mandados de busca e apreensão sobre concessão de CACs em Ipatinga', 8),
    ]
    erros = 0
    for t, esperado in casos:
        ok_rel = relevante(t) == (esperado is not None)
        cat = categorias(t)[0] if relevante(t) else None
        ok_cat = esperado is None or cat == esperado
        if not (ok_rel and ok_cat):
            erros += 1
            print('ERRO:', t, '| relevante:', relevante(t), '| categoria:', cat, '| esperado:', esperado)
    print(f'{len(casos) - erros}/{len(casos)} casos corretos')
    raise SystemExit(1 if erros else 0)
