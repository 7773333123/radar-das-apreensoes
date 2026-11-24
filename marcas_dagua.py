#!/usr/bin/env python3
"""Fotos com marca d'água ou nome do jornal carimbado (regra do dono, 24/11/2026).

"Não quero nas matérias marcas d'água, nomes de jornais na foto": a foto exibida tem de ser limpa.
Quando a versão exibida tem a foto carimbada, o site usa a foto limpa de outra fonte da mesma
notícia; sem foto limpa, a notícia fica com o marcador da editoria (sem buscar a foto original).

Como se descobre a marca, sem lista feita à mão: o veículo carimba a marca SEMPRE no mesmo lugar
(canto, rodapé, centro). Em fotos diferentes do mesmo veículo, as bordas (contornos) da cena caem
em lugares diferentes; as da marca caem sempre nos mesmos pixels. Somando os mapas de bordas de
8 a 14 fotos distintas, os pixels com borda em 60% ou mais das fotos formam a "máscara" da marca
do veículo. Depois, cada foto do veículo é conferida contra a máscara: com borda em metade ou mais
dos pixels da máscara, a foto tem a marca (foto sem a marca fica em ~20%, o acaso).

  python marcas_dagua.py --aprender   # máscara dos veículos com fotos recentes (refaz após 21 dias)
  python marcas_dagua.py --marcar     # confere as fotos recentes dos veículos com máscara

Grava marcas_dagua.json (máscara por veículo) e, em noticias.json, img_marca = {url: 1 ou 0}.
gerar_feed_site.py usa os dois (foto_com_marca).
"""
import argparse
import io
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / 'noticias.json'
MASCARAS = RAIZ / 'marcas_dagua.json'
LADO = 64              # mapa de bordas 64x64
TOPO = 0.20            # cada foto: os 20% de pixels com borda mais forte
FREQ_MASCARA = 0.6     # pixel da máscara: borda em 60%+ das fotos do veículo
MIN_FOTOS = 8          # fotos distintas para aprender a máscara
MIN_PIXELS = 10        # máscara menor que isso é acaso
MARCADA = 0.5          # foto com borda em metade+ da máscara tem a marca
FONTE_MARCA = 0.6      # veículo que carimba 60%+ das fotos: foto não conferida conta como carimbada
REFAZER_DIAS = 21


def chave_fonte(n):
    """Veículo da notícia: o site de origem (gov.br separa cada órgão pelo endereço)."""
    for campo in ('url_original', 'url', 'imagem_url'):
        u = str(n.get(campo) or '')
        if u.startswith('http') and 'news.google.com' not in u:
            host = urlsplit(u).netloc.lower().split(':')[0]
            return host[4:] if host.startswith('www.') else host
    d = str(n.get('dominio_fonte') or '').lower()
    return d[4:] if d.startswith('www.') else d


def bordas(dados):
    """Mapa de bordas 64x64 (inteiro de 4096 bits: 1 = entre os 20% de borda mais forte)."""
    from PIL import Image, ImageFilter
    with Image.open(io.BytesIO(dados)) as img:
        img.draft('L', (256, 256))
        cinza = img.convert('L').resize((LADO, LADO), Image.Resampling.BOX)
    px = list(cinza.filter(ImageFilter.FIND_EDGES).getdata())
    return _binario(px)


def _binario(px):
    lim = max(16, sorted(px)[int(len(px) * (1 - TOPO))])
    bits = 0
    for k, v in enumerate(px):
        y, x = divmod(k, LADO)
        if v >= lim and 2 <= x < LADO - 2 and 2 <= y < LADO - 2:  # a moldura do filtro não conta
            bits |= 1 << k
    return bits


def mascara(mapas):
    """Máscara da marca a partir dos mapas de bordas de fotos distintas do veículo (0 = sem marca)."""
    if len(mapas) < MIN_FOTOS:
        return 0
    conta = [0] * (LADO * LADO)
    for m in mapas:
        k = 0
        while m:
            if m & 1:
                conta[k] += 1
            m >>= 1
            k += 1
    minimo = FREQ_MASCARA * len(mapas)
    pix = {k for k, c in enumerate(conta) if c >= minimo}
    # Linha reta inteira (tarja de foto vertical, borda de recorte) não é marca: tira linhas/colunas cheias.
    for eixo in (0, 1):
        por = defaultdict(int)
        for k in pix:
            por[divmod(k, LADO)[eixo]] += 1
        cheias = {v for v, c in por.items() if c > LADO * 0.5}
        pix = {k for k in pix if divmod(k, LADO)[eixo] not in cheias}
    if len(pix) < MIN_PIXELS:
        return 0
    linhas = {k // LADO for k in pix}
    colunas = {k % LADO for k in pix}
    if len(linhas) < 3 or len(colunas) < 3:
        return 0
    bits = 0
    for k in pix:
        bits |= 1 << k
    return bits


def nota(mapa, masc):
    """Fração dos pixels da máscara com borda nesta foto (0 a 1)."""
    total = bin(masc).count('1')
    return bin(mapa & masc).count('1') / total if total else 0.0


def carregar_mascaras():
    try:
        return json.loads(MASCARAS.read_text(encoding='utf-8')).get('fontes', {})
    except (OSError, ValueError):
        return {}


def foto_com_marca(n, url, mascaras):
    """A foto `url` da notícia `n` tem marca d'água/nome do jornal? (para gerar_feed_site.py)"""
    conferidas = n.get('img_marca') or {}
    if url in conferidas:
        return bool(conferidas[url])
    info = mascaras.get(chave_fonte(n)) or {}
    return bool(info.get('m')) and float(info.get('pct') or 0) >= FONTE_MARCA


def _baixar_mapa(url, timeout):
    from hash_imagens import HEADERS, MAX_BYTES
    from urllib.request import Request, urlopen
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        dados = r.read(MAX_BYTES + 1)
    if len(dados) > MAX_BYTES:
        raise ValueError('imagem grande demais')
    return bordas(dados)


def _mapas(urls, timeout, trabalhadores):
    def um(u):
        try:
            return u, _baixar_mapa(u, timeout)
        except Exception:  # rede, HTTP, formato
            return u, None
    with ThreadPoolExecutor(max_workers=trabalhadores) as pool:
        return {u: m for u, m in pool.map(um, urls) if m is not None}


def _fotos(n, galeria):
    fotos = [n.get('imagem_url')] + (list(n.get('imagens') or [])[:galeria] if galeria else [])
    return [f for f in dict.fromkeys(fotos) if isinstance(f, str) and f.startswith('http')]


def aprender(noticias, mascaras, fontes_max, fotos_por_fonte, timeout, trabalhadores):
    hoje = datetime.now(timezone.utc).date()
    corte = (hoje - timedelta(days=30)).isoformat()
    refazer = (hoje - timedelta(days=REFAZER_DIAS)).isoformat()
    por_fonte = defaultdict(list)
    for n in sorted(noticias, key=lambda n: str(n.get('data_iso') or ''), reverse=True):
        if str(n.get('data_iso') or '') < corte or not str(n.get('imagem_url') or '').startswith('http'):
            continue
        por_fonte[chave_fonte(n)].append(n)
    candidatas = [f for f, ns in por_fonte.items() if f and len(ns) >= MIN_FOTOS
                  and str((mascaras.get(f) or {}).get('em') or '') < refazer]
    candidatas.sort(key=lambda f: -len(por_fonte[f]))
    candidatas = candidatas[:fontes_max]
    print(f'Veículos com {MIN_FOTOS}+ fotos no mês: {sum(1 for ns in por_fonte.values() if len(ns) >= MIN_FOTOS)}; '
          f'aprendendo agora: {len(candidatas)}', flush=True)
    com_marca = 0
    for fonte in candidatas:
        # Fotos distintas: dHash diferente (o veículo às vezes repete a mesma arte).
        urls, vistos = [], []
        for n in por_fonte[fonte]:
            h = n.get('img_dhash')
            if h and any(bin(int(h, 16) ^ v).count('1') <= 10 for v in vistos):
                continue
            if h:
                vistos.append(int(h, 16))
            urls.append(n['imagem_url'])
            if len(urls) >= fotos_por_fonte + 4:
                break
        mapas = list(_mapas(urls, timeout, trabalhadores).values())[:fotos_por_fonte]
        masc = mascara(mapas)
        pct = (sum(1 for m in mapas if nota(m, masc) >= MARCADA) / len(mapas)) if masc and mapas else 0.0
        mascaras[fonte] = {'n': len(mapas), 'm': format(masc, 'x') if masc else '', 'px': bin(masc).count('1'),
                           'pct': round(pct, 2), 'em': hoje.isoformat()}
        if masc:
            com_marca += 1
            print(f'  marca d\'água: {fonte} ({len(mapas)} fotos, máscara {bin(masc).count("1")} px, '
                  f'{pct:.0%} das fotos carimbadas)', flush=True)
    print(f'Veículos com marca d\'água encontrados nesta rodada: {com_marca} de {len(candidatas)}')


def marcar(noticias, mascaras, dias, limite, galeria, timeout, trabalhadores):
    corte = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()[:10]
    pendentes = []
    for n in noticias:
        if str(n.get('data_iso') or '') < corte:
            continue
        info = mascaras.get(chave_fonte(n)) or {}
        if not info.get('m'):
            continue
        feitas = n.get('img_marca') or {}
        falta = [u for u in _fotos(n, galeria) if u not in feitas]
        if falta:
            pendentes.append((n, falta, int(info['m'], 16)))
    pendentes.sort(key=lambda p: str(p[0].get('data_iso') or ''), reverse=True)
    lote = pendentes[:limite]
    urls = [u for _, falta, _ in lote for u in falta]
    mapas = _mapas(urls, timeout, trabalhadores)
    carimbadas = conferidas = 0
    for n, falta, masc in lote:
        feitas = dict(n.get('img_marca') or {})
        for u in falta:
            if u in mapas:
                v = 1 if nota(mapas[u], masc) >= MARCADA else 0
                feitas[u] = v
                carimbadas += v
                conferidas += 1
        if feitas:
            n['img_marca'] = feitas
    print(f'Fotos conferidas contra a marca do veículo: {conferidas} ({carimbadas} com marca d\'água); '
          f'notícias pendentes: {len(pendentes)}, nesta rodada: {len(lote)}')
    return bool(lote)


GENERICAS = {'portal', 'noticias', 'noticia', 'jornal', 'news', 'online', 'agora', 'diario', 'folha', 'gazeta', 'tribuna',
             'radio', 'blog', 'site', 'globo', 'internet', 'brasil', 'www', 'http', 'https', 'cidade', 'policia', 'policial', 'militar', 'civil'}


def _letras(t):
    import unicodedata
    t = unicodedata.normalize('NFKD', str(t or '').lower())
    return ''.join(c for c in t if c.isalnum() or c in ' .\n')


def palavras_do_veiculo(nome, dominio):
    """Palavras que identificam o jornal ("agreste", "violento", "campos24horas"), sem as genéricas."""
    import re
    base = _letras(nome) + ' ' + _letras(dominio.split('.')[0]) + ' ' + _letras(dominio.replace('.com', ' ').replace('.br', ' '))
    return {p for p in re.split(r'[^a-z0-9]+', base) if len(p) >= 5 and p not in GENERICAS}


def texto_na_foto(dados):
    """Texto escrito na foto (OCR, tesseract): marca d'água, nome do jornal, endereço do site."""
    import subprocess
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(dados)) as img:
        c = img.convert('L')
    if c.width < 1200:  # letra pequena de marca d'água: amplia antes de ler
        f = 1200 / c.width
        c = c.resize((1200, max(1, round(c.height * f))))
    saida = []
    for versao in (c, ImageOps.invert(c)):  # marca branca sobre a foto: invertida fica preta
        b = io.BytesIO()
        versao.save(b, 'PNG')
        r = subprocess.run(['tesseract', 'stdin', 'stdout', '-l', 'por', '--psm', '11'], input=b.getvalue(),
                           capture_output=True, timeout=60)
        saida.append(r.stdout.decode('utf-8', 'ignore'))
    return _letras(' '.join(saida))


def nome_na_foto(texto, palavras):
    """O texto lido na foto tem o nome do jornal ou um endereço de site?"""
    import re
    achou = [p for p in palavras if p in texto.replace(' ', '') or p in texto]
    site = re.findall(r'[a-z0-9-]{3,}\.com(?:\.br)?|www\.[a-z0-9-]{3,}', texto)
    return achou, site


def diagnostico(noticias, fontes, timeout, trabalhadores):
    """Calibração com fotos reais: para cada veículo, quantos pixels passariam com limiares diferentes."""
    global TOPO
    por_fonte = defaultdict(list)
    for n in sorted(noticias, key=lambda n: str(n.get('data_iso') or ''), reverse=True):
        if str(n.get('imagem_url') or '').startswith('http'):
            por_fonte[chave_fonte(n)].append(n['imagem_url'])
    for fonte in fontes:
        urls = list(dict.fromkeys(por_fonte.get(fonte, [])))[:16]
        brutos, ocr = {}, {}
        def um(u):
            try:
                from hash_imagens import HEADERS, MAX_BYTES
                from urllib.request import Request, urlopen
                from PIL import Image, ImageFilter
                with urlopen(Request(u, headers=HEADERS), timeout=timeout) as r:
                    dados = r.read(MAX_BYTES)
                ocr[u] = dados
                with Image.open(io.BytesIO(dados)) as img:
                    img.draft('L', (256, 256))
                    c = img.convert('L')
                    tam = c.size
                    c = c.resize((LADO, LADO), Image.Resampling.BOX)
                return u, (list(c.filter(ImageFilter.FIND_EDGES).getdata()), tam)
            except Exception as e:
                return u, None
        with ThreadPoolExecutor(max_workers=trabalhadores) as pool:
            for u, v in pool.map(um, urls):
                if v:
                    brutos[u] = v
        print(f'== {fonte}: {len(brutos)} fotos baixadas de {len(urls)}; tamanhos: {sorted(set(t for _, t in brutos.values()))[:6]}')
        for topo in (0.2, 0.3, 0.4):
            TOPO = topo
            mapas = [_binario(px) for px, _ in brutos.values()]
            conta = [0] * (LADO * LADO)
            for m in mapas:
                for k in range(LADO * LADO):
                    if m >> k & 1:
                        conta[k] += 1
            n = max(1, len(mapas))
            linha = [f'topo {topo}: freq máx {max(conta) / n:.2f}']
            for f in (0.4, 0.5, 0.6):
                pix = [k for k, c in enumerate(conta) if c >= f * n]
                if pix:
                    ys = [k // LADO for k in pix]; xs = [k % LADO for k in pix]
                    linha.append(f'≥{f}: {len(pix)} px (x {min(xs)}-{max(xs)}, y {min(ys)}-{max(ys)})')
                else:
                    linha.append(f'≥{f}: 0 px')
            print('   ' + '; '.join(linha))
        TOPO = 0.20
        nome = next((str(n.get('fonte') or '') for n in noticias if chave_fonte(n) == fonte), '')
        palavras = palavras_do_veiculo(nome, fonte)
        com_nome = com_site = 0
        for u, dados in list(ocr.items())[:12]:
            try:
                txt = texto_na_foto(dados)
            except Exception as e:
                print(f'   OCR falhou: {e!r}'[:120])
                continue
            achou, site = nome_na_foto(txt, palavras)
            com_nome += bool(achou)
            com_site += bool(site)
            print(f'   OCR: nome={achou} site={site[:2]} texto={" ".join(txt.split())[:90]!r}')
        print(f'   palavras do veículo: {sorted(palavras)}; fotos com o nome: {com_nome}; com endereço de site: {com_site} (de {min(12, len(ocr))})')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--aprender', action='store_true')
    ap.add_argument('--marcar', action='store_true')
    ap.add_argument('--fontes', type=int, default=400, help='veículos a aprender por rodada')
    ap.add_argument('--fotos', type=int, default=12, help='fotos por veículo para aprender a máscara')
    ap.add_argument('--dias', type=int, default=7, help='--marcar: notícias destes últimos dias')
    ap.add_argument('--limite', type=int, default=3000, help='--marcar: notícias por rodada')
    ap.add_argument('--galeria', type=int, default=5, help='--marcar: fotos da galeria conferidas por notícia')
    ap.add_argument('--timeout', type=int, default=10)
    ap.add_argument('--trabalhadores', type=int, default=16)
    ap.add_argument('--diagnostico', default='', help='veículos separados por vírgula: só mostra a calibração')
    args = ap.parse_args()
    inicio = time.time()
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = [n for n in (dados['noticias'] if isinstance(dados, dict) else dados) if isinstance(n, dict)]
    mascaras = carregar_mascaras()
    if args.diagnostico:
        diagnostico(noticias, [f.strip() for f in args.diagnostico.split(',') if f.strip()], args.timeout, args.trabalhadores)
        return
    if args.aprender:
        aprender(noticias, mascaras, args.fontes, args.fotos, args.timeout, args.trabalhadores)
        MASCARAS.write_text(json.dumps({'atualizado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                        'fontes': dict(sorted(mascaras.items()))}, ensure_ascii=False, indent=0) + '\n',
                            encoding='utf-8')
    if args.marcar and marcar(noticias, mascaras, args.dias, args.limite, args.galeria, args.timeout, args.trabalhadores):
        tmp = ARQUIVO.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        tmp.replace(ARQUIVO)
    print(f'Marcas d\'água: {time.time() - inicio:.0f} s')


if __name__ == '__main__':
    main()
