#!/bin/bash
# Chamado pelo launchd todo dia (ver "4 - Agendar coleta diaria.command"). Nao precisa rodar na mao.
source "$(dirname "$0")/comum.sh"
mkdir -p logs
{ echo "===== $(date '+%d/%m/%Y %H:%M') ====="; uv run radar; } >> "logs/coleta-$(date +%Y-%m).log" 2>&1
