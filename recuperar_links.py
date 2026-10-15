#!/usr/bin/env python3
"""Recuperação conservadora de links originais; somente biblioteca padrão."""
import argparse
import base64
import html
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse, unquote, urlencode
from urllib.request import Request, urlopen

ARQUIVO = Path(__file__).resolve().parent / "noticias.json"
AGREGADORES = ("google.com", "googleusercontent.com", "googleapis.com", "gstatic.com")

def url_valida(url):
    if not isinstance(url, str):
        return False
    try:
        p = urlparse(url.strip())
        host = (p.hostname or "").lower()
        return p.scheme in ("http", "https") and bool(host) and not any(
            host == d or host.endswith("." + d) for d in AGREGADORES
        )
    except ValueError:
        return False

def extrair_do_codigo(url):
    """Links antigos incluem URL original dentro do identificador base64."""
    try:
        codigo = urlparse(url).path.rstrip("/").split("/")[-1]
        bruto = base64.urlsafe_b64decode(codigo + "=" * (-len(codigo) % 4))
        for match in re.finditer(rb"https?://[^\x00-\x20\x7f\"'<>]+", bruto):
            candidato = match.group().decode("utf-8", "ignore")
            # Remover eventual delimitador de protobuf no final.
            candidato = re.split(r"[\x00-\x1f]", candidato)[0]
            if url_valida(candidato):
                return candidato
    except (ValueError, UnicodeError, TypeError):
        pass
    return ""

def extrair_html(pagina):
    # Aceitar somente URLs externas explicitamente declaradas como destino.
    padroes = (
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical',
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:url',
    )
    for padrao in padroes:
        for m in re.finditer(padrao, pagina, re.I):
            candidato = html.unescape(m.group(1))
            if url_valida(candidato):
                return candidato
    return ""

def google_rpc(url):
    """Tenta resolver os identificadores recentes via endpoint público do Google Notícias."""
    codigo = urlparse(url).path.rstrip('/').split('/')[-1]
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,}', codigo):
        return ''
    try:
        pagina = f'https://news.google.com/rss/articles/{codigo}?hl=pt-BR&gl=BR&ceid=BR:pt-419'
        req = Request(pagina, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=7) as resp:
            corpo = resp.read(220000).decode('utf-8', 'replace')
        ident = re.search(r'data-n-a-id="([^"]+)"', corpo)
        assinatura = re.search(r'data-n-a-sg="([^"]+)"', corpo)
        if not ident or not assinatura:
            return ''
        payload = json.dumps([['Fbv4je', json.dumps(["garturlreq", [["pt-BR", "BR", ["FINANCE_TOP_INDICES", "WEB_TEST_1_0_0"], None, None, 1, 1, "BR:pt-419", None, 180, None, None, None, None, None, 0, None, None, [1608992183, 723341000]], "pt-BR", "BR", 1, [2, 3, 4, 8], 1, 0, "655000234", 0, 0, None, 0], ident.group(1), assinatura.group(1)]), None, 'generic']])
        post = urlencode({'f.req': payload}).encode()
        req = Request('https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je', data=post, headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'})
        with urlopen(req, timeout=9) as resp:
            resposta = resp.read(180000).decode('utf-8', 'replace')
        for m in re.finditer(r'https?://[^\\"\s<>]+', resposta):
            candidato = m.group(0).replace('\\/', '/').rstrip('\\')
            if url_valida(candidato):
                return candidato
    except Exception:
        pass
    return ''

def resolver(url):
    original = extrair_do_codigo(url)
    if original:
        return original, "recuperada_codigo"
    via_rpc = google_rpc(url)
    if via_rpc:
        return via_rpc, "recuperada_google_rpc"
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; RadarApreensoes/1.0)"})
        with urlopen(req, timeout=9) as resp:
            destino = resp.geturl()
            if url_valida(destino):
                return destino, "recuperada_redirecionamento"
            conteudo = resp.read(180000).decode("utf-8", "replace")
            original = extrair_html(conteudo)
            if original:
                return original, "recuperada_canonical"
        return "", "nao_resolvida"
    except Exception as exc:
        return "", "erro_" + type(exc).__name__

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=int(os.getenv("LIMITE_DECODIFICACAO", "200")))
    parser.add_argument("--trabalhadores", type=int, default=6)
    args = parser.parse_args()
    if not ARQUIVO.exists():
        raise SystemExit("noticias.json ausente; nada alterado")
    dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    noticias = dados.get("noticias") if isinstance(dados, dict) else dados
    if not isinstance(noticias, list):
        raise SystemExit("Formato inválido; nada alterado")
    pendentes = []
    existentes = 0
    for noticia in noticias:
        if not isinstance(noticia, dict):
            continue
        if url_valida(noticia.get("url_original")):
            existentes += 1
            continue
        google = noticia.get("url_google_noticias") or noticia.get("url") or ""
        if url_valida(google):
            noticia["url_original"] = google
            noticia["url_original_status"] = "direta"
            existentes += 1
        elif "news.google.com/" in google:
            if noticia.get("url_original_status", "").startswith(("erro_", "nao_resolvida")) and not os.getenv("REPETIR_FALHAS"):
                continue
            pendentes.append((noticia, google))
    lote = pendentes[:max(0, args.limite)]
    print(f"Acervo: {len(noticias)}; links originais: {existentes}; aguardando: {len(pendentes)}; tentativa: {len(lote)}", flush=True)
    sucesso, erros = 0, {}
    with ThreadPoolExecutor(max_workers=max(1, min(args.trabalhadores, 8))) as pool:
        futures = {pool.submit(resolver, url): (noticia, url) for noticia, url in lote}
        for future in as_completed(futures):
            noticia, google = futures[future]
            try:
                original, status = future.result()
            except Exception as exc:
                original, status = "", "erro_" + type(exc).__name__
            noticia.setdefault("url_google_noticias", google)
            if original:
                noticia["url_original"] = original
                noticia["url_original_status"] = status
                noticia["leitura_fonte_status"] = "pendente_leitura_original"
                sucesso += 1
            else:
                noticia["url_original_status"] = status
                erros[status] = erros.get(status, 0) + 1
    if lote:
        temp = ARQUIVO.with_suffix(".json.tmp")
        temp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(ARQUIVO)
    print(f"Recuperados: {sucesso}/{len(lote)}; falhas: {erros}; acervo preservado: {len(noticias)}.", flush=True)

if __name__ == "__main__":
    main()
