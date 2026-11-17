#!/usr/bin/env python3
"""Resumo do Radar: fatos, quem atuou, base legal e outros veículos que noticiaram.

Tudo é redigido pelo Radar: os fatos vêm de resumo_fatos.py, as explicações
são textos próprios e o contexto é calculado sobre o próprio acervo (já sem
duplicatas). Nenhuma frase da reportagem é copiada.
"""
import re

from localizar_uf import NOMES_ESTADOS
from resumo_fatos import PREP_UF, _data_extenso, _fmt, _juntar, redigir

ORGAO_PAPEL = {
    'Polícia Federal': 'que investiga crimes federais, como o tráfico internacional de drogas e de armas, o contrabando e os crimes em áreas de fronteira',
    'Polícia Rodoviária Federal': 'que fiscaliza as rodovias federais, por onde circula grande parte das cargas que cruzam o país',
    'Receita Federal': 'que controla a entrada de mercadorias no país e atua contra o contrabando e o descaminho',
    'Polícia Rodoviária Estadual': 'que patrulha as rodovias estaduais',
    'Polícia Militar': 'responsável pelo policiamento ostensivo e pelas abordagens nas ruas e estradas',
    'Polícia Civil': 'que conduz as investigações e os inquéritos no estado',
    'Polícia Penal': 'que atua no sistema prisional',
    'FICCO': 'a Força Integrada de Combate ao Crime Organizado, que reúne forças federais e estaduais',
    'Guarda Municipal': 'que atua na segurança do município',
    'Ibama': 'o órgão federal de fiscalização ambiental',
    'Ministério Público': 'que investiga e denuncia crimes à Justiça',
    'Força Nacional': 'que reforça a segurança pública nos estados a pedido dos governos',
    'Marinha': 'que fiscaliza rios, portos e o litoral',
    'Exército': 'que atua em fronteiras e na fiscalização de produtos controlados',
}
CATEGORIA_NOTA = [
    'O tráfico de drogas é crime previsto na Lei de Drogas (Lei 11.343/2006); apreensões de grande volume costumam ocorrer em rodovias e em regiões de fronteira.',
    'O porte, a posse e o comércio ilegal de armas e munições são crimes previstos no Estatuto do Desarmamento (Lei 10.826/2003).',
    'Contrabando é a entrada ou saída de mercadoria proibida; descaminho é a entrada de mercadoria permitida sem o pagamento dos impostos devidos (Código Penal, artigos 334 e 334-A).',
    'Veículos são apreendidos quando usados no transporte de produtos ilícitos, quando têm sinais de adulteração ou quando são produto de roubo ou furto.',
    'Dinheiro, joias e outros valores costumam ser apreendidos em investigações de tráfico e de lavagem de dinheiro.',
    'Crimes como a extração ilegal de madeira, a pesca predatória e o tráfico de animais silvestres estão previstos na Lei de Crimes Ambientais (Lei 9.605/1998).',
    'A venda de medicamentos falsificados ou sem registro na Anvisa é crime contra a saúde pública (Código Penal, artigo 273).',
    'Bloqueios e sequestros de bens buscam atingir o patrimônio obtido com o crime, uma das principais estratégias contra organizações criminosas.',
    '',
]
CAT_NOME = ['drogas', 'armas e munições', 'contrabando e descaminho', 'veículos', 'dinheiro e valores',
            'crimes ambientais', 'medicamentos e produtos irregulares', 'bloqueio de bens', 'outras apreensões']
# "Entenda": termos que aparecem na notícia, explicados em uma frase (sem citar artigos de lei).
ENTENDA = [
    (r'\bsk[ua]nk|supermaconha', 'Skunk', 'variedade de maconha cultivada para ter mais THC, a substância que causa o efeito da droga; costuma valer mais que a maconha comum.'),
    (r'\bhaxixe', 'Haxixe', 'resina extraída da planta da maconha, prensada em blocos; é mais concentrada que a erva.'),
    (r'pasta[ -]base', 'Pasta-base', 'produto intermediário da cocaína, antes do refino; também é a matéria-prima do crack.'),
    (r'\bcrack\b', 'Crack', 'derivado da pasta-base de cocaína, vendido em pedras para ser fumado.'),
    (r'\bdrogas? sint[ée]ticas?|ecstasy|\bmdma\b|\blsd\b|metanfetamina', 'Drogas sintéticas', 'produzidas em laboratório (como ecstasy, LSD e metanfetamina), e não extraídas de plantas.'),
    (r'\bfuzi[ls]\b', 'Fuzil', 'arma longa de uso restrito das forças armadas e policiais; a apreensão de fuzis indica crime organizado com alto poder de fogo.'),
    (r'\bsimulacro', 'Simulacro', 'réplica de arma de fogo (de brinquedo ou de pressão) usada para intimidar.'),
    (r'\bdescaminho', 'Descaminho', 'entrada de mercadoria permitida no país sem pagar os impostos; contrabando é a entrada de mercadoria proibida.'),
    (r'\bcontrabando|contrabandead', 'Contrabando', 'entrada ou saída de mercadoria proibida no país, como cigarros sem registro e agrotóxicos não autorizados.'),
    (r'cigarros? eletr[ôo]nicos?|\bvapes?\b|\bpods?\b', 'Cigarro eletrônico', 'a venda, a importação e a propaganda são proibidas no Brasil pela Anvisa desde 2009.'),
    (r'canetas? emagrecedoras?', 'Canetas emagrecedoras', 'remédios injetáveis que só podem ser vendidos com receita; as contrabandeadas não têm controle de qualidade.'),
    (r'em flagrante|\bflagrante\b', 'Prisão em flagrante', 'feita no momento do crime ou logo depois; a Justiça decide em seguida se a pessoa continua presa.'),
    (r'mandados? de busca', 'Mandado de busca e apreensão', 'ordem da Justiça que autoriza a polícia a entrar num local e recolher provas.'),
    (r'\bFICCO\b', 'FICCO', 'Força Integrada de Combate ao Crime Organizado: une polícias federais e estaduais numa mesma equipe.'),
    (r'\bDOF\b|Departamento de Opera[çc][õo]es de Fronteira', 'DOF', 'Departamento de Operações de Fronteira, a polícia de fronteira de Mato Grosso do Sul.'),
    (r'\bGefron\b|\bGEFRON\b', 'Gefron', 'Grupo Especial de Segurança na Fronteira, a polícia de fronteira de Mato Grosso.'),
    (r'\bBPFron\b|Batalh[ãa]o de Pol[íi]cia de Fronteira', 'BPFron', 'Batalhão de Polícia de Fronteira, da Polícia Militar do Paraná.'),
    (r'\bfundo falso|compartimento (?:oculto|secreto|falso)', 'Fundo falso', 'espaço escondido montado no veículo ou na bagagem para transportar a carga sem ser visto na abordagem.'),
    (r'\bmula\b|\bmulas\b', 'Mula', 'pessoa paga para transportar a droga, em geral sem saber o tamanho da organização para quem trabalha.'),
    (r'\bagrot[óo]xicos?', 'Agrotóxico contrabandeado', 'produto sem registro no Brasil, que pode contaminar o solo, a água e os alimentos.'),
]


def _entenda(texto):
    vistos, saida = set(), []
    for padrao, termo, explicacao in ENTENDA:
        if termo not in vistos and re.search(padrao, texto, re.I):
            vistos.add(termo)
            saida.append(f'{termo}: {explicacao}')
        if len(saida) == 2:
            break
    return ' '.join(saida)


def _ordinal(n):
    return f'{n}ª'


def _mandados(texto):
    """'1 mandados de prisão' -> 'Foi cumprido 1 mandado de prisão.'"""
    texto = re.sub(r'^1 mandados', '1 mandado', texto)
    return ('Foi cumprido ' if texto.startswith('1 mandado') else 'Foram cumpridos ') + texto + '.'


def _onde(uf):
    return f'{PREP_UF[uf]} {NOMES_ESTADOS[uf]}' if uf in NOMES_ESTADOS else 'no Brasil'


def _agentes(fatos, uf):
    orgaos = (fatos or {}).get('orgaos', [])[:2]
    partes = []
    for o in orgaos:
        papel = ORGAO_PAPEL.get(o)
        if not papel:
            continue
        artigo = 'o' if o in ('Ibama', 'Ministério Público', 'Exército') else 'a'
        partes.append(f'{artigo} {o}, {papel}')
    frases = []
    if partes:
        frases.append('A ação envolveu ' + _juntar(partes) + '.')
    rod = (fatos or {}).get('rodovia', '')
    if rod.startswith('BR-'):
        frases.append(f'A ocorrência foi registrada na {rod}, rodovia federal.')
    elif rod:
        sigla = rod.split('-')[0]
        if sigla in NOMES_ESTADOS:
            de = {'no': 'do', 'na': 'da', 'em': 'de'}[PREP_UF[sigla]]
            frases.append(f'A ocorrência foi registrada na {rod}, rodovia estadual {de} {NOMES_ESTADOS[sigla]}.')
    return ' '.join(frases)


INTERNOS = {'em um fundo falso', 'em um compartimento oculto', 'no tanque de combustível', 'dentro de pneus', 'no porta-malas'}


def _pessoas(n):
    return 'uma pessoa' if n == 1 else f'{_fmt(n)} pessoas'


def _idades(idades):
    if not idades:
        return ''
    if len(idades) == 1:
        return f', de {idades[0]} anos'
    return ', com idades entre ' + f'{min(idades)} e {max(idades)} anos'


def resumo_secoes(item, fatos, ctx=None):
    """Resumo do Radar em seções [(título, texto)], todas redigidas pelo Radar.

    ctx (opcional, calculado sobre o acervo): posição da apreensão no estado e no país
    nos 30 dias anteriores, polo de fronteira, notícias na mesma cidade em 12 meses.
    """
    fatos = fatos or {}
    ctx = ctx or {}
    fonte = item.get('f', '')
    uf = item.get('uf', '')
    cats = item.get('c', [])
    secoes = []

    # 1. O que aconteceu (cidades de origem/destino não são o local da apreensão)
    rota = [x for x in (fatos.get('origem'), fatos.get('destino')) if x]
    local = dict(fatos)
    if rota and local.get('cidades'):
        local['cidades'] = [c for c in local['cidades'] if not any(c.split(' (')[0] in r for r in rota)]
    # Presos, mandados, operação e valores ficam nas seções próprias.
    for k in ('presos', 'presos_texto', 'mandados', 'operacao', 'valor'):
        local.pop(k, None)
    # Sem quantidade, o valor ("R$ 355 mil em mercadorias") é o tamanho da apreensão: fica no fato.
    if fatos.get('valor') and fatos.get('apreendido') and not any(re.search(r'\d', i) for i in fatos['apreendido']):
        local['valor'] = fatos['valor']
    base = redigir(local, '', item.get('d', ''), uf) if fatos else ''
    if not base:
        tema = CAT_NOME[cats[0]] if cats else 'apreensões'
        onde = f' em {item["cid"]} ({uf})' if item.get('cid') else (f' {_onde(uf)}' if uf else '')
        base = f'Notícia sobre {tema}{onde}, publicada por {fonte or "um veículo de imprensa"}.'
    if fatos.get('periodo'):
        base += f' A ocorrência foi na {fatos["periodo"]}, de acordo com a reportagem.'
    secoes.append(('O que aconteceu', base))

    # Por que importa: contexto calculado sobre o próprio acervo do Radar.
    frases = []
    tema = CAT_NOME[cats[0]] if cats else ''
    if ctx.get('rank_br') == 1 and ctx.get('total_br', 0) >= 10:
        frases.append(f'É a maior apreensão de {tema} noticiada no país nos 30 dias anteriores, entre {ctx["total_br"]} com quantidade informada.')
    elif ctx.get('rank_br') and ctx['rank_br'] <= 5 and ctx.get('total_br', 0) >= 10:
        frases.append(f'Está entre as cinco maiores apreensões de {tema} noticiadas no país nos 30 dias anteriores ({_ordinal(ctx["rank_br"])} de {ctx["total_br"]}).')
    elif ctx.get('rank_uf') == 1 and ctx.get('total_uf', 0) >= 3:
        frases.append(f'É a maior apreensão de {tema} noticiada {_onde(uf)} nos 30 dias anteriores, entre {ctx["total_uf"]} com quantidade informada.')
    elif ctx.get('rank_uf') and ctx['rank_uf'] <= 3 and ctx.get('total_uf', 0) >= 5:
        frases.append(f'É a {_ordinal(ctx["rank_uf"])} maior apreensão de {tema} noticiada {_onde(uf)} nos 30 dias anteriores, entre {ctx["total_uf"]}.')
    if ctx.get('polo'):
        frases.append(f'{item.get("cid") or "A região"} faz parte do polo {ctx["polo"]}, uma das rotas de fronteira por onde entram '
                      'drogas, armas e contrabando no Brasil.')
    if ctx.get('cidade_12m', 0) >= 3 and item.get('cid'):
        frases.append(f'O Radar registrou {ctx["cidade_12m"]} notícias de apreensões em {item["cid"]} nos 12 meses anteriores.')
    n_fontes = len([o for o in item.get('o', []) if o and o[0]]) + 1
    if n_fontes >= 3:
        frases.append(f'O caso repercutiu: {n_fontes} veículos publicaram a notícia.')
    if frases:
        secoes.append(('Por que importa', ' '.join(frases)))

    # 2. Como foi a ação
    frases = []
    if fatos.get('como'):
        frases.append('A apreensão foi feita ' + _juntar(fatos['como']) + '.')
    if fatos.get('esconderijo') or fatos.get('veiculo'):
        veic = fatos.get('veiculo')
        artigo = 'uma' if veic in ('caminhonete', 'motocicleta', 'van', 'embarcação', 'aeronave') else 'um'
        no_veiculo = [e for e in fatos.get('esconderijo', []) if e in INTERNOS]
        outros = [e for e in fatos.get('esconderijo', []) if e not in INTERNOS]
        if veic and no_veiculo:
            frases.append(f'O material estava escondido {_juntar(no_veiculo)} de {artigo} {veic}.')
        elif veic:
            frases.append(f'O caso envolveu {artigo} {veic}.')
        elif no_veiculo:
            frases.append(f'O material estava escondido {_juntar(no_veiculo)} do veículo.')
        if outros:
            frases.append(f'Parte do material estava {_juntar(outros)}.' if no_veiculo else f'O material foi encontrado {_juntar(outros)}.')
    # Trajeto (de onde veio, para onde ia) não entra no resumo: só o local da apreensão.
    if fatos.get('rodovia'):
        rod = fatos['rodovia']
        if rod.startswith('BR-'):
            frases.append(f'A {rod} é uma rodovia federal, fiscalizada pela Polícia Rodoviária Federal.')
        elif rod.split('-')[0] in NOMES_ESTADOS:
            sigla = rod.split('-')[0]
            de = {'no': 'do', 'na': 'da', 'em': 'de'}[PREP_UF[sigla]]
            frases.append(f'A {rod} é uma rodovia estadual {de} {NOMES_ESTADOS[sigla]}.')
    if fatos.get('operacao'):
        frases.append(f'A ação fez parte da {fatos["operacao"]}.')
    if frases:
        secoes.append(('Como foi a ação', ' '.join(frases)))

    # 3. Envolvidos
    frases = []
    identificados = fatos.get('presos_iniciais') or []
    if identificados:
        # Só iniciais e idade: "J. C. S., de 34 anos".
        lista = [re.sub(r' \((\d+) anos\)$', r', de \1 anos', p) for p in identificados]
        n = max(len(lista), fatos.get('presos') or 0)
        verbo = 'Foi preso' if n == 1 else 'Foram presos'
        juntos = lista[0] if len(lista) == 1 else ', '.join(lista[:-1]) + ', e ' + lista[-1]
        frases.append(f'{verbo} {juntos}.' + (f' Ao todo, {_fmt(n)} pessoas foram presas.' if n > len(lista) else ''))
    elif fatos.get('presos'):
        frases.append(f'{_pessoas(fatos["presos"]).capitalize()} {"foi presa" if fatos["presos"] == 1 else "foram presas"}'
                      f'{_idades(fatos.get("idades"))}.')
    elif fatos.get('presos_texto'):
        flagrante = ' em flagrante' if 'flagrante' in fatos['presos_texto'] else ''
        idades = fatos.get('idades') or []
        if len(idades) == 1:
            frases.append(f'Uma pessoa, de {idades[0]} anos, foi presa{flagrante}.')
        elif idades:
            frases.append(f'Pessoas com idades entre {min(idades)} e {max(idades)} anos foram presas{flagrante}.')
        else:
            frases.append(f'Segundo a reportagem, {fatos["presos_texto"]}.')
    if fatos.get('mandados'):
        frases.append(_mandados(fatos["mandados"]))
    if fatos.get('crimes'):
        frases.append('Os envolvidos podem responder por ' + _juntar(fatos['crimes']) + '.')
    if fatos.get('encaminhamento'):
        frases.append(f'O caso foi encaminhado à {fatos["encaminhamento"]}.'.replace('à Polícia', 'à Polícia')
                      .replace('à Delegacia', 'à Delegacia').replace('à DP', 'ao DP').replace('à Distrito', 'ao Distrito')
                      .replace('à Plantão', 'ao Plantão'))
    pessoas = bool(frases)  # presos, mandados, crimes ou encaminhamento: há pessoas envolvidas
    if (fatos.get('valor') and re.search(r'mil|milh|bilh|\d\.\d{3}', fatos['valor'])  # R$ 379 não informa nada
            and fatos['valor'] not in base):
        frases.append(f'Os valores citados chegam a {fatos["valor"]}.')
    if pessoas:
        frases.append('Pessoas presas ou investigadas são consideradas inocentes até decisão definitiva da Justiça.')
    if frases:
        secoes.append(('Envolvidos e próximos passos', ' '.join(frases)))

    # 4. Quem atuou
    agentes = _agentes({k: v for k, v in fatos.items() if k != 'rodovia'}, uf)
    if agentes:
        secoes.append(('Quem atuou', agentes))

    # 5. Entenda: termos da notícia explicados em uma frase.
    termos = _entenda(' '.join([item.get('t', ''), item.get('r', ''), ' '.join(fatos.get('apreendido', [])),
                                ' '.join(fatos.get('esconderijo', [])), ' '.join(fatos.get('crimes', [])), fatos.get('presos_texto', '')]))
    if termos:
        secoes.append(('Entenda', termos))

    # 6. Repercussão
    outras = [o[0] for o in item.get('o', []) if o and o[0]]
    if outras:
        secoes.append(('Quem noticiou', f'A notícia foi publicada por {fonte} e também por {_juntar(outras[:8])}.'))
    return [(t, re.sub(r'\s+', ' ', x).strip()) for t, x in secoes if x.strip()]


def resumo_ampliado(item, fatos):
    """Texto corrido (parágrafos separados por linha em branco), para descrição e busca."""
    return '\n\n'.join(texto for _, texto in resumo_secoes(item, fatos))
