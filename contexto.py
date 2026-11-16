#!/usr/bin/env python3
"""Resumo do Radar ampliado: fatos + quem atuou + contexto em números + cobertura.

Tudo é redigido pelo Radar: os fatos vêm de resumo_fatos.py, as explicações
são textos próprios e o contexto é calculado sobre o próprio acervo (já sem
duplicatas). Nenhuma frase da reportagem é copiada.
"""
import bisect
import re
from datetime import datetime, timedelta

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
    'Apreensões de drogas são o tipo mais frequente no acervo do Radar; as de grande volume costumam ocorrer em rodovias e em regiões de fronteira.',
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
MATERIAL_NOME = {'coc': 'cocaína', 'mac': 'maconha', 'skh': 'skunk e haxixe', 'cra': 'crack', 'dro': 'drogas',
                 'arm': 'armas de fogo', 'fuz': 'fuzis', 'mun': 'munições'}


def _dt(d):
    try:
        return datetime.fromisoformat(d[:16])
    except (TypeError, ValueError):
        return None


def _onde(uf):
    return f'{PREP_UF[uf]} {NOMES_ESTADOS[uf]}' if uf in NOMES_ESTADOS else 'no Brasil'


def _ordinal(n):
    return f'{n}ª'


class Contexto:
    """Índices do acervo para responder 'quantas notícias antes desta' rapidamente."""

    def __init__(self, itens):
        self.por_uf_cat, self.por_cat, self.por_uf_mat, self.por_uf = {}, {}, {}, {}
        for x in itens:
            d = x.get('d', '')[:16]
            if not d:
                continue
            if x.get('uf'):
                self.por_uf.setdefault(x['uf'], []).append(d)
            for c in x.get('c', []):
                self.por_cat.setdefault(c, []).append(d)
                if x.get('uf'):
                    self.por_uf_cat.setdefault((x['uf'], c), []).append(d)
            if x.get('uf'):
                for m, v in (x.get('q') or {}).items():
                    self.por_uf_mat.setdefault((x['uf'], m), []).append((d, v))
        for lista in (*self.por_uf_cat.values(), *self.por_cat.values(), *self.por_uf.values()):
            lista.sort()
        for lista in self.por_uf_mat.values():
            lista.sort()

    @staticmethod
    def _contar(datas, ini, fim):
        return bisect.bisect_left(datas, fim) - bisect.bisect_left(datas, ini)

    def paragrafo(self, item, categorias):
        d = _dt(item.get('d', ''))
        cats = item.get('c', [])
        if not d or not cats:
            return ''
        c, uf = cats[0], item.get('uf', '')
        ini30 = (d - timedelta(days=30)).isoformat()[:16]
        fim = item['d'][:16]
        frases = []
        n_br = self._contar(self.por_cat.get(c, []), ini30, fim)
        if uf and (uf, c) in self.por_uf_cat:
            n_uf = self._contar(self.por_uf_cat[(uf, c)], ini30, fim)
            frases.append(f'Nos 30 dias anteriores a esta notícia, o Radar reuniu {_fmt(n_uf)} '
                          f'{"notícia" if n_uf == 1 else "notícias"} de {CAT_NOME[c]} {_onde(uf)} '
                          f'e {_fmt(n_br)} em todo o país.')
        elif n_br:
            frases.append(f'Nos 30 dias anteriores a esta notícia, o Radar reuniu {_fmt(n_br)} notícias de {CAT_NOME[c]} em todo o país.')
        if uf in self.por_uf:
            ini12 = (d - timedelta(days=365)).isoformat()[:16]
            contagem = {u: self._contar(v, ini12, fim) for u, v in self.por_uf.items()}
            if contagem[uf]:
                pos = 1 + sum(1 for v in contagem.values() if v > contagem[uf])
                frases.append(f'Em 12 meses, o acervo registrou {_fmt(contagem[uf])} notícias de apreensões {_onde(uf)}, '
                              f'{"o estado com mais registros" if pos == 1 else f"o {pos}º estado com mais registros"} no período.')
        q = item.get('q') or {}
        if q and uf:
            # Material principal: o de maior peso (drogas) ou, sem drogas, armas/munições.
            pesos = {m: v for m, v in q.items() if m in ('coc', 'mac', 'skh', 'cra', 'dro')}
            m = max(pesos, key=pesos.get) if pesos else ('arm' if 'arm' in q else ('mun' if 'mun' in q else None))
            if m and (uf, m) in self.por_uf_mat:
                ini12 = (d - timedelta(days=365)).isoformat()[:16]
                janela = [v for dd, v in self.por_uf_mat[(uf, m)] if ini12 <= dd <= fim]
                total = sum(janela)
                posicao = 1 + sum(1 for v in janela if v > q[m])
                unidade = 'kg' if m in pesos else 'un'
                tot = (f'{_fmt(round(total / 1000, 1))} toneladas' if unidade == 'kg' and total >= 1000
                       else f'{_fmt(round(total, 1))} kg' if unidade == 'kg' else f'{_fmt(total)} {MATERIAL_NOME[m]}')
                frase = (f'Somadas as notícias dos 12 meses anteriores {_onde(uf)}, foram citados {tot}'
                         f'{" de " + MATERIAL_NOME[m] if unidade == "kg" else ""}')
                if len(janela) >= 3 and posicao <= 10:
                    frase += f'; esta é a {_ordinal(posicao)} maior apreensão de {MATERIAL_NOME[m]} noticiada no estado no período'
                frases.append(frase + '.')
        return ' '.join(frases)


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


def resumo_ampliado(item, fatos, contexto, categorias):
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
    lacunas = []
    if not any(re.search(r'\d', a) for a in (fatos or {}).get('apreendido', [])):
        lacunas.append('a quantidade apreendida')
    if not (fatos or {}).get('presos') and not (fatos or {}).get('presos_texto') \
            and not re.search(r'\bpres[oa]s?\b|\bprend|\bpris[ãa]o|\bpris[õo]es|\bdetid', item['t'], re.I):
        lacunas.append('se houve prisões')
    if not (fatos or {}).get('orgaos'):
        lacunas.append('qual corporação conduziu a ação')
    nota = f'Manchete da reportagem: “{item["t"]}”.' if base and fatos else ''
    if lacunas:
        nota += (f' Os dados lidos pelo Radar não informam {_juntar(lacunas)}; esses detalhes, quando divulgados, '
                 'costumam constar da reportagem completa ou dos boletins oficiais das corporações.')
    if nota.strip():
        paragrafos.append(nota)
    ctx = contexto.paragrafo(item, categorias)
    if ctx:
        paragrafos.append(ctx)
    outras = [o[0] for o in item.get('o', []) if o and o[0]]
    cobertura = f'A notícia foi publicada por {fonte}' if fonte else 'A notícia foi publicada pela imprensa'
    if outras:
        cobertura += f' e também por {_juntar(outras[:6])}'
        cobertura += '. O Radar reúne as versões em uma única página, sem contar a mesma apreensão mais de uma vez'
    paragrafos.append(cobertura + '. A reportagem completa está no link da fonte. Para acompanhar outras ocorrências, '
                      f'use o filtro {"do estado ou " if uf else ""}do tipo de apreensão na Central ou consulte o Observatório.')
    return '\n\n'.join(re.sub(r'\s+', ' ', p).strip() for p in paragrafos if p.strip())
