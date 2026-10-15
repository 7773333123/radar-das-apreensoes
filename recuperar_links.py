#!/usr/bin/env python3
"""Recupera URLs originais do Google Notícias, preservando notícias e dados existentes.
Uso: python recuperar_links.py --limite 60
"""
import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from googlenewsdecoder import gnewsdecoder

ARQUIVO = Path(__file__).resolve().parent / 'noticias.json'


def url_valida(url):
    try:
        p = urlparse(str(url))
        host = (p.hostname or '').lower()
        return p.scheme in ('http', 'https') and bool(host) and host not in ('news.google.com', 'google.com', 'www.google.com') and not host.endswith('.google.com') and not host.endswith('.googleusercontent.com')
    except (ValueError, TypeError):
        return False


def resolver(url):
    try:
        resultado = gnewsdecoder(url, timeout=12.0)
        if isinstance(resultado, dict):
            destino = resultado.get('decoded_url') or ''
            sucesso = resultado.get('success', resultado.get('status', False))
            if sucesso and url_valida(destino):
                return destino, 'recuperada_google_news'
            return '', 'falha_decodificacao'
        return '', 'resposta_invalida'
    except Exception as exc:
        return '', 'erro_' + type(exc).__name__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limite', type=int, default=int(os.getenv('LIMITE_DECODIFICACAO', '60')))
    parser.add_argument('--trabalhadores', type=int, default=6)
    args = parser.parse_args()
    if not ARQUIVO.exists():
        raise SystemExit('noticias.json não encontrado; nenhum arquivo alterado')
    dados = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    noticias = dados['noticias'] if isinstance(dados, dict) else dados
    if not isinstance(noticias, list):
        raise SystemExit('Formato de notícias inválido; arquivo preservado')
    pendentes = []
    existentes = 0
    for noticia in noticias:
        if not isinstance(noticia, dict):
            continue
        if url_valida(noticia.get('url_original')):
            existentes += 1
            continue
        google = noticia.get('url_google_noticias') or noticia.get('url') or ''
        if 'news.google.com/' not in google:
            if url_valida(google):
                noticia['url_original'] = google
                noticia['url_original_status'] = 'direta'
                existentes += 1
            continue
        # Tentar novamente em execuções futuras apenas para falhas transitórias,
        # evitando milhares de requisições repetidas no mesmo dia.
        if noticia.get('url_original_status') == 'falha_decodificacao_definitiva':
            continue
        pendentes.append((noticia, google))
    lote = pendentes[:max(0, args.limite)]
    print(f'Acervo: {len(noticias)}; links originais já disponíveis: {existentes}; aguardando: {len(pendentes)}; tentativa nesta execução: {len(lote)}', flush=True)
    sucesso = 0
    erros = {}
    with ThreadPoolExecutor(max_workers=max(1, min(args.trabalhadores, 8))) as executor:
        futuros = {executor.submit(resolver, google): (noticia, google) for noticia, google in lote}
        for futuro in as_completed(futuros):
            noticia, google = futuros[futuro]
            original, status = futuro.result()
            noticia.setdefault('url_google_noticias', google)
            if original:
                noticia['url_original'] = original
                noticia['url_original_status'] = status
                # A leitura antiga do agregador não pode ser reaproveitada.
                if noticia.get('leitura_fonte_status') in ('lida', 'aguardando_url_original'):
                    noticia['leitura_fonte_status'] = 'pendente_leitura_original'
                sucesso += 1
            else:
                noticia['url_original_status'] = status
                erros[status] = erros.get(status, 0) + 1
    if lote:
        temporario = ARQUIVO.with_suffix('.json.tmp')
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
        temporario.replace(ARQUIVO)
    print(f'Decodificação: {sucesso}/{len(lote)} URLs originais recuperadas; falhas: {erros}; acervo preservado: {len(noticias)}.', flush=True)
    if lote and sucesso == 0:
        print('ATENÇÃO: nenhuma URL recuperada. Verifique logs/restrições do Google; não considerar leitura concluída.', flush=True)


if __name__ == '__main__':
    main()
