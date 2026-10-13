#!/bin/bash
# Radar i9+ — cancela a coleta diaria automatica.
source "$(dirname "$0")/comum.sh"
ROTULO="br.inovemais.radar-i9.coleta"
launchctl bootout "gui/$(id -u)/$ROTULO" 2>/dev/null || launchctl unload -w "$HOME/Library/LaunchAgents/$ROTULO.plist" 2>/dev/null
rm -f "$HOME/Library/LaunchAgents/$ROTULO.plist"
ok "Coleta diaria cancelada. O Painel e o historico continuam iguais."
pausa
