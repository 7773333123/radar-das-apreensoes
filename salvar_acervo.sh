#!/usr/bin/env bash
# Grava o acervo na main. Se outra coleta tiver gravado antes (envio recusado),
# mescla as duas versões (mesclar_acervo.py), regenera o site e tenta de novo.
# Uso: bash salvar_acervo.sh "mensagem do commit" [arquivos extras...]
set -euo pipefail
MSG="$1"; shift || true
EXTRAS=("$@")
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'

preparar() {
  git add noticias.json feed.json feed_links.json
  for f in analise_nacional.json cobertura_historica.json "${EXTRAS[@]}"; do [ -e "$f" ] && git add "$f"; done
  for pasta in detalhes textos dados; do git add -A -- "$pasta" 2>/dev/null || true; done
}

preparar
if git diff --cached --quiet; then echo 'Nenhuma alteração a salvar.'; exit 0; fi
git commit -q -m "$MSG"
for tentativa in 1 2 3 4; do
  if git push -q origin HEAD:main; then echo "Acervo salvo (tentativa $tentativa)."; exit 0; fi
  echo "Outra coleta gravou antes; mesclando (tentativa $tentativa)..."
  NOSSA="$RUNNER_TEMP/noticias_desta_execucao.json"
  git show HEAD:noticias.json > "$NOSSA"
  EXTRA_SALVOS="$RUNNER_TEMP/extras"; rm -rf "$EXTRA_SALVOS"; mkdir -p "$EXTRA_SALVOS"
  for f in "${EXTRAS[@]}"; do [ -e "$f" ] && cp "$f" "$EXTRA_SALVOS/"; done
  git fetch -q origin main
  git reset -q --hard origin/main
  for f in "${EXTRAS[@]}"; do [ -e "$EXTRA_SALVOS/$(basename "$f")" ] && cp "$EXTRA_SALVOS/$(basename "$f")" "$f"; done
  python mesclar_acervo.py "$NOSSA"
  python gerar_feed_site.py
  python compactar_acervo.py
  preparar
  git diff --cached --quiet && { echo 'Nada novo após mesclar.'; exit 0; }
  git commit -q -m "$MSG"
  sleep $((tentativa * 5))
done
echo 'Não foi possível salvar após 4 tentativas.' >&2
exit 1
