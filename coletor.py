"""Radar das Apreensões: coleta incremental e busca histórica opcional.

Uso:
  python coletor.py
  python coletor.py --historico --ano 2020
"""
import argparse
import json
import re
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


def chave(n):
    # URLs Google News podem variar; normalizar título e fonte reduz duplicações.
    titulo = re.sub(r'\W+', ' ', str(n.get('titulo', '')).lower()).strip()
    fonte = re.sub(r'\W+', ' ', str(n.get('fonte', '')).lower()).strip()
    return (titulo, fonte) if titulo else ('url', n.get('url', ''))


def executar():
    parser = argparse.ArgumentParser()
    parser.add_argument('--historico', action='store_true', help='Busca mês a mês em um ano específico')
    parser.add_argument('--ano', type=int, help='Ano histórico de 2020 até o atual')
    args = parser.parse_args()
    ano_atual = datetime.now(timezone.utc).year
    if args.historico and (args.ano is None or not 2020 <= args.ano <= ano_atual):
        parser.error('Informe --ano entre 2020 e o ano atual')
    existentes = ler_existentes()
    registros = {chave(n): n for n in existentes if isinstance(n, dict)}
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
            consultas.append((f'(apreensão OR apreende OR operação) site:{dominio} when:7d', None))
    novos = 0
    erros = 0
    for i, (consulta, categoria) in enumerate(consultas, 1):
        try:
            itens = coletar(consulta, categoria)
            for noticia in itens:
                identificador = chave(noticia)
                if identificador not in registros:
                    registros[identificador] = noticia
                    novos += 1
            print(f'Consulta {i}/{len(consultas)}: {len(itens)} resultados, {novos} novos acumulados')
        except (OSError, ET.ParseError, ValueError) as exc:
            erros += 1
            print(f'AVISO: consulta {i} falhou: {exc}')
        if args.historico:
            time.sleep(1.5)
    if erros == len(consultas):
        raise RuntimeError('Todas as consultas falharam; arquivo preservado')
    noticias = list(registros.values())
    noticias.sort(key=lambda n: n.get('data_iso') or data_iso(n.get('data_publicacao', '')), reverse=True)
    resultado = {'atualizado_em': datetime.now(timezone.utc).isoformat(), 'total': len(noticias), 'noticias': noticias}
    temporario = ARQUIVO.with_suffix('.json.tmp')
    temporario.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    temporario.replace(ARQUIVO)
    print(f'Concluído: {novos} novas; {len(noticias)} no acervo; {erros} consultas falharam.')


if __name__ == '__main__':
    executar()
