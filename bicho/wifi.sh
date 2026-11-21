#!/usr/bin/env bash
# Conecta el bicho a otra red WiFi (por ejemplo, el router del equipo) y la deja como preferida.
# La clave se escribe al correrlo: no queda en el repo ni en el historial.
#
#   sudo ./wifi.sh                        # muestra a qué red está, qué redes ve y cuáles tiene guardadas
#   sudo ./wifi.sh "NombreDeLaRed"        # la agrega como preferida y se cambia a ella
#   sudo ./wifi.sh "NombreDeLaRed" --despues   # la agrega, pero se cambia recién al reiniciar
#
# Las redes que ya tenía (el hotspot) quedan guardadas como respaldo: si el router se apaga, vuelve a ellas solo.
# Ojo: el Raspberry Pi 3 solo ve redes de 2.4 GHz.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Córrelo con sudo: sudo ./wifi.sh" >&2
  exit 1
fi
if ! command -v nmcli >/dev/null; then
  echo "Este Pi no usa NetworkManager (nmcli). Hay que configurar el WiFi con sudo raspi-config." >&2
  exit 1
fi

SSID="${1:-}"
DESPUES=""
[[ "${2:-}" == "--despues" ]] && DESPUES=1

ver() {
  echo "Conectado a:"
  nmcli -t -f TYPE,STATE,CONNECTION dev | awk -F: '$2=="connected" && $1!="loopback" {print "  " $1 ": " $3}'
  echo "IP: $(hostname -I | awk '{print $1}')   ·   http://$(hostname).local:8080"
  echo
  echo "Redes guardadas (la de prioridad más alta gana):"
  nmcli -t -f NAME,TYPE,AUTOCONNECT-PRIORITY con show |
    awk -F: '$2=="802-11-wireless" {printf "  %-28s prioridad %s\n", $1, $3}'
}

redes_visibles() {
  nmcli dev wifi rescan 2>/dev/null || true
  sleep 4
  nmcli -t -f SSID,SIGNAL,CHAN dev wifi list | awk -F: '$1!="" {print}' | sort -t: -k1,1 -u
}

if [[ -z "$SSID" ]]; then
  ver
  echo
  echo "Redes que ve ahora (nombre · señal · canal):"
  redes_visibles | awk -F: '{printf "  %-28s %3s%%  canal %s\n", $1, $2, $3}'
  exit 0
fi

echo "→ Buscando «$SSID»…"
VISIBLES="$(redes_visibles | cut -d: -f1)"
if ! grep -Fxq -- "$SSID" <<<"$VISIBLES"; then
  echo "✘ El Pi no ve la red «$SSID»." >&2
  echo "  El Pi 3 solo ve 2.4 GHz: revisa que el router tenga prendida la banda de 2.4 GHz" >&2
  echo "  (y, si separa las bandas, usa el nombre de la de 2.4 GHz). Redes que sí ve:" >&2
  sed 's/^/    /' <<<"$VISIBLES" >&2
  exit 1
fi

read -rsp "Clave de «$SSID»: " PSK
echo
if [[ ${#PSK} -lt 8 ]]; then
  echo "✘ Una clave WPA tiene al menos 8 caracteres." >&2
  exit 1
fi

# Si ya estaba guardada, se actualiza; si no, se crea. Prioridad 50: le gana al hotspot (0).
GUARDADAS="$(nmcli -t -f NAME con show)"
if grep -Fxq -- "$SSID" <<<"$GUARDADAS"; then
  nmcli con modify "$SSID" 802-11-wireless.ssid "$SSID" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK" \
    connection.autoconnect yes connection.autoconnect-priority 50
else
  nmcli con add type wifi ifname wlan0 con-name "$SSID" ssid "$SSID" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK" \
    connection.autoconnect yes connection.autoconnect-priority 50 >/dev/null
fi
unset PSK
echo "✔ «$SSID» quedó guardada como red preferida."

if [[ -n "$DESPUES" ]]; then
  echo "  Se cambia sola la próxima vez que el Pi se reinicie: sudo reboot"
  exit 0
fi

# El cambio corre aparte: si estás por SSH a través del hotspot, la sesión se corta, pero el cambio sigue.
# Si no logra conectarse (clave mala, router lejos), vuelve a la red en la que estaba.
ANTES="$(nmcli -t -f NAME,TYPE con show --active | awk -F: '$2=="802-11-wireless" {print $1; exit}')"
LOG=/var/log/bicho-wifi.log
NUEVA="$SSID" ANTES="$ANTES" setsid bash -c '
  sleep 2
  echo "$(date "+%F %T") cambiando a $NUEVA (antes: ${ANTES:-ninguna})"
  if nmcli --wait 40 con up "$NUEVA"; then
    echo "$(date "+%F %T") conectado a $NUEVA, IP $(hostname -I | cut -d" " -f1)"
  else
    echo "$(date "+%F %T") no se pudo conectar a $NUEVA"
    [[ -n "$ANTES" ]] && nmcli con up "$ANTES" && echo "$(date "+%F %T") de vuelta en $ANTES"
  fi
' >>"$LOG" 2>&1 </dev/null &

echo "→ Cambiándose a «$SSID». Si estás por SSH, la sesión se va a cortar en unos segundos."
echo "  Conecta tu computador a «$SSID» y entra de nuevo: ssh $(logname 2>/dev/null || echo "$SUDO_USER")@$(hostname).local"
echo "  Qué pasó: cat $LOG   ·   En bicho·dev, la línea «Red» del bicho debe decir «WiFi: $SSID»."
