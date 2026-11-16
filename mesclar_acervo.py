#!/usr/bin/env python3
"""Junta duas versões de noticias.json sem perder nada.

Uso: python mesclar_acervo.py /caminho/da/nossa_versao.json
Mescla a versão indicada (desta execução) no noticias.json atual (o que outra
coleta acabou de publicar). Notícias são identificadas pelo link (ou pelo
título). Para cada campo, fica o valor mais completo: o que existir, a lista
maior, o contador maior. Usado quando duas coletas gravam ao mesmo tempo.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent / 'noticias.json'
MAIOR = ('materia_lida_v', 'tentativas_leitura', 'tentativas_url_original_v2', 'tentativas_busca_indice', 'tentativas_imagem')


def chave(n):
    url = str(n.get('url') or '').split('?')[0].rstrip('/')
    if url:
        return 'u:' + url
    t = unicodedata.normalize('NFKD', str(n.get('titulo') or ''))
    t = ''.join(c for c in t if not unicodedata.combining(c)).lower()
    return 't:' + re.sub(r'[^a-z0-9]+', ' ', t).strip()


def juntar(base, outro):
    for campo, valor in outro.items():
        atual = base.get(campo)
        if valor in (None, '', [], {}):
            continue
        if atual in (None, '', [], {}):
            base[campo] = valor
        elif campo in MAIOR:
            try:
                base[campo] = max(int(atual), int(valor))
            except (TypeError, ValueError):
                pass
        elif isinstance(valor, list) and isinstance(atual, list) and len(valor) > len(atual):
            base[campo] = valor
        elif campo == 'url_original' and 'news.google.com' in str(atual) and 'news.google.com' not in str(valor):
            base[campo] = valor


def main():
    nossa = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    atual = json.loads(ARQUIVO.read_text(encoding='utf-8'))
    lista_atual = atual['noticias'] if isinstance(atual, dict) else atual
    lista_nossa = nossa['noticias'] if isinstance(nossa, dict) else nossa
    indice = {chave(n): n for n in lista_atual if isinstance(n, dict)}
    novas = completadas = 0
    for n in lista_nossa:
        if not isinstance(n, dict):
            continue
        k = chave(n)
        if k in indice:
            antes = json.dumps(indice[k], sort_keys=True)
            juntar(indice[k], n)
            completadas += antes != json.dumps(indice[k], sort_keys=True)
        else:
            lista_atual.append(n)
            indice[k] = n
            novas += 1
    if isinstance(atual, dict):
        atual['total'] = len(lista_atual)
        atual['atualizado_em'] = max(str(atual.get('atualizado_em') or ''), str(nossa.get('atualizado_em') or '')) or None
    tmp = ARQUIVO.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(atual, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(ARQUIVO)
    print(f'Mesclagem: {novas} notícias desta execução acrescentadas, {completadas} completadas; acervo: {len(lista_atual)}')


if __name__ == '__main__':
    main()
