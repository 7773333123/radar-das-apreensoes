#!/usr/bin/env python3
"""Radar das Apreensões: análise conservadora e auditável de notícias.

Executar: python analisar_noticias.py
Lê noticias.json, escreve analise_nacional.json; não altera o acervo.
Não usa LLM nem afirma contagem de ocorrências únicas.
"""
import collections
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent
CATEGORIES = {
    'Drogas e entorpecentes': [r'\bdrogas?\b', r'\btrafic', r'\bcocain', r'\bmaconha\b', r'\bcrack\b', r'\bentorpecent', r'\bhaxixe\b', r'\becstasy\b'],
    'Armas e munições': [r'\barmas?\b', r'\bfuzis?\b', r'\bfuzil\b', r'\bpistolas?\b', r'\brevolver', r'\bmunic', r'\bexplosiv', r'\barmamento'],
    'Contrabando e descaminho': [r'\bcontraband', r'\bdescaminho\b', r'\bcigarros?\b', r'\baduaneir', r'\bmercadorias? irregulares?\b'],
    'Veículos': [r'\bveiculos?\b', r'\bcarros?\b', r'\bautomove', r'\bcaminh', r'\bmotociclet', r'\bembarcac', r'\baeronave'],
    'Dinheiro e valores': [r'\bdinheiro\b', r'\bouro\b', r'\bjoias?\b', r'\bnumerario\b', r'\bvalores apreendid'],
    'Crimes ambientais': [r'\bambiental', r'\bmadeira ilegal\b', r'\banimais? silvestres?\b', r'\bpesca ilegal\b', r'\bpescado\b', r'\bminerio', r'\bdesmatamento\b'],
    'Medicamentos e produtos': [r'\bmedicamento', r'\bremedios?\b', r'\banabolizante', r'\bproduto falsificad', r'\bproduto proibido'],
    'Operações patrimoniais': [r'\bbloqueio de bens\b', r'\bsequestro de bens\b', r'\bpatrimonio\b', r'\blavagem de dinheiro\b'],
}
UFS = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value or '').lower()) if unicodedata.category(c) != 'Mn')


def parse_date(value):
    v = str(value or '')[:10]
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    return None


def main():
    src = BASE / 'noticias.json'
    if not src.exists():
        raise SystemExit('Arquivo noticias.json não encontrado na mesma pasta.')
    raw = json.loads(src.read_text(encoding='utf-8'))
    items = raw if isinstance(raw, list) else raw.get('noticias', [])
    if not isinstance(items, list):
        raise SystemExit('Formato de noticias.json inválido.')
    counts = collections.Counter()
    states = collections.Counter()
    months = collections.Counter()
    sources = set()
    enriched = []
    for n in items:
        if not isinstance(n, dict):
            continue
        title = str(n.get('titulo') or n.get('t') or '')
        description = str(n.get('descricao') or n.get('resumo') or n.get('desc') or '')
        text = fold(title + ' ' + description)
        labels = [name for name, patterns in CATEGORIES.items() if any(re.search(p, text) for p in patterns)]
        if not labels:
            labels = ['Outras apreensões'] if re.search(r'\bapreens|\bapreendid|\bconfiscad', text) else ['Não classificada']
        for label in labels:
            counts[label] += 1
        uf = str(n.get('uf') or n.get('estado') or '').upper().strip()
        if uf in UFS:
            states[uf] += 1
        date = parse_date(n.get('data_publicacao') or n.get('data') or n.get('date'))
        if date:
            months[date.strftime('%Y-%m')] += 1
        source = str(n.get('fonte') or n.get('source') or '').strip()
        if source:
            sources.add(source)
        enriched.append({'url': n.get('url') or n.get('link'), 'categorias_sugeridas': labels,
                         'classificacao': 'regras_textuais', 'revisao_humana_recomendada': True})
    result = {
        'gerado_em_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'metodologia': 'Classificação por regras textuais; não utiliza modelo de IA generativa.',
        'aviso': 'Contagens de notícias, NÃO de apreensões ou operações únicas. Categorias podem se sobrepor.',
        'noticias_analisadas': len(enriched),
        'fontes_distintas_informadas': len(sources),
        'noticias_por_categoria': dict(counts.most_common()),
        'noticias_por_uf_explicita': dict(states.most_common()),
        'noticias_por_mes': dict(sorted(months.items())),
        'classificacoes': enriched,
    }
    target = BASE / 'analise_nacional.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Analisadas {len(enriched)} notícias. Resultado: {target.name}')


if __name__ == '__main__':
    main()
