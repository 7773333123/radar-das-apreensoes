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

Decisões em juiz_decisoes.json ou, com juízes em paralelo, juiz_decisoes_<n>.json ({"decisoes": {"<id>-<id>": {"v": "mesmo"|"diferente"|"incerto", ...}}}),
lidas pelo auditor na próxima geração do site.

  python juiz_duplicatas.py --modelo modelo.gguf [--max 200] [--tempo-max 2400]
  python juiz_duplicatas.py --modelo modelo.gguf --so-calibrar [--shard k --shards 4 --saida cal_k.json]
  python juiz_duplicatas.py --modelo modelo.gguf --aprovar cal_0.json ... (grava juiz_calibracao.json)
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
CALIBRACAO = RAIZ / 'juiz_calibracao.json'
CONFIANCA_MIN = 80

INSTRUCOES = """Você confere duplicatas num site que reúne notícias de apreensões policiais publicadas por vários veículos de imprensa.
Receberá duas matérias de veículos diferentes. Decida se as duas noticiam o MESMO FATO: a mesma ação policial
(mesma prisão, apreensão ou operação), ainda que com palavras, enfoques e detalhes diferentes.

Como comparar:
1. O "estado do veículo" é onde o jornal fica, NÃO o local do fato. Operações grandes (PF, Receita, Gaeco) são
   noticiadas por jornais de vários estados e citam cidades diferentes onde houve mandados: isso NÃO é contradição.
2. Datas de publicação podem diferir em até 2 dias para o mesmo fato.
3. Detalhes que aparecem em só uma das matérias (nomes, valores, itens apreendidos, número de mandados, perfil do
   investigado, desdobramento no mesmo dia) NÃO são contradição.
4. Só é fato DIFERENTE quando há contradição concreta e explícita: cidades do fato diferentes numa ação local,
   quantidades diferentes do MESMO material (5 kg x 50 kg), número de presos incompatível ("homem" x "trio"),
   idades diferentes, crimes diferentes (tráfico x posse de arma), ou fases/datas diferentes de uma operação.
5. Duas prisões parecidas na mesma cidade (ex.: "homem preso por tráfico em Leme") podem ser fatos diferentes:
   sem nada em comum que as identifique (bairro, quantidade, nome, idade, operação), responda com confiança baixa.

Responda só com JSON: primeiro "comparacao" (uma frase: o que coincide e o que contradiz), depois
"mesmo_fato" (true ou false) e "confianca" (0 a 100)."""

GRAMATICA = r'''
root ::= "{" ws "\"comparacao\":" ws texto "," ws "\"mesmo_fato\":" ws booleano "," ws "\"confianca\":" ws numero ws "}"
booleano ::= "true" | "false"
numero ::= [0-9] | [1-9] [0-9] | "100"
texto ::= "\"" [^"\\\n]{0,300} "\""
ws ::= [ ]?
'''


def versao_juiz(modelo=''):
    """Assinatura das instruções e do modelo: decisões de outra versão podem ser revistas."""
    import hashlib
    return hashlib.sha1((INSTRUCOES + GRAMATICA + Path(str(modelo or '')).name).encode()).hexdigest()[:10]


def todas_decisoes():
    """Decisões de todos os arquivos (juiz_decisoes*.json); para o mesmo par vale a mais recente."""
    saida = {}
    for arq in sorted(RAIZ.glob('juiz_decisoes*.json')):
        try:
            for k, v in json.loads(arq.read_text(encoding='utf-8')).get('decisoes', {}).items():
                if k not in saida or v.get('em', '') >= saida[k].get('em', ''):
                    saida[k] = v
        except Exception:
            pass
    return saida


def materia(rotulo, m):
    _, fonte, titulo, data, uf, lead = (list(m) + ['', '', '', '', ''])[:6]
    cid = m[6] if len(m) > 6 else ''
    lead = re.sub(r'\s+', ' ', str(lead or '')).strip()
    linhas = [f'Matéria {rotulo}', f'Veículo: {fonte}' + (f' (estado do veículo: {uf})' if uf else ''),
              f'Publicada em: {str(data)[:10]}' if data else '', f'Cidade do fato (lida pelo robô): {cid}' if cid else '',
              f'Título: {titulo}', f'Começo do texto: {lead[:700] or "(sem texto)"}']
    return '\n'.join(x for x in linhas if x)


class Juiz:
    def __init__(self, modelo, threads=None):
        from llama_cpp import Llama, LlamaGrammar
        import os
        # Todos os núcleos (o padrão do motor usa só a metade na geração da resposta).
        threads = threads or os.cpu_count()
        self.llm = Llama(model_path=str(modelo), n_ctx=3072, n_threads=threads, n_threads_batch=threads, verbose=False)
        self.gramatica = LlamaGrammar.from_string(GRAMATICA, verbose=False)

    def perguntar(self, a, b):
        msgs = [{'role': 'system', 'content': INSTRUCOES},
                {'role': 'user', 'content': materia('A', a) + '\n\n' + materia('B', b)}]
        r = self.llm.create_chat_completion(messages=msgs, temperature=0, max_tokens=220, grammar=self.gramatica)
        try:
            d = json.loads(r['choices'][0]['message']['content'])
            d['motivo'] = d.get('comparacao', '')
            return d
        except Exception:
            return {'mesmo_fato': False, 'confianca': 0, 'motivo': 'resposta inválida'}

    def julgar(self, a, b):
        """Pergunta nos dois sentidos (o modelo muda de opinião com a ordem). 'mesmo' só se os dois
        disserem mesmo fato com confiança alta; 'diferente' se algum disser diferente com confiança alta."""
        def sim(r):
            return bool(r.get('mesmo_fato')) and int(r.get('confianca', 0)) >= CONFIANCA_MIN
        def nao(r):
            return not r.get('mesmo_fato') and int(r.get('confianca', 0)) >= CONFIANCA_MIN
        r1 = self.perguntar(a, b)
        if nao(r1) and int(r1.get('confianca', 0)) >= 90:
            return 'diferente', r1, None
        r2 = self.perguntar(b, a)
        if sim(r1) and sim(r2):
            return 'mesmo', r1, r2
        if nao(r1) or nao(r2):
            return 'diferente', r1, r2
        return 'incerto', r1, r2


def assinatura_calibracao(modelo, casos):
    import hashlib
    return hashlib.sha1((versao_juiz(modelo) + Path(casos).read_text(encoding='utf-8')).encode()).hexdigest()[:12]


def calibracao_valida(modelo, casos):
    """A calibração aprovou esta versão do juiz (instruções + modelo + casos) nas últimas 26 horas."""
    if not CALIBRACAO.exists():
        return False
    c = json.loads(CALIBRACAO.read_text(encoding='utf-8'))
    try:
        idade = time.time() - datetime.fromisoformat(c.get('em', '')).timestamp()
    except ValueError:
        return False
    return bool(c.get('ok')) and c.get('assinatura') == assinatura_calibracao(modelo, casos) and idade < 26 * 3600


def situacao_calibracao(modelo, casos):
    """ok: aprovada (vale); reprovada: esta mesma versão foi reprovada nas últimas 26 h (não
    recalibra à toa; só uma mudança no juiz, no modelo ou nos casos, ou o dia seguinte, refaz);
    precisa: nunca calibrada ou vencida."""
    if calibracao_valida(modelo, casos):
        return 'ok'
    if CALIBRACAO.exists():
        c = json.loads(CALIBRACAO.read_text(encoding='utf-8'))
        try:
            idade = time.time() - datetime.fromisoformat(c.get('em', '')).timestamp()
        except ValueError:
            idade = 10 ** 9
        if not c.get('ok') and c.get('assinatura') == assinatura_calibracao(modelo, casos) and idade < 26 * 3600:
            return 'reprovada'
    return 'precisa'


def calibrar(juiz, arquivo, modelo, shard=None, shards=1, saida=None):
    """Julga os casos conferidos à mão (ou a parte deles desta fatia) e grava o resultado."""
    casos = json.loads(Path(arquivo).read_text(encoding='utf-8'))
    if shard is not None:
        casos = [c for k, c in enumerate(casos) if k % shards == shard]
    juntou_errado, perdeu, acertos = [], [], 0
    for c in casos:
        v, r1, r2 = juiz.julgar(c['a'], c['b'])
        certo = (v == 'mesmo') == c['mesmo']
        acertos += certo
        conf = f"{r1.get('mesmo_fato')}/{r1.get('confianca')}" + (f" {r2.get('mesmo_fato')}/{r2.get('confianca')}" if r2 else '')
        print(f"{'OK ' if certo else 'ERRO'} esperado={'mesmo' if c['mesmo'] else 'diferente'} juiz={v} [{conf}] | "
              f"{c['a'][2][:60]} | {c['b'][2][:60]} | {r1.get('motivo', '')[:120]}", flush=True)
        if v == 'mesmo' and not c['mesmo']:
            juntou_errado.append([c['a'][2], c['b'][2]])
        elif v != 'mesmo' and c['mesmo']:
            perdeu.append([c['a'][2], c['b'][2]])
    print(f'Calibração: {acertos}/{len(casos)} certos; juntou errado: {len(juntou_errado)}; deixou de juntar: {len(perdeu)}')
    if saida:
        Path(saida).write_text(json.dumps({'assinatura': assinatura_calibracao(modelo, arquivo), 'parte': shard,
                                           'acertos': acertos, 'total': len(casos), 'juntou_errado': juntou_errado,
                                           'deixou_de_juntar': perdeu}, ensure_ascii=False), encoding='utf-8')
    return not juntou_errado  # juntar fato diferente é o erro que não se aceita


def aprovar(arquivos, modelo, casos):
    """Junta as partes da calibração: aprova só se todas rodaram com esta versão e nenhuma juntou errado."""
    assinatura = assinatura_calibracao(modelo, casos)
    partes = [json.loads(Path(a).read_text(encoding='utf-8')) for a in arquivos if Path(a).exists()]
    validas = [p for p in partes if p.get('assinatura') == assinatura]
    total = sum(p['total'] for p in validas)
    esperado = len(json.loads(Path(casos).read_text(encoding='utf-8')))
    errados = [e for p in validas for e in p['juntou_errado']]
    ok = total == esperado and not errados
    res = {'assinatura': assinatura, 'versao': versao_juiz(modelo), 'modelo': Path(modelo).name, 'ok': ok,
           'em': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'acertos': sum(p['acertos'] for p in validas),
           'total': total, 'juntou_errado': errados, 'deixou_de_juntar': [e for p in validas for e in p['deixou_de_juntar']]}
    CALIBRACAO.write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f"Calibração {'APROVADA' if ok else 'REPROVADA'}: {res['acertos']}/{total} certos (de {esperado}); "
          f"juntou errado: {len(errados)}; deixou de juntar: {len(res['deixou_de_juntar'])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modelo', default='')
    ap.add_argument('--calibrar', default=str(RAIZ / 'testes' / 'juiz_casos.json'), help='Casos conferidos à mão')
    ap.add_argument('--so-calibrar', action='store_true')
    ap.add_argument('--so-contar', action='store_true', help='Só conta os pares pendentes (sem o modelo)')
    ap.add_argument('--max', type=int, default=200)
    ap.add_argument('--tempo-max', type=int, default=2400)
    ap.add_argument('--threads', type=int)
    ap.add_argument('--shard', type=int, help='Juízes em paralelo: esta fatia (0..shards-1)')
    ap.add_argument('--shards', type=int, default=1)
    ap.add_argument('--saida', help='Calibração em partes: arquivo com o resultado desta parte')
    ap.add_argument('--aprovar', nargs='*', help='Junta os resultados das partes e grava juiz_calibracao.json')
    ap.add_argument('--situacao-calibracao', action='store_true', help='CALIBRACAO=ok se a de hoje vale')
    args = ap.parse_args()
    inicio = time.monotonic()
    if args.situacao_calibracao:
        print('CALIBRACAO=' + situacao_calibracao(args.modelo, args.calibrar))
        return
    if args.aprovar:
        aprovar(args.aprovar, args.modelo, args.calibrar)
        return
    if args.so_calibrar:
        juiz = Juiz(args.modelo, args.threads)
        calibrar(juiz, args.calibrar, args.modelo, args.shard, args.shards, args.saida)
        return
    # Com juízes em paralelo, cada um grava o seu arquivo (juiz_decisoes_<n>.json) e só julga a
    # sua fatia dos pares; o auditor lê todos os arquivos juntos.
    proprio = DECISOES if args.shard is None else RAIZ / f'juiz_decisoes_{args.shard}.json'
    dados = json.loads(proprio.read_text(encoding='utf-8')) if proprio.exists() else {}
    decisoes = dados.get('decisoes', {})
    ja_julgados = todas_decisoes()
    suspeitas = json.loads(SUSPEITAS.read_text(encoding='utf-8')).get('suspeitas', []) if SUSPEITAS.exists() else []
    # Pares nunca julgados primeiro; depois os que uma versão anterior do juiz deixou em dúvida ou
    # separou (a versão atual relê; "mesmo" de versões anteriores fica, foi conferido na calibração).
    versao = versao_juiz(args.modelo)
    novos = [s for s in suspeitas if len(s['a']) >= 6 and chave_par(s['a'][0], s['b'][0]) not in ja_julgados]
    rever = [s for s in suspeitas if len(s['a']) >= 6 and chave_par(s['a'][0], s['b'][0]) in ja_julgados
             and ja_julgados[chave_par(s['a'][0], s['b'][0])].get('v') != 'mesmo'
             and ja_julgados[chave_par(s['a'][0], s['b'][0])].get('ver') != versao]
    pendentes = novos + rever
    total_pendentes = len(pendentes)
    if args.shard is not None:
        import hashlib
        pendentes = [s for s in pendentes if int(hashlib.sha1(chave_par(s['a'][0], s['b'][0]).encode()).hexdigest()[:8], 16)
                     % args.shards == args.shard]
    print(f'{len(novos)} pares novos e {len(rever)} para rever com a versão {versao} do juiz.')
    print(f'{len(suspeitas)} pares em dúvida; {total_pendentes} ainda sem decisão do juiz'
          + (f'; {len(pendentes)} nesta fatia ({args.shard}/{args.shards}).' if args.shard is not None else '.'), flush=True)
    if args.so_contar:
        print(f'PENDENTES={total_pendentes}')
        return
    if not pendentes and not args.so_calibrar:
        print('Nenhum par novo para julgar.')
        return
    juiz = Juiz(args.modelo, args.threads)
    print(f'Modelo carregado em {time.monotonic() - inicio:.0f}s', flush=True)
    if not calibracao_valida(args.modelo, args.calibrar):
        print('A calibração de hoje não aprovou esta versão do juiz (ou não rodou): nada é julgado.')
        sys.exit(1)
    contagem = {'mesmo': 0, 'diferente': 0, 'incerto': 0}
    for s in pendentes[:args.max]:
        if time.monotonic() - inicio > args.tempo_max:
            print('Tempo esgotado; o restante fica para a próxima execução.')
            break
        v, r1, r2 = juiz.julgar(s['a'], s['b'])
        contagem[v] += 1
        decisoes[chave_par(s['a'][0], s['b'][0])] = {
            'v': v, 'c': int(r1.get('confianca', 0)), 'm': str(r1.get('motivo', ''))[:200], 'ver': versao,
            'c2': int((r2 or {}).get('confianca', -1)), 'm2': str((r2 or {}).get('motivo', ''))[:200],
            'em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            't': [s['a'][2][:120], s['b'][2][:120]]}
        conf = f"{r1.get('mesmo_fato')}/{r1.get('confianca')}" + (f" {r2.get('mesmo_fato')}/{r2.get('confianca')}" if r2 else '')
        print(f"{v:9} [{conf}] {s['a'][1][:20]:20} {s['a'][2][:55]:55} | {s['b'][1][:20]:20} {s['b'][2][:55]} | {r1.get('motivo', '')[:80]}",
              flush=True)
    # Guarda só as decisões dos últimos 60 dias (o auditor olha as notícias recentes).
    limite = datetime.now(timezone.utc).timestamp() - 60 * 86400
    decisoes = {k: v for k, v in decisoes.items()
                if datetime.fromisoformat(v.get('em', '2000-01-01T00:00:00+00:00')).timestamp() >= limite}
    proprio.write_text(json.dumps({'atualizado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                    'decisoes': decisoes}, ensure_ascii=False, indent=0, sort_keys=True) + '\n',
                        encoding='utf-8')
    print(f"Juiz: {contagem['mesmo']} mesmo fato, {contagem['diferente']} diferentes, {contagem['incerto']} incertos; "
          f'{len(decisoes)} decisões guardadas.')


if __name__ == '__main__':
    main()
