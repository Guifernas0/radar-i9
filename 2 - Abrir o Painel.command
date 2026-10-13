#!/bin/bash
# Radar i9+ — abre o Painel no navegador. Deixe esta janela aberta enquanto usa o Painel.
source "$(dirname "$0")/scripts/mac/comum.sh"
precisa_uv
URL="http://localhost:8501"
if curl -s -o /dev/null "$URL"; then
  ok "O Painel ja esta aberto. Abrindo no navegador..."; open "$URL"; exit 0
fi
titulo "Radar i9+ - Painel"
echo "Iniciando... o navegador abre sozinho em alguns segundos."
echo "Deixe ESTA JANELA ABERTA enquanto usa o Painel. Para desligar: feche a janela (ou Control+C)."
echo
( for _ in $(seq 1 60); do sleep 1; curl -s -o /dev/null "$URL" && { open "$URL"; break; }; done ) &
exec uv run streamlit run painel.py --server.headless true --server.port 8501 --server.address localhost  # so este Mac acessa
