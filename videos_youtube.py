#!/usr/bin/env python3
"""Vídeos oficiais no YouTube (dono do site, 25/11/2026: "existem muitos perfis postando vídeos de fontes
públicas; busque vídeos").

Lê o feed público (RSS) dos canais que os PRÓPRIOS órgãos mantêm no YouTube (PRF, PF, Receita, polícias
estaduais...) e guarda os vídeos de apreensão das últimas 72 h em videos_oficiais.json. Não precisa de conta
nem de canal do Radar e nada é baixado: o site mostra o vídeo pelo player do YouTube (youtube-nocookie) na
notícia correspondente (gerar_feed_site.py) e a análise das 8h lista os vídeos do dia para os Reels (o arquivo
para o Reels, só pedido à assessoria do órgão: baixar do YouTube não é permitido).

Canais: CANAIS abaixo (endereço público do canal). O id do canal é lido uma vez na página do canal e guardado
em youtube_canais.json; canal que não responde fica registrado com o erro e é tentado de novo no dia seguinte.

  python videos_youtube.py            # roda no GitHub Actions (videos_youtube.yml)
"""
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / 'videos_oficiais.json'
CACHE = RAIZ / 'youtube_canais.json'
HORAS = 72
UA = {'User-Agent': 'Mozilla/5.0 (compatible; RadarDasApreensoes/1.0)', 'Accept-Language': 'pt-BR,pt;q=0.9'}

# Endereço público do canal oficial -> nome do órgão (crédito). Endereços conferidos na primeira rodada;
# os que não existirem aparecem no registro (youtube_canais.json, "erro") para ajuste.
CANAIS = {
    # Conferidos em 25/11/2026 pelo nome do canal no YouTube (youtube_canais.json, "nome"). Só entram canais
    # comprovadamente oficiais; endereço que levou a canal de terceiros (ex.: @pmgo, @pmmt) foi retirado.
    'https://www.youtube.com/@prfbrasil': 'PRF',                       # "PRF Brasil"
    'https://www.youtube.com/pfnatela': 'Polícia Federal',             # "PFnaTela"
    'https://www.youtube.com/@pmmgoficial': 'Polícia Militar de MG',   # "TV PMMG"
    'https://www.youtube.com/@pmscoficial': 'Polícia Militar de SC',   # "PMSC Oficial"
    'https://www.youtube.com/@pmpe': 'Polícia Militar de PE',          # "PM PE"
}
# Vídeo de apreensão: os mesmos termos do site (classificar.relevante) ou palavras típicas dos títulos dos órgãos.
APREENSAO = re.compile(r'apreen|apreende|cocaína|cocaina|maconha|skunk|haxixe|crack|droga|entorpecente|fuzil|fuzis|'
                       r'arma|munição|munições|contrabando|descaminho|cigarro|tráfico|trafico|operação|operacao', re.I)


def baixar(url, limite=2_000_000):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read(limite).decode('utf-8', 'replace')


def id_do_canal(url, cache):
    c = cache.get(url) or {}
    if c.get('id'):
        return c['id']
    hoje = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if c.get('erro') and c.get('em') == hoje:
        return None
    try:
        pagina = baixar(url)
        m = re.search(r'"(?:externalId|channelId)":"(UC[\w-]{22})"', pagina) or \
            re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', pagina)
        if not m:
            raise ValueError('id do canal não encontrado')
        cache[url] = {'id': m.group(1), 'em': hoje}
        return m.group(1)
    except Exception as erro:  # noqa: BLE001 - registra e segue para o próximo canal
        cache[url] = {'erro': str(erro)[:120], 'em': hoje}
        return None


def videos_do_canal(cid, orgao):
    ns = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
    raiz = ET.fromstring(baixar(f'https://www.youtube.com/feeds/videos.xml?channel_id={cid}'))
    yield {'_nome': html.unescape((raiz.findtext('a:title', '', ns) or '').strip())}
    for e in raiz.findall('a:entry', ns):
        vid = (e.findtext('yt:videoId', '', ns) or '').strip()
        titulo = html.unescape((e.findtext('a:title', '', ns) or '').strip())
        quando = (e.findtext('a:published', '', ns) or '').strip()
        if re.fullmatch(r'[\w-]{11}', vid) and titulo and quando:
            yield {'yt': vid, 't': titulo, 'd': quando[:19], 'orgao': orgao}


def main():
    try:
        cache = json.loads(CACHE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        cache = {}
    try:
        antigos = json.loads(SAIDA.read_text(encoding='utf-8')).get('videos', [])
    except (OSError, ValueError):
        antigos = []
    limite = (datetime.now(timezone.utc) - timedelta(hours=HORAS)).isoformat()[:19]
    novos, falhas = {}, []
    for url, orgao in CANAIS.items():
        cid = id_do_canal(url, cache)
        if not cid:
            falhas.append(url)
            continue
        try:
            for v in videos_do_canal(cid, orgao):
                if '_nome' in v:
                    cache[url]['nome'] = v['_nome']  # nome do canal no YouTube (conferir se é mesmo o oficial)
                    continue
                if v['d'] >= limite and APREENSAO.search(v['t']):
                    novos[v['yt']] = v
        except Exception as erro:  # noqa: BLE001
            falhas.append(f'{url} ({str(erro)[:60]})')
    for v in antigos:  # mantém os já vistos dentro da janela (feed traz só os 15 últimos de cada canal)
        if v.get('d', '') >= limite:
            novos.setdefault(v['yt'], v)
    lista = sorted(novos.values(), key=lambda v: v['d'], reverse=True)
    SAIDA.write_text(json.dumps({'atualizado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                 'videos': lista}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(f'Vídeos oficiais (YouTube, {HORAS} h): {len(lista)}; canais sem resposta: {len(falhas)}')
    for f in falhas:
        print('  sem resposta:', f)
    for v in lista[:15]:
        print(' ', v['d'], v['orgao'], '|', v['t'][:90])


if __name__ == '__main__':
    main()
