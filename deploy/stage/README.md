# Ambiente di test di Padova

Odoo e mude-app pubblici, perché il cliente possa prenotare e provare i QR sul totem di Padova
(SSC 1.13, `totem.padova`).

| Servizio | Dominio | Nel compose |
|---|---|---|
| Odoo (API `/api/v1`, backend) | `padova-stage-backend.back-iot.it` | `odoo` su `127.0.0.1:8069` |
| mude-app (frontend) | `padova-frontend-stage.back-iot.it` | file statici in `/var/www/padova-frontend-stage` |

Server: `iot-casa.back-iot.it` (65.21.160.244). Apache con certbot occupa già 80 e 443
(`dashboard.back-iot.it` → Node-RED): i due domini sono virtual host in più
(`apache/padova-stage.conf`), con i certificati di certbot.

## DNS

Due record A verso il server:

```
padova-stage-backend.back-iot.it.   A   65.21.160.244
padova-frontend-stage.back-iot.it.  A   65.21.160.244
```

Con i DNS propagati: `sudo certbot --apache -d padova-stage-backend.back-iot.it -d padova-frontend-stage.back-iot.it --redirect`.

## File sul server (cartella `~/camajora-stage`)

- `docker-compose.yml`, `setup-server.sh`, `apache/` (questa cartella);
- `.env` da `env.example`, con le password (mai nel repo).

Una tantum, con sudo: `sudo bash setup-server.sh` (Docker, gruppo docker per giacomo, moduli e
virtual host di Apache, cartella del frontend).

## Passi

1. **Immagine Odoo**, senza Docker Hub (il codice degli addon non va pubblicato):
   ```
   docker build -t mudesrl/service.back-iot:1.1 ~/git/camajora-backend-docker
   docker save mudesrl/service.back-iot:1.1 | gzip | ssh giacomo@iot-casa.back-iot.it 'gunzip | docker load'
   ```
2. **Frontend**: la build legge le variabili dalla shell, che hanno la precedenza su `.env.local`.
   `npm run build` non rigenera il CSS: va lanciato prima `build:css`.
   ```
   cd ~/git/mude_app/app-main
   npm run build:css
   REACT_APP_BACKEND_HOST=https://padova-stage-backend.back-iot.it/api/v1 \
   REACT_APP_GOOGLE_MAPS_API_KEY=<chiave> npm run build
   rsync -a --delete build/ giacomo@iot-casa.back-iot.it:/var/www/padova-frontend-stage/
   ```
   Il dominio del frontend va aggiunto ai referrer della chiave Google Maps.
3. **Database**: dump del DB locale `odoo_camajora` con i dati già presenti, e del
   filestore (`/var/lib/odoo/filestore/odoo_camajora`), poi restore nei volumi `pgdata` e `odoo_data`.
4. **Avvio**: `docker compose up -d` in `~/camajora-stage`.
5. **Odoo**: `web.base.url` = `https://padova-stage-backend.back-iot.it`; `scc_address` della sede
   di Padova; dati aziendali.
6. **SSC sul totem**: dalla pagina "Provider QR" un provider con URL
   `https://padova-stage-backend.back-iot.it`, endpoint `/api/v1/unlock` e l'API key di Odoo di
   test, assegnato alla sede di Padova. Il codice sede restituito da Odoo deve coincidere con il
   riferimento della sede in SSC.
