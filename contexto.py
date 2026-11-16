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


def resumo_ampliado(item, fatos):
    """Texto do Radar em parágrafos (separados por linha em branco)."""
    fonte = item.get('f', '')
    uf = item.get('uf', '')
    cats = item.get('c', [])
    paragrafos = []
    base = redigir(fatos, '', item.get('d', ''), uf) if fatos else ''
    if not base:
        quando = _data_extenso(item.get('d', ''))
        tema = CAT_NOME[cats[0]] if cats else 'apreensões'
        base = (f'{fonte or "Um veículo de imprensa"} publicou{" em " + quando if quando else ""} uma notícia sobre {tema}'
                f'{" " + _onde(uf) if uf else ""}: “{item["t"]}”.')
    paragrafos.append(base)
    segundo = ' '.join(p for p in (_agentes(fatos, uf), CATEGORIA_NOTA[cats[0]] if cats else '') if p)
    if segundo:
        paragrafos.append(segundo)
    if fatos and base:
        paragrafos.append(f'Manchete da reportagem: “{item["t"]}”.')
    outras = [o[0] for o in item.get('o', []) if o and o[0]]
    if outras:
        paragrafos.append(f'O caso também foi noticiado por {_juntar(outras[:8])}.')
    return '\n\n'.join(re.sub(r'\s+', ' ', p).strip() for p in paragrafos if p.strip())
