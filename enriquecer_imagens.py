"""Enriquece noticias.json com imagens das páginas originais.
Uso: python enriquecer_imagens.py --limite 40
Sem dependências externas; preserva imagens existentes.
"""
import argparse
import html
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

HEADERS = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile Safari/604.1', 'Accept': 'text/html,application/xhtml+xml'}
URL_FIELDS = ('url_original', 'link_original', 'original_url', 'fonte_url', 'source_url', 'url_fonte', 'link_fonte', 'url', 'link')
IMAGE_FIELDS = ('imagem', 'imagem_url', 'image', 'image_url', 'thumbnail', 'foto', 'foto_url')

class ImageMeta(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.base = ''
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'base' and a.get('href'):
            self.base = a['href']
        if tag == 'meta':
            key = (a.get('property') or a.get('name') or a.get('itemprop') or '').lower()
            if key in ('og:image', 'og:image:url', 'twitter:image', 'twitter:image:src', 'image', 'thumbnailurl'):
                self.images.append(a.get('content', ''))
        if tag == 'link' and 'image_src' in a.get('rel', '').lower():
            self.images.append(a.get('href', ''))

def valid_url(url):
    try:
        p = urlsplit(str(url).strip())
        return p.scheme in ('http', 'https') and bool(p.hostname)
    except (ValueError, TypeError):
        return False

def google_news(url):
    host = (urlsplit(url).hostname or '').lower()
    return host == 'news.google.com' or host.endswith('.news.google.com')

def get_image(url, timeout):
    if not valid_url(url) or google_news(url):
        return '', 'link Google Notícias não resolvido'
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=timeout) as resp:
        if 'html' not in resp.headers.get('Content-Type', '').lower():
            return '', 'resposta não é HTML'
        page = resp.read(450000).decode('utf-8', 'replace')
        base = resp.geturl()
    parser = ImageMeta()
    parser.feed(page)
    base = urljoin(base, parser.base) if parser.base else base
    for candidate in parser.images:
        img = urljoin(base, html.unescape(candidate).strip())
        if valid_url(img) and not img.lower().startswith('data:'):
            return img, ''
    # Fallback para JSON-LD de notícias, sem usar imagens genéricas do site.
    for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page, re.I | re.S):
        try:
            obj = json.loads(html.unescape(match.group(1)))
            stack = [obj]
            while stack:
                item = stack.pop()
                if isinstance(item, list):
                    stack.extend(item)
                elif isinstance(item, dict):
                    typ = item.get('@type', '')
                    types = typ if isinstance(typ, list) else [typ]
                    if any(t in ('NewsArticle', 'Article', 'ReportageNewsArticle') for t in types):
                        image = item.get('image') or item.get('thumbnailUrl')
                        candidates = image if isinstance(image, list) else [image]
                        for c in candidates:
                            if isinstance(c, dict):
                                c = c.get('url') or c.get('contentUrl')
                            if isinstance(c, str):
                                img = urljoin(base, c)
                                if valid_url(img):
                                    return img, ''
                    stack.extend(v for v in item.values() if isinstance(v, (list, dict)))
        except (ValueError, TypeError):
            pass
    return '', 'página sem imagem de matéria identificável'

def extract_rows(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ('noticias', 'articles', 'artigos', 'items', 'resultados', 'dados'):
            if isinstance(data.get(key), list):
                return data[key]
        for value in data.values():
            if isinstance(value, list) and any(isinstance(x, dict) for x in value):
                return value
    raise ValueError('Formato de noticias.json não reconhecido. Verifique a estrutura do arquivo.')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limite', type=int, default=40)
    ap.add_argument('--timeout', type=int, default=10)
    args = ap.parse_args()
    path = Path(__file__).resolve().parent / 'noticias.json'
    if not path.exists():
        path = Path('noticias.json')
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = extract_rows(data)
    print(f'Notícias carregadas: {len(rows)}; formato: {type(data).__name__}', flush=True)
    consulted = found = already = missing = google = 0
    for n in rows:
        if not isinstance(n, dict):
            continue
        if any(isinstance(n.get(k), str) and n[k].strip() for k in IMAGE_FIELDS):
            already += 1
            continue
        urls = [n.get(k) for k in URL_FIELDS if isinstance(n.get(k), str) and valid_url(n[k])]
        url = next((u for u in urls if not google_news(u)), None)
        if not url:
            if urls:
                google += 1
            else:
                missing += 1
            continue
        if consulted >= max(args.limite, 0):
            break
        consulted += 1
        try:
            image, reason = get_image(url, args.timeout)
            if image:
                n['imagem_url'] = image
                found += 1
            else:
                print(f'[{consulted}] Sem imagem: {reason} | {url[:100]}', flush=True)
        except Exception as exc:
            print(f'[{consulted}] Falha na página: {type(exc).__name__}: {str(exc)[:100]}', flush=True)
        time.sleep(0.2)
    if found:
        temp = path.with_name(path.name + '.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(path)
    print(f'Páginas consultadas: {consulted}; imagens encontradas: {found}; já com imagem: {already}; links Google não resolvidos: {google}; sem URL: {missing}', flush=True)
    if not consulted:
        print('ATENÇÃO: nenhuma página original disponível para consulta. Verifique o passo de recuperação dos links e os campos do noticias.json.', flush=True)

if __name__ == '__main__':
    main()
