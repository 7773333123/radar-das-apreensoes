"""Radar das Apreensões: coleta incremental e busca histórica opcional.

Uso:
  python coletor.py
  python coletor.py --historico --ano 2020
"""
import argparse
import json
import re
import unicodedata
from difflib import SequenceMatcher
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ARQUIVO = Path('noticias.json')
BASE = 'https://news.google.com/rss/search?'
TEMAS = {
    'Drogas': 'apreensão drogas cocaína maconha tráfico',
    'Armas': 'apreensão armas munições polícia',
    'Contrabando': 'apreensão contrabando descaminho Receita Federal',
    'Lavagem de dinheiro': 'operação lavagem de dinheiro tráfico polícia',
}
FONTES = {
    'Polícia Federal': 'gov.br/pf',
    'Polícia Rodoviária Federal': 'gov.br/prf',
    'Receita Federal': 'gov.br/receitafederal',
}
ESTADOS = 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split()
# As consultas estaduais cobrem os 27 entes federativos, inclusive ocorrências
# publicadas por polícias civil, militar, penal, científica e guardas municipais.
TIPOS_ORGAOS = [
    'polícia civil', 'polícia militar', 'polícia penal',
    'polícia científica', 'guarda municipal', 'bombeiros',
    'secretaria segurança pública', 'Receita Federal',
]
TERMOS_APREENSAO = '(apreensão OR apreende OR apreendido OR contrabando OR tráfico)'
FONTES_EXTRAS = Path('fontes.json')
META_FONTES = 10000
# Cadastro de domínios é distinto de consultas por execução.



def carregar_fontes_extras():
    """Lê até milhares de fontes cadastradas em fontes.json, sem inventar domínios.

    Formato: {"fontes": [{"nome": "...", "dominio": "exemplo.gov.br", "uf": "PR"}]}
    Domínios devem ser cadastrados e verificados antes de entrar na lista.
    """
    if not FONTES_EXTRAS.exists():
        return []
    dados = json.loads(FONTES_EXTRAS.read_text(encoding='utf-8'))
    itens = dados.get('fontes', []) if isinstance(dados, dict) else dados
    if not isinstance(itens, list):
        raise ValueError('fontes.json deve conter uma lista de fontes')
    saida = []
    vistos = set()
    for item in itens:
        if not isinstance(item, dict):
            continue
        dominio = str(item.get('dominio', '')).strip().lower()
        dominio = re.sub(r'^https?://', '', dominio).split('/')[0].split(':')[0]
        uf = str(item.get('uf', '')).strip().upper()
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.[a-z]{2,}', dominio):
            continue
        if uf and uf not in ESTADOS:
            continue
        if dominio in vistos:
            continue
        vistos.add(dominio)
        saida.append({'dominio': dominio, 'uf': uf, 'nome': str(item.get('nome', dominio))})
    return saida


def selecionar_rodizio(itens, limite, data_referencia):
    """Alterna consultas entre execuções diárias, com ordem determinística."""
    if not itens or limite <= 0:
        return []
    # Rotação por blocos: percorre a lista inteira antes de reiniciar.
    blocos = (len(itens) + limite - 1) // limite
    bloco = data_referencia.toordinal() % blocos
    inicio = bloco * limite
    return itens[inicio:inicio + limite]



def ler_existentes():
    if not ARQUIVO.exists():
        return []
    try:
        dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
        if isinstance(dados, dict):
            return dados.get('noticias', []) if isinstance(dados.get('noticias'), list) else []
        return dados if isinstance(dados, list) else []
    except (ValueError, OSError) as exc:
        raise RuntimeError('Arquivo noticias.json existente inválido; não será sobrescrito') from exc


def data_iso(valor):
    try:
        return parsedate_to_datetime(valor).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, IndexError):
        return ''


def coletar(query, categoria=None):
    parametros = urllib.parse.urlencode({'q': query, 'hl': 'pt-BR', 'gl': 'BR', 'ceid': 'BR:pt-419'})
    requisicao = urllib.request.Request(BASE + parametros, headers={'User-Agent': 'Mozilla/5.0 RadarDasApreensoes/2.0'})
    with urllib.request.urlopen(requisicao, timeout=35) as resposta:
        raiz = ET.fromstring(resposta.read())
    saida = []
    for item in raiz.findall('./channel/item'):
        titulo = (item.findtext('title') or '').strip()
        url = (item.findtext('link') or '').strip()
        data = (item.findtext('pubDate') or '').strip()
        fonte = (item.findtext('source') or 'Google Notícias').strip()
        if not titulo or not url:
            continue
        noticia = {'titulo': titulo, 'url': url, 'data_publicacao': data, 'fonte': fonte}
        if categoria:
            noticia['categoria'] = categoria
        iso = data_iso(data)
        if iso:
            noticia['data_iso'] = iso
        saida.append(noticia)
    return saida


def texto_normalizado(valor):
    valor = unicodedata.normalize('NFKD', str(valor or '').casefold())
    valor = ''.join(c for c in valor if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', valor).strip()


def titulo_base(n):
    titulo = str(n.get('titulo') or n.get('t') or '')
    fonte = str(n.get('fonte') or '')
    # O Google News costuma acrescentar o nome do veículo ao título.
    if fonte and titulo.casefold().endswith(' - ' + fonte.casefold()):
        titulo = titulo[:-(len(fonte) + 3)]
    return texto_normalizado(titulo)


def url_base(n):
    url = str(n.get('url') or '').strip()
    try:
        p = urllib.parse.urlsplit(url)
        dominio = (p.hostname or '').lower().removeprefix('www.')
        caminho = p.path.rstrip('/')
        # Evitar parâmetros de rastreamento na identidade da notícia.
        params = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        params = [(k, v) for k, v in params if not k.lower().startswith('utm_') and k.lower() not in {'fbclid','gclid','oc'}]
        return dominio + caminho + ('?' + urllib.parse.urlencode(sorted(params)) if params else '')
    except ValueError:
        return url


def dia_publicacao(n):
    data = str(n.get('data_iso') or '')
    if not data:
        data = data_iso(n.get('data_publicacao', ''))
    return data[:10]


def mesma_materia(a, b):
    if url_base(a) and url_base(a) == url_base(b):
        return True
    ta, tb = titulo_base(a), titulo_base(b)
    if not ta or not tb:
        return False
    da, db = dia_publicacao(a), dia_publicacao(b)
    # Não misturar ocorrências diferentes apenas porque têm manchetes parecidas.
    if da and db:
        try:
            if abs((datetime.fromisoformat(da) - datetime.fromisoformat(db)).days) > 2:
                return False
        except ValueError:
            pass
    if ta == tb:
        return True
    # Semelhança muito alta: retira republicações com pequenas variações.
    return len(ta) >= 55 and len(tb) >= 55 and SequenceMatcher(None, ta, tb).ratio() >= 0.96


def deduplicar(itens):
    # Primeiro por URL e manchete exata; depois compara apenas candidatos
    # com início de título semelhante, evitando comparação global quadrática.
    unicos = []
    urls = set()
    indices = {}
    descartadas = 0
    for n in itens:
        if not isinstance(n, dict):
            continue
        u = url_base(n)
        t = titulo_base(n)
        dia = dia_publicacao(n)
        if u and u in urls:
            descartadas += 1
            continue
        prefixo = ' '.join(t.split()[:4])
        candidatos = indices.get(prefixo, [])
        if any(mesma_materia(n, unicos[i]) for i in candidatos):
            descartadas += 1
            continue
        unicos.append(n)
        if u:
            urls.add(u)
        indices.setdefault(prefixo, []).append(len(unicos)-1)
    return unicos, descartadas


def executar():
    parser = argparse.ArgumentParser()
    parser.add_argument('--historico', action='store_true', help='Busca mês a mês em um ano específico')
    parser.add_argument('--ano', type=int, help='Ano histórico de 2020 até o atual')
    parser.add_argument('--limite-fontes', type=int, default=24, help='Fontes extras consultadas por execução (padrão: 24)')
    parser.add_argument('--limite-estados', type=int, default=9, help='Estados consultados por execução (padrão: 9)')
    args = parser.parse_args()
    hoje = datetime.now(timezone.utc)
    ano_atual = hoje.year
    if args.limite_fontes < 0 or args.limite_estados < 0:
        parser.error('Os limites de consultas não podem ser negativos')
    if args.historico and (args.ano is None or not 2020 <= args.ano <= ano_atual):
        parser.error('Informe --ano entre 2020 e o ano atual')
    existentes = ler_existentes()
    registros, duplicadas_anteriores = deduplicar(existentes)
    print(f'Duplicatas já existentes descartadas: {duplicadas_anteriores}')
    consultas = []
    if args.historico:
        # Uma execução por ano, para não sobrecarregar a fonte.
        for mes in range(1, 13):
            if args.ano == ano_atual and mes > datetime.now(timezone.utc).month:
                break
            seguinte = f'{args.ano + 1}-01-01' if mes == 12 else f'{args.ano}-{mes + 1:02d}-01'
            inicio = f'{args.ano}-{mes:02d}-01'
            for categoria, termos in TEMAS.items():
                consultas.append((f'{termos} after:{inicio} before:{seguinte}', categoria))
    else:
        for categoria, termos in TEMAS.items():
            consultas.append((termos + ' Brasil when:7d', categoria))
        for nome, dominio in FONTES.items():
            consultas.append((f'{TERMOS_APREENSAO} site:{dominio} when:7d', None))
        # Três blocos rotativos de nove estados cobrem os 27 estados/DF
        # ao longo de três execuções diárias, sem gerar centenas de buscas.
        for uf in selecionar_rodizio(ESTADOS, args.limite_estados, hoje):
            consultas.append((f'{TERMOS_APREENSAO} "{uf}" polícia when:7d', None))
        extras = carregar_fontes_extras()
        for fonte in selecionar_rodizio(extras, args.limite_fontes, hoje):
            consultas.append((f'{TERMOS_APREENSAO} site:{fonte["dominio"]} when:7d', None))
        print(f'Meta: {META_FONTES} fontes; extras cadastradas: {len(extras)}; consultadas nesta execução: {min(len(extras), args.limite_fontes)}')
    novos = 0
    erros = 0
    recebidas = []
    for i, (consulta, categoria) in enumerate(consultas, 1):
        try:
            itens = coletar(consulta, categoria)
            recebidas.extend(itens)
            print(f'Consulta {i}/{len(consultas)}: {len(itens)} resultados, {novos} novos acumulados')
        except (OSError, ET.ParseError, ValueError) as exc:
            erros += 1
            print(f'AVISO: consulta {i} falhou: {exc}')
        time.sleep(1.5 if args.historico else 0.5)
    if erros == len(consultas):
        raise RuntimeError('Todas as consultas falharam; arquivo preservado')
    noticias, descartadas = deduplicar(registros + recebidas)
    novos = len(noticias) - len(registros)
    print(f'Duplicatas detectadas nesta execução: {descartadas}')
    noticias.sort(key=lambda n: n.get('data_iso') or data_iso(n.get('data_publicacao', '')), reverse=True)
    resultado = {'atualizado_em': datetime.now(timezone.utc).isoformat(), 'total': len(noticias), 'noticias': noticias}
    temporario = ARQUIVO.with_suffix('.json.tmp')
    temporario.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    temporario.replace(ARQUIVO)
    print(f'Concluído: {novos} novas; {len(noticias)} no acervo; {erros} consultas falharam.')


if __name__ == '__main__':
    executar()
