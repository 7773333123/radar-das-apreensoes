#!/usr/bin/env python3
"""Foto de capa = foto do material apreendido (regra do dono do site, 24/11/2026).

Na capa de uma notícia vai, sempre que existir, a foto que mostra o que foi apreendido (drogas, armas,
dinheiro, mercadorias...), e não a de policial, viatura, fachada ou brasão. O Claude Haiku olha as fotos
de cada notícia recente (miniaturas de 256 px, uma pergunta por notícia) e diz quais mostram o material.

Resultado em capas_ia.json: {"fotos": {url: 1 (mostra o material) | 0 (não mostra)}, "gasto": {...}}. O gerador do site
(gerar_feed_site.py) põe primeiro as fotos marcadas com 1 e a versão exibida de um grupo de duplicatas
troca a capa pela foto do material de outra fonte (duplicatas.agrupar). Gasto próprio, com teto de
US$ 8 por mês (TETO_USD), separado do teto do juiz de duplicatas (US$ 9).

  python capas_ia.py --horas 36 --max 250
"""
import argparse
import base64
import io
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / 'capas_ia.json'
ACERVO = RAIZ / 'noticias.json'
MODELO = 'claude-haiku-5-5'
MAX_FOTOS = 5
TETO_USD = 8.0  # autorizado pelo dono do site (24/11/2026): todas as notícias
UA = 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://www.radardasapreensoes.com.br)'
PERGUNTA = ('Estas fotos são de uma notícia policial brasileira sobre uma apreensão. Para cada foto, diga se ela '
            'MOSTRA o material apreendido em destaque: drogas (tabletes, pacotes, pó, plantas), armas, munições, '
            'dinheiro, celulares, cigarros, mercadorias, animais resgatados, veículo carregado com a carga. '
            'NÃO conta: foto só de policial, viatura, fachada, pessoa, brasão, logotipo, mapa ou arte gráfica. '
            'Responda com os números das fotos que mostram o material.')
ESQUEMA = {'type': 'object', 'additionalProperties': False, 'required': ['fotos_com_material'],
           'properties': {'fotos_com_material': {'type': 'array', 'items': {'type': 'integer'}}}}


def carregar():
    try:
        d = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        d = {}
    mes = datetime.now(timezone.utc).strftime('%Y-%m')
    g = d.get('gasto') or {}
    return d.get('fotos') or {}, (g if g.get('mes') == mes else {'mes': mes, 'usd': 0.0, 'noticias': 0})


def fotos_conferidas():
    """{url: 1|0} para o gerador do site."""
    return carregar()[0]


def miniatura(url):
    """JPEG de até 320 px em base64, ou None (foto fora do ar, grande demais ou não é imagem)."""
    from PIL import Image
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=8) as r:
            dados = r.read(6_000_000)
        im = Image.open(io.BytesIO(dados)).convert('RGB')
        if min(im.size) < 120:
            return None  # ícone/logotipo pequeno
        im.thumbnail((256, 256))
        saida = io.BytesIO()
        im.save(saida, 'JPEG', quality=70)
        return base64.standard_b64encode(saida.getvalue()).decode('ascii')
    except Exception:
        return None


def candidatas(horas, ja):
    """[(id, [urls ainda não classificadas])] das notícias das últimas `horas` horas."""
    d = json.loads(ACERVO.read_text(encoding='utf-8'))
    ns = d['noticias'] if isinstance(d, dict) else d
    limite = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
    saida = []
    for n in ns:
        if not isinstance(n, dict) or str(n.get('data_iso') or '') < limite[:19]:
            continue
        fotos = []
        for f in [n.get('imagem_url')] + list(n.get('imagens') or []):
            if isinstance(f, str) and f.startswith('http') and f not in fotos:
                fotos.append(f)
        fotos = fotos[:MAX_FOTOS]
        if fotos and any(f not in ja for f in fotos):
            saida.append((n.get('id') or n.get('url'), fotos))
    saida.sort(key=lambda x: -len(x[1]))  # galerias primeiro: é onde a escolha da capa muda alguma coisa
    return saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--horas', type=float, default=36)
    ap.add_argument('--max', type=int, default=250, help='notícias por execução')
    a = ap.parse_args()
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print('Capas: sem ANTHROPIC_API_KEY; nada a fazer.')
        return
    import anthropic
    from juiz_duplicatas import PRECO_CLAUDE
    cache, gasto = carregar()
    if gasto['usd'] >= TETO_USD:
        print('Capas: teto mensal atingido; nada a fazer.')
        return
    fila = candidatas(a.horas, cache)[:a.max]
    client = anthropic.Anthropic(max_retries=4)
    pe, ps = PRECO_CLAUDE[MODELO]
    feitas = falhas = 0

    def classificar(par):
        _, fotos = par
        imgs = [(f, miniatura(f)) for f in fotos]
        imgs = [(f, b) for f, b in imgs if b]
        if not imgs:
            return {f: 0 for f in fotos}, None
        conteudo = []
        for k, (_, b) in enumerate(imgs, 1):
            conteudo += [{'type': 'text', 'text': f'Foto {k}:'},
                         {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b}}]
        conteudo.append({'type': 'text', 'text': PERGUNTA})
        try:
            r = client.messages.create(model=MODELO, max_tokens=300, messages=[{'role': 'user', 'content': conteudo}],
                                       output_config={'effort': 'low', 'format': {'type': 'json_schema', 'schema': ESQUEMA}})
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as erro:
            print(f'Capas: erro na API: {erro!r}'[:200], flush=True)
            return None, None
        if r.stop_reason != 'end_turn':
            return None, r.usage
        try:
            sim = set(json.loads(next((x.text for x in r.content if x.type == 'text'), '{}')).get('fotos_com_material', []))
        except ValueError:
            return None, r.usage
        res = {f: int(k in sim) for k, (f, _) in enumerate(imgs, 1)}
        res.update({f: 0 for f in fotos if f not in res})  # fora do ar ou ícone: não vira capa
        return res, r.usage

    with ThreadPoolExecutor(max_workers=6) as pool:
        for res, u in pool.map(classificar, fila):
            if gasto['usd'] >= TETO_USD:
                break
            if u is not None:
                gasto['usd'] = round(gasto['usd'] + ((u.input_tokens or 0) * pe + (u.output_tokens or 0) * ps) / 1e6, 6)
            if res is None:
                falhas += 1
                continue
            cache.update(res)
            feitas += 1
            gasto['noticias'] += 1
    # Guarda só as dos últimos 20 dias de uso (o arquivo não cresce sem fim): ordem de inserção.
    if len(cache) > 60000:
        cache = dict(list(cache.items())[-60000:])
    ARQUIVO.write_text(json.dumps({'gasto': gasto, 'fotos': cache}, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'Capas: {feitas} notícias conferidas ({falhas} sem resposta), {sum(cache.values())} fotos do material '
          f'no total; gasto do mês US$ {gasto["usd"]:.4f}')


if __name__ == '__main__':
    main()
