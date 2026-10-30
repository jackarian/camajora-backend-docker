#!/bin/bash
# Preparazione una tantum di iot-casa.back-iot.it, da lanciare con sudo:
#   sudo bash setup-server.sh
# Installa Docker, mette giacomo nel gruppo docker, abilita i moduli Apache e il virtual host,
# crea la cartella del frontend. I certificati si chiedono dopo, quando i DNS sono attivi.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi
# rsync serve per copiare la build del frontend
apt-get install -y rsync
usermod -aG docker giacomo

a2enmod proxy proxy_http proxy_wstunnel headers rewrite ssl
install -d -o giacomo -g www-data -m 0755 /var/www/padova-frontend-stage
install -m 0644 apache/padova-stage.conf /etc/apache2/sites-available/padova-stage.conf
a2ensite padova-stage
apache2ctl configtest
systemctl reload apache2

echo
echo "Fatto. Esci e rientra perché il gruppo docker valga per giacomo."
echo "Quando i DNS puntano qui:"
echo "  sudo certbot --apache -d padova-stage-backend.back-iot.it -d padova-frontend-stage.back-iot.it --redirect"
