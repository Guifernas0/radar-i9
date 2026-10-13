# Radar i9+ — trechos usados por todos os .command do Mac. Não precisa abrir este arquivo.
RADAR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$RADAR_DIR" || exit 1
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONUTF8=1

titulo() { printf '\n\033[1;34m== %s ==\033[0m\n\n' "$1"; }
ok()     { printf '\033[32m%s\033[0m\n' "$1"; }
aviso()  { printf '\033[33m%s\033[0m\n' "$1"; }
erro()   { printf '\033[31m%s\033[0m\n' "$1"; }
pausa()  { echo; read -n 1 -s -r -p "Aperte qualquer tecla para fechar esta janela..."; echo; }

precisa_uv() {
  if ! command -v uv >/dev/null 2>&1 || [ ! -d "$RADAR_DIR/.venv" ]; then
    erro "O Radar ainda nao foi instalado neste Mac."
    echo "De duplo clique em '1 - Instalar.command' primeiro."
    pausa; exit 1
  fi
}

pasta_protegida() {  # o macOS impede tarefas agendadas de ler Mesa, Documentos, Downloads e iCloud
  case "$RADAR_DIR" in
    "$HOME/Desktop"*|"$HOME/Documents"*|"$HOME/Downloads"*|"$HOME/Library/Mobile Documents"*) return 0 ;;
  esac
  return 1
}
