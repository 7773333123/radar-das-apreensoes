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
import base64
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageFilter

ARQUIVO = Path(__file__).resolve().parent / 'noticias.json'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; +https://www.radardasapreensoes.com.br)',
    'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8',
}
MAX_BYTES = 6_000_000


LADO = 16  # miniatura para comparar recortes: 16 colunas (ou 16 linhas), o dobro no sentido do recorte


def miniaturas(cinza):
    """Duas miniaturas desfocadas em tons de cinza (base64, com o tamanho na frente), para
    achar a mesma foto recortada de outro jeito por outro veículo:
    'v<linhas>:' = 16 colunas e linhas proporcionais x2 (recortes de cima/baixo);
    'h<colunas>:' = 16 linhas e colunas proporcionais x2 (recortes dos lados).
    O desfoque deixa a comparação estável mesmo com o deslocamento entre os recortes."""
    w, h = cinza.size
    alt = max(4, min(96, round(2 * LADO * h / w)))
    larg = max(4, min(96, round(2 * LADO * w / h)))
    base_v = cinza.resize((4 * LADO, max(4, round(4 * LADO * h / w))), Image.Resampling.BOX).filter(ImageFilter.GaussianBlur(3))
    base_h = cinza.resize((max(4, round(4 * LADO * w / h)), 4 * LADO), Image.Resampling.BOX).filter(ImageFilter.GaussianBlur(3))
    v = base_v.resize((LADO, alt), Image.Resampling.BOX).tobytes()
    hz = base_h.resize((larg, LADO), Image.Resampling.BOX).tobytes()
    return f'v{alt}:' + base64.b64encode(v).decode(), f'h{larg}:' + base64.b64encode(hz).decode()


def impressoes(dados):
    with Image.open(io.BytesIO(dados)) as img:
        img.draft('L', (256, 256))  # JPEG: decodifica já reduzido (mais rápido)
        cinza = img.convert('L')
        px = list(cinza.resize((9, 8), Image.Resampling.LANCZOS).getdata())
        mv, mh = miniaturas(cinza)
    bits = 0
    for linha in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[linha * 9 + col] > px[linha * 9 + col + 1])
    return f'{bits:016x}', mv, mh


def baixar(url, timeout):
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        dados = r.read(MAX_BYTES + 1)
    if len(dados) > MAX_BYTES:
        raise ValueError('imagem grande demais')
    return impressoes(dados)


def comparar_recortes(novas, noticias, corte):
    """Compara cada foto nova com as de notícias do mesmo dia (ou vizinho), do mesmo estado e
    com uma palavra própria em comum no título; guarda em img_iguais o endereço das fotos
    que são a mesma imagem recortada de outro jeito (duplicatas.py junta as notícias)."""
    import re
    from duplicatas import GENERICAS, MATERIAIS, mesma_foto_recortada, palavras, radical

    def chaves(n):
        t = re.sub(r'pol[ií]cia rodovi[aá]ria(?: federal| estadual)?', ' ', str(n.get('titulo') or '').rsplit(' - ', 1)[0], flags=re.I)
        return {radical(w) for w in palavras(t) if not w.isdigit() and w not in MATERIAIS
                and (w not in GENERICAS or w in ('rodoviaria', 'rodoviario'))}

    def dia(n):
        try:
            return datetime.fromisoformat(str(n.get('data_iso'))[:10]).toordinal()
        except ValueError:
            return None

    from datetime import datetime
    base = [n for n in noticias if isinstance(n, dict) and n.get('img_mini') and str(n.get('data_iso') or '') >= corte]
    indice = {}
    for n in base:
        d = dia(n)
        if d is not None:
            for c in chaves(n):
                indice.setdefault((d, c), []).append(n)
    try:
        import numpy  # noqa: F401  (com numpy a comparação é ~8x mais rápida)
        teto = 60000
    except ImportError:
        teto = 4000
    pares = comparadas = 0
    for n in novas:
        if comparadas >= teto:
            break
        d = dia(n)
        if d is None:
            continue
        vistos = {id(n)}
        for c in chaves(n):
            for dd in (d - 1, d, d + 1):
                lista = indice.get((dd, c), [])
                if len(lista) > 40:  # palavra comum demais no dia
                    continue
                for o in lista:
                    if id(o) in vistos or o.get('imagem_url') == n.get('imagem_url'):
                        continue
                    vistos.add(id(o))
                    if n.get('uf') and o.get('uf') and n['uf'] != o['uf']:
                        continue
                    comparadas += 1
                    if mesma_foto_recortada((n['img_mini'], n.get('img_minih', '')), (o['img_mini'], o.get('img_minih', ''))):
                        for x, y in ((n, o), (o, n)):
                            lista_x = x.setdefault('img_iguais', [])
                            if y['imagem_url'] not in lista_x:
                                lista_x.append(y['imagem_url'])
                        pares += 1
    return pares


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=500)
    ap.add_argument('--timeout', type=int, default=10)
    ap.add_argument('--trabalhadores', type=int, default=12)
    ap.add_argument('--periodo', default='', help='Só notícias deste período (AAAA ou AAAA-MM): coleta retroativa')
    args = ap.parse_args()
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    # Sem impressão digital, ou recente (45 dias) sem as miniaturas de recorte.
    from datetime import datetime, timedelta, timezone
    corte = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()[:10]
    if args.periodo:  # retroativo: miniaturas e comparação dentro do período
        corte = args.periodo[:7] + ('-01' if len(args.periodo) >= 7 else '-01-01')
        noticias_periodo = [n for n in noticias if isinstance(n, dict) and str(n.get('data_iso') or '').startswith(args.periodo)]
    else:
        noticias_periodo = noticias
    pendentes = [n for n in noticias_periodo if isinstance(n, dict) and str(n.get('imagem_url') or '').startswith('http')
                 and int(n.get('img_dhash_tentativas') or 0) < 2
                 and (not n.get('img_dhash') or (not n.get('img_mini') and str(n.get('data_iso') or '') >= corte))]
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
                n['img_dhash'], n['img_mini'], n['img_minih'] = futuro.result()
                n['img_dhash_url'] = n['imagem_url']
                ok += 1
            except Exception:  # rede, HTTP, formato não suportado
                n['img_dhash_tentativas'] = int(n.get('img_dhash_tentativas') or 0) + 1
                falhas += 1
    iguais = comparar_recortes([n for n in lote if n.get('img_mini')], noticias_periodo, corte)
    if lote:
        tmp = ARQUIVO.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        tmp.replace(ARQUIVO)
    print(f'Impressões digitais: {ok} novas, {falhas} falhas; mesma foto recortada: {iguais} pares; {time.time() - inicio:.0f} s')


if __name__ == '__main__':
    main()
