#!/usr/bin/env python3
"""Coleta incremental de publicações oficiais (2020+), sem excluir notícias antigas.
Usa apenas biblioteca padrão; coleta páginas diretamente, não Google News.
"""
import argparse
import datetime as dt
import html
import json
import re
import time
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'noticias.json'
REPORT = ROOT / 'cobertura_historica.json'
NOW = dt.datetime.now(dt.timezone.utc)
MONTHS = ('janeiro','fevereiro','marco','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro')
KEY = re.compile(r'\b(apreend\w*|apreens\w*|retid\w*|ret[eé]m|localiz\w*|flagrante|contrabando|descaminho)\b',re.I)
OBJECT = re.compile(r'\b(drogas?|maconha|coca[ií]na|crack|haxixe|entorpecentes?|cigarros?|armas?|muni[cç][oõ]es|ve[ií]culos?|carros?|caminh[oõ]es|motocicletas?|celulares?|mercadorias?|medicamentos?|anabolizantes?|dinheiro|reais|d[oó]lares|ouro|madeira|animais?|pescado|eletr[oô]nicos?|coca[ií]na|cannabis|toneladas?|quilos?|kg|litros?|sementes?)\b',re.I)
BAD = re.compile(r'\b(mandados? de busca e apreens[aã]o|busca e apreens[aã]o judicial)\b',re.I)

class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.href=None; self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a': self.href=dict(attrs).get('href'); self.text=[]
    def handle_data(self,data):
        if self.href is not None: self.text.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.href:
            title=' '.join(''.join(self.text).split())
            if title: self.links.append((self.href,title))
            self.href=None; self.text=[]

def get(url, timeout=13):
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; RadarApreensoes/1.0; pesquisa publica)'})
    with urlopen(req,timeout=timeout) as response:
        if 'text/html' not in response.headers.get('Content-Type','text/html').lower(): return ''
        return response.read(750000).decode('utf-8','replace')

def valid(url, source, year):
    p=urlparse(url); path=p.path.lower(); host=(p.hostname or '').lower()
    if host!='www.gov.br': return False
    if source=='Polícia Federal':
        return bool(re.search(r'/pf/pt-br/assuntos/noticias/'+str(year)+r'/\d{2}/[^/]+$',path))
    return bool(re.search(r'/receitafederal/pt-br/assuntos/noticias/'+str(year)+r'/[^/]+/[^/]+$',path)) and not path.endswith('/view')

def pages(year, month):
    # Arquivos PF mensais; Receita possui estrutura anual/mensal variável.
    return [
      ('Polícia Federal',f'https://www.gov.br/pf/pt-br/assuntos/noticias/{year}/{month:02d}'),
      ('Receita Federal',f'https://www.gov.br/receitafederal/pt-br/assuntos/noticias/{year}/{MONTHS[month-1]}'),
    ]

def published(page):
    for pattern in [r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)',r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time']:
        m=re.search(pattern,page,re.I)
        if m:
            try: return dt.datetime.fromisoformat(m.group(1).replace('Z','+00:00')).isoformat()
            except ValueError: pass
    m=re.search(r'Publicado em\s*(\d{2}/\d{2}/\d{4})\s*(\d{2}h\d{2})?',re.sub(r'<[^>]+>',' ',page),re.I)
    if m:
        try:
            date=dt.datetime.strptime(m.group(1),'%d/%m/%Y').date()
            if m.group(2): return date.isoformat()+'T'+m.group(2).replace('h',':')+':00-03:00'
            return date.isoformat()
        except ValueError: pass
    return ''

def collect(years, max_pages):
    if DATA.exists():
        original=json.loads(DATA.read_text(encoding='utf-8'))
        rows=original.get('noticias') if isinstance(original,dict) else original
        if not isinstance(rows,list): raise ValueError('noticias.json em formato inesperado; preservado')
    else: original={'noticias':[]};rows=original['noticias']
    initial=len(rows)
    known={r.get('url_original') or r.get('url') for r in rows if isinstance(r,dict)}
    totals=Counter(); failures=[]; candidates=[]; seen=set()
    for year in years:
      for month in range(1,13):
       if (year,month)>(NOW.year,NOW.month): continue
       for source,base in pages(year,month):
        # A paginação Plone usa b_start:int, quando disponível.
        for offset in range(max_pages):
         url=base+(f'?b_start%3Aint={offset*20}' if offset else '')
         try: page=get(url)
         except Exception as e:
          failures.append({'fonte':source,'ano':year,'mes':month,'erro':type(e).__name__})
          break
         parser=Anchors();parser.feed(page)
         links=[]
         for href,title in parser.links:
          target=urljoin(base,html.unescape(href)).split('#')[0]
          if not valid(target,source,year):continue
          if not (KEY.search(title) and OBJECT.search(title)): continue
          if BAD.search(title) and not OBJECT.search(title.replace('busca e apreensão','')):continue
          if target not in seen:links.append((target,title));seen.add(target)
         totals[f'{year}_paginas']+=1
         if not links and offset:break
         for target,title in links:
          totals[f'{year}_candidatas']+=1
          if target not in known:
           candidates.append((year,source,target,title))
         if len(parser.links)<8:break
         time.sleep(.12)
    for year,source,url,title in candidates:
      try:
       page=get(url)
       date=published(page)
      except Exception: date=''
      if date and date[:4]!=str(year):
       # Evitar registrar notícia fora do ano do arquivo consultado.
       continue
      row={'titulo':title,'url':url,'url_original':url,'url_original_status':'fonte_direta_oficial',
           'fonte':source,'origem_coleta':'arquivo_oficial_direto','data_iso':date,
           'data_publicacao':date,'leitura_fonte_status':'pendente_leitura_original',
           'ano_arquivo_fonte':year}
      rows.append(row);known.add(url);totals[f'{year}_adicionadas']+=1
      time.sleep(.08)
    if isinstance(original,dict):
        original['noticias']=rows;original['total']=len(rows);original['atualizado_em']=NOW.isoformat()
    tmp=DATA.with_suffix('.json.tmp');tmp.write_text(json.dumps(original,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(DATA)
    distribution=Counter()
    for r in rows:
      if not isinstance(r,dict):continue
      date=str(r.get('data_iso') or r.get('data_publicacao') or r.get('data') or '')
      m=re.search(r'(?<!\\d)(20(?:2\\d|3\\d))(?!\\d)',date)
      if m and int(m.group(1))>=2020:
       pass

    for r in rows:
      if not isinstance(r,dict):continue
      date=str(r.get('data_iso') or r.get('data_publicacao') or '')
      m=re.search(r'20(?:2\d|3\d)',date)
      if m:distribution[m.group(0)]+=1
      else:distribution['sem_data']+=1
    report={'atualizado_em':NOW.isoformat(),'periodo_solicitado':'2020-'+str(NOW.year),
            'acervo_antes':initial,'acervo_depois':len(rows),'adicionadas_nesta_execucao':len(rows)-initial,
            'por_ano_data_publicacao':dict(sorted(distribution.items())),
            'contagens_da_coleta':dict(sorted(totals.items())),
            'falhas_de_acesso_amostra':failures[:30], 'total_falhas_acesso':len(failures),
            'aviso':'Cobertura parcial: arquivos indisponíveis e publicações não indexadas não são contabilizados; ano da publicação não é necessariamente ano da ocorrência.'}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Acervo preservado:',initial,'->',len(rows),'| Novas diretas:',len(rows)-initial)
    print('Distribuição por ano:',report['por_ano_data_publicacao'])
    print('Falhas de acesso:',len(failures))

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--todos-anos',action='store_true')
    ap.add_argument('--ano',type=int)
    ap.add_argument('--paginas',type=int,default=2,help='Páginas por mês e fonte')
    args=ap.parse_args()
    if args.ano and not 2020<=args.ano<=NOW.year:ap.error('Ano fora de 2020 até o ano atual')
    years=[args.ano] if args.ano else (list(range(2020,NOW.year+1)) if args.todos_anos else [NOW.year])
    collect(years,max(1,min(args.paginas,8)))
