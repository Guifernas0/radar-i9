#!/bin/bash
# Radar i9+ — uma Coleta agora: busca, resume com a IA, envia os e-mails do dia (se configurados).
source "$(dirname "$0")/scripts/mac/comum.sh"
precisa_uv
titulo "Radar i9+ - Coleta"
mkdir -p logs
uv run radar 2>&1 | tee -a "logs/coleta-$(date +%Y-%m).log"
echo
ok "Coleta terminada. Atualize o Painel no navegador (tecla R ou recarregar) para ver as novidades."
pausa
