#!/usr/bin/env python3
"""Veículos fora da coleta e do site: conteúdo pago (assinatura) e exclusões pedidas pelo responsável.

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
    # Avaliação de 600 sites (avaliar_sites.yml, 17/11/2026): pagos, robots.txt proíbe ou bloqueiam sem RSS aberto:
    '24horasmt.com.br', 'acheisudoeste.com.br', 'blogdojuares.com.br', 'campograndenews.com.br',
    'cartacapital.com.br', 'espiritosantonoticias.com.br', 'extra.globo.com', 'guiamuriae.com.br', 'leiaja.com',
    'marechalnews.com.br', 'midiabahia.com.br', 'oestemais.com', 'osepeense.com', 'parlamentopb.com.br',
    'portalribeira.com.br', 'portalrondon.com.br', 'thmais.com.br',
    # Excluídos a pedido do responsável (bloqueiam a leitura das matérias e o RSS; verificar_rss.yml, 17/11/2026):
    'amazonasatual.com.br', 'ampost.com.br', 'atibaiahoje.com.br', 'bandnewsfmcuritiba.com',
    'blogdovalente.com.br', 'bol.uol.com.br', 'caldeiraopolitico.com.br', 'capitalnews.com.br', 'catve.com',
    'cbncuritiba.com.br', 'cbngoiania.com.br', 'cbnvale.com.br', 'cgn.inf.br', 'cliquediario.com.br',
    'd24am.com', 'diariodecuiaba.com.br', 'diariodeuberlandia.com.br', 'diariogm.com.br', 'diariosm.com.br',
    'divinews.com', 'douradosnews.com.br', 'estacaolivremt.com.br', 'euviemlinhares.net', 'extraclasse.org.br',
    'faxaju.com.br', 'folhadoes.com', 'folhamax.com', 'hojemais.com.br', 'infoverus.com.br',
    'issoenoticia.com.br', 'jornalrepercussao.com.br', 'maisgoias.com.br', 'midiajur.com.br', 'midianews.com.br',
    'noticiamax.com.br', 'noticias.uol.com.br', 'obomdanoticia.com.br', 'onacional.com.br',
    'portaldecamaqua.com.br', 'portalhortolandia.com.br', 'powermix.com.br', 'radaramazonico.com.br',
    'rdnews.com.br', 'setelagoas.com.br', 'studio.tv.br', 'sucessofm.com', 'surgiu.com.br', 'tasabendo.com.br',
    'topelegance.com.br', 'tribunadoplanalto.com.br', 'uniaometropolitana.com.br', 'unicanews.com.br',
    'viagora.com.br', 'wscom.com.br',
    # Excluído a pedido do responsável (24/11/2026): carimba marca d'água em todas as fotos (notícias sem foto no site).
    'lsmnoticias.com.br',
}
# Notícias do Google Notícias sem link do veículo: pelo nome da fonte (nome exato).
NOMES = {
    'valor econômico', 'valor', 'o globo', 'época', 'época negócios', 'folha de s.paulo', 'folha de s. paulo', 'folha',
    'revista piauí', 'estadão', 'estadão mobilidade', 'o estado de s. paulo', 'gzh', 'estado de minas',
    'jornal estado de minas on msn', 'gazeta do povo', 'veja', 'nsc total', 'o tempo', 'correio braziliense',
    'diário do nordeste', 'o povo', 'exame', 'crusoé', 'jota', 'jota jornalismo', 'jota info', 'revista oeste', 'a tarde',
    'correio', 'top elegance',
    # veículos que bloqueiam leitura e RSS
    '24 horas mt', 'achei sudoeste', 'blog do juares', 'campo grande news', 'cartacapital', 'extra online', 'guia muriaé', 'jornal espírito santo notícias', 'jornal o sepeense', 'leiajá', 'marechal news', 'mídia bahia', 'oeste mais', 'parlamento pb', 'portal rondon', 'portalribeira', 'thmais',
    'am post', 'amazonas atual', 'atibaia hoje', 'band news fm curitiba', 'blog do valente', 'bol',
    'caldeirão político', 'capital news', 'catve', 'cbn curitiba', 'cbn goiânia',
    'cbn são josé dos campos e vale', 'cgn', 'clique diário', 'd24am', 'diario de cuiabá', 'divinews',
    'diário de santa maria', 'diário de uberlândia', 'diário gm', 'dourados news', 'estação livre mt',
    'eu vi em linhares', 'extra classe', 'faxaju', 'folha do es', 'folhamax', 'hojemais.com.br', 'infoverus',
    'infoverus.com.br', 'isso é notícia', 'jornal repercussão', 'mais goiás', 'midia jur', 'midianews',
    'notícia max', 'o bom da notícia', 'o nacional', 'portal de camaquã', 'portal hortolândia', 'power mix',
    'radar amazônico', 'rdnews', 'sete lagoas . com . br', 'sete lagoas .com.br', 'studio notícias',
    'sucesso fm', 'surgiu', 'topelegance', 'tribuna do planalto', 'tásabendo', 'união metropolitana',
    'união metropolitana curitiba', 'uol notícias', 'viagora', 'wscom', 'www.capitalnews.com.br',
    'www.midiajur.com.br', 'www.sucessofm.com', 'única news',
    'lsm notícias', 'lsm noticias',
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
