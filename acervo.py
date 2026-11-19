#!/usr/bin/env python3
"""Acervo e dados do site guardados numa Release do GitHub, fora do histórico do Git.

Antes, noticias.json (38 MB) e os arquivos gerados (feed, det/, dados/) eram
regravados no Git a cada 20 minutos, e o repositório crescia ~80 MB por dia.
Agora ficam como arquivos da release "dados" (que não acumulam histórico), e o
Git guarda só dados_versao.json, um ponteiro com o nome da versão atual.

  Acervo em partes: "quente" (últimos 45 dias, das coletas do dia) e uma parte por ano.
  python acervo.py baixar [--parte AAAA]   noticias.json da parte (padrão: quente)
  python acervo.py dividir                 migração única: separa o acervo em partes
  python acervo.py rotacionar              notícias que passaram do corte vão para o ano
  python acervo.py regenerar "msg"         regenera o site de todas as partes
  python acervo.py montar                  junta o site de todas as partes (feed.json, det/...)
  python acervo.py baixar --site     também feed.json, feed_links.json, det/ e dados/
  python acervo.py salvar "msg" [arquivos extras do Git...]
  python acervo.py salvar --sem-dados "msg" arquivos...   (só arquivos do Git)

Gravação segura entre coletas simultâneas: cada gravação sobe arquivos com nome
único e só vale quando o commit do ponteiro entra na main (push fast-forward).
Se outra coleta gravou antes, apaga o que subiu, baixa a versão nova, mescla
(mesclar_acervo.py), regenera o site e tenta de novo.
"""
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parent
ROTACAO_ARQ = RAIZ / 'rotacao_quente.json'  # notícias que a rotação tirou da parte quente
PONTEIRO = RAIZ / 'dados_versao.json'
ACERVO = RAIZ / 'noticias.json'
SITE = ['feed.json', 'feed-recente.json', 'feed_links.json', 'det', 'dados']
TAG = 'dados'
REPO = os.environ.get('GITHUB_REPOSITORY', '7773333123/radar-das-apreensoes')
TMP = Path(os.environ.get('RUNNER_TEMP', '/tmp'))


def sh(*cmd, check=True, captura=False):
    r = subprocess.run(cmd, cwd=RAIZ, text=True, capture_output=captura)
    if check and r.returncode:
        raise RuntimeError(f'falhou: {" ".join(cmd)}\n{r.stderr if captura else ""}')
    return r


def ponteiro():
    return json.loads(PONTEIRO.read_text(encoding='utf-8')) if PONTEIRO.exists() else {}


# ---------------------------------------------------------------------------
# Partes do acervo: "quente" (notícias dos últimos CORTE_DIAS dias e as sem data), usada
# pelas coletas do dia; e uma parte por ano ("2025", "2024"...) com o resto, usada pela
# coleta retroativa/histórica daquele ano. Cada parte guarda o próprio acervo e o próprio
# pedaço do site já gerado (feed, links, det/); o site publicado junta as partes
# (scripts/baixar-dados.js e montar_site() abaixo). Assim nenhuma coleta precisa baixar e
# reprocessar os 20 anos inteiros.
CORTE_DIAS = 45
PARTE_ARQ = RAIZ / '.parte'  # parte baixada nesta pasta (lida por salvar e gerar_feed_site.py)


def corte_quente():
    return (datetime.now(timezone.utc) - timedelta(days=CORTE_DIAS)).date().isoformat()


def parte_baixada():
    return PARTE_ARQ.read_text(encoding='utf-8').strip() if PARTE_ARQ.exists() else 'quente'


def info_parte(p, parte):
    if parte == 'quente':
        return {'acervo': p.get('acervo'), 'site': p.get('site')}
    return dict((p.get('partes') or {}).get(parte) or {})


def gravar_info(p, parte, acervo=None, site=None):
    alvo = p if parte == 'quente' else p.setdefault('partes', {}).setdefault(parte, {})
    if acervo:
        alvo['acervo'] = acervo
    if site:
        alvo['site'] = site


def marcador(parte):
    return TMP / f'acervo_versao_baixada_{parte}.txt'


def url(nome):
    return f'https://github.com/{REPO}/releases/download/{TAG}/{nome}'


def baixar_arquivo(nome, destino, tentativas=5):
    for k in range(tentativas):
        try:
            with urlopen(Request(url(nome), headers={'User-Agent': 'radar-acervo'}), timeout=120) as r, open(destino, 'wb') as f:
                shutil.copyfileobj(r, f)
            return
        except OSError as exc:
            if k == tentativas - 1:
                raise
            print(f'Download de {nome} falhou ({exc}); tentando de novo...', flush=True)
            time.sleep(5 * (k + 1))


def baixar_acervo_parte(parte, destino):
    """Acervo de uma parte em `destino` (vazio se a parte ainda não existe). Devolve o nome da versão."""
    info = info_parte(ponteiro(), parte)
    if not info.get('acervo'):
        destino.write_text(json.dumps({'noticias': []}), encoding='utf-8')
        return ''
    gz = TMP / info['acervo']
    baixar_arquivo(info['acervo'], gz)
    with gzip.open(gz, 'rb') as f, open(destino, 'wb') as out:
        shutil.copyfileobj(f, out)
    return info['acervo']


def baixar(site=False, parte='quente'):
    p = ponteiro()
    if parte == 'quente' and not p.get('acervo'):
        raise SystemExit('dados_versao.json sem versão do acervo')
    versao = baixar_acervo_parte(parte, ACERVO)
    marcador(parte).write_text(versao, encoding='utf-8')  # versão de partida desta execução
    PARTE_ARQ.write_text(parte, encoding='utf-8')
    print(f'Acervo baixado ({parte}): {versao or "parte nova, vazia"} ({ACERVO.stat().st_size / 1e6:.1f} MB)')
    if site:
        montar_site()


def montar_site():
    """Baixa o site de todas as partes e junta em feed.json, feed-recente.json, feed_links.json e det/
    (o mesmo que scripts/baixar-dados.js faz no build da Vercel)."""
    p = ponteiro()
    partes = ['quente'] + sorted((p.get('partes') or {}), reverse=True)
    for nome in SITE:
        alvo = RAIZ / nome
        shutil.rmtree(alvo, ignore_errors=True) if alvo.is_dir() else alvo.unlink(missing_ok=True)
    pasta = TMP / 'partes_site'
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True)
    for parte in partes:
        nome = info_parte(p, parte).get('site')
        if not nome:
            continue
        tgz = TMP / nome
        baixar_arquivo(nome, tgz)
        with tarfile.open(tgz) as t:
            t.extractall(pasta, filter='data')
    # Pacote antigo (antes das partes): os arquivos vêm na raiz do pacote.
    if (pasta / 'feed.json').exists():
        for nome in SITE:
            if (pasta / nome).exists():
                shutil.move(str(pasta / nome), str(RAIZ / nome))
        print('Dados do site baixados (pacote único).')
        return
    juntar_partes_site(pasta / 'partes', RAIZ)


def juntar_partes_site(origem, destino):
    feeds, links, det, recente = {}, {}, {}, None
    for d in sorted(origem.iterdir()) if origem.exists() else []:
        if (d / 'feed.json').exists():
            feeds[d.name] = json.loads((d / 'feed.json').read_text(encoding='utf-8'))
        if d.name == 'quente' and (d / 'feed-recente.json').exists():
            recente = (d / 'feed-recente.json').read_text(encoding='utf-8')
        if (d / 'feed_links.json').exists():
            links.update(json.loads((d / 'feed_links.json').read_text(encoding='utf-8')))
        for lote in (d / 'det').glob('*.json') if (d / 'det').exists() else []:
            det.setdefault(lote.name, {}).update(json.loads(lote.read_text(encoding='utf-8')))
    feed = None
    if feeds:
        feed = dict(feeds.get('quente') or next(iter(feeds.values())))
        feed['noticias'] = [n for f in feeds.values() for n in f.get('noticias', [])]
    if feed is None:
        raise SystemExit('nenhuma parte do site encontrada')
    vistos, unicas = set(), []
    for n in feed['noticias']:
        if n.get('i') not in vistos:
            vistos.add(n.get('i'))
            unicas.append(n)
    unicas.sort(key=lambda x: x.get('d', ''), reverse=True)
    feed['noticias'], feed['total'] = unicas, len(unicas)
    (destino / 'feed.json').write_text(json.dumps(feed, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    if recente:
        (destino / 'feed-recente.json').write_text(recente, encoding='utf-8')
    (destino / 'feed_links.json').write_text(json.dumps(links, separators=(',', ':')), encoding='utf-8')
    (destino / 'det').mkdir(exist_ok=True)
    for nome, conteudo in det.items():
        (destino / 'det' / nome).write_text(json.dumps(conteudo, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Site montado das partes: {len(unicas)} notícias')


def _hash(caminho):
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for bloco in iter(lambda: f.read(1 << 20), b''):
            h.update(bloco)
    return h.hexdigest()[:12]


def empacotar(parte='quente'):
    """noticias-<parte>-<hash>.json.gz e site-<parte>-<hash>.tar.gz (site em partes/<parte>/)."""
    carimbo = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    gz = TMP / 'noticias.json.gz'
    with open(ACERVO, 'rb') as f, gzip.open(gz, 'wb', compresslevel=6) as out:
        shutil.copyfileobj(f, out)
    nome_acervo = f'noticias-{parte}-{carimbo}-{_hash(gz)}.json.gz'
    gz = gz.rename(TMP / nome_acervo)
    tgz = TMP / 'site.tar.gz'
    with tarfile.open(tgz, 'w:gz', compresslevel=6) as t:
        for nome in SITE:
            if nome != 'dados' and (RAIZ / nome).exists():
                t.add(RAIZ / nome, arcname=f'partes/{parte}/{nome}')
    nome_site = f'site-{parte}-{carimbo}-{_hash(tgz)}.tar.gz'
    tgz = tgz.rename(TMP / nome_site)
    return gz, tgz


def garantir_release():
    if sh('gh', 'release', 'view', TAG, '--repo', REPO, check=False, captura=True).returncode:
        sh('gh', 'release', 'create', TAG, '--repo', REPO, '--title', 'Dados do Radar (acervo e site)',
           '--notes', 'Arquivos gerados automaticamente pela coleta. A versão em uso está em dados_versao.json.',
           '--latest=false')


def em_uso_todas():
    p = ponteiro()
    nomes = {p.get('acervo'), p.get('site')}
    for info in (p.get('partes') or {}).values():
        nomes |= {info.get('acervo'), info.get('site')}
    return {n for n in nomes if n}


def limpar_antigos(em_uso):
    """Apaga versões antigas (mais de 3 h e fora do ponteiro): outra coleta pode estar subindo a dela."""
    r = sh('gh', 'api', f'repos/{REPO}/releases/tags/{TAG}', captura=True)
    limite = datetime.now(timezone.utc) - timedelta(hours=3)
    apagados = 0
    for a in json.loads(r.stdout).get('assets', []):
        criado = datetime.fromisoformat(a['created_at'].replace('Z', '+00:00'))
        if a['name'] not in em_uso and criado < limite:
            sh('gh', 'api', '-X', 'DELETE', f'repos/{REPO}/releases/assets/{a["id"]}', check=False, captura=True)
            apagados += 1
    if apagados:
        print(f'Versões antigas apagadas da release: {apagados}')


def configurar_git():
    sh('git', 'config', 'user.name', 'github-actions[bot]')
    sh('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')


def versao_remota(parte):
    sh('git', 'fetch', '-q', 'origin', 'main', check=False)
    r = sh('git', 'show', 'origin/main:dados_versao.json', check=False, captura=True)
    try:
        return info_parte(json.loads(r.stdout), parte).get('acervo') if r.returncode == 0 else None
    except ValueError:
        return None


def unir_com_release(parte):
    """Une o acervo desta execução à versão atual da mesma parte na release (nunca perde notícias)."""
    atual = versao_remota(parte)
    base = marcador(parte).read_text(encoding='utf-8').strip() if marcador(parte).exists() else ''
    if (atual or '') == base:
        print(f'Parte {parte} igual à baixada nesta execução: sem nova mesclagem.')
        feed = RAIZ / 'feed.json'
        if not feed.exists() or feed.stat().st_mtime < ACERVO.stat().st_mtime:  # site desatualizado
            sh(sys.executable, 'gerar_feed_site.py')
            sh(sys.executable, 'compactar_acervo.py')
        return
    nossa = TMP / 'noticias_coletadas.json'
    if ACERVO.exists():
        shutil.copy2(ACERVO, nossa)
    sh('git', 'fetch', '-q', 'origin', 'main')
    sh('git', 'show', 'origin/main:dados_versao.json', captura=True)
    PONTEIRO.write_text(sh('git', 'show', 'origin/main:dados_versao.json', captura=True).stdout, encoding='utf-8')
    baixar(parte=parte)
    if nossa.exists():
        sh(sys.executable, 'mesclar_acervo.py', str(nossa))
    sh(sys.executable, 'gerar_feed_site.py')
    sh(sys.executable, 'compactar_acervo.py')


def salvar(msg, extras, sem_dados=False, parte=None):
    parte = parte or parte_baixada()
    if parte != 'quente' and not sem_dados and not ponteiro().get('partes'):
        # Antes da divisão (acervo.py dividir), uma parte de ano gravada sozinha faria a parte
        # quente esconder todas as notícias antigas do site.
        raise SystemExit(f'Acervo ainda não dividido em partes: a parte {parte} não pode ser gravada.')
    configurar_git()
    if not sem_dados:
        garantir_release()
        unir_com_release(parte)
    so_acervo = False  # depois de um conflito na MESMA parte: grava só o acervo mesclado
    gz = tgz = None
    for tentativa in range(1, 9):
        subidos = []
        if not sem_dados:
            if gz is None:  # empacota uma vez; outra parte gravando não muda a nossa
                gz, tgz = empacotar(parte)
                for arq in ((gz,) if so_acervo else (gz, tgz)):
                    sh('gh', 'release', 'upload', TAG, str(arq), '--repo', REPO, '--clobber')
            subidos = [gz.name] + ([] if so_acervo else [tgz.name])
            p = ponteiro()
            gravar_info(p, parte, acervo=gz.name, site=None if so_acervo else tgz.name)
            p['atualizado_em'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
            PONTEIRO.write_text(json.dumps(p, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            sh('git', 'add', PONTEIRO.name)
        for e in extras:
            if (RAIZ / e).exists():
                sh('git', 'add', e)
        if sh('git', 'diff', '--cached', '--quiet', check=False).returncode == 0:
            print('Nada a salvar.')
            return
        sh('git', 'commit', '-q', '-m', msg)
        if sh('git', 'push', '-q', 'origin', 'HEAD:main', check=False).returncode == 0:
            print(f'Salvo ({parte}, tentativa {tentativa}): {", ".join(subidos) or "só arquivos do Git"}')
            if not sem_dados:
                limpar_antigos(em_uso_todas())
                # A release agora é a nossa: o próximo salvar desta execução não precisa mesclar.
                marcador(parte).write_text(gz.name, encoding='utf-8')
            return
        guardados = TMP / 'extras_desta_execucao'
        shutil.rmtree(guardados, ignore_errors=True)
        guardados.mkdir(parents=True)
        for e in extras:
            if (RAIZ / e).exists():
                shutil.copy2(RAIZ / e, guardados / Path(e).name)
        base = marcador(parte).read_text(encoding='utf-8').strip() if marcador(parte).exists() else ''
        mudou_mesma_parte = not sem_dados and (versao_remota(parte) or '') != base
        sh('git', 'fetch', '-q', 'origin', 'main')
        sh('git', 'reset', '-q', '--hard', 'origin/main')
        for e in extras:
            if (guardados / Path(e).name).exists():
                shutil.copy2(guardados / Path(e).name, RAIZ / e)
        if not mudou_mesma_parte:
            # Outra coleta gravou OUTRA parte (ou só arquivos do Git): basta reaplicar o ponteiro.
            print(f'Outra coleta gravou antes (outra parte); regravando o ponteiro (tentativa {tentativa})...', flush=True)
            time.sleep(2 * tentativa)
            continue
        print(f'Outra coleta gravou a mesma parte ({parte}); mesclando (tentativa {tentativa})...', flush=True)
        for nome in subidos:  # o que subimos não vai ser usado
            sh('gh', 'release', 'delete-asset', TAG, nome, '--repo', REPO, '--yes', check=False, captura=True)
        nossa = TMP / 'noticias_desta_execucao.json'
        shutil.copy2(ACERVO, nossa)
        baixar(parte=parte)
        sh(sys.executable, 'mesclar_acervo.py', str(nossa))
        # Regenerar o site leva minutos e, nesse tempo, outra coleta grava de novo (corrida
        # sem fim). Grava só o acervo mesclado; a próxima geração desta parte atualiza o site.
        sh(sys.executable, 'compactar_acervo.py')
        so_acervo = True
        gz = tgz = None
        time.sleep(3 * tentativa)
    raise SystemExit('Não foi possível salvar após 8 tentativas.')


def parte_de_data(data):
    """Parte onde fica uma notícia (ou um mês "AAAA-MM") com esta data."""
    data = str(data or '')
    if not data or data[:10] >= corte_quente()[:len(data[:10])]:
        return 'quente'
    return data[:4]


def _ler(caminho):
    d = json.loads(Path(caminho).read_text(encoding='utf-8'))
    return d, (d['noticias'] if isinstance(d, dict) else d)


def _gravar(caminho, dados):
    Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def _gerar_parte(parte):
    PARTE_ARQ.write_text(parte, encoding='utf-8')
    sh(sys.executable, 'gerar_feed_site.py')
    sh(sys.executable, 'compactar_acervo.py')


def dividir():
    """Migração única: separa o acervo inteiro em parte quente + uma parte por ano."""
    if ponteiro().get('partes'):
        print('O acervo já está dividido em partes.')
        return
    configurar_git()
    garantir_release()
    baixar(parte='quente')
    base_quente = marcador('quente').read_text(encoding='utf-8').strip()
    dados, noticias = _ler(ACERVO)
    corte = corte_quente()
    quentes, por_ano = [], {}
    for n in noticias:
        d = str(n.get('data_iso') or '')[:10] if isinstance(n, dict) else ''
        if not d or d >= corte:
            quentes.append(n)
        else:
            por_ano.setdefault(d[:4], []).append(n)
    p = ponteiro()
    for ano in sorted(por_ano, reverse=True):
        _gravar(ACERVO, {'noticias': por_ano[ano], 'total': len(por_ano[ano])})
        p.setdefault('partes', {})[ano] = {}
        PONTEIRO.write_text(json.dumps(p, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        _gerar_parte(ano)
        gz, tgz = empacotar(ano)
        for arq in (gz, tgz):
            sh('gh', 'release', 'upload', TAG, str(arq), '--repo', REPO, '--clobber')
        gravar_info(p, ano, acervo=gz.name, site=tgz.name)
        print(f'Parte {ano}: {len(por_ano[ano])} notícias', flush=True)
    for tentativa in range(1, 9):
        _gravar(ACERVO, dict(dados, noticias=quentes, total=len(quentes)) if isinstance(dados, dict) else quentes)
        PONTEIRO.write_text(json.dumps(p, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        _gerar_parte('quente')
        gz, tgz = empacotar('quente')
        for arq in (gz, tgz):
            sh('gh', 'release', 'upload', TAG, str(arq), '--repo', REPO, '--clobber')
        gravar_info(p, 'quente', acervo=gz.name, site=tgz.name)
        p['atualizado_em'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        PONTEIRO.write_text(json.dumps(p, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        sh('git', 'add', PONTEIRO.name)
        sh('git', 'commit', '-q', '-m', 'Acervo dividido em partes: recente + um arquivo por ano')
        if sh('git', 'push', '-q', 'origin', 'HEAD:main', check=False).returncode == 0:
            print(f'Acervo dividido: quente {len(quentes)}; anos: ' + ', '.join(f'{a} {len(v)}' for a, v in sorted(por_ano.items())))
            marcador('quente').write_text(gz.name, encoding='utf-8')
            return
        # A coleta rápida gravou o acervo inteiro enquanto dividíamos: entram as notícias
        # recentes que ela trouxe (as antigas já estão nas partes dos anos).
        sh('git', 'fetch', '-q', 'origin', 'main')
        sh('git', 'reset', '-q', '--hard', 'origin/main')
        remoto = ponteiro()
        if remoto.get('acervo') != base_quente:
            tmp = TMP / 'quente_remoto.json'
            base_quente = baixar_acervo_parte('quente', tmp) or base_quente
            import mesclar_acervo
            _, remotas = _ler(tmp)
            indice = {mesclar_acervo.chave(n): n for n in quentes if isinstance(n, dict)}
            for n in remotas:
                if not isinstance(n, dict):
                    continue
                d = str(n.get('data_iso') or '')[:10]
                if d and d < corte:
                    continue
                k = mesclar_acervo.chave(n)
                if k in indice:
                    mesclar_acervo.juntar(indice[k], n)
                else:
                    indice[k] = n
                    quentes.append(n)
        remoto.setdefault('partes', {}).update(p.get('partes', {}))
        p = remoto
        print(f'Outra coleta gravou durante a divisão; mesclando a parte quente (tentativa {tentativa})...', flush=True)
    raise SystemExit('Não foi possível gravar a divisão.')


def rotacionar():
    """Notícias que passaram do corte saem da parte quente e vão para a parte do ano."""
    if not ponteiro().get('partes'):
        print('Acervo ainda não dividido; nada a rotacionar.')
        return
    import mesclar_acervo
    configurar_git()
    garantir_release()
    baixar(parte='quente')
    _, noticias = _ler(ACERVO)
    corte = corte_quente()
    por_ano = {}
    for n in noticias:
        d = str(n.get('data_iso') or '')[:10] if isinstance(n, dict) else ''
        if d and d < corte:
            por_ano.setdefault(d[:4], []).append(n)
    if not por_ano:
        print('Nada a rotacionar.')
        return
    movidas = set()
    for ano, itens in sorted(por_ano.items(), reverse=True):
        baixar(parte=ano)
        dados_ano, ano_lista = _ler(ACERVO)
        indice = {mesclar_acervo.chave(n): n for n in ano_lista if isinstance(n, dict)}
        for n in itens:
            k = mesclar_acervo.chave(n)
            if k in indice:
                mesclar_acervo.juntar(indice[k], n)
            else:
                indice[k] = n
                ano_lista.append(n)
            movidas.add(k)
        _gravar(ACERVO, dict(dados_ano, noticias=ano_lista, total=len(ano_lista)) if isinstance(dados_ano, dict) else ano_lista)
        _gerar_parte(ano)
        salvar(f'Rotação: {len(itens)} notícias para a parte {ano}', [], parte=ano)
        print(f'Parte {ano}: +{len(itens)} notícias', flush=True)
    baixar(parte='quente')
    dados, noticias = _ler(ACERVO)
    restantes = [n for n in noticias if not (isinstance(n, dict) and mesclar_acervo.chave(n) in movidas)]
    _gravar(ACERVO, dict(dados, noticias=restantes, total=len(restantes)) if isinstance(dados, dict) else restantes)
    _gerar_parte('quente')
    # Registro das que saíram (por 3 dias): uma coleta que baixou a parte quente antes desta
    # rotação não as devolve ao gravar (mesclar_acervo.removidas_pela_rotacao).
    hoje = datetime.now(timezone.utc).date().isoformat()
    reg = json.loads(ROTACAO_ARQ.read_text(encoding='utf-8')) if ROTACAO_ARQ.exists() else {}
    limite = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()
    removidas = {h: d for h, d in reg.get('removidas', {}).items() if d >= limite}
    removidas.update({mesclar_acervo.marca(k): hoje for k in movidas})
    ROTACAO_ARQ.write_text(json.dumps({'atualizado_em': hoje, 'removidas': removidas}, separators=(',', ':')) + '\n',
                           encoding='utf-8')
    salvar(f'Rotação: {len(movidas)} notícias saíram da parte quente', [ROTACAO_ARQ.name], parte='quente')


def regenerar_todas(msg):
    """Regra do site mudou: regenera o site de todas as partes (o acervo não muda)."""
    partes = ['quente'] + sorted(ponteiro().get('partes') or {}, reverse=True)
    for parte in partes:
        baixar(parte=parte)
        _gerar_parte(parte)
        salvar(f'{msg} ({parte})', [], parte=parte)


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ('baixar', 'salvar', 'dividir', 'rotacionar', 'regenerar', 'parte-de', 'montar'):
        raise SystemExit(__doc__)
    parte = None
    if '--parte' in args:
        k = args.index('--parte')
        parte = args[k + 1]
        args = args[:k] + args[k + 2:]
    if args[0] == 'baixar':
        baixar(site='--site' in args, parte=parte or 'quente')
    elif args[0] == 'montar':
        montar_site()
    elif args[0] == 'dividir':
        dividir()
    elif args[0] == 'rotacionar':
        rotacionar()
    elif args[0] == 'parte-de':  # parte de um mês/data: python acervo.py parte-de 2025-12
        print(parte_de_data(args[1]))
    elif args[0] == 'regenerar':
        regenerar_todas(args[1] if len(args) > 1 else 'Regenerar o site com a regra atualizada')
    else:
        sem_dados = '--sem-dados' in args
        resto = [a for a in args[1:] if a != '--sem-dados']
        if not resto:
            raise SystemExit('informe a mensagem do commit')
        salvar(resto[0], resto[1:], sem_dados=sem_dados, parte=parte)


if __name__ == '__main__':
    main()
