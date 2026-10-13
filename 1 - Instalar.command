#!/bin/bash
# Radar i9+ — instala tudo (uma vez só). Precisa de internet. Leva 1 a 3 minutos.
source "$(dirname "$0")/scripts/mac/comum.sh"
titulo "Radar i9+ - instalacao"

# os outros .command vieram da internet: libera o duplo clique neles
xattr -dr com.apple.quarantine "$RADAR_DIR" 2>/dev/null
chmod +x "$RADAR_DIR"/*.command "$RADAR_DIR"/scripts/mac/*.sh 2>/dev/null

if ! command -v uv >/dev/null 2>&1; then
  echo "Instalando o uv (gerenciador de Python, da Astral)..."
  if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
    erro "Nao consegui baixar o uv. Confira a internet e tente de novo."; pausa; exit 1
  fi
  export PATH="$HOME/.local/bin:$PATH"
fi
ok "uv $(uv --version | cut -d' ' -f2) pronto."

echo "Instalando o Python 3.13 e as bibliotecas do Radar (so na pasta do Radar, nao mexe no resto do Mac)..."
if ! uv sync; then
  erro "A instalacao das bibliotecas falhou. Veja a mensagem acima."; pausa; exit 1
fi

mkdir -p "$HOME/.streamlit"
[ -f "$HOME/.streamlit/credentials.toml" ] || printf '[general]\nemail = ""\n' > "$HOME/.streamlit/credentials.toml"
[ -f "$RADAR_DIR/.env" ] || cp "$RADAR_DIR/.env.example" "$RADAR_DIR/.env"
mkdir -p "$RADAR_DIR/logs"

echo "Conferindo..."
if uv run pytest -q 2>&1 | tail -1 | grep -q passed; then ok "Testes do Radar: todos passaram."; else aviso "Algum teste falhou (rode 'uv run pytest' para ver). O Painel deve abrir mesmo assim."; fi

titulo "Pronto!"
echo "Proximos passos:"
echo "  2 - Abrir o Painel.command     -> abre o Radar no navegador"
echo "  Painel > aba Configuracoes     -> cole a chave gratis do Gemini (aistudio.google.com/apikey)"
echo "  3 - Coletar agora.command      -> busca as noticias de hoje (ou o botao 'Coletar agora' no Painel)"
echo "  4 - Agendar coleta diaria      -> o Mac coleta sozinho todo dia"
if pasta_protegida; then
  echo
  aviso "Atencao: a pasta do Radar esta em Mesa/Documentos/Downloads/iCloud."
  aviso "Funciona para usar na mao, mas para AGENDAR a coleta diaria mova a pasta para a sua pasta pessoal"
  aviso "(Finder > Ir > Inicio) antes de rodar o '4 - Agendar coleta diaria'."
fi
echo
read -r -p "Abrir o Painel agora? [S/n] " r
if [[ ! "$r" =~ ^[nN] ]]; then exec "$RADAR_DIR/2 - Abrir o Painel.command"; fi
pausa
