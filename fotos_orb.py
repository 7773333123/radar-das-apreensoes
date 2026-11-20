#!/usr/bin/env python3
"""Reconhece a MESMA FOTO mesmo recortada, com zoom, redimensionada ou recomprimida.

O dHash (hash_imagens.py) só acha fotos quase idênticas, e as miniaturas de recorte só valem
para cortes num sentido e quando os títulos têm uma palavra própria em comum. Veículos que
republicam o comunicado da polícia usam a mesma foto com outro enquadramento e títulos
genéricos ("Polícia Civil apreende revólver durante operação"). Aqui cada foto vira um
conjunto de pontos característicos (ORB, OpenCV); duas fotos são a mesma imagem quando
muitos pontos coincidem numa mesma transformação (escala, deslocamento e giro: RANSAC).
Testado nos casos reais de 19/11/2026: mesma foto 36 a 325 pontos em comum; fotos
diferentes, no máximo 6. O limite usado é MIN_PONTOS.

Para cada notícia recente (DIAS) com foto: baixa a foto (uma vez; os pontos ficam em
orb_cache/, guardado entre execuções pelo cache do GitHub Actions), compara com as fotos das
notícias do mesmo estado em até 2 dias e grava em noticias.json:
- img_orb: 1 (foto analisada) ou img_orb_falhas (download falhou);
- img_mesma: {url da outra foto: pontos em comum}, nos dois lados do par.
duplicatas.py junta as notícias (regra 'mesma-foto'); gerar_feed_site.py segura a notícia
nova até a foto ser analisada.

  python fotos_orb.py [--limite 1500] [--trabalhadores 16] [--dias 3]
"""
import argparse
import hashlib
import re
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parent
dias_por_url = {}
ARQUIVO = RAIZ / 'noticias.json'
CACHE = RAIZ / 'orb_cache'
MIN_PONTOS = 15        # pontos em comum (RANSAC) para dizer que é a mesma foto
LADO = 640             # a foto é reduzida para este lado maior antes de extrair os pontos
PONTOS = 800           # pontos característicos por foto
JANELA = 2             # dias entre as duas notícias
TRIAGEM = 200          # pontos usados na triagem rápida
MAX_BYTES = 8_000_000
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://www.radardasapreensoes.com.br)',
    'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8',
}


def _cv():
    import cv2  # opencv-python-headless
    return cv2


def pontos(dados):
    """Pontos (x, y) e descritores ORB da foto (bytes), ou None se não der para ler."""
    import numpy as np
    cv2 = _cv()
    arr = np.frombuffer(dados, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:  # formatos que o OpenCV não lê (webp antigo, avif): via Pillow
        from PIL import Image
        with Image.open(io.BytesIO(dados)) as im:
            img = np.array(im.convert('L'))
    h, w = img.shape[:2]
    if min(h, w) < 60:
        return None
    s = LADO / max(h, w)
    img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    kps, desc = cv2.ORB_create(nfeatures=PONTOS, fastThreshold=8).detectAndCompute(img, None)
    if desc is None or len(kps) < 20:
        return None
    ordem = np.argsort([-k.response for k in kps])  # os mais fortes primeiro (triagem rápida)
    xy = np.array([kps[i].pt for i in ordem], dtype=np.float32)
    return xy, desc[ordem]


def pontos_em_comum(a, b):
    """Quantos pontos coincidem numa mesma transformação (escala + deslocamento + giro)."""
    import numpy as np
    cv2 = _cv()
    (xa, da), (xb, db) = a, b
    pares = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
    bons = [p[0] for p in pares if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if len(bons) < 6:
        return 0
    pa = np.float32([xa[m.queryIdx] for m in bons])
    pb = np.float32([xb[m.trainIdx] for m in bons])
    _, mask = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=4)
    return int(mask.sum()) if mask is not None else 0


def mesma_foto(a, b):
    """Pontos em comum, com triagem: primeiro só os 200 pontos mais fortes da foto a (4x mais
    rápido); só os pares promissores vão para a comparação completa."""
    if pontos_em_comum((a[0][:TRIAGEM], a[1][:TRIAGEM]), b) < 6:
        return 0
    return pontos_em_comum(a, b)


def _arq(url):
    return CACHE / (hashlib.sha1(url.encode()).hexdigest()[:20] + '.npz')


def carregar(url):
    import numpy as np
    p = _arq(url)
    if not p.exists():
        return None
    try:
        z = np.load(p)
        return z['xy'], z['d']
    except Exception:
        return None


def guardar(url, pts):
    import numpy as np
    CACHE.mkdir(exist_ok=True)
    np.savez_compressed(_arq(url), xy=pts[0], d=pts[1])


def baixar(url, timeout):
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        dados = r.read(MAX_BYTES + 1)
    if len(dados) > MAX_BYTES:
        raise ValueError('foto grande demais')
    return pontos(dados)


def _dia(n):
    try:
        return datetime.fromisoformat(str(n.get('data_iso'))[:10]).toordinal()
    except ValueError:
        return None


def foto_util(url):
    u = (url or '').lower()
    if not u.startswith('http') or any(x in u for x in ('logo', 'placeholder', 'default-image', 'sem-imagem', 'favicon')):
        return False
    # Imagem padrão do site (compartilhamento, ícone, banner): a mesma em centenas de notícias.
    return not re.search(r'/og/|og-image|opengra|share|compartilh|/_si/|icon|banner|cropped-|thumb-default|padrao', u)


def limpar_cache(urls_vivas):
    """Apaga do cache as fotos que saíram da janela de comparação."""
    if not CACHE.exists():
        return 0
    vivos = {_arq(u).name for u in urls_vivas}
    apagados = 0
    for p in CACHE.glob('*.npz'):
        if p.name not in vivos:
            p.unlink()
            apagados += 1
    return apagados


def revisar(noticias, desde, ate, trabalhadores, timeout, tempo_max, inicio):
    """Revisão completa de um período (acervo antigo): dia a dia, do mais antigo ao mais novo,
    baixa as fotos do dia e compara com as do mesmo estado nos JANELA dias anteriores (em
    memória; nada vai para o cache). Retoma de onde parou (img_orb marca o que já foi feito)."""
    dias = {}
    for n in noticias:
        if isinstance(n, dict) and foto_util(n.get('imagem_url')) and n.get('uf') and desde <= str(n.get('data_iso') or '')[:10] <= ate:
            d = _dia(n)
            if d is not None:
                dias.setdefault(d, []).append(n)
    global dias_por_url
    dias_por_url = {}
    for ns in dias.values():
        for n in ns:
            dias_por_url.setdefault(n['imagem_url'], []).append(n)
    ordem = sorted(dias)
    feitos = [d for d in ordem if all(n.get('img_orb') or int(n.get('img_orb_falhas') or 0) >= 2 for n in dias[d])]
    pendentes = [d for d in ordem if d not in set(feitos)]
    if not pendentes:
        print('Revisão: período já revisado.')
        return 0, 0
    comeco = pendentes[0] - JANELA  # reabre a janela anterior para comparar
    janela, pares, total = {}, 0, 0
    for d in [x for x in ordem if x >= comeco]:
        if time.time() - inicio > tempo_max:
            print(f'Revisão: tempo esgotado em {datetime.fromordinal(d).date()}; a próxima execução continua.')
            break
        urls = {}
        for n in dias[d]:
            urls.setdefault(n['imagem_url'], []).append(n)
        with ThreadPoolExecutor(max_workers=max(1, min(trabalhadores, 16))) as pool:
            tarefas = {pool.submit(baixar, u, timeout): u for u in urls}
            novos = {}
            for futuro in as_completed(tarefas):
                u = tarefas[futuro]
                try:
                    pts = futuro.result()
                except Exception:
                    pts = None
                for n in urls[u]:
                    if pts is None:
                        n['img_orb_falhas'] = int(n.get('img_orb_falhas') or 0) + 1
                    else:
                        n['img_orb'] = 1
                if pts is not None:
                    novos[u] = (pts, urls[u][0]['uf'])
        for u, (pts, uf) in novos.items():
            for dd in range(d - JANELA, d + 1):
                for v, (pv, ufv) in janela.get(dd, {}).items():
                    if ufv != uf or v == u:
                        continue
                    total += 1
                    k = mesma_foto(pts, pv)
                    if k >= MIN_PONTOS:
                        pares += 1
                        for x, y in ((u, v), (v, u)):
                            for n in (urls.get(x) or dias_por_url.get(x, ())):
                                n.setdefault('img_mesma', {})[y] = k
            janela.setdefault(d, {})[u] = (pts, uf)
        for dd in [x for x in janela if x < d - JANELA]:
            del janela[dd]
        print(f'Revisão {datetime.fromordinal(d).date()}: {len(novos)} fotos; pares até agora: {pares}', flush=True)
    return pares, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=1500, help='fotos baixadas por execução')
    ap.add_argument('--trabalhadores', type=int, default=16)
    ap.add_argument('--timeout', type=int, default=10)
    ap.add_argument('--dias', type=int, default=3)
    ap.add_argument('--revisar', help='Revisão completa do período AAAA-MM-DD:AAAA-MM-DD (acervo inteiro da parte)')
    ap.add_argument('--tempo-max', type=int, default=16000)
    args = ap.parse_args()
    inicio = time.time()
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    if args.revisar:
        desde, ate = (args.revisar.split(':') + [''])[:2]
        pares, total = revisar(noticias, desde, ate or '9999', args.trabalhadores, args.timeout, args.tempo_max, inicio)
        tmp = ARQUIVO.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        tmp.replace(ARQUIVO)
        print(f'Revisão: {total} comparações; mesma foto (recorte/zoom): {pares} pares; {time.time() - inicio:.0f} s')
        return
    corte = (datetime.now(timezone.utc) - timedelta(days=args.dias)).isoformat()[:10]
    recentes = [n for n in noticias if isinstance(n, dict) and str(n.get('data_iso') or '') >= corte
                and foto_util(n.get('imagem_url')) and n.get('uf')]
    # Fotos ainda sem pontos no cache (novas, ou cache perdido): as mais recentes primeiro.
    faltam = [n for n in recentes if not _arq(n['imagem_url']).exists() and int(n.get('img_orb_falhas') or 0) < 2]
    faltam.sort(key=lambda n: n.get('data_iso') or '', reverse=True)
    lote, vistos = [], set()
    for n in faltam:
        if n['imagem_url'] not in vistos:
            vistos.add(n['imagem_url'])
            lote.append(n)
        if len(lote) >= args.limite:
            break
    print(f'Notícias recentes com foto: {len(recentes)}; fotos sem análise: {len(faltam)}; analisando agora: {len(lote)}', flush=True)
    por_url = {}
    for n in recentes:
        por_url.setdefault(n['imagem_url'], []).append(n)
    novas, falhas = set(), 0
    with ThreadPoolExecutor(max_workers=max(1, min(args.trabalhadores, 16))) as pool:
        tarefas = {pool.submit(baixar, n['imagem_url'], args.timeout): n for n in lote}
        for futuro in as_completed(tarefas):
            url = tarefas[futuro]['imagem_url']
            try:
                pts = futuro.result()
            except Exception:
                pts = None
            if pts is None:
                falhas += 1
                for n in por_url.get(url, ()):
                    n['img_orb_falhas'] = int(n.get('img_orb_falhas') or 0) + 1
                continue
            guardar(url, pts)
            novas.add(url)
    # Analisadas: com pontos no cache (agora ou antes).
    for n in recentes:
        if _arq(n['imagem_url']).exists():
            n['img_orb'] = 1
    # Compara cada foto nova com as do mesmo estado em até JANELA dias.
    indice = {}
    for url, ns in por_url.items():
        for n in ns:
            d = _dia(n)
            if d is not None:
                indice.setdefault(n['uf'], {}).setdefault(d, set()).add(url)
    memo, pares, comparadas = {}, 0, 0

    def pts_de(u):
        if u not in memo:
            memo[u] = carregar(u)
        return memo[u]

    for url in novas:
        a = pts_de(url)
        if a is None:
            continue
        candidatos = set()
        for n in por_url[url]:
            d = _dia(n)
            if d is None:
                continue
            for dd in range(d - JANELA, d + JANELA + 1):
                candidatos |= indice.get(n['uf'], {}).get(dd, set())
        candidatos.discard(url)
        for outra in candidatos:
            b = pts_de(outra)
            if b is None:
                continue
            comparadas += 1
            k = mesma_foto(a, b)
            if k >= MIN_PONTOS:
                pares += 1
                for x, y in ((url, outra), (outra, url)):
                    for n in por_url.get(x, ()):
                        n.setdefault('img_mesma', {})[y] = max(k, int((n.get('img_mesma') or {}).get(y, 0)))
    apagados = limpar_cache(por_url)
    if lote or pares:
        tmp = ARQUIVO.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        tmp.replace(ARQUIVO)
    print(f'Fotos analisadas: {len(novas)} novas, {falhas} falhas; comparações: {comparadas}; '
          f'mesma foto (recorte/zoom): {pares} pares; cache: {apagados} antigas apagadas; {time.time() - inicio:.0f} s')


if __name__ == '__main__':
    main()
