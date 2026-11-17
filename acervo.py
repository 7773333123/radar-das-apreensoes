#!/usr/bin/env python3
"""Acervo e dados do site guardados numa Release do GitHub, fora do histórico do Git.

Antes, noticias.json (38 MB) e os arquivos gerados (feed, det/, dados/) eram
regravados no Git a cada 20 minutos, e o repositório crescia ~80 MB por dia.
Agora ficam como arquivos da release "dados" (que não acumulam histórico), e o
Git guarda só dados_versao.json, um ponteiro com o nome da versão atual.

  python acervo.py baixar            noticias.json da versão atual
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
PONTEIRO = RAIZ / 'dados_versao.json'
ACERVO = RAIZ / 'noticias.json'
SITE = ['feed.json', 'feed-recente.json', 'feed_links.json', 'det', 'dados']
TAG = 'dados'
REPO = os.environ.get('GITHUB_REPOSITORY', '7773333123/radar-das-apreensoes')
TMP = Path(os.environ.get('RUNNER_TEMP', '/tmp'))
BAIXADO = TMP / 'acervo_versao_baixada.txt'


def sh(*cmd, check=True, captura=False):
    r = subprocess.run(cmd, cwd=RAIZ, text=True, capture_output=captura)
    if check and r.returncode:
        raise RuntimeError(f'falhou: {" ".join(cmd)}\n{r.stderr if captura else ""}')
    return r


def ponteiro():
    return json.loads(PONTEIRO.read_text(encoding='utf-8')) if PONTEIRO.exists() else {}


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


def baixar(site=False):
    p = ponteiro()
    if not p.get('acervo'):
        raise SystemExit('dados_versao.json sem versão do acervo')
    gz = TMP / p['acervo']
    baixar_arquivo(p['acervo'], gz)
    with gzip.open(gz, 'rb') as f, open(ACERVO, 'wb') as out:
        shutil.copyfileobj(f, out)
    BAIXADO.write_text(p['acervo'], encoding='utf-8')  # versão de partida desta execução
    print(f'Acervo baixado: {p["acervo"]} ({ACERVO.stat().st_size / 1e6:.1f} MB)')
    if site and p.get('site'):
        tgz = TMP / p['site']
        baixar_arquivo(p['site'], tgz)
        for nome in SITE:
            alvo = RAIZ / nome
            shutil.rmtree(alvo, ignore_errors=True) if alvo.is_dir() else alvo.unlink(missing_ok=True)
        with tarfile.open(tgz) as t:
            t.extractall(RAIZ, filter='data')
        print(f'Dados do site baixados: {p["site"]}')


def _hash(caminho):
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for bloco in iter(lambda: f.read(1 << 20), b''):
            h.update(bloco)
    return h.hexdigest()[:12]


def empacotar():
    """noticias-<hash>.json.gz e site-<hash>.tar.gz com nomes únicos."""
    carimbo = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    gz = TMP / 'noticias.json.gz'
    with open(ACERVO, 'rb') as f, gzip.open(gz, 'wb', compresslevel=6) as out:
        shutil.copyfileobj(f, out)
    nome_acervo = f'noticias-{carimbo}-{_hash(gz)}.json.gz'
    gz = gz.rename(TMP / nome_acervo)
    tgz = TMP / 'site.tar.gz'
    with tarfile.open(tgz, 'w:gz', compresslevel=6) as t:
        for nome in SITE:
            if (RAIZ / nome).exists():
                t.add(RAIZ / nome, arcname=nome)
    nome_site = f'site-{carimbo}-{_hash(tgz)}.tar.gz'
    tgz = tgz.rename(TMP / nome_site)
    return gz, tgz


def garantir_release():
    if sh('gh', 'release', 'view', TAG, '--repo', REPO, check=False, captura=True).returncode:
        sh('gh', 'release', 'create', TAG, '--repo', REPO, '--title', 'Dados do Radar (acervo e site)',
           '--notes', 'Arquivos gerados automaticamente pela coleta. A versão em uso está em dados_versao.json.',
           '--latest=false')


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


def unir_com_release():
    """Une o acervo desta execução à versão atual da release (nunca perde notícias).

    Protege contra execuções que coletaram a partir de um acervo antigo ou
    incompleto: o resultado é sempre a união das duas versões.
    """
    if not ponteiro().get('acervo'):
        return
    # Ninguém gravou desde que esta execução baixou o acervo: não há o que unir
    # (evita baixar, mesclar e gerar o site de novo a cada rodada: ~2,5 min).
    sh('git', 'fetch', '-q', 'origin', 'main', check=False)
    r = sh('git', 'show', 'origin/main:dados_versao.json', check=False, captura=True)
    try:
        atual = json.loads(r.stdout).get('acervo') if r.returncode == 0 else None
    except ValueError:
        atual = None
    if atual and BAIXADO.exists() and BAIXADO.read_text(encoding='utf-8').strip() == atual:
        print('Acervo da release igual ao baixado nesta execução: sem nova mesclagem.')
        feed = RAIZ / 'feed.json'
        if not feed.exists() or feed.stat().st_mtime < ACERVO.stat().st_mtime:  # site desatualizado
            sh(sys.executable, 'gerar_feed_site.py')
            sh(sys.executable, 'compactar_acervo.py')
        return
    nossa = TMP / 'noticias_coletadas.json'
    if ACERVO.exists():
        shutil.copy2(ACERVO, nossa)
    baixar()
    if nossa.exists():
        sh(sys.executable, 'mesclar_acervo.py', str(nossa))
    sh(sys.executable, 'gerar_feed_site.py')
    sh(sys.executable, 'compactar_acervo.py')


def salvar(msg, extras, sem_dados=False):
    configurar_git()
    if not sem_dados:
        garantir_release()
        unir_com_release()
    for tentativa in range(1, 7):
        subidos = []
        if not sem_dados:
            gz, tgz = empacotar()
            for arq in (gz, tgz):
                sh('gh', 'release', 'upload', TAG, str(arq), '--repo', REPO)
                subidos.append(arq.name)
            p = ponteiro()
            p.update(acervo=gz.name, site=tgz.name, atualizado_em=datetime.now(timezone.utc).isoformat(timespec='seconds'))
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
            print(f'Salvo (tentativa {tentativa}): {", ".join(subidos) or "só arquivos do Git"}')
            if not sem_dados:
                limpar_antigos({ponteiro()['acervo'], ponteiro()['site']})
            return
        print(f'Outra coleta gravou antes; mesclando (tentativa {tentativa})...', flush=True)
        for nome in subidos:  # o que subimos não vai ser usado
            sh('gh', 'release', 'delete-asset', TAG, nome, '--repo', REPO, '--yes', check=False, captura=True)
        guardados = TMP / 'extras_desta_execucao'
        shutil.rmtree(guardados, ignore_errors=True)
        guardados.mkdir(parents=True)
        for e in extras:
            if (RAIZ / e).exists():
                shutil.copy2(RAIZ / e, guardados / Path(e).name)
        nossa = TMP / 'noticias_desta_execucao.json'
        if not sem_dados:
            shutil.copy2(ACERVO, nossa)
        sh('git', 'fetch', '-q', 'origin', 'main')
        sh('git', 'reset', '-q', '--hard', 'origin/main')
        for e in extras:
            if (guardados / Path(e).name).exists():
                shutil.copy2(guardados / Path(e).name, RAIZ / e)
        if not sem_dados:
            if ponteiro().get('acervo'):
                baixar()  # senão (migração), vale o noticias.json que ainda está no Git
            sh(sys.executable, 'mesclar_acervo.py', str(nossa))
            sh(sys.executable, 'gerar_feed_site.py')
            sh(sys.executable, 'compactar_acervo.py')
        time.sleep(3 * tentativa)
    raise SystemExit('Não foi possível salvar após 6 tentativas.')


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ('baixar', 'salvar'):
        raise SystemExit(__doc__)
    if args[0] == 'baixar':
        baixar(site='--site' in args)
        return
    sem_dados = '--sem-dados' in args
    resto = [a for a in args[1:] if a != '--sem-dados']
    if not resto:
        raise SystemExit('informe a mensagem do commit')
    salvar(resto[0], resto[1:], sem_dados=sem_dados)


if __name__ == '__main__':
    main()
