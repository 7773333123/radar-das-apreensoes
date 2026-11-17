#!/usr/bin/env python3
"""Veículos com conteúdo pago (assinatura para ler a matéria): fora da coleta e do site.

Decisão do responsável pelo site (17/11/2026): o leitor do Radar não pode cair numa
matéria que exige assinatura. A notícia sai do acervo; se outro veículo gratuito
publicou o mesmo fato, a versão gratuita continua no site.
"""
import re
from urllib.parse import urlsplit

DOMINIOS = {
    'valor.globo.com', 'valorinveste.globo.com', 'oglobo.globo.com', 'blogs.oglobo.globo.com', 'epoca.globo.com',
    'epocanegocios.globo.com', 'folha.uol.com.br', 'piaui.folha.uol.com.br', 'estadao.com.br', 'gauchazh.clicrbs.com.br',
    'em.com.br', 'gazetadopovo.com.br', 'veja.abril.com.br', 'nsctotal.com.br', 'otempo.com.br', 'correiobraziliense.com.br',
    'diariodonordeste.verdesmares.com.br', 'opovo.com.br', 'exame.com', 'crusoe.com.br', 'jota.info', 'revistaoeste.com',
    'atarde.com.br', 'correio24horas.com.br',
}
# Notícias do Google Notícias sem link do veículo: pelo nome da fonte (nome exato).
NOMES = {
    'valor econômico', 'valor', 'o globo', 'época', 'época negócios', 'folha de s.paulo', 'folha de s. paulo', 'folha',
    'revista piauí', 'estadão', 'estadão mobilidade', 'o estado de s. paulo', 'gzh', 'estado de minas',
    'jornal estado de minas on msn', 'gazeta do povo', 'veja', 'nsc total', 'o tempo', 'correio braziliense',
    'diário do nordeste', 'o povo', 'exame', 'crusoé', 'jota', 'jota jornalismo', 'jota info', 'revista oeste', 'a tarde',
    'correio',
}


def dominio_pago(url_ou_dominio):
    h = str(url_ou_dominio or '').strip().lower()
    if '://' in h:
        h = urlsplit(h).hostname or ''
    h = h.removeprefix('www.')
    return any(h == d or h.endswith('.' + d) for d in DOMINIOS)


def pago(n):
    """A notícia é de veículo com conteúdo pago?"""
    for campo in ('url_original', 'dominio_fonte'):
        v = str(n.get(campo) or '')
        if v and 'news.google' not in v and dominio_pago(v):
            return True
    u = str(n.get('url') or '')
    if u and 'news.google' not in u and dominio_pago(u):
        return True
    return re.sub(r'\s+', ' ', str(n.get('fonte') or '')).strip().lower() in NOMES
