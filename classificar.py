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
    r'\barmas?\b|armamentos?|fuzil|fuzis|pistolas?|rev[oó]lver|rev[oó]lveres|\bmuni[çc][ãaõo]|cartuchos?|'
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
    r'fuzil|fuzis|\bmuni[çc][ãaõo]|pistolas?\b|rev[oó]lver|armas? de fogo|arsenal|contraband|descaminho|'
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
    r'|(?<!busca e )\bapreens[ãa]o\s+(?:sobre|quanto|diante)\b|\bapreensiv[oa]s?\b'
    # Preocupação dita por alguém (23/11/2026: "Comércio estima crescimento..., mas ressalta apreensão").
    r'|\b(?:ressalta|ressaltam|ressaltou|demonstra|demonstram|demonstrou|manifesta|manifestam|manifestou|expressa|expressam|'
    r'expressou|relata|relatam|relatou|admite|admitem|admitiu|vive|vivem|viveu|vê|veem|viu|acompanha|acompanham|'
    r'acompanhou|observa|observam)\s+(?:com\s+)?(?:certa\s+|muita\s+|grande\s+)?apreens[ãa]o\b(?!\s+(?:de|da|do|das|dos|judicial|policial)\b)', re.I)


def apreensao_sentimento(titulo):
    """Título em que "apreensão" é preocupação, sem outro termo forte de apreensão policial."""
    if not _APREENSAO_SENTIMENTO.search(titulo):
        return False
    return not FORTE.search(_APREENSAO_SENTIMENTO.sub(' ', titulo))


# Aviso fúnebre (funerária comunica falecimento, nota de pesar, velório, missa de sétimo dia) nunca
# entra no site, mesmo com palavra parecida com apreensão. Pedido do dono do site, 21/11/2026.
# Ação policial ligada a isso (Operação Luctus: venda de dados de óbitos a funerárias; prisão
# durante velório) continua entrando.
_FUNEBRE = re.compile(r'funer[áa]rias?|falecimento|nota de pesar|com (?:profundo )?pesar|vel[óo]rio|sepultamento|'
                      r'missa de (?:s[ée]timo|7º?) dia|obitu[áa]rio|in memoriam|descanse em paz', re.I)
_ACAO_POLICIAL = re.compile(r'opera[çc][ãa]o|\bpren(?:de|dem|deu)|\bpres[oa]s?\b|pris[ãa]o|pol[íi]cia|investig|esquema|'
                            r'tr[aá]fico|apreend|\bPF\b|\bPM\b|\bPRF\b|Gaeco|mandados?', re.I)


def aviso_funebre(titulo):
    return bool(_FUNEBRE.search(titulo) and not _ACAO_POLICIAL.search(titulo))


# Busca sem apreensão ("nenhum entorpecente foi localizado", "nada foi encontrado"): não é apreensão.
# Caso real (21/11/2026): virou manchete porque o texto citava 176 kg de uma apreensão ANTERIOR.
_SEM_APREENSAO = re.compile(
    r"\b(?:nenhum|nenhuma)\s+(?:\w+\s+){0,2}?(?:droga|entorpecente|arma|material|il[ií]cito|objeto|subst[âa]ncia|muni[çc][ãa]o)s?\b"
    r"[^.]{0,40}?(?:localizad|encontrad|apreendid|achad)\w*"
    r"|\bnada\s+(?:de\s+il[ií]cito\s+)?(?:foi|é)\s+(?:localizad|encontrad|apreendid|achad)\w*"
    r"|\bsem\s+(?:encontrar|localizar|apreender)\s+(?:nada|drogas?|armas?)\b"
    r"|\bn[ãa]o\s+(?:foi|foram)\s+(?:localizad|encontrad|apreendid)\w*\s+(?:nenhum|nenhuma|nada|drogas?|armas?|entorpecentes?)", re.I)


def sem_apreensao(titulo):
    return bool(_SEM_APREENSAO.search(titulo))


# Fato no exterior (22/11/2026: prisão do "Chapo Isidro" no México entrava na faixa AGORA): fica fora do
# site, a não ser que o título cite polícia, órgão ou lugar do Brasil ("PF prende mexicano em Guarulhos").
_EXTERIOR = re.compile(
    r"\bM[ée]xico\b|\bmexican[oa]s?\b|\bSinaloa\b|\bJalisco\b|\bEl Chapo\b|\bChapo Isidro\b|\bFBI\b|\bDEA\b"
    r"|\b(?:nos|nas)\s+(?:Estados Unidos|EUA)\b"
    r"|\b(?:na|em)\s+(?:Col[ôo]mbia|Venezuela|Argentina|Bol[ií]via|Espanha|It[áa]lia|Holanda|B[ée]lgica|França|Alemanha|China|Europa"
    r"|Austr[áa]lia|Inglaterra|Rússia|Ucr[âa]nia|Israel|Gaza|[ÁA]frica)\b"
    r"|\b(?:no|em)\s+(?:Equador|Peru|Chile|Uruguai|Jap[ãa]o|Reino Unido|Haiti|Panam[áa])\b"
    # país estrangeiro como sujeito da frase ("Por que a China arrisca...", "O Irã está..."), 22/11/2026;
    # "com a Bolívia" / "a Europa" como destino não contam.
    r"|(?:^|\bque\s+|:\s*)(?:a|o)\s+(?:China|R[úu]ssia|Coreia do Norte|Ucr[âa]nia|Venezuela|Col[ôo]mbia|Argentina"
    r"|Bol[ií]via|EUA|Estados Unidos|Europa|Israel|Ir[ãa])\b", re.I)
_BRASIL = re.compile(
    r"\b(?:Brasil|brasileir\w*|PF|PRF|PM\w*|PC\w*|Pol[ií]cia (?:Federal|Rodovi[áa]ria|Civil|Militar|Penal)|Receita Federal|RFB"
    r"|Brigada Militar|Gaeco|FICCO|BPFron|DOF|Gefron|Ibama|Marinha do Brasil|Ex[ée]rcito Brasileiro|BR-\d+|aeroporto de"
    r"|Acre|Alagoas|Amap[áa]|Amazonas|Bahia|Cear[áa]|Distrito Federal|Esp[ií]rito Santo|Goi[áa]s|Maranh[ãa]o|Mato Grosso"
    r"|Minas Gerais|Par[áa]|Para[ií]ba|Paran[áa]|Pernambuco|Piau[ií]|Rio de Janeiro|Rio Grande|Rond[ôo]nia|Roraima"
    r"|Santa Catarina|S[ãa]o Paulo|Sergipe|Tocantins|Foz do Igua[çc]u|Guarulhos|Santos|Paranagu[áa]|Manaus|Bel[ée]m"
    r"|Fortaleza|Recife|Salvador|Curitiba|Porto Alegre|Florian[óo]polis|Campo Grande|Cuiab[áa]|Goi[âa]nia|Bras[ií]lia"
    r"|BH|Belo Horizonte|CV|PCC|Comando Vermelho|Amaz[ôo]nia)\b", re.I)


def exterior(titulo):
    return bool(_EXTERIOR.search(titulo)) and not _BRASIL.search(titulo)


def relevante(titulo):
    if apreensao_sentimento(titulo) or aviso_funebre(titulo) or sem_apreensao(titulo) or exterior(titulo):
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
        # "comunica" não é "munição" (aviso de falecimento entrava como armas, 21/11/2026).
        ('Funerária Santa Cruz comunica com pesar o falecimento de Deomira Seghetto Ceriolli', None),
        ('Escolas sem casos de sarna em Campo Grande preparam comunicado de alerta', None),
        ('Militares apreenderam rádios comunicadores, munições e outros pertences', 1),
        # Aviso fúnebre nunca entra; operação policial ligada a funerárias/velório entra.
        ('A Funerária Alta Floresta comunica o falecimento do Senhor Justimiano Ferreira', None),
        ('Nota de pesar: morre ex-delegado que comandou apreensão histórica de cocaína', None),
        ('Operação Luctus mira esquema ilegal de venda de dados de óbitos para funerárias', 8),
        ('Polícia Civil prende mulher durante velório por envolvimento em tortura de ex-companheira de traficante', 0),
        # Apreensão no sentido de preocupação dita por alguém (23/11/2026).
        ('AGUARDANDO DECISÕES - Comércio estima crescimento nas vendas em 10% para o final de ano, mas ressalta apreensão', None),
        ('Moradores acompanham com apreensão a cheia do rio', None),
        ('PM realiza grande apreensão de drogas em Campo Grande', 0),
        ('POLÍCIA MILITAR ACOMPANHA APREENSÃO JUDICIAL DE CAMINHONETE EM SABÁUDIA', 3),
        ('Polícia faz apreensão de armas com apreensão de munições em Goiás', 1),
        # Busca sem apreensão não entra (21/11/2026).
        ('Policiais realizaram buscas em vegetação e oficina mecânica na região de Pitangueiras, mas nenhum entorpecente foi localizado durante a varredura.', None),
        ('Polícia faz buscas mas não foram encontradas drogas', None),
        ('PM apreende drogas e nenhum suspeito foi localizado', 0),
        # Fato no exterior fica fora; com polícia ou lugar do Brasil, entra (22/11/2026).
        ('Prisão de chefão do narcotráfico no México exigiu grampos e drones', None),
        ('Forças armadas do México prendem Chapo Isidro em Sinaloa', None),
        ('Autoridades Mexicanas Prendem 14 Membros do Cartel de Sinaloa em Grande Operação no Sul do País', None),
        ('Polícia apreende 2 toneladas de cocaína em porto na Espanha', None),
        ('PF prende mexicano com cocaína no aeroporto de Guarulhos', 0),
        ('Polícia apreende cocaína que seria enviada à Europa em contêiner no Porto de Santos', 0),
        ('PRF apreende maconha vinda do Paraguai na BR-277', 0),
        ('Carga de cocaína vinda da Bolívia é apreendida em Mato Grosso', 0),
        ('Polícia encontra drogas escondidas em churrasqueira e prende dois por tráfico em Franca, SP', 0),
        ('Mexicano é preso com 20 kg de cocaína em BH', 0),
        ('Por que a China arrisca tudo no contrabando de chips de inteligência artificial', None),
        ('Fiscalização apreende drogas e fetos de lhama na fronteira de MS com a Bolívia', 0),
        ('Empresário ligado a envio de cocaína a Europa é preso em Balneário Camboriú', 0),
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
