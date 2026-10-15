#!/usr/bin/env python3
"""Busca somente fotos declaradas na página original da notícia (og:image / twitter:image).
Nunca associa fotos por tema ou por semelhança de título.
"""
import argparse
import html
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "noticias.json"

class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        a = dict(attrs)
        key = (a.get("property") or a.get("name") or "").lower()
        if key in ("og:image", "og:image:url", "twitter:image", "twitter:image:src"):
            self.meta.setdefault(key, html.unescape(a.get("content") or ""))

def valid(url):
    try:
        u = urlparse(url)
        h = (u.hostname or "").lower()
        return u.scheme == "https" and bool(h) and not (
            h == "news.google.com" or h.endswith(".google.com")
        )
    except (ValueError, TypeError):
        return False

def photo(url):
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; RadarApreensoes/1.0)"})
        with urlopen(req, timeout=12) as response:
            final = response.geturl()
            if not valid(final):
                return "", "redirecionamento_nao_original"
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                return "", "nao_html"
            data = response.read(350000).decode("utf-8", "replace")
        parser = MetaParser()
        parser.feed(data)
        for key in ("og:image", "og:image:url", "twitter:image", "twitter:image:src"):
            candidate = urljoin(final, parser.meta.get(key, ""))
            if valid(candidate) and candidate != final:
                return candidate, "foto_da_fonte"
        return "", "sem_metadados_de_imagem"
    except Exception as exc:
        return "", "erro_" + type(exc).__name__

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=60)
    args = ap.parse_args()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    rows = data.get("noticias") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise SystemExit("Formato de noticias.json inválido; arquivo preservado.")
    processed = saved = 0
    statuses = {}
    # Priorizamos notícias recentes com link direto, sem refazer tentativas infrutíferas.
    for row in rows:
        if processed >= max(0, args.limite):
            break
        if not isinstance(row, dict):
            continue
        if row.get("imagem_url") or row.get("foto_fonte_status"):
            continue
        url = row.get("url_original") or row.get("url") or ""
        if not valid(url):
            continue
        # Não tratar anexos como reportagens.
        if re.search(r"\\.(?:jpe?g|png|webp|gif|pdf)(?:/view)?(?:[?#]|$)", url, re.I):
            row["foto_fonte_status"] = "anexo_nao_reportagem"
            continue
        processed += 1
        found, status = photo(url)
        row["foto_fonte_status"] = status
        if found:
            row["imagem_url"] = found
            row["imagem_credito"] = row.get("fonte") or urlparse(url).hostname
            row["imagem_origem_pagina"] = url
            saved += 1
        statuses[status] = statuses.get(status, 0) + 1
        time.sleep(0.15)
    if processed:
        tmp = DATA.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(DATA)
    print(f"Fotos verificadas: {saved}/{processed} | {statuses} | Notícias preservadas: {len(rows)}", flush=True)

if __name__ == "__main__":
    main()
