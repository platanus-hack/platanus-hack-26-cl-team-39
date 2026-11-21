#!/usr/bin/env bash
# Instala bichod en el Raspberry Pi como servicio. Se corre una sola vez, desde esta carpeta:
#
#   sudo ./install.sh                     # deja el hostname como está
#   sudo ./install.sh --hostname bicho    # además lo renombra, para entrar por bicho.local
#
# Después las versiones nuevas llegan desde bicho·dev por WiFi; no hace falta volver a correrlo.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Córrelo con sudo: sudo ./install.sh" >&2
  exit 1
fi

NEW_HOSTNAME=""
if [[ "${1:-}" == "--hostname" && -n "${2:-}" ]]; then NEW_HOSTNAME="$2"; fi

HERE="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR=/opt/bicho
RUN_USER="${SUDO_USER:-pi}"
VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$HERE/version.json")"

echo "→ Instalando bichod v$VERSION en $HOME_DIR (usuario $RUN_USER)"
apt-get install -y -qq python3-venv >/dev/null

mkdir -p "$HOME_DIR/releases"
rm -rf "$HOME_DIR/releases/$VERSION"
mkdir -p "$HOME_DIR/releases/$VERSION"
cp "$HERE"/*.py "$HERE"/version.json "$HERE"/requirements.txt "$HOME_DIR/releases/$VERSION/"
ln -sfn "releases/$VERSION" "$HOME_DIR/current"

# venv con los paquetes del sistema (gpiozero, etc.) para que pip pueda instalar extras
if [[ ! -x "$HOME_DIR/venv/bin/python" ]]; then
  python3 -m venv --system-site-packages "$HOME_DIR/venv"
fi
if grep -qvE '^\s*(#|$)' "$HERE/requirements.txt"; then
  "$HOME_DIR/venv/bin/pip" install -q -r "$HERE/requirements.txt"
fi
chown -R "$RUN_USER": "$HOME_DIR"
# acceso a GPIO e I2C sin sudo
usermod -aG gpio,i2c "$RUN_USER" 2>/dev/null || true

# WiFi siempre despierto: con el ahorro de energía del Pi 3 la conexión al relé se queda muda de a ratos
if [[ -d /etc/NetworkManager/conf.d ]]; then
  printf '[connection]\nwifi.powersave = 2\n' > /etc/NetworkManager/conf.d/bicho-wifi-despierto.conf
fi
iw dev wlan0 set power_save off 2>/dev/null || true

if [[ -n "$NEW_HOSTNAME" ]]; then
  echo "→ Hostname: $NEW_HOSTNAME (quedará en http://$NEW_HOSTNAME.local:8080)"
  OLD="$(hostname)"
  hostnamectl set-hostname "$NEW_HOSTNAME"
  sed -i "s/\b$OLD\b/$NEW_HOSTNAME/g" /etc/hosts
  systemctl restart avahi-daemon 2>/dev/null || true
fi

cat > /etc/systemd/system/bichod.service <<EOF
[Unit]
Description=bichod (agente del bicho)
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
Environment=BICHO_HOME=$HOME_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$HOME_DIR/venv/bin/python $HOME_DIR/current/bichod.py
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now bichod
systemctl restart bichod

echo "✔ Listo. bichod corre en http://$(hostname).local:8080"
echo "  Logs: journalctl -u bichod -f"
