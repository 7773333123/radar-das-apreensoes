#!/usr/bin/env bash
# Compatibilidade: a gravação agora é feita por acervo.py (acervo e dados do site
# na release "dados" do GitHub, fora do histórico do Git).
# Uso: bash salvar_acervo.sh "mensagem do commit" [arquivos extras...]
set -euo pipefail
exec python acervo.py salvar "$@"
