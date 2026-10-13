#!/bin/bash
# Radar i9+ — agenda uma Coleta por dia neste Mac (launchd, o agendador do proprio macOS).
source "$(dirname "$0")/scripts/mac/comum.sh"
precisa_uv
titulo "Radar i9+ - coleta diaria automatica"
if pasta_protegida; then
  erro "A pasta do Radar esta em Mesa/Documentos/Downloads/iCloud."
  echo "O macOS nao deixa tarefas agendadas lerem essas pastas, e a coleta falharia calada."
  echo "Mova a pasta 'radar-i9' para a sua pasta pessoal (Finder > Ir > Inicio) e rode este arquivo de novo de la."
  pausa; exit 1
fi
read -r -p "Que horas a coleta deve rodar? (0 a 23) [8] " HORA
HORA="${HORA:-8}"
if ! [[ "$HORA" =~ ^[0-9]+$ ]] || [ "$HORA" -gt 23 ]; then erro "Hora invalida: $HORA"; pausa; exit 1; fi

ROTULO="br.inovemais.radar-i9.coleta"
PLIST="$HOME/Library/LaunchAgents/$ROTULO.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$RADAR_DIR/logs"
esc() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$ROTULO</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$(esc "$RADAR_DIR/scripts/mac/coleta-agendada.sh")</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>$HORA</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$(esc "$RADAR_DIR/logs/agendador.log")</string>
  <key>StandardErrorPath</key><string>$(esc "$RADAR_DIR/logs/agendador.log")</string>
</dict>
</plist>
PL
launchctl bootout "gui/$(id -u)/$ROTULO" 2>/dev/null
if launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load -w "$PLIST" 2>/dev/null; then
  ok "Agendado: todo dia as ${HORA}h00."
  echo "Se o Mac estiver dormindo nesse horario, a coleta roda quando ele acordar. Desligado, pula o dia."
  echo "Historico das coletas agendadas: pasta logs/ do Radar."
  echo "Para cancelar: scripts/mac/remover-agendamento.command"
else
  erro "Nao consegui registrar o agendamento no macOS."
fi
pausa
