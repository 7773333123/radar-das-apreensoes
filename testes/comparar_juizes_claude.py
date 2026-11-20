#!/usr/bin/env python3
"""Teste (manual): modelos Claude como juiz de duplicatas, contra os mesmos casos do juiz atual.

Casos: testes/juiz_casos.json (50 da calibração) + testes/juiz_casos_reais.json (erros reais
conferidos à mão). Mesmas instruções e mesmas matérias que o juiz de IA próprio (Qwen) recebe.
Mostra, por modelo: acertos, uniões erradas (o pior erro), duplicatas perdidas e custo.

Uso (no GitHub Actions, com o secret ANTHROPIC_API_KEY):
    python testes/comparar_juizes_claude.py [--modelos claude-haiku-5-5,claude-sonnet-5-5,claude-opus-5-5]
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from juiz_duplicatas import INSTRUCOES, materia  # noqa: E402

PRECO = {  # US$ por 1 milhão de tokens (entrada, saída)
    'claude-haiku-5-5': (0.10, 0.50),
    'claude-sonnet-5-5': (2.00, 10.00),
    'claude-opus-5-5': (4.00, 20.00),
}
ESQUEMA = {
    'type': 'object',
    'properties': {
        'comparacao': {'type': 'string'},
        'mesmo_fato': {'type': 'boolean'},
        'confianca': {'type': 'integer'},
    },
    'required': ['comparacao', 'mesmo_fato', 'confianca'],
    'additionalProperties': False,
}


def julgar(client, modelo, caso):
    """Uma chamada por par. Devolve (resposta, tokens de entrada, tokens de saída)."""
    for tentativa in range(3):
        try:
            r = client.messages.create(
                model=modelo,
                max_tokens=4000,
                system=[{'type': 'text', 'text': INSTRUCOES, 'cache_control': {'type': 'ephemeral'}}],
                messages=[{'role': 'user', 'content': materia('A', caso['a']) + '\n\n' + materia('B', caso['b'])}],
                output_config={'effort': 'low', 'format': {'type': 'json_schema', 'schema': ESQUEMA}},
            )
            uso = r.usage
            entrada = (uso.input_tokens or 0) + (uso.cache_creation_input_tokens or 0) + (uso.cache_read_input_tokens or 0) * 0.1
            if r.stop_reason == 'refusal':
                return {'erro': 'recusa'}, entrada, uso.output_tokens or 0
            texto = next((b.text for b in r.content if b.type == 'text'), '{}')
            return json.loads(texto), entrada, uso.output_tokens or 0
        except anthropic.RateLimitError:
            time.sleep(20 * (tentativa + 1))
        except (anthropic.APIConnectionError, json.JSONDecodeError) as erro:
            ultimo = erro
            time.sleep(5)
        except anthropic.APIStatusError as erro:
            return {'erro': f'HTTP {erro.status_code}: {erro.message[:120]}'}, 0, 0
    return {'erro': 'sem resposta'}, 0, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modelos', default='claude-haiku-5-5,claude-sonnet-5-5,claude-opus-5-5')
    args = ap.parse_args()
    casos = [dict(c, origem='calibração') for c in json.loads((RAIZ / 'testes/juiz_casos.json').read_text(encoding='utf-8'))]
    reais = RAIZ / 'testes/juiz_casos_reais.json'
    if reais.exists():
        casos += [dict(c, origem='erro real') for c in json.loads(reais.read_text(encoding='utf-8'))]
    client = anthropic.Anthropic()
    resumo = []
    for modelo in args.modelos.split(','):
        with ThreadPoolExecutor(max_workers=4) as ex:
            resultados = list(ex.map(lambda c: julgar(client, modelo, c), casos))
        acertos = juntou_errado = perdeu = falhas = 0
        entrada = saida = 0
        linhas = []
        for caso, (r, ti, to) in zip(casos, resultados):
            entrada += ti
            saida += to
            if 'erro' in r:
                falhas += 1
                linhas.append(f'  FALHA ({r["erro"]}) | {caso["a"][2][:60]} || {caso["b"][2][:60]}')
                continue
            disse = bool(r.get('mesmo_fato')) and int(r.get('confianca', 0)) >= 80
            if disse == caso['mesmo']:
                acertos += 1
                continue
            if disse:
                juntou_errado += 1
                tipo = 'JUNTOU ERRADO'
            else:
                perdeu += 1
                tipo = 'perdeu duplicata'
            linhas.append(f'  {tipo} [{caso["origem"]}] c={r.get("confianca")} | {caso["a"][2][:60]} || {caso["b"][2][:60]}\n'
                          f'      motivo: {str(r.get("comparacao", ""))[:200]}')
        pe, ps = PRECO.get(modelo, (0, 0))
        custo = (entrada * pe + saida * ps) / 1e6
        por_par = custo / max(1, len(casos))
        print(f'\n=== {modelo}: {acertos}/{len(casos)} certos; uniões erradas {juntou_errado}; '
              f'duplicatas perdidas {perdeu}; falhas {falhas}; custo do teste US$ {custo:.3f} '
              f'(~US$ {por_par * 1000:.2f} por mil pares)')
        print('\n'.join(linhas))
        resumo.append((modelo, acertos, juntou_errado, perdeu, falhas, custo, por_par))
    print('\nRESUMO (modelo | certos | uniões erradas | perdidas | falhas | custo do teste | US$ por mil pares)')
    for m, a, j, p, f, c, pp in resumo:
        print(f'{m} | {a}/{len(casos)} | {j} | {p} | {f} | {c:.3f} | {pp * 1000:.2f}')


if __name__ == '__main__':
    main()
