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


def resumo_secoes(item, fatos):
    """Resumo do Radar em seções [(título, texto)], todas redigidas pelo Radar."""
    fatos = fatos or {}
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
    base = redigir(local, '', item.get('d', ''), uf) if fatos else ''
    if not base:
        quando = _data_extenso(item.get('d', ''))
        tema = CAT_NOME[cats[0]] if cats else 'apreensões'
        base = (f'{fonte or "Um veículo de imprensa"} publicou{" em " + quando if quando else ""} uma notícia sobre {tema}'
                f'{" " + _onde(uf) if uf else ""}.')
    if fatos.get('periodo'):
        base += f' A ocorrência foi na {fatos["periodo"]}, de acordo com a reportagem.'
    secoes.append(('O que aconteceu', base))

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
    if fatos.get('origem') and fatos.get('destino'):
        frases.append(f'De acordo com a reportagem, a carga saiu de {fatos["origem"]} e seguiria para {fatos["destino"]}.')
    elif fatos.get('destino'):
        frases.append(f'De acordo com a reportagem, o destino seria {fatos["destino"]}.')
    elif fatos.get('origem'):
        frases.append(f'De acordo com a reportagem, a carga vinha de {fatos["origem"]}.')
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
    if fatos.get('valor'):
        frases.append(f'Os valores citados chegam a {fatos["valor"]}.')
    if frases:
        frases.append('Pessoas presas ou investigadas são consideradas inocentes até decisão definitiva da Justiça.')
        secoes.append(('Envolvidos e próximos passos', ' '.join(frases)))

    # 4. Quem atuou
    agentes = _agentes({k: v for k, v in fatos.items() if k != 'rodovia'}, uf)
    if agentes:
        secoes.append(('Quem atuou', agentes))

    # 6. Repercussão
    outras = [o[0] for o in item.get('o', []) if o and o[0]]
    if outras:
        secoes.append(('Quem noticiou', f'A notícia foi publicada por {fonte} e também por {_juntar(outras[:8])}.'))
    return [(t, re.sub(r'\s+', ' ', x).strip()) for t, x in secoes if x.strip()]


def resumo_ampliado(item, fatos):
    """Texto corrido (parágrafos separados por linha em branco), para descrição e busca."""
    return '\n\n'.join(texto for _, texto in resumo_secoes(item, fatos))
