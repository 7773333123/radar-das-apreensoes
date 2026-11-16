#!/usr/bin/env python3
"""Impressão digital visual (dHash de 64 bits) da foto principal de cada notícia.

Duas versões da mesma matéria costumam usar a mesma foto (da polícia, da
agência ou do próprio veículo), mesmo quando ela foi recortada, comprimida ou
redimensionada. O dHash reduz a foto a 9x8 tons de cinza e compara pixels
vizinhos: fotos iguais ou quase iguais ficam a poucos bits de distância
(distância de Hamming). gerar_feed_site.py usa isso para agrupar duplicatas.

Grava em noticias.json: img_dhash (16 dígitos hexadecimais) e, em falha,
img_dhash_tentativas. Mais recentes primeiro.
"""
import argparse
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image

ARQUIVO = Path(__file__).resolve().parent / 'noticias.json'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://www.radardasapreensoes.com.br)',
    'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8',
}
MAX_BYTES = 6_000_000


def dhash(dados):
    with Image.open(io.BytesIO(dados)) as img:
        img.draft('L', (64, 64))  # JPEG: decodifica já reduzido (mais rápido)
        cinza = img.convert('L').resize((9, 8), Image.Resampling.LANCZOS)
        px = list(cinza.getdata())
    bits = 0
    for linha in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[linha * 9 + col] > px[linha * 9 + col + 1])
    return f'{bits:016x}'


def baixar(url, timeout):
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        dados = r.read(MAX_BYTES + 1)
    if len(dados) > MAX_BYTES:
        raise ValueError('imagem grande demais')
    return dhash(dados)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=500)
    ap.add_argument('--timeout', type=int, default=10)
    ap.add_argument('--trabalhadores', type=int, default=12)
    args = ap.parse_args()
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    pendentes = [n for n in noticias if isinstance(n, dict) and str(n.get('imagem_url') or '').startswith('http')
                 and not n.get('img_dhash') and int(n.get('img_dhash_tentativas') or 0) < 2]
    pendentes.sort(key=lambda n: n.get('data_iso') or '', reverse=True)
    lote = pendentes[:max(0, args.limite)]
    print(f'Fotos sem impressão digital: {len(pendentes)}; calculando agora: {len(lote)}', flush=True)
    ok = falhas = 0
    inicio = time.time()
    with ThreadPoolExecutor(max_workers=max(1, min(args.trabalhadores, 16))) as pool:
        tarefas = {pool.submit(baixar, n['imagem_url'], args.timeout): n for n in lote}
        for futuro in as_completed(tarefas):
            n = tarefas[futuro]
            try:
                n['img_dhash'] = futuro.result()
                n['img_dhash_url'] = n['imagem_url']
                ok += 1
            except Exception:  # rede, HTTP, formato não suportado
                n['img_dhash_tentativas'] = int(n.get('img_dhash_tentativas') or 0) + 1
                falhas += 1
    if lote:
        tmp = ARQUIVO.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        tmp.replace(ARQUIVO)
    print(f'Impressões digitais: {ok} novas, {falhas} falhas, {time.time() - inicio:.0f} s')


if __name__ == '__main__':
    main()
