"""Enriquece noticias.json com imagens reais declaradas na página original.
Uso: python enriquecer_imagens.py --limite 40
Sem dependências externas. Não substitui imagens existentes.
"""
import argparse, json, re, html, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlsplit
from html.parser import HTMLParser

class Meta(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'meta': return
        a=dict(attrs); key=(a.get('property') or a.get('name') or '').lower()
        if key in ('og:image','og:image:url','twitter:image','twitter:image:src'):
            self.tags.append(a.get('content',''))

def imagem_pagina(url):
    u=urlsplit(url)
    if u.scheme not in ('http','https') or not u.hostname or u.hostname.endswith('google.com'): return ''
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0)'})
    with urlopen(req,timeout=10) as resp:
        if 'text/html' not in resp.headers.get('Content-Type',''): return ''
        page=resp.read(250000).decode('utf-8','replace')
        base=resp.geturl()
    parser=Meta(); parser.feed(page)
    for candidate in parser.tags:
        img=urljoin(base,html.unescape(candidate).strip())
        if urlsplit(img).scheme in ('https','http') and urlsplit(img).hostname:
            return img
    return ''

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--limite',type=int,default=40)
    args=ap.parse_args()
    p=Path('noticias.json')
    data=json.loads(p.read_text(encoding='utf-8'))
    rows=data if isinstance(data,list) else data.get('noticias',[])
    checked=found=0
    for n in rows:
        if checked>=max(0,args.limite):break
        if n.get('imagem') or n.get('imagem_url'):continue
        url=n.get('url_original') or n.get('url') or ''
        host=urlsplit(url).hostname or ''
        if not url or not host or host=='news.google.com':continue
        checked+=1
        try:
            img=imagem_pagina(url)
            if img:n['imagem_url']=img;found+=1
        except Exception as exc:print('Imagem indisponível:',str(exc)[:100])
        time.sleep(.3)
    if found:
        temp=p.with_suffix('.json.tmp')
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(p)
    print(f'Páginas consultadas: {checked}; imagens encontradas: {found}')
if __name__=='__main__':main()
