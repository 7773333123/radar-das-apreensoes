#!/usr/bin/env python3
"""Radar das Apreensões — classificação múltipla auditável.
Lê e atualiza noticias.json, gera analise_nacional.json. Usa apenas biblioteca padrão.
A leitura externa é opcional, limitada, e pode falhar (paywall, robots, Google News).
"""
import argparse
import collections
import datetime as dt
import html
from html.parser import HTMLParser
import json
import re
import time
import ipaddress
import socket
import unicodedata
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from email.utils import parsedate_to_datetime

BASE = Path(__file__).resolve().parent
UFS = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())
PATTERNS = {
 'Drogas e entorpecentes': [r'\bcocain',r'\bmaconha',r'\bcrack\b',r'\bhaxixe',r'\bentorpecent',r'\bmetanfetamin',r'\becstasy',r'\bskunk',r'\bcannabis',r'\bheroina',r'\bketamina',r'\bdrogas?\b',r'\btrafico de drogas?\b',r'\bporcoes? de (?:cocaina|maconha|crack)\b',r'\bsubstancias? entorpecentes?\b'],
 'Armas e munições': [r'\bfuzis?\b',r'\bpistolas?\b',r'\brevolver',r'\bespingard',r'\bmunic',r'\bcartuchos?\b',r'\barmas?\b',r'\barmas? de fogo\b',r'\bexplosivos?\b',r'\barmamento',r'\bcalibre\s*(?:9\s*mm|12|38|40|380)\b'],
 'Contrabando e descaminho': [r'\bcontraband',r'\bdescaminho',r'\bcigarros?\b',r'\bmercadorias? sem nota',r'\bmercadorias? irregulares?',r'\bimportac[aã]o irregular',r'\bprodutos? contrabandead'],
 'Veículos': [r'\bveiculos? apreendid',r'\bcarros? apreendid',r'\bautomoveis? apreendid',r'\bcaminh(?:ao|oes) apreendid',r'\bmotociclet\w* apreendid',r'\bembarcac\w* apreendid',r'\baeronave\w* apreendid',r'\bveiculos? roubad',r'\bveiculos? recuperad',r'\b(?:apreendid|recuperad|retid)\w*[^.!?]{0,45}\b(?:veiculos?|carros?|motos?|caminhoes?|embarcacoes?)\b'],
 'Dinheiro e valores': [r'\bdinheiro apreendid',r'\b(?:apreendid\w*|confiscad\w*|retid\w*)\s+(?:r\$\s*)?\d+[\d.,]*\s*(?:mil|milhoes?)?\s*(?:reais|em dinheiro)',r'\br\$\s*\d+[\d.,]*\s*(?:mil|milhoes?)?\s*(?:apreendid\w*|confiscad\w*)',r'\bvalores? apreendid',r'\bquantia em especie',r'\bnumerario',r'\bcedulas? apreendid',r'\bouro apreendid',r'\bjoias? apreendid',r'\breais? em especie',r'\b(?:dinheiro|cedulas?|numerario)\b[^.!?]{0,55}\b(?:apreendid|confiscad|retid)\w*'],
 'Crimes ambientais': [r'\bmadeira ilegal',r'\bmadeira apreendid',r'\banimais? silvestres?',r'\bfauna silvestre',r'\bpesca ilegal',r'\bpescado apreendid',r'\bminerio apreendid',r'\bgarimpo ilegal',r'\bdesmatamento ilegal',r'\baves? silvestres?',r'\b(?:apreendid|resgatad)\w*[^.!?]{0,45}\b(?:madeira|animais?|pescado|aves?)\b'],
 'Medicamentos e produtos': [r'\bmedicamentos? irregulares?',r'\bcanetas? emagrecedoras?',r'\bmedicamentos? apreendid',r'\bremedios? apreendid',r'\banabolizantes?',r'\bprodutos? falsificad',r'\bprodutos? proibid',r'\bcosmeticos? irregulares?'],
 'Operações patrimoniais': [r'\bbloqueio de bens',r'\bbens bloqueados?',r'\bsequestro de bens',r'\bindisponibilidade de bens',r'\bconfisco de bens',r'\bbens sequestrados?',r'\bbloqueio judicial de',r'\bbens confiscados?'],
}
OTHER = 'Outras apreensões'
UNCLASSIFIED = 'Não classificada'
LEGACY = {
 'drogas':'Drogas e entorpecentes', 'entorpecentes':'Drogas e entorpecentes',
 'armas':'Armas e munições', 'municoes':'Armas e munições',
 'contrabando':'Contrabando e descaminho', 'descaminho':'Contrabando e descaminho',
 'veiculos':'Veículos', 'dinheiro':'Dinheiro e valores',
 'ambiental':'Crimes ambientais', 'meio ambiente':'Crimes ambientais',
 'medicamentos':'Medicamentos e produtos', 'patrimonial':'Operações patrimoniais'
}



def fold(s):
 return ''.join(c for c in unicodedata.normalize('NFD',str(s or '').lower()) if unicodedata.category(c)!='Mn')


def date_of(n):
 for key in ('data_iso','data_publicacao','data','date'):
  v=str(n.get(key) or '').strip()
  if not v: continue
  try: return dt.date.fromisoformat(v[:10])
  except ValueError: pass
  try: return parsedate_to_datetime(v).date()
  except (ValueError,TypeError,OverflowError,IndexError): pass
  try: return dt.datetime.strptime(v[:10],'%d/%m/%Y').date()
  except ValueError: pass
 return None


class PageText(HTMLParser):
 """Extrai parágrafos de article/main e metadados sem misturar menus."""
 def __init__(self):
  super().__init__(convert_charrefs=True)
  self.parts=[];self.focus=[];self.meta=[];self.title=[]
  self.stack=[];self.hidden=0;self.article_depth=0;self.title_depth=0
  self.jsonld=[];self.in_jsonld=False
 def handle_starttag(self,tag,attrs):
  d=dict(attrs);tag=tag.lower()
  if tag=='meta':
   name=(d.get('name') or d.get('property') or '').lower()
   if name in ('description','og:description','twitter:description'):
    self.meta.append(d.get('content',''))
  if tag=='script' and d.get('type','').lower()=='application/ld+json':
   self.in_jsonld=True;self.jsonld.append('');return
  if tag in ('script','style','nav','footer','header','aside','noscript','svg','form'):
   self.hidden+=1
  if tag in ('article','main'):self.article_depth+=1
  if tag=='title':self.title_depth+=1
  self.stack.append(tag)
 def handle_endtag(self,tag):
  tag=tag.lower()
  if tag=='script' and self.in_jsonld:self.in_jsonld=False;return
  if tag in self.stack:
   # Recover from malformed HTML; decrement only elements actually popped.
   idx=len(self.stack)-1-self.stack[::-1].index(tag)
   for t in self.stack[idx:]:
    if t in ('script','style','nav','footer','header','aside','noscript','svg','form'):self.hidden=max(0,self.hidden-1)
    if t in ('article','main'):self.article_depth=max(0,self.article_depth-1)
    if t=='title':self.title_depth=max(0,self.title_depth-1)
   self.stack=self.stack[:idx]
 def handle_data(self,data):
  if self.in_jsonld:
   self.jsonld[-1]+=data;return
  if self.title_depth:self.title.append(data.strip())
  if self.hidden or len(data.strip())<3:return
  data=' '.join(data.split())
  self.parts.append(data)
  if self.article_depth:self.focus.append(data)
 def article_text(self):
  candidates=[' '.join(self.focus),' '.join(self.parts)]
  for raw in self.jsonld:
   try: obj=json.loads(raw)
   except (ValueError,TypeError):continue
   def visit(o,depth=0):
    if depth>10:return
    if isinstance(o,list):
     for v in o:yield from visit(v,depth+1)
    elif isinstance(o,dict):
     if isinstance(o.get('articleBody'),str):yield o['articleBody']
     for v in o.values():yield from visit(v,depth+1)
   candidates.extend(visit(obj))
  # Prefer actual article body; a page's navigation text is not a full article.
  candidates.sort(key=len,reverse=True)
  body=max((c for c in candidates if len(c)>=30),key=len,default='')
  return ' '.join(x for x in (' '.join(self.title),' '.join(self.meta),body) if x).strip()


def fetch_article(url,timeout=8):
 """Reads public HTML; returns text and an auditable failure reason."""
 from urllib.error import HTTPError, URLError
 try:
  u=urlparse(url)
  if u.scheme not in ('https','http') or not u.hostname:return '', 'url_invalida'
  host=u.hostname.lower()
  if host in ('localhost','0.0.0.0') or host.endswith(('.local','.internal')):return '', 'url_restrita'
  try:
   addresses=socket.getaddrinfo(host,None)
   if any(not ipaddress.ip_address(addr[4][0]).is_global for addr in addresses):return '', 'url_restrita'
  except OSError:return '', 'falha_dns'
  req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0; news research)','Accept':'text/html,application/xhtml+xml','Accept-Language':'pt-BR,pt;q=0.9','Accept-Encoding':'identity'})
  with urlopen(req,timeout=timeout) as response:
   final=urlparse(response.geturl())
   if final.scheme not in ('http','https') or not final.hostname:return '', 'redirecionamento_invalido'
   # Never read a redirected private network destination.
   try:
    ips=socket.getaddrinfo(final.hostname,None)
    if any(not ipaddress.ip_address(addr[4][0]).is_global for addr in ips):return '', 'url_restrita'
   except OSError:return '', 'falha_dns'
   if 'html' not in response.headers.get('Content-Type','').lower():return '', 'nao_html'
   data=response.read(750_000)
   charset=response.headers.get_content_charset() or 'utf-8'
   page=PageText();page.feed(data.decode(charset,errors='replace'))
   txt=page.article_text()
   if len(txt)<100:return '', 'texto_insuficiente'
   f=fold(txt[:1500])
   if any(term in f for term in ('enable javascript','habilite o javascript','access denied','acesso negado','verify you are human','captcha')) and len(txt)<1000:
    return '', 'bloqueio_ou_javascript'
   return txt[:50000], 'lida'
 except HTTPError as e:return '', f'http_{e.code}'
 except (TimeoutError,URLError) as e:return '', 'erro_rede_ou_timeout'
 except (UnicodeError,ValueError):return '', 'erro_conteudo'
 except Exception:return '', 'erro_inesperado'


def previous_labels(n):
 out=[]
 for v in (n.get('categorias_identificadas') or []):
  if v in PATTERNS or v==OTHER:
   if v not in out:out.append(v)
 for key in ('categoria','categorias','cat'):
  v=n.get(key,[])
  if isinstance(v,str):v=[v]
  if not isinstance(v,list):continue
  for label in v:
   mapped=LEGACY.get(fold(label),label if label in PATTERNS else None)
   if mapped and mapped not in out:out.append(mapped)
 return out

def combined_labels(old,new):
 specific=list(dict.fromkeys(x for x in old+new if x in PATTERNS))
 if specific:return specific
 return [OTHER] if OTHER in old+new else [UNCLASSIFIED]

def evidence_text(n):
 # Full article is used when available; do not silently discard existing source text.
 return ' '.join(str(n.get(k) or '') for k in
  ('titulo','t','descricao','resumo','desc','texto_completo','conteudo','texto_analisado_resumo'))

def classify(text):
 f=fold(text)
 labels=[]; evidence={}
 for label,patterns in PATTERNS.items():
  found=[]
  for p in patterns:
   m=re.search(p,f)
   if m: found.append(f[max(0,m.start()-70):min(len(f),m.end()+100)].strip())
  if found:labels.append(label);evidence[label]=found[:2]
 if not labels:
  if re.search(r'\b(?:objetos?|materiais?|mercadorias?|produtos?|bens?|cargas?)\b.{0,60}\b(?:apreendid|confiscad)|\b(?:apreend|confisc)\w*.{0,60}\b(?:objetos?|materiais?|mercadorias?|produtos?|bens?|cargas?)\b',f):labels=[OTHER]
  else:labels=[UNCLASSIFIED]
 return labels,evidence


# Extracao conservadora: quantidade e objeto devem estar na mesma expressao.
# Não converte "toneladas" para kg na evidência; agrega em kg apenas quando a unidade é inequívoca.
MATERIAIS = {
 'cocaina': ('Drogas e entorpecentes','Cocaína','massa'),
 'maconha': ('Drogas e entorpecentes','Maconha','massa'),
 'crack': ('Drogas e entorpecentes','Crack','massa'),
 'skunk': ('Drogas e entorpecentes','Skunk','massa'),
 'fuzil': ('Armas e munições','Fuzis','unidade'),
 'fuzis': ('Armas e munições','Fuzis','unidade'),
 'pistola': ('Armas e munições','Pistolas','unidade'),
 'pistolas': ('Armas e munições','Pistolas','unidade'),
 'revolver': ('Armas e munições','Revólveres','unidade'),
 'revolveres': ('Armas e munições','Revólveres','unidade'),
 'municao': ('Armas e munições','Munições','unidade'),
 'municoes': ('Armas e munições','Munições','unidade'),
 'cartucho': ('Armas e munições','Cartuchos','unidade'),
 'cartuchos': ('Armas e munições','Cartuchos','unidade'),
 'veiculo': ('Veículos','Veículos','unidade'),
 'veiculos': ('Veículos','Veículos','unidade'),
 'carro': ('Veículos','Carros','unidade'),
 'carros': ('Veículos','Carros','unidade'),
 'motocicleta': ('Veículos','Motocicletas','unidade'),
 'motocicletas': ('Veículos','Motocicletas','unidade'),
 'caminhao': ('Veículos','Caminhões','unidade'),
 'caminhoes': ('Veículos','Caminhões','unidade'),
 'cigarro': ('Contrabando e descaminho','Cigarros','unidade'),
 'cigarros': ('Contrabando e descaminho','Cigarros','unidade'),
 'macos': ('Contrabando e descaminho','Maços de cigarros','unidade'),
 'maco': ('Contrabando e descaminho','Maços de cigarros','unidade'),
 'madeira': ('Crimes ambientais','Madeira','volume'),
 'pescado': ('Crimes ambientais','Pescado','massa'),
 'medicamentos': ('Medicamentos e produtos','Medicamentos','unidade'),
 'comprimidos': ('Medicamentos e produtos','Comprimidos','unidade'),
}
NUMBER = r'(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[,.]\d+)?)'
UNIT = r'(?:quilogramas?|quilos?|kg|gramas?|g|toneladas?|ton\.?|litros?|l|m(?:etros?)?\s*(?:cubicos?|c[uú]bicos?)|m[³3]|unidades?|mil|milh(?:ao|oes)|bilh(?:ao|oes))'
ITEM = r'(?:cocaina|maconha|crack|skunk|fuzis?|pistolas?|revolveres?|municoes?|cartuchos?|veiculos?|carros?|motocicletas?|caminhoes?|cigarros?|macos?|madeira|pescado|medicamentos?|comprimidos?)'
PAT_QUANT = re.compile(r'(?<!\w)('+NUMBER+r')\s*('+UNIT+r')?\s*(?:de\s+)?('+ITEM+r')\b',re.I)
PAT_MONEY = re.compile(r'\bR\$\s*('+NUMBER+r')\s*(milhoes?|milhao|bilhoes?|bilhao|mil)?\b',re.I)

def number_value(raw):
 raw=raw.strip()
 if '.' in raw and ',' in raw:raw=raw.replace('.','').replace(',','.')
 elif ',' in raw:raw=raw.replace(',','.')
 elif raw.count('.')>1 or ('.' in raw and len(raw.split('.')[-1])==3):raw=raw.replace('.','')
 try:return float(raw)
 except ValueError:return None

def quantificar(texto):
 """Somente pares quantidade-material explícitos; não estima valores ausentes."""
 normalized=fold(texto)
 records=[];seen=set()
 for m in PAT_QUANT.finditer(normalized):
  val=number_value(m.group(1));un=(m.group(2) or '').strip();item=m.group(3)
  if val is None or val<=0:continue
  categoria,nome,tipo=MATERIAIS[item]
  if un in ('mil','milhao','milhoes','bilhao','bilhoes'):
   val*= {'mil':1000,'milhao':1e6,'milhoes':1e6,'bilhao':1e9,'bilhoes':1e9}[un];un=''
  if tipo=='massa':
   if un in ('kg','quilo','quilos','quilograma','quilogramas'):val*=1;unidade='kg'
   elif un in ('ton','ton.','tonelada','toneladas'):val*=1000;unidade='kg'
   elif un in ('g','grama','gramas'):val/=1000;unidade='kg'
   else:continue
  elif tipo=='volume':
   if re.fullmatch(r'm(?:etros?)?\s*(?:cubicos?)|m[³3]',un):unidade='m³'
   else:continue
  else:
   if un and un not in ('unidade','unidades'):continue
   if val!=int(val):continue
   unidade='unidades'
  evidence=texto[max(0,m.start()-45):min(len(texto),m.end()+55)].strip()
  key=(nome,unidade,val)
  if key in seen:continue
  seen.add(key)
  records.append({'categoria':categoria,'material':nome,'quantidade':int(val) if val.is_integer() else round(val,4),'unidade':unidade,'evidencia':evidence,'metodo':'expressao_explicita','verificacao':'automatica_pendente_revisao'})
 for m in PAT_MONEY.finditer(normalized):
  val=number_value(m.group(1));mult=(m.group(2) or '')
  # Exige vínculo textual claro entre o valor e sua apreensão/bloqueio.
  # Dívida, prejuízo, faturamento e estimativa não equivalem a dinheiro apreendido.
  before=normalized[max(0,m.start()-85):m.start()]
  after=normalized[m.end():min(len(normalized),m.end()+65)]
  before=before.split(';')[-1].split('.')[-1]
  after=after.split(';')[0].split('.')[0]
  action=r'(?:apreend\w*|apreens\w*|confiscad\w*|bloquead\w*|sequestrad\w*|retid\w*)'
  nearby=bool(re.search(action+r'[^.!?;]{0,65}$',before) or re.match(r'[^.!?;]{0,40}'+action,after))
  bad=r'\b(?:divida|prejuizo|faturamento|avaliad[oa]s?|estimad[oa]s?|propina|indenizacao|movimentad[oa]s?)\b'
  if not nearby or re.search(bad,before[-45:]+' '+after[:45]):continue
  if val is None or val<=0:continue
  val*= {'':1,'mil':1000,'milhao':1e6,'milhoes':1e6,'bilhao':1e9,'bilhoes':1e9}[mult]
  evidence=texto[max(0,m.start()-45):min(len(texto),m.end()+55)].strip()
  key=('Dinheiro em reais','BRL',val)
  if key in seen:continue
  seen.add(key)
  records.append({'categoria':'Dinheiro e valores','material':'Dinheiro em reais','quantidade':round(val,2),'unidade':'BRL','evidencia':evidence,'metodo':'expressao_explicita','verificacao':'automatica_pendente_revisao'})
 return records

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--max-leituras',type=int,default=150,help='Limite de matérias externas por execução (padrão: 150)')
 ap.add_argument('--repetir-leituras',action='store_true',help='Tentar novamente links anteriormente indisponíveis')
 ap.add_argument('--sem-web',action='store_true',help='Somente texto já armazenado')
 args=ap.parse_args()
 path=BASE/'noticias.json'
 raw=json.loads(path.read_text(encoding='utf-8'))
 items=raw if isinstance(raw,list) else raw.get('noticias',[])
 if not isinstance(items,list):raise SystemExit('Formato inesperado de noticias.json')
 counts=collections.Counter();quant_status=collections.Counter();multi=0;states=collections.Counter();months=collections.Counter();years=collections.Counter();sources=set();missing_date=0;read_count=0;read_status=collections.Counter();details=[];pending=0;review=collections.Counter();quant_totals=collections.defaultdict(float);quant_count=0
 for n in items:
  if not isinstance(n,dict):continue
  title=str(n.get('titulo') or n.get('t') or '')
  desc=str(n.get('descricao') or n.get('resumo') or n.get('desc') or '')
  stored=str(n.get('texto_completo') or n.get('conteudo') or n.get('texto_analisado_resumo') or '')
  labels,evidence=classify(evidence_text(n))
  labels=combined_labels(previous_labels(n),labels)
  status='dados_existentes'
  # Consulta uma única vez por execução apenas notícias sem categoria específica.
  # Reprocessa categorias a cada rodada; não sobrescreve dados originais.
  if labels in ([UNCLASSIFIED],[OTHER]) and not args.sem_web and read_count<max(0,args.max_leituras) and (args.repetir_leituras or n.get('leitura_fonte_versao')!='extrator_v2'):
   url=str(n.get('url') or n.get('link') or '')
   if url:
    read_count+=1
    content,status=fetch_article(url)
    read_status[status]+=1
    n['leitura_fonte_versao']='extrator_v2'
    if content:
     new_labels,evidence=classify(' '.join((title,desc,content)))
     labels=combined_labels(labels,new_labels)
     if labels not in ([UNCLASSIFIED],[OTHER]):
      n['texto_analisado_resumo']=content[:20000]
      n['leitura_fonte_status']='lida'
     else:
      n['texto_analisado_resumo']=content[:20000]
      n['leitura_fonte_status']='sem_evidencia_especifica'
    else:n['leitura_fonte_status']=status
  # Extrai quantidades apenas do texto efetivamente disponível; sem extrapolação.
  texto_quant=' '.join(dict.fromkeys(x for x in (title,desc,stored) if x))
  if n.get('texto_analisado_resumo') and n['texto_analisado_resumo'] not in texto_quant:texto_quant+=' '+str(n['texto_analisado_resumo'])
  registros=quantificar(texto_quant)
  # Indicador independente da categoria: não quantificada não significa fora do escopo.
  # O marcador é aplicado somente a matérias com categoria de apreensão identificada.
  # Notícias sem evidência permanecem pendentes de verificação.
  tem_categoria_apreensao = any(x in PATTERNS or x == OTHER for x in labels)
  if registros:
   situacao_quantitativa = 'com_informacao_quantitativa'
  elif tem_categoria_apreensao:
   situacao_quantitativa = 'materia_sem_informacao_quantitativa'
  else:
   situacao_quantitativa = 'pendente_verificacao_apreensao'
  n['situacao_quantitativa'] = situacao_quantitativa
  n['materia_sem_informacao_quantitativa'] = situacao_quantitativa == 'materia_sem_informacao_quantitativa'
  n['itens_quantificados']=registros
  quant_count+=len(registros)
  for registro in registros:
   quant_totals[(registro['categoria'],registro['material'],registro['unidade'])]+=registro['quantidade']
   if registro['categoria'] not in labels:
    labels=[x for x in labels if x not in (UNCLASSIFIED,OTHER)]+[registro['categoria']]
  # Reavalia após incluir categorias comprovadas pelos registros quantitativos.
  if registros:
   n['situacao_quantitativa'] = 'com_informacao_quantitativa'
  elif any(x in PATTERNS or x == OTHER for x in labels):
   n['situacao_quantitativa'] = 'materia_sem_informacao_quantitativa'
  else:
   n['situacao_quantitativa'] = 'pendente_verificacao_apreensao'
  n['materia_sem_informacao_quantitativa'] = n['situacao_quantitativa'] == 'materia_sem_informacao_quantitativa'
  quant_status[n['situacao_quantitativa']] += 1
  # Não converte notícias genéricas em apreensões comprovadas.
  if len([x for x in labels if x in PATTERNS])>1:multi+=1
  n['categorias_identificadas']=labels
  n['status_revisao']='pendente_evidencia' if labels==[UNCLASSIFIED] else ('outras_apreensoes_a_revisar' if labels==[OTHER] else 'classificacao_automatica')
  review[n['status_revisao']]+=1
  previous_evidence=n.get('evidencias_classificacao') or {}
  if isinstance(previous_evidence,dict):
   for key,excerpts in previous_evidence.items():
    if key in labels and key not in evidence:evidence[key]=excerpts
  n['evidencias_classificacao']=evidence
  n['metodo_classificacao']='regras_textuais_com_leitura_opcional'
  n['revisao_humana_recomendada']=True
  if labels==[UNCLASSIFIED]:pending+=1
  for label in labels:
   if label!=UNCLASSIFIED:counts[label]+=1
  uf=str(n.get('uf') or n.get('estado') or '').upper().strip()
  if uf in UFS:states[uf]+=1
  d=date_of(n)
  if d:months[d.strftime('%Y-%m')]+=1;years[str(d.year)]+=1
  else:missing_date+=1
  source=str(n.get('fonte') or n.get('source') or '').strip()
  if source:sources.add(source)
  details.append({'url':n.get('url') or n.get('link'),'categorias_sugeridas':labels,'evidencias':evidence,'leitura_fonte_status':n.get('leitura_fonte_status','nao_necessaria')})
 result={'gerado_em_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
 'metodologia':'Regras textuais e leitura opcional de HTML público. Não utiliza IA generativa. Uma notícia pode ter várias categorias. Ausência de quantidade não exclui a notícia.',
 'aviso':'Contagens de notícias, NÃO de operações únicas. Notícias sem evidência não são exibidas como categoria pública. Categorias se sobrepõem; quantidades são preliminares.',
 'situacao_quantitativa':dict(quant_status),
 'materias_sem_informacao_quantitativa':quant_status['materia_sem_informacao_quantitativa'],
 'nota_situacao_quantitativa':'Sem informação quantitativa: notícia classificada em tema de apreensão, sem quantidade explícita extraída. Não significa fora do escopo nem quantidade zero. Pendentes de evidência são contabilizadas separadamente.',
 'noticias_multicategoria':multi,'noticias_com_quantidades':sum(bool(n.get('itens_quantificados')) for n in items if isinstance(n,dict)),'noticias_analisadas':len(details),'fontes_distintas_informadas':len(sources),
 'noticias_por_categoria':dict(counts.most_common()),'noticias_por_uf_explicita':dict(states.most_common()),
 'noticias_por_mes':dict(sorted(months.items())),'noticias_por_ano':dict(sorted(years.items())),
 'status_processamento':dict(review),'status_leitura_fonte':dict(collections.Counter(str(n.get('leitura_fonte_status') or 'nao_tentada') for n in items if isinstance(n,dict))),'noticias_sem_data_valida':missing_date,'noticias_sem_classificacao':pending,'noticias_pendentes_revisao':pending,
 'versao_extrator':'extrator_v2','leituras_externas_tentadas':read_count,'resultados_leituras_externas':dict(read_status),'classificacoes':details,
 'quantificacao':{'itens_extraidos':quant_count,'totais_preliminares':[{'categoria':k[0],'material':k[1],'unidade':k[2],'quantidade':round(v,4)} for k,v in sorted(quant_totals.items())], 'aviso':'Totais preliminares por notícia, sem deduplicação entre matérias sobre a mesma operação. Não são totais oficiais; requerem revisão.'}}
 # Gera arquivos temporários e substitui somente depois de concluir o processamento.
 out=BASE/'analise_nacional.json'
 ptmp=path.with_suffix('.json.tmp');otmp=out.with_suffix('.json.tmp')
 ptmp.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
 otmp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 ptmp.replace(path);otmp.replace(out)
 print(f'Analisadas {len(details)} notícias; {pending} não classificadas; {multi} multicategoria; {quant_count} registros quantitativos; {read_count} leituras externas tentadas; acessos: {dict(read_status)}; revisão: {dict(review)}.')

if __name__=='__main__':main()
