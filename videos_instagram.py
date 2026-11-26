#!/usr/bin/env python3
"""Vídeos oficiais no Instagram (dono do site, 26/11/2026: "colete vídeos do Instagram").

Lê, pela API OFICIAL da Meta (Graph API, "business discovery"), os posts públicos das contas que os PRÓPRIOS
órgãos mantêm no Instagram (instagram_contas.json: PRF, PF, PMs, Polícias Civis e grupos táticos, conferidas
uma a uma) e guarda os vídeos de apreensão das últimas 72 h em videos_instagram.json. Nada é baixado: o site
mostra o vídeo na notícia do mesmo fato pelo player do próprio Instagram (gerar_feed_site.py).

Token: segredo RADAR_META do repositório (token do app "Radar Leitor", só leitura). Sem token, não faz nada.
Limite da Meta (~100 chamadas/hora para o app, medido em 26/11/2026): cada rodada lê só LOTE contas, em rodízio (instagram_cursor.json).

  RADAR_META=... python videos_instagram.py
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CONTAS = RAIZ / 'instagram_contas.json'
SAIDA = RAIZ / 'videos_instagram.json'
CURSOR = RAIZ / 'instagram_cursor.json'
NOSSA_CONTA = '17841452435152748'  # Instagram do Radar (dono do app); a consulta parte dela
API = 'https://graph.facebook.com/v21.0/'
HORAS = 72
# ~4 rodadas/h x 15 = 60 consultas/h (o app tem ~100/h); instagram_agora.yml lê todas de uma vez (IG_LOTE).
LOTE = int(os.environ.get('IG_LOTE') or 15)
APREENSAO = re.compile(r'apreen|cocaína|cocaina|maconha|skunk|haxixe|crack|droga|entorpecente|fuzil|fuzis|arma|'
                       r'munição|munições|contrabando|descaminho|cigarro|tráfico|trafico|flagrante', re.I)


def consultar(usuario, token):
    campos = (f'business_discovery.username({usuario})'
              '{media.limit(12){media_type,media_product_type,timestamp,permalink,caption}}')
    url = API + NOSSA_CONTA + '?' + urllib.parse.urlencode({'fields': campos})
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get('business_discovery', {}).get('media', {}).get('data', [])


def codigo(permalink):
    """'reel/ABC123' ou 'p/ABC123' do endereço público do post."""
    m = re.search(r'instagram\.com/(reel|p|tv)/([\w-]{5,40})', permalink or '')
    return f"{'reel' if m.group(1) == 'tv' else m.group(1)}/{m.group(2)}" if m else None


def titulo(legenda):
    linha = next((x.strip() for x in (legenda or '').splitlines() if len(x.strip()) > 15), '')
    return re.sub(r'\s+', ' ', linha)[:200]


def main():
    token = os.environ.get('RADAR_META', '').strip()
    if not token:
        print('Sem RADAR_META: Instagram não lido.')
        return
    contas = json.loads(CONTAS.read_text(encoding='utf-8'))['contas']
    nomes = sorted(contas)
    try:
        pos = int(json.loads(CURSOR.read_text(encoding='utf-8')).get('pos', 0)) % len(nomes)
    except (OSError, ValueError):
        pos = 0
    lote = [nomes[(pos + k) % len(nomes)] for k in range(min(LOTE, len(nomes)))]
    try:
        antigos = json.loads(SAIDA.read_text(encoding='utf-8')).get('videos', [])
    except (OSError, ValueError):
        antigos = []
    limite = (datetime.now(timezone.utc) - timedelta(hours=HORAS)).isoformat()[:19]
    novos, falhas, lidas = {}, [], 0
    for usuario in lote:
        lidas += 1
        try:
            for m in consultar(usuario, token):
                quando = (m.get('timestamp') or '')[:19]
                cod = codigo(m.get('permalink'))
                if m.get('media_type') != 'VIDEO' or not cod or quando < limite:
                    continue
                if not APREENSAO.search(m.get('caption') or ''):
                    continue
                novos[cod] = {'ig': cod, 't': titulo(m.get('caption')), 'd': quando, 'conta': usuario,
                              'orgao': contas[usuario]['orgao']}
        except urllib.error.HTTPError as erro:
            corpo = erro.read().decode('utf-8', 'replace')
            if '"code":4,' in corpo or '"code":17,' in corpo or '"code":32,' in corpo:
                lidas -= 1  # limite da Meta: para e retoma desta conta na próxima rodada
                falhas.append(f'{usuario} (limite da Meta; retoma na próxima rodada)')
                break
            falhas.append(f'{usuario} ({corpo[:80]})')
        except Exception as erro:  # noqa: BLE001 - registra e segue (conta mudou de nome, rede...)
            falhas.append(f'{usuario} ({str(erro)[:60]})')
    for v in antigos:  # mantém os já vistos dentro da janela (cada conta é lida a cada ~1 h)
        if v.get('d', '') >= limite:
            novos.setdefault(v['ig'], v)
    lista = sorted(novos.values(), key=lambda v: v['d'], reverse=True)
    SAIDA.write_text(json.dumps({'atualizado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                 'videos': lista}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    CURSOR.write_text(json.dumps({'pos': (pos + lidas) % len(nomes)}) + '\n', encoding='utf-8')
    print(f'Instagram: {lidas} contas lidas, {len(lista)} vídeos de apreensão ({HORAS} h); falhas: {len(falhas)}')
    for f in falhas[:10]:
        print('  falha:', f)
    for v in lista[:10]:
        print(' ', v['d'], '@' + v['conta'], '|', v['t'][:90])


if __name__ == '__main__':
    main()
