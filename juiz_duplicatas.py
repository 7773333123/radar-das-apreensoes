#!/usr/bin/env python3
"""Juiz de duplicatas com IA própria (modelo aberto, roda no GitHub Actions, sem chave paga).

O auditor de duplicatas (duplicatas.py) junta sozinho os pares com duas evidências fortes e
deixa em dúvida (duplicatas_suspeitas.json) os pares parecidos com uma só. Este juiz lê o
título e a abertura das duas matérias de cada par em dúvida e decide se são o MESMO fato.

Cuidados para não juntar fatos diferentes:
- o modelo responde nos DOIS sentidos (A,B e B,A); só junta se as duas respostas disserem
  "mesmo fato" com confiança alta; qualquer outra combinação fica "diferente" ou "incerto";
- antes de valer, o juiz passa pela calibração (testes/juiz_casos.json, pares conferidos à
  mão): se juntar algum par diferente, o workflow para e nada é gravado;
- as vetos do auditor (cidades, materiais, bairros, nomes diferentes) continuam valendo: o
  juiz só é consultado para pares que o auditor já achou parecidos.

Decisões em juiz_decisoes.json ({"decisoes": {"<id>-<id>": {"v": "mesmo"|"diferente"|"incerto", ...}}}),
lidas pelo auditor na próxima geração do site.

  python juiz_duplicatas.py --modelo modelo.gguf [--max 200] [--tempo-max 2400]
  python juiz_duplicatas.py --modelo modelo.gguf --calibrar testes/juiz_casos.json
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from duplicatas import chave_par

RAIZ = Path(__file__).resolve().parent
SUSPEITAS = RAIZ / 'duplicatas_suspeitas.json'
DECISOES = RAIZ / 'juiz_decisoes.json'
CONFIANCA_MIN = 80

INSTRUCOES = """Você confere duplicatas num site que reúne notícias de apreensões policiais publicadas por vários veículos.
Receberá duas matérias (título, data, estado e começo do texto) de veículos diferentes.
Decida se as duas contam o MESMO FATO: a mesma ação policial, no mesmo lugar, na mesma ocasião.

Regras:
- Notícias do mesmo tipo de crime na mesma cidade e no mesmo dia podem ser fatos DIFERENTES (duas prisões distintas).
- Se houver contradição concreta (quantidades ou materiais diferentes, número de presos diferente, pessoas descritas de forma incompatível — ex.: "homem" x "adolescente", "trio" x "homem" —, bairros ou locais diferentes), responda que NÃO é o mesmo fato.
- Uma matéria pode ter mais detalhes que a outra; detalhes a mais não são contradição.
- Desdobramentos (nova fase de uma operação, julgamento, investigação posterior) são fatos diferentes da ação original, exceto quando as duas falam da mesma fase/ação.
- Na dúvida, responda que NÃO é o mesmo fato.

Responda só com JSON: {"mesmo_fato": true ou false, "confianca": número de 0 a 100, "motivo": "frase curta"}"""

GRAMATICA = r'''
root ::= "{" ws "\"mesmo_fato\":" ws booleano "," ws "\"confianca\":" ws numero "," ws "\"motivo\":" ws texto ws "}"
booleano ::= "true" | "false"
numero ::= [0-9] | [1-9] [0-9] | "100"
texto ::= "\"" [^"\\\n]* "\""
ws ::= [ ]?
'''


def materia(rotulo, m):
    _, fonte, titulo, data, uf, lead = (list(m) + ['', '', '', ''])[:6]
    lead = re.sub(r'\s+', ' ', str(lead or '')).strip()
    return (f'Matéria {rotulo} ({fonte}{", " + uf if uf else ""}{", " + str(data)[:10] if data else ""})\n'
            f'Título: {titulo}\nComeço do texto: {lead[:400] or "(sem texto)"}')


class Juiz:
    def __init__(self, modelo, threads=None):
        from llama_cpp import Llama, LlamaGrammar
        self.llm = Llama(model_path=str(modelo), n_ctx=2048, n_threads=threads, verbose=False)
        self.gramatica = LlamaGrammar.from_string(GRAMATICA, verbose=False)

    def perguntar(self, a, b):
        msgs = [{'role': 'system', 'content': INSTRUCOES},
                {'role': 'user', 'content': materia('A', a) + '\n\n' + materia('B', b)}]
        r = self.llm.create_chat_completion(messages=msgs, temperature=0, max_tokens=120, grammar=self.gramatica)
        try:
            return json.loads(r['choices'][0]['message']['content'])
        except Exception:
            return {'mesmo_fato': False, 'confianca': 0, 'motivo': 'resposta inválida'}

    def julgar(self, a, b):
        """'mesmo' só se os dois sentidos concordarem com confiança alta."""
        r1 = self.perguntar(a, b)
        if not (r1.get('mesmo_fato') and int(r1.get('confianca', 0)) >= CONFIANCA_MIN):
            v = 'diferente' if not r1.get('mesmo_fato') and int(r1.get('confianca', 0)) >= CONFIANCA_MIN else 'incerto'
            return v, r1, None
        r2 = self.perguntar(b, a)
        if r2.get('mesmo_fato') and int(r2.get('confianca', 0)) >= CONFIANCA_MIN:
            return 'mesmo', r1, r2
        return 'incerto', r1, r2


def calibrar(juiz, arquivo):
    casos = json.loads(Path(arquivo).read_text(encoding='utf-8'))
    juntou_errado, perdeu, acertos = [], [], 0
    for c in casos:
        v, r1, r2 = juiz.julgar(c['a'], c['b'])
        certo = (v == 'mesmo') == c['mesmo']
        acertos += certo
        conf = f"{r1.get('mesmo_fato')}/{r1.get('confianca')}" + (f" {r2.get('mesmo_fato')}/{r2.get('confianca')}" if r2 else '')
        print(f"{'OK ' if certo else 'ERRO'} esperado={'mesmo' if c['mesmo'] else 'diferente'} juiz={v} [{conf}] | "
              f"{c['a'][2][:60]} | {c['b'][2][:60]} | {r1.get('motivo', '')[:90]}", flush=True)
        if v == 'mesmo' and not c['mesmo']:
            juntou_errado.append(c)
        elif v != 'mesmo' and c['mesmo']:
            perdeu.append(c)
    print(f'Calibração: {acertos}/{len(casos)} certos; juntou errado: {len(juntou_errado)}; deixou de juntar: {len(perdeu)}')
    return not juntou_errado  # juntar fato diferente é o erro que não se aceita


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modelo', default='')
    ap.add_argument('--calibrar', help='Casos conferidos à mão: calibra antes de julgar (uma vez por dia)')
    ap.add_argument('--so-calibrar', action='store_true')
    ap.add_argument('--so-contar', action='store_true', help='Só conta os pares pendentes (sem o modelo)')
    ap.add_argument('--max', type=int, default=200)
    ap.add_argument('--tempo-max', type=int, default=2400)
    ap.add_argument('--threads', type=int)
    args = ap.parse_args()
    inicio = time.monotonic()
    dados = json.loads(DECISOES.read_text(encoding='utf-8')) if DECISOES.exists() else {}
    decisoes = dados.get('decisoes', {})
    suspeitas = json.loads(SUSPEITAS.read_text(encoding='utf-8')).get('suspeitas', []) if SUSPEITAS.exists() else []
    pendentes = [s for s in suspeitas if len(s['a']) >= 6 and chave_par(s['a'][0], s['b'][0]) not in decisoes]
    print(f'{len(suspeitas)} pares em dúvida; {len(pendentes)} ainda sem decisão do juiz.', flush=True)
    if args.so_contar:
        print(f'PENDENTES={len(pendentes)}')
        return
    if not pendentes and not args.so_calibrar:
        print('Nenhum par novo para julgar.')
        return
    juiz = Juiz(args.modelo, args.threads)
    print(f'Modelo carregado em {time.monotonic() - inicio:.0f}s', flush=True)
    if args.calibrar:
        # Calibração: sempre que o juiz, os casos ou o modelo mudam, e ao menos uma vez por dia.
        import hashlib
        assinatura = hashlib.sha1((Path(__file__).read_bytes() + Path(args.calibrar).read_bytes()
                                   + Path(args.modelo).name.encode())).hexdigest()[:16]
        cal = dados.get('calibracao', {})
        recente = cal.get('em', '') >= (datetime.now(timezone.utc).replace(microsecond=0).isoformat()[:10])
        if cal.get('assinatura') == assinatura and recente and not args.so_calibrar:
            print(f"Calibração de hoje vale (assinatura {assinatura}); pulando.")
        else:
            if not calibrar(juiz, args.calibrar):
                sys.exit(1)
            dados['calibracao'] = {'assinatura': assinatura, 'em': datetime.now(timezone.utc).isoformat(timespec='seconds')}
        if args.so_calibrar:
            return
    contagem = {'mesmo': 0, 'diferente': 0, 'incerto': 0}
    for s in pendentes[:args.max]:
        if time.monotonic() - inicio > args.tempo_max:
            print('Tempo esgotado; o restante fica para a próxima execução.')
            break
        v, r1, r2 = juiz.julgar(s['a'], s['b'])
        contagem[v] += 1
        decisoes[chave_par(s['a'][0], s['b'][0])] = {
            'v': v, 'c': int(r1.get('confianca', 0)), 'm': str(r1.get('motivo', ''))[:160],
            'em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            't': [s['a'][2][:120], s['b'][2][:120]]}
        conf = f"{r1.get('mesmo_fato')}/{r1.get('confianca')}" + (f" {r2.get('mesmo_fato')}/{r2.get('confianca')}" if r2 else '')
        print(f"{v:9} [{conf}] {s['a'][1][:20]:20} {s['a'][2][:55]:55} | {s['b'][1][:20]:20} {s['b'][2][:55]} | {r1.get('motivo', '')[:80]}",
              flush=True)
    # Guarda só as decisões dos últimos 60 dias (o auditor olha as notícias recentes).
    limite = datetime.now(timezone.utc).timestamp() - 60 * 86400
    decisoes = {k: v for k, v in decisoes.items()
                if datetime.fromisoformat(v.get('em', '2000-01-01T00:00:00+00:00')).timestamp() >= limite}
    DECISOES.write_text(json.dumps({'atualizado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                    'calibracao': dados.get('calibracao', {}),
                                    'decisoes': decisoes}, ensure_ascii=False, indent=0, sort_keys=True) + '\n',
                        encoding='utf-8')
    print(f"Juiz: {contagem['mesmo']} mesmo fato, {contagem['diferente']} diferentes, {contagem['incerto']} incertos; "
          f'{len(decisoes)} decisões guardadas.')


if __name__ == '__main__':
    main()
