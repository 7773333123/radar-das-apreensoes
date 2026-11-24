#!/usr/bin/env python3
"""Revisão de português dos títulos (dono do site, 24/11/2026: "corrigir qualquer erro de português nas
matérias, consulte as melhores referências gramaticais").

O Claude Haiku revisa os títulos das notícias recentes (lotes de 40) e aponta só erros claros de ortografia,
acentuação, crase, concordância, regência e pontuação, pelas referências: Bechara (Moderna Gramática
Portuguesa), Cunha & Cintra (Nova Gramática do Português Contemporâneo), VOLP da ABL e os manuais de redação
(Presidência da República, Folha, Estadão). Trava: a correção só vale se mantiver os números, os nomes
próprios e quase todo o texto (difflib >= 0,85); senão, fica o título original.

Resultado em revisao_titulos.json: {"titulos": {original: corrigido ou "" (sem erro)}, "gasto": {...}}. O
gerador do site (gerar_feed_site.py) exibe o título corrigido. Gasto próprio, teto de US$ 2 por mês.

  python revisar_titulos.py --horas 36 --max 400
"""
import argparse
import difflib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / 'revisao_titulos.json'
ACERVO = RAIZ / 'noticias.json'
MODELO = 'claude-haiku-5-5'
LOTE = 40
TETO_USD = 2.0
PEDIDO = ('Você é revisor de um jornal brasileiro. Revise os títulos de notícias abaixo segundo a norma-padrão do '
          'português do Brasil (Bechara, Cunha & Cintra, VOLP da ABL, Manual de Redação da Presidência da República, '
          'manuais da Folha e do Estadão). Corrija SÓ erros claros: ortografia, acentuação, crase, concordância '
          'verbal e nominal, regência, pontuação e digitação (letra trocada, palavra repetida, espaço faltando). '
          'NÃO mude estilo, ordem das palavras, sentido, números, siglas, nomes de pessoas, lugares, operações e '
          'órgãos; não troque sinônimos; não reescreva. Na dúvida, não corrija. Responda só com os títulos que '
          'tinham erro, com o número e o título corrigido inteiro.\n\n')
ESQUEMA = {'type': 'object', 'additionalProperties': False, 'required': ['correcoes'],
           'properties': {'correcoes': {'type': 'array', 'items': {
               'type': 'object', 'additionalProperties': False, 'required': ['n', 'titulo'],
               'properties': {'n': {'type': 'integer'}, 'titulo': {'type': 'string'}}}}}}


def carregar():
    try:
        d = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        d = {}
    mes = datetime.now(timezone.utc).strftime('%Y-%m')
    g = d.get('gasto') or {}
    return d.get('titulos') or {}, (g if g.get('mes') == mes else {'mes': mes, 'usd': 0.0, 'titulos': 0, 'corrigidos': 0})


def correcoes():
    """{título original: título corrigido} para o gerador do site (só os que mudaram)."""
    return {k: v for k, v in carregar()[0].items() if v}


_NOMES = re.compile(r'\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ú]+')


def aceitavel(original, corrigido):
    """Trava: a correção não pode mudar números, nomes próprios nem reescrever o título."""
    if not corrigido or corrigido == original or len(corrigido) > len(original) * 1.15 + 3:
        return False
    if re.findall(r'\d+', original) != re.findall(r'\d+', corrigido):
        return False
    # Nomes próprios: os do original continuam (sem acento conta como o mesmo nome, ex.: "Itajai" -> "Itajaí").
    sem = lambda x: x.lower().translate(str.maketrans('áéíóúâêôãõçà', 'aeiouaeoaoca'))
    nomes_c = {sem(n) for n in _NOMES.findall(corrigido)}
    if sum(sem(n) not in nomes_c for n in _NOMES.findall(original)[1:]) > 0:
        return False
    return difflib.SequenceMatcher(None, original, corrigido).ratio() >= 0.85


def candidatos(horas, ja):
    d = json.loads(ACERVO.read_text(encoding='utf-8'))
    ns = d['noticias'] if isinstance(d, dict) else d
    limite = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()[:19]
    vistos, saida = set(), []
    for n in sorted((x for x in ns if isinstance(x, dict)), key=lambda x: str(x.get('data_iso') or ''), reverse=True):
        t = str(n.get('titulo') or '').strip()
        if str(n.get('data_iso') or '') < limite or not t or t in ja or t in vistos:
            continue
        vistos.add(t)
        saida.append(t)
    return saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--horas', type=float, default=36)
    ap.add_argument('--max', type=int, default=400, help='títulos por execução')
    a = ap.parse_args()
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print('Títulos: sem ANTHROPIC_API_KEY; nada a fazer.')
        return
    import anthropic
    from juiz_duplicatas import AJUSTE_REAL, PRECO_CLAUDE
    cache, gasto = carregar()
    if gasto['usd'] >= TETO_USD:
        print('Títulos: teto mensal atingido; nada a fazer.')
        return
    fila = candidatos(a.horas, cache)[:a.max]
    lotes = [fila[k:k + LOTE] for k in range(0, len(fila), LOTE)]
    client = anthropic.Anthropic(max_retries=4)
    pe, ps = PRECO_CLAUDE[MODELO]

    def revisar(lote):
        lista = '\n'.join(f'{k}. {t}' for k, t in enumerate(lote, 1))
        try:
            r = client.messages.create(model=MODELO, max_tokens=3000, messages=[{'role': 'user', 'content': PEDIDO + lista}],
                                       output_config={'effort': 'low', 'format': {'type': 'json_schema', 'schema': ESQUEMA}})
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as erro:
            print(f'Títulos: erro na API: {erro!r}'[:200], flush=True)
            return lote, None, None
        if r.stop_reason != 'end_turn':
            return lote, None, r.usage
        try:
            itens = json.loads(next((x.text for x in r.content if x.type == 'text'), '{}')).get('correcoes', [])
        except ValueError:
            return lote, None, r.usage
        return lote, {c['n']: c['titulo'].strip() for c in itens if isinstance(c.get('n'), int)}, r.usage

    corrigidos = recusados = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for lote, res, u in pool.map(revisar, lotes):
            if u is not None:
                gasto['usd'] = round(gasto['usd'] + AJUSTE_REAL * ((u.input_tokens or 0) * pe + (u.output_tokens or 0) * ps) / 1e6, 6)
            if res is None:
                continue
            for k, t in enumerate(lote, 1):
                novo = res.get(k, '')
                if novo and not aceitavel(t, novo):
                    recusados += 1
                    novo = ''
                cache[t] = novo
                corrigidos += bool(novo)
            gasto['titulos'] += len(lote)
            if gasto['usd'] >= TETO_USD:
                break
    gasto['corrigidos'] += corrigidos
    if len(cache) > 80000:
        cache = dict(list(cache.items())[-80000:])
    ARQUIVO.write_text(json.dumps({'gasto': gasto, 'titulos': cache}, ensure_ascii=False, indent=0) + '\n', encoding='utf-8')
    print(f'Títulos: {len(fila)} revisados, {corrigidos} corrigidos ({recusados} correções recusadas pela trava); '
          f'gasto do mês US$ {gasto["usd"]:.4f}')


if __name__ == '__main__':
    main()
