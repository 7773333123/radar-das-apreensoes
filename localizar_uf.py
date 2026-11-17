#!/usr/bin/env python3
"""Identifica a UF de uma notícia por evidência explícita.

Ordem das evidências (a primeira que der um único estado vence):
  1. UF informada por fonte direta (feed estadual, órgão estadual cadastrado);
  2. veículo/órgão de origem (domínio *.ba.gov.br, "Polícia Civil do Paraná", "Repórter PB");
  3. título e resumo: nome do estado, sigla explícita ("Belém (PA)", "Maringá/PR")
     ou nome de município (lista oficial de 5.570 municípios em municipios.json).

A comparação de nomes é sensível a acentos e maiúsculas: "para" (preposição)
não é "Pará", e "canoas" não é a cidade de Canoas.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

PASTA = Path(__file__).resolve().parent
NOMES_ESTADOS = {
    'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas', 'BA': 'Bahia',
    'CE': 'Ceará', 'DF': 'Distrito Federal', 'ES': 'Espírito Santo', 'GO': 'Goiás',
    'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul', 'MG': 'Minas Gerais',
    'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná', 'PE': 'Pernambuco', 'PI': 'Piauí',
    'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte', 'RS': 'Rio Grande do Sul',
    'RO': 'Rondônia', 'RR': 'Roraima', 'SC': 'Santa Catarina', 'SP': 'São Paulo',
    'SE': 'Sergipe', 'TO': 'Tocantins',
}
ESTADOS = set(NOMES_ESTADOS)
CAPITAIS = {
    'Rio Branco': 'AC', 'Maceió': 'AL', 'Macapá': 'AP', 'Manaus': 'AM', 'Salvador': 'BA',
    'Fortaleza': 'CE', 'Brasília': 'DF', 'Vitória': 'ES', 'Goiânia': 'GO', 'São Luís': 'MA',
    'Cuiabá': 'MT', 'Campo Grande': 'MS', 'Belo Horizonte': 'MG', 'Belém': 'PA',
    'João Pessoa': 'PB', 'Curitiba': 'PR', 'Recife': 'PE', 'Teresina': 'PI',
    'Rio de Janeiro': 'RJ', 'Natal': 'RN', 'Porto Alegre': 'RS', 'Porto Velho': 'RO',
    'Boa Vista': 'RR', 'Florianópolis': 'SC', 'São Paulo': 'SP', 'Aracaju': 'SE', 'Palmas': 'TO',
}
# Apelidos e regiões que identificam o estado sem ambiguidade.
APELIDOS = {
    'Grande Vitória': 'ES', 'Baixada Fluminense': 'RJ', 'Baixada Santista': 'SP',
    'Região Metropolitana de Belém': 'PA', 'Grande Florianópolis': 'SC', 'Grande BH': 'MG',
    'Zona da Mata Mineira': 'MG', 'Triângulo Mineiro': 'MG', 'Recôncavo Baiano': 'BA',
    'Sertão Pernambucano': 'PE', 'Agreste Pernambucano': 'PE', 'Vale do Itajaí': 'SC',
    'Serra Gaúcha': 'RS', 'Litoral Norte Gaúcho': 'RS', 'Distrito Federal': 'DF',
    'capital paulista': 'SP', 'capital fluminense': 'RJ', 'capital mineira': 'MG',
    'capital baiana': 'BA', 'capital paraense': 'PA', 'capital gaúcha': 'RS',
    'capital paranaense': 'PR', 'capital catarinense': 'SC', 'capital cearense': 'CE',
    'capital pernambucana': 'PE', 'capital amazonense': 'AM', 'capital goiana': 'GO',
    'capital maranhense': 'MA', 'capital potiguar': 'RN', 'capital paraibana': 'PB',
    'capital alagoana': 'AL', 'capital sergipana': 'SE', 'capital piauiense': 'PI',
    'capital mato-grossense': 'MT', 'capital sul-mato-grossense': 'MS', 'capital capixaba': 'ES',
    'capital rondoniense': 'RO', 'capital roraimense': 'RR', 'capital amapaense': 'AP',
    'capital acreana': 'AC', 'capital tocantinense': 'TO', 'capital federal': 'DF',
}
# Municípios cujo nome também é palavra comum, nome de pessoa ou de operação
# policial: só contam quando acompanhados do estado ("Natal (RN)").
NOMES_AMBIGUOS = {
    'Natal', 'Vitória', 'Serra', 'Bonito', 'Formosa', 'Estrela', 'Esperança', 'Liberdade',
    'Triunfo', 'Paraíso', 'Alegre', 'Central', 'Floresta', 'Bandeirantes', 'Pedras', 'Campos',
    'Planalto', 'Fronteira', 'Amparo', 'Recreio', 'Saudade', 'Aurora', 'Glória', 'Princesa',
    'Brasil Novo', 'Mundo Novo', 
    'Cristal', 'Divino', 'Jesus', 'Bom Jesus', 'Santa Cruz', 'São José', 'Santo Antônio',
    'São Francisco', 'São Pedro', 'São João', 'Santa Maria', 'Santa Luzia', 'Santa Rita',
    'Santa Helena', 'Santa Inês', 'Santa Rosa', 'São Sebastião', 'São Domingos', 'São Gabriel',
    'Nova Esperança', 'Boa Esperança', 'Bom Sucesso', 'Sucesso', 'Ouro', 'Prata', 'Barra',
    'Canaã', 'Jardim', 'Cruzeiro', 'Lagoa', 'Cachoeira', 'Monte Alegre', 'Riachão', 'Cascata',
    'Colorado', 'Independência', 'Progresso', 'Sossego', 'Tupi', 'Marcos', 'Augusto', 'Fernando',
    'Mário', 'Gaúcha', 'Lula', 'Bastos', 'Ribeiro', 'Ferraz', 'Andradas', 'Contenda', 'Anta',
    'Ingá', 'Porto', 'Rio', 'Ilha', 'Mar', 'Areia', 'Cajá', 'Feliz', 'Inocência', 'Itaú',
    'Capela', 'Conquista', 'Delta',
    'Estiva', 'Matriz', 'Machado', 'Palmeira', 'Palmeiras', 
    'Arapuá', 'Óleo', 'Pinhão', 'Piranhas', 'Toledo', 
    'Cocal', 'Guarani', 'Indiana', 'Mirante', 'Primavera', 'Queimadas', 'Serrinha', 'Sapé',
    'Tabuleiro', 'Areial', 'Brasil', 'Brasileira', 'Valença', 'Prudente de Morais',
}
NOMES_AMBIGUOS.discard('')
SIGLA_EXPLICITA = re.compile(r'(?:\(|/|\s[-–]\s|\b(?:em|no|na|de|do|da|pelo|pela|para o|para a)\s)(' + '|'.join(sorted(ESTADOS)) + r')(?![A-Za-zÀ-ÿ])\)?')
SIGLA_EM_NOME = re.compile(r'(?<![A-Za-zÀ-ÿ])(' + '|'.join(sorted(ESTADOS)) + r')(?![A-Za-zÀ-ÿ])')
OPERACAO = re.compile(r'\b[Oo]pera[çc][ãa]o\s+(?:[A-ZÀ-Ý][\wÀ-ÿ\'-]*\s*){1,3}')
DOMINIO_ESTADUAL = re.compile(r'(?:^|\.)(' + '|'.join(u.lower() for u in ESTADOS) + r')\.(?:gov|leg|jus|mp|def)\.br$')
# Veículos regionais frequentes no acervo (nome -> UF).
VEICULOS = {
    'Campo Grande News': 'MS', 'GZH': 'RS', 'Correio Braziliense': 'DF', 'Metrópoles': 'DF',
    'TNH1': 'AL', 'Folha Vitória': 'ES', 'Agência Pará': 'PA', 'O Liberal': 'PA',
    'Diário do Pará': 'PA', 'Roma News': 'PA', 'A Tarde': 'BA', 'Correio': 'BA',
    'Bahia Notícias': 'BA', 'NSC Total': 'SC', 'ND Mais': 'SC', 'Banda B': 'PR',
    'Bem Paraná': 'PR', 'Tribuna PR': 'PR', 'Massa News': 'PR', 'O Povo': 'CE',
    'Diário do Nordeste': 'CE', 'Jornal do Commercio': 'PE', 'Diario de Pernambuco': 'PE',
    'JC': 'PE', 'Estado de Minas': 'MG', 'O Tempo': 'MG', 'Itatiaia': 'MG', 'O Dia': 'RJ',
    'Extra': 'RJ', 'A Gazeta': 'ES', 'ES Hoje': 'ES', 'Tribuna Online': 'ES', 'Midia Jur': 'MT',
    'Única News': 'MT', 'Olhar Direto': 'MT', 'Gazeta Digital': 'MT', 'Primeira Página': 'MT',
    'Rondônia ao Vivo': 'RO', 'Rondoniaovivo': 'RO', 'Diário da Amazônia': 'RO', 'A Crítica': 'AM',
    'Portal do Holanda': 'AM', 'D24AM': 'AM', 'Em Tempo': 'AM', 'SelesNafes.com': 'AP',
    'G1 AP': 'AP', 'ac24horas': 'AC', 'Folha BV': 'RR', 'Roraima em Tempo': 'RR',
    'Cidadeverde.com': 'PI', 'GP1': 'PI', 'Meio Norte': 'PI', 'O Imparcial': 'MA',
    'Imirante': 'MA', 'Tribuna do Norte': 'RN', 'Agora RN': 'RN', 'Portal Correio': 'PB',
    'Jornal da Paraíba': 'PB', 'F5 News': 'SE', 'Infonet': 'SE', 'Gazeta de Alagoas': 'AL',
    'Cada Minuto': 'AL', 'Mais Goiás': 'GO', 'O Popular': 'GO', 'Jornal Opção': 'GO',
    'Diário da Região': 'SP', 'Jornal Cruzeiro do Sul': 'SP', 'Agência SP': 'SP',
    'Conexão Tocantins': 'TO', 'T1 Notícias': 'TO', 'Diário do Grande ABC': 'SP',
    'Eu vi em Linhares': 'ES', 'SCC10': 'SC', 'Confirma Notícia': 'PA', 'Repórter PB': 'PB',
}


def _fronteira(nome):
    return re.compile(r'(?<![A-Za-zÀ-ÿ])' + re.escape(nome) + r'(?![A-Za-zÀ-ÿ])')


@lru_cache(maxsize=1)
def _indice():
    """Lista (nome, regex, ufs) ordenada do nome mais longo para o mais curto."""
    municipios = json.loads((PASTA / 'municipios.json').read_text(encoding='utf-8'))
    por_nome = {}
    for uf, cidades in municipios.items():
        for cidade in cidades:
            por_nome.setdefault(cidade, set()).add(uf)
    entradas = {}
    for nome, ufs in por_nome.items():
        if nome in NOMES_AMBIGUOS or len(nome) < 4:
            continue
        if len(ufs) > 1:
            if nome in CAPITAIS:
                ufs = {CAPITAIS[nome]}  # "Campo Grande" = capital de MS
            else:
                ufs = set()  # homônimo: só conta se o estado também aparecer
        entradas[nome] = ('municipio', ufs)
    for nome, uf in APELIDOS.items():
        entradas[nome] = ('estado', {uf})
    for uf, nome in NOMES_ESTADOS.items():
        entradas[nome] = ('estado', {uf})  # estado prevalece sobre município homônimo
    ordem = sorted(entradas, key=len, reverse=True)
    # Uma regex única por bloco de nomes é muito mais rápida que 5.600 buscas.
    blocos = []
    for i in range(0, len(ordem), 400):
        parte = ordem[i:i + 400]
        blocos.append(re.compile(r'(?<![A-Za-zÀ-ÿ])(' + '|'.join(re.escape(n) for n in parte) + r')(?![A-Za-zÀ-ÿ])'))
    return entradas, blocos


def _ufs_no_texto(texto, detalhado=False):
    """Retorna (ufs_por_estado_ou_sigla, ufs_por_municipio[, ufs_de_municipio_apos_'em'])."""
    if not texto:
        return (set(), set(), set()) if detalhado else (set(), set())
    texto = OPERACAO.sub(' ', texto)  # "Operação Natal" não é Natal/RN
    texto = re.sub(r"\b[Dd][’'´`]", "d'", texto)  # "São Jorge D’Oeste" = "São Jorge d'Oeste"
    estados, cidades, local = set(), set(), set()
    for m in SIGLA_EXPLICITA.finditer(texto):
        estados.add(m.group(1))
    entradas, blocos = _indice()
    ocupado = [False] * len(texto)
    achados = []
    for bloco in blocos:
        for m in bloco.finditer(texto):
            achados.append((m.start(), m.end(), m.group(1)))
    # Nome mais longo primeiro: "Pará de Minas" não vira "Pará".
    for ini, fim, nome in sorted(achados, key=lambda a: a[0] - a[1]):
        if any(ocupado[ini:fim]):
            continue
        for k in range(ini, fim):
            ocupado[k] = True
        tipo, ufs = entradas[nome]
        (estados if tipo == 'estado' else cidades).update(ufs)
        # "... em Campinas": a cidade depois de "em" costuma ser o local do fato.
        if tipo == 'municipio' and re.search(r'\b(?:em|no município de|na cidade de)\s+$', texto[max(0, ini - 25):ini]):
            local.update(ufs)
    return (estados, cidades, local) if detalhado else (estados, cidades)


def uf_da_fonte(noticia, fontes_cadastradas=None):
    dominio = str(noticia.get('dominio_fonte') or '').lower().removeprefix('www.')
    m = DOMINIO_ESTADUAL.search(dominio)
    if m:
        return m.group(1).upper()
    for item in fontes_cadastradas or []:
        d = item.get('dominio', '').lower()
        if item.get('uf') and d and (dominio == d or dominio.endswith('.' + d)):
            return item['uf']
    fonte = str(noticia.get('fonte') or '').strip()
    if fonte in VEICULOS:
        return VEICULOS[fonte]
    if fonte and fonte != 'G1':
        estados, _ = _ufs_no_texto(fonte)
        siglas = {s for s in SIGLA_EM_NOME.findall(fonte) if s in ESTADOS}
        candidatos = estados | siglas
        if len(candidatos) == 1:
            return next(iter(candidatos))
    url = str(noticia.get('url_original') or '')
    m = re.match(r'https?://g1\.globo\.com/([a-z]{2})/', url)
    if m and m.group(1).upper() in ESTADOS:
        return m.group(1).upper()
    return ''


def inferir_uf(noticia, fontes_cadastradas=None):
    """Devolve a sigla da UF ou '' quando não há evidência inequívoca."""
    titulo = str(noticia.get('titulo') or '')
    fonte = str(noticia.get('fonte') or '')
    if fonte and titulo.endswith(' - ' + fonte):
        titulo = titulo[:-len(fonte) - 3]
    estados, cidades, local = _ufs_no_texto(titulo, detalhado=True)
    # Estado escrito no título ("em SC", "no Maranhão") vence o estado do veículo:
    # um jornal gaúcho que noticia apreensão em SC não faz dela uma notícia do RS.
    if len(estados) == 1:
        return next(iter(estados))
    if noticia.get('uf_fonte') in ESTADOS:
        return noticia['uf_fonte']
    uf = uf_da_fonte(noticia, fontes_cadastradas)
    if uf:
        return uf
    if not estados and not cidades:
        estados, cidades, local = _ufs_no_texto(str(noticia.get('descricao') or noticia.get('resumo') or ''), detalhado=True)
    if len(estados) == 1:
        return next(iter(estados))  # estado explícito vence município
    if not estados and len(cidades) == 1:
        return next(iter(cidades))
    if not estados and len(local) == 1:
        return next(iter(local))
    return ''


if __name__ == '__main__':
    import sys
    for linha in sys.argv[1:]:
        print(repr(linha), '->', inferir_uf({'titulo': linha}) or '?')


def municipios_no_texto(texto):
    """Municípios citados (nome oficial, UF), na ordem em que aparecem.

    Só nomes sem homônimo em outro estado (ou capitais); homônimos ficam de fora.
    """
    if not texto:
        return []
    texto = OPERACAO.sub(' ', texto)
    texto = re.sub(r"\b[Dd][’'´`]", "d'", texto)
    entradas, blocos = _indice()
    achados = []
    for bloco in blocos:
        for m in bloco.finditer(texto):
            achados.append((m.start(), m.end(), m.group(1)))
    ocupado = [False] * len(texto)
    escolhidos = []
    for ini, fim, nome in sorted(achados, key=lambda a: a[0] - a[1]):
        if any(ocupado[ini:fim]):
            continue
        for k in range(ini, fim):
            ocupado[k] = True
        tipo, ufs = entradas[nome]
        if tipo == 'municipio' and len(ufs) == 1:
            escolhidos.append((ini, nome, next(iter(ufs))))
    vistos, saida = set(), []
    for _, nome, uf in sorted(escolhidos):
        if nome not in vistos:
            vistos.add(nome)
            saida.append((nome, uf))
    return saida


@lru_cache(maxsize=None)
def _cidades_da_uf(uf):
    """Regex com os municípios de uma UF (inclui homônimos de outros estados: a UF já é conhecida)."""
    municipios = json.loads((PASTA / 'municipios.json').read_text(encoding='utf-8'))
    nomes = [c for c in municipios.get(uf, []) if c not in NOMES_AMBIGUOS and len(c) >= 4 and c != NOMES_ESTADOS.get(uf)]
    if not nomes:
        return None
    nomes.sort(key=len, reverse=True)
    return re.compile(r'(?<![A-Za-zÀ-ÿ#])(' + '|'.join(re.escape(n) for n in nomes) + r')(?![A-Za-zÀ-ÿ])')


# Capital com o mesmo nome do estado: só vale com indicação de que é a cidade.
CAPITAL_HOMONIMA = {'SP': 'São Paulo', 'RJ': 'Rio de Janeiro'}
INDICA_CAPITAL = re.compile(r'capital (?:paulista|fluminense)|cidade d[eo] (?:São Paulo|Rio)|[Zz]ona (?:Norte|Sul|Leste|Oeste|Central)|'
                            r'Baixada Fluminense|centro d[oe] (?:São Paulo|Rio)|\bna capital\b')
# Município com nome de país ("Equador"/RN) e cidades citadas como origem, destino ou moradia.
NAO_CIDADE = {'Equador', 'Bolívia', 'Paraguai', 'Peru', 'Chile', 'Colômbia', 'Argentina', 'Venezuela', 'Uruguai', 'México', 'Brasil'}
ANTES_NAO_LOCAL = re.compile(r'\b(?:natural de|morador(?:a|es)? de|residente (?:em|de)|nascid[oa] em|vind[oa]s? de|saiu de|sa[íi]da de|'
                             r'proveniente de|oriund[oa]s? de|com destino a|destinad[oa]s? a|levad[oa]s? (?:para|a)|seguia (?:para|a)|'
                             r'rumo a|para|at[ée]|bairro|bairro d[aeo]s?|vila|jardim|rua|avenida|av\.|travessa|loteamento|'
                             r'conjunto|comunidade|residencial|praia|distrito de|estrada|fazenda|s[íi]tio|condom[íi]nio)\s+$', re.I)
PERTO_DE_LOCAL = re.compile(r'\b(?:em|no município de|na cidade de|no interior de|na zona rural de|perto de|próximo a|nas proximidades de)\s+$')


# Contexto que indica que a cidade NÃO é o local da apreensão, mesmo depois de "em":
# para onde o preso foi levado, onde mora, onde foi julgado ou enterrado.
NAO_LOCAL_PERTO = re.compile(r'encaminhad|conduzid|levad[oa]|apresentad|transferid|recambiad|delegacia|presídio|penitenci|'
                             r'cadeia|audi[êe]ncia|julgad|f[óo]rum|morador|mora |moram |reside|natural|nascid|vel[óo]rio|'
                             r'sepultad|enterrad|internad|hospital', re.I)
# Abertura com o lugar: "Ubatã: suspeito...", "MEDIANEIRA, PR – ...", "Foz do Iguaçu (PR) - ...".
DATELINE = re.compile(r'^\s*([A-ZÀ-Ý][\wÀ-ÿ\'’. -]{2,40}?)\s*(?::|(?:[,/]\s*|\s+\()[A-Z]{2}\)?\s*[–—-])', re.U)


def cidade_do_fato(uf, titulo='', resumo='', cidades_fatos=(), rota=()):
    """Município ONDE A APREENSÃO OCORREU, ou '' quando o texto não diz com clareza.

    Só vale a cidade escrita como local do fato: depois de "em", "no município de",
    "na cidade de", "no interior de", "perto de" (título ou começo do resumo), ou na
    abertura da notícia ("Ubatã: ...", "MEDIANEIRA, PR – ..."). Não valem: cidade só
    citada (delegacia, moradia, origem/destino da carga, julgamento), bairros e nomes
    de país. Só municípios da UF da notícia (resolve homônimos de outros estados).
    """
    if uf not in NOMES_ESTADOS:
        return ''
    regex = _cidades_da_uf(uf)
    if not regex:
        return ''
    rota_txt = ' '.join(rota or ())

    def valida(nome):
        return nome not in rota_txt and nome not in NAO_CIDADE

    def no_local(texto):
        texto = OPERACAO.sub(' ', texto or '')
        texto = re.sub(r"\b[Dd][’'´`]", "d'", texto)
        for m in regex.finditer(texto):
            nome, ini = m.group(1), m.start()
            antes = texto[max(0, ini - 45):ini]
            if (valida(nome) and PERTO_DE_LOCAL.search(texto[max(0, ini - 25):ini])
                    and not NAO_LOCAL_PERTO.search(antes) and not ANTES_NAO_LOCAL.search(texto[max(0, ini - 30):ini])):
                return nome
        return ''

    def abertura(texto):
        m = DATELINE.match(texto or '')
        if not m:
            return ''
        candidato = m.group(1).strip().rstrip('.').strip()
        achado = regex.fullmatch(candidato) or regex.fullmatch(candidato.title())
        if not achado:
            for c in (candidato, candidato.title()):
                a = regex.search(c)
                if a and a.group(1).lower() == c.lower():
                    achado = a
                    break
        return achado.group(1) if achado and valida(achado.group(1)) else ''

    for texto in (titulo, (resumo or '')[:400]):
        c = abertura(texto) or no_local(texto)
        if c:
            return c
    capital = CAPITAL_HOMONIMA.get(uf)
    if capital and INDICA_CAPITAL.search(f'{titulo} {(resumo or "")[:400]}'):
        return capital
    return ''
