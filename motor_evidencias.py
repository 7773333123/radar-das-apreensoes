#!/usr/bin/env python3
"""Motor de evidências contra duplicatas (record linkage, modelo de Fellegi–Sunter).

Em vez de regras soltas, cada par candidato de notícias recebe um PLACAR: a soma do peso de
cada indício (log da razão de chances "mesmo fato" x "fato diferente"), com pesos aprendidos
dos dados rotulados (decisões do juiz de IA, casos conferidos à mão, uniões das regras) contra
pares aleatórios do mesmo estado e dia (quase sempre fatos diferentes: mostram o acaso).

Indícios de cada par:
- texto completo: semelhança TF-IDF (palavras raras pesam mais: nomes, bairros, números) do
  título e do trecho da reportagem; trechos idênticos de 5 palavras (cópia do comunicado);
- foto: a mesma imagem (impressão digital ou pontos em comum, com recorte/zoom);
- fatos: cidade do fato, quantidade por material, número de presos, idades, itens raros;
- link, data, estado e veículo.
Contradições concretas (outra cidade, outra quantidade, outro número de presos, outra
idade, materiais diferentes) tiram muitos pontos.

Decisão (limites escolhidos para que NENHUM par diferente conhecido seja unido):
- placar >= UNIR: o mesmo fato;
- DUVIDA <= placar < UNIR: vai para o juiz de IA;
- abaixo: fatos diferentes.
O agrupamento verifica a coerência do grupo inteiro (nenhuma contradição entre membros).

Pesos em motor_pesos.json (treinar_motor.py recalcula com os rótulos novos).
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

from duplicatas import (PALAVRAS_VAZIAS, VAZIAS_AUDITOR, compativeis, materiais_titulo, normal,
                        numeros_fortes, quantidades_titulo, radical)

RAIZ = Path(__file__).resolve().parent
PESOS_ARQ = RAIZ / 'motor_pesos.json'
JANELA = 2
VAZIAS = set(PALAVRAS_VAZIAS) | set(VAZIAS_AUDITOR) | set('''nesta neste nessa nesse desta deste dessa desse sobre ainda
    segundo conforme apos durante tambem foram sera seria pode podem disse informou afirmou ocorrencia
    local momento equipe equipes guarnicao guarnicoes viatura abordagem abordado suspeitos
    material materiais encaminhado encaminhada delegacia flagrante quinta sexta sabado domingo segunda terca quarta
    feira manha tarde noite madrugada dia dias ontem hoje'''.split())
ANO = re.compile(r'\b(19|20)\d\d\b')
ESTRADA = re.compile(r'\b[A-Z]{2,3}-\d+|(?i:\bkm\s?\d+)')

INDICIOS = ['cos_txt', 'cos_tit', 'copia', 'foto', 'link', 'cid_igual', 'cid_dif', 'qtd_igual', 'qtd_conflito',
            'presos_igual', 'presos_conflito', 'idade_igual', 'idade_conflito', 'raros', 'mats_conflito',
            'num_comum', 'dias', 'mesmo_veiculo', 'sem_texto']


def tokens(texto):
    return [radical(w) for w in normal(texto).split() if len(w) > 2 and w not in VAZIAS and not w.isdigit()]


def shingles(texto, n=5):
    p = [w for w in normal(texto).split() if len(w) > 1]
    return {' '.join(p[k:k + n]) for k in range(max(0, len(p) - n + 1))}


class Corpus:
    """TF-IDF das notícias de uma janela (estado x dia) para comparar textos."""

    def __init__(self, itens):
        self.itens = itens
        self.tok_t, self.tok_x = [], []
        df = Counter()
        for it in itens:
            tt = tokens(it.get('t', ''))
            tx = tokens(str(it.get('_txt') or it.get('_lead') or '')[:2500])
            self.tok_t.append(tt)
            self.tok_x.append(tx)
            df.update(set(tt) | set(tx))
        n = max(1, len(itens))
        self.idf = {w: math.log((n + 1) / (c + 1)) + 1 for w, c in df.items()}
        self.vt = [self._vet(t, 1.0) for t in self.tok_t]
        self.vx = [self._vet(tt * 2 + tx, 1.0) for tt, tx in zip(self.tok_t, self.tok_x)]
        self.sh = [shingles(str(it.get('_txt') or '')[:2500]) for it in itens]
        self.nums = [self._nums(it) for it in itens]

    def _vet(self, toks, _):
        c = Counter(toks)
        v = {w: (1 + math.log(k)) * self.idf.get(w, 1) for w, k in c.items()}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1
        return {w: x / norma for w, x in v.items()}

    @staticmethod
    def _nums(it):
        t = ESTRADA.sub(' ', it.get('t', '') + ' ' + str(it.get('_txt') or '')[:1500])
        t = ANO.sub(' ', t)
        return {n for n in numeros_fortes(t) if float(n) >= 10}

    @staticmethod
    def cos(a, b):
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(w, 0) for w, x in a.items())

    def termos_raros(self, k, quantos=12):
        """As palavras mais raras da notícia (para achar candidatas)."""
        v = self.vx[k]
        return [w for w, _ in sorted(v.items(), key=lambda x: -x[1])[:quantos]]


def _dia(it):
    from datetime import date
    try:
        return date.fromisoformat(str(it.get('d', ''))[:10]).toordinal()
    except ValueError:
        return None


def indicios(c, a, b, extra=None):
    """Indícios do par (a, b) do corpus c."""
    ia, ib = c.itens[a], c.itens[b]
    ext = extra or {}
    f = dict.fromkeys(INDICIOS, 0.0)
    f['cos_txt'] = c.cos(c.vx[a], c.vx[b])
    f['cos_tit'] = c.cos(c.vt[a], c.vt[b])
    sa, sb = c.sh[a], c.sh[b]
    if sa and sb:
        f['copia'] = len(sa & sb) / min(len(sa), len(sb))
    f['sem_texto'] = float(not (sa and sb))
    # Foto: impressão digital, mesma imagem (pontos em comum) ou o mesmo endereço.
    ha, hb = ia.get('_h'), ib.get('_h')
    fotos_a = set(ia.get('_mesma') or ()) | set(ia.get('_iguais') or ())
    fotos_b = set(ib.get('_mesma') or ()) | set(ib.get('_iguais') or ())
    mesma = (ia.get('img') and ia.get('img') == ib.get('img')) or \
        (ib.get('img') and ib['img'] in fotos_a) or (ia.get('img') and ia['img'] in fotos_b)
    if mesma or (ha is not None and hb is not None and (ha ^ hb).bit_count() <= 8):
        f['foto'] = 0.0 if ext.get('foto_generica') else 1.0
    f['link'] = float(bool(ia.get('u')) and ia.get('u') == ib.get('u'))
    ca, cb = ia.get('_cid'), ib.get('_cid')
    if ca and cb:
        f['cid_igual' if ca == cb else 'cid_dif'] = 1.0
    qa, qb = ia.get('_q') or {}, ib.get('_q') or {}
    for m in set(qa) & set(qb):
        x, y = qa[m], qb[m]
        if abs(x - y) <= 0.05 * max(x, y):
            f['qtd_igual'] = 1.0
        elif abs(x - y) > 0.15 * max(x, y):
            f['qtd_conflito'] = 1.0
    ta, tb = quantidades_titulo(ia.get('t', '')), quantidades_titulo(ib.get('t', ''))
    if ta and tb and not compativeis(ta, tb):
        f['qtd_conflito'] = 1.0
    fa, fb = ia.get('_fx') or {}, ib.get('_fx') or {}
    if fa.get('p') and fb.get('p'):
        f['presos_igual' if fa['p'] == fb['p'] else 'presos_conflito'] = 1.0
    if fa.get('i') and fb.get('i'):
        f['idade_igual' if set(fa['i']) & set(fb['i']) else 'idade_conflito'] = 1.0
    f['raros'] = float(len(set(fa.get('r') or ()) & set(fb.get('r') or ())))
    ma, mb = materiais_titulo(ia.get('t', '')), materiais_titulo(ib.get('t', ''))
    f['mats_conflito'] = float(bool(ma and mb and not (ma & mb)))
    f['num_comum'] = float(min(3, len(c.nums[a] & c.nums[b])))
    da, db = _dia(ia), _dia(ib)
    f['dias'] = float(abs(da - db)) if da is not None and db is not None else 3.0
    f['mesmo_veiculo'] = float(bool(ia.get('f')) and ia.get('f') == ib.get('f'))
    return f


def carregar_pesos():
    if PESOS_ARQ.exists():
        return json.loads(PESOS_ARQ.read_text(encoding='utf-8'))
    return None


def placar(f, pesos):
    """Log da razão de chances (logit) do par ser o mesmo fato."""
    return pesos['vies'] + sum(pesos['w'].get(k, 0) * v for k, v in f.items())


def ancora(f):
    """Além do placar, uma prova concreta de que é o mesmo fato (não só palavras parecidas)."""
    return bool((f['foto'] and f['cos_txt'] >= 0.5) or f['copia'] >= 0.3 or f['link']
                or (f['qtd_igual'] and f['num_comum'] >= 1) or f['presos_igual'] or f['raros'] >= 1
                or (f['num_comum'] >= 2 and f['cos_txt'] >= 0.6))


def contradiz(f):
    """Contradição concreta: nunca une, por maior que seja o resto do placar."""
    return bool(f['cid_dif'] or f['qtd_conflito'] or f['presos_conflito'] or f['idade_conflito'] or f['mats_conflito'])


def candidatos(c, k_raros=12, max_lista=40):
    """Pares candidatos: mesmo estado (ou um sem estado), até JANELA dias, com palavra rara do
    texto em comum (índice invertido), ou a mesma foto/link."""
    dias = [_dia(it) for it in c.itens]
    indice = {}
    for k, it in enumerate(c.itens):
        if dias[k] is None:
            continue
        for w in c.termos_raros(k, k_raros):
            indice.setdefault(w, []).append(k)
    pares = set()
    for w, lista in indice.items():
        if len(lista) > max_lista * 6:
            continue  # palavra comum demais
        lista = sorted(lista, key=lambda k: dias[k])
        for x in range(len(lista)):
            a = lista[x]
            for y in range(x + 1, len(lista)):
                b = lista[y]
                if dias[b] - dias[a] > JANELA:
                    break
                ua, ub = c.itens[a].get('uf'), c.itens[b].get('uf')
                if ua and ub and ua != ub:
                    continue
                pares.add((a, b) if a < b else (b, a))
    return pares


_GENERICOS_LUGAR = None


def _conflito(ia, ib):
    """Contradição concreta entre duas notícias (para a coerência do grupo)."""
    ca, cb = ia.get('_cid'), ib.get('_cid')
    if ca and cb and ca != cb:
        return True
    fa, fb = ia.get('_fx') or {}, ib.get('_fx') or {}
    if fa.get('p') and fb.get('p') and fa['p'] != fb['p']:
        return True
    if fa.get('i') and fb.get('i') and not set(fa['i']) & set(fb['i']):
        return True
    qa, qb = ia.get('_q') or {}, ib.get('_q') or {}
    for m in set(qa) & set(qb):
        if abs(qa[m] - qb[m]) > 0.15 * max(qa[m], qb[m]):
            return True
    return False


def aplicar(itens, dia, unir, raiz, dias=None, suspeitas=None, motivos_juiz=None):
    """Passa o motor nos pares ainda separados: une (placar >= unir, sem contradição e com o
    grupo coerente), manda ao juiz de IA (duvida <= placar < unir) ou deixa separado.
    dias: só as notícias dos últimos dias (coleta rápida); None = todas."""
    global _GENERICOS_LUGAR
    if _GENERICOS_LUGAR is None:
        from duplicatas import AREAS_GENERICAS, lugares
        _GENERICOS_LUGAR = set(AREAS_GENERICAS) | set(lugares())
    pesos = carregar_pesos()
    if not pesos:
        return 0
    validos = [d for d in dia if d is not None]
    if not validos:
        return 0
    limite = (max(validos) - dias) if dias else min(validos)
    sel = [k for k in range(len(itens)) if dia[k] is not None and dia[k] >= limite]
    sub = [itens[k] for k in sel]
    c = Corpus(sub)
    juiz = motivos_juiz or {}
    membros = {}
    for k in sel:
        membros.setdefault(raiz(k), []).append(k)
    unidos = duvidas = 0
    ordem, fs = [], {}
    for a, b in candidatos(c):
        ka, kb = sel[a], sel[b]
        if raiz(ka) == raiz(kb):
            continue
        cos_t = c.cos(c.vt[a], c.vt[b])
        cos_x = c.cos(c.vx[a], c.vx[b])
        if cos_t < 0.25 and cos_x < 0.3:
            continue  # nada em comum de verdade no texto: não vale o cálculo completo
        f = indicios(c, a, b)
        if not (f['foto'] or f['copia'] >= 0.5 or f['link']):
            # Sem foto nem texto copiado: precisa de 3+ palavras em comum além da cidade e do estado.
            local = set(tokens(' '.join(x for x in (itens[ka].get('_cid'), itens[kb].get('_cid'), itens[ka].get('uf'),
                                                     itens[kb].get('uf')) if x)))
            comuns = (set(c.tok_t[a]) | set(c.tok_x[a])) & (set(c.tok_t[b]) | set(c.tok_x[b]))
            comuns -= local | _GENERICOS_LUGAR
            if len(comuns) < 3:
                continue
        s = placar(f, pesos)
        if s >= pesos['duvida'] and not contradiz(f):
            ordem.append((s, ka, kb))
            fs[(ka, kb)] = f
    ordem.sort(reverse=True)  # os pares mais certos primeiro
    for s, ka, kb in ordem:
        ra, rb = raiz(ka), raiz(kb)
        if ra == rb:
            continue
        ia, ib = itens[ka], itens[kb]
        chave = '-'.join(sorted((str(ia.get('i')), str(ib.get('i'))), key=lambda x: (len(x), x)))
        decisao = (juiz.get(chave) or {}).get('v')
        if decisao == 'diferente':
            continue
        ga, gb = membros.get(ra, [ka]), membros.get(rb, [kb])
        if any(_conflito(itens[x], itens[y]) for x in ga[:40] for y in gb[:40]):
            continue  # o grupo ficaria incoerente (outra cidade, outro número de presos...)
        if (s >= pesos['unir'] and ancora(fs[(ka, kb)])) or decisao == 'mesmo':
            unir(ka, kb, 'motor' if s >= pesos['unir'] else 'motor+juiz')
            nova = raiz(ka)
            membros[nova] = ga + gb
            unidos += 1
        elif suspeitas is not None:
            duvidas += 1
            suspeitas.append({'nota': round(s, 2), 'motivos': ['motor de evidências'],
                              'a': [ia['i'], ia.get('f', ''), ia['t'], ia.get('d', ''), ia.get('uf', ''),
                                    str(ia.get('_txt') or ia.get('_lead', ''))[:700], ia.get('_cid') or ''],
                              'b': [ib['i'], ib.get('f', ''), ib['t'], ib.get('d', ''), ib.get('uf', ''),
                                    str(ib.get('_txt') or ib.get('_lead', ''))[:700], ib.get('_cid') or '']})
    return unidos
