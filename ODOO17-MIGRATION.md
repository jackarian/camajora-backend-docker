# Odoo 17 migration notes

Questo file raccoglie lo stato reale della migrazione Odoo 17 del progetto `camajora-backend-docker`, i fix applicati, i moduli esterni aggiunti e le procedure operative per reinstallazione e upgrade.

## Stato attuale

L'istanza locale Odoo 17 si avvia correttamente con:

- `queue_job` caricato come `server_wide_module`
- `multi_step_wizard` installato
- `onchange_helper` installato
- `base_rest` installato
- tutti i moduli `rental*` installati

Moduli verificati come `installed`:

- `rental`
- `rental_api`
- `rental_credits`
- `rental_credits_api`
- `rental_kafka`
- `rental_unlock_api`
- `rental_website`
- `rest_shop`
- `queue_job`
- `multi_step_wizard`
- `onchange_helper`

## Addon esterni integrati

Per rendere installabile la catena di moduli su Odoo 17 sono stati aggiunti come codice versionato nel repository questi sorgenti esterni:

- `external/connector`
- `external/queue`
- `external/rest-framework`
- `external/server-tools`
- `external/server-ux`

Mount attivi in `docker-compose.yml`:

- `./external/connector:/mnt/bundle-addons/connector`
- `./external/queue:/mnt/bundle-addons/queue`
- `./external/rest-framework:/mnt/bundle-addons/rest-framework`
- `./external/server-tools:/mnt/bundle-addons/server-tools`
- `./external/server-ux:/mnt/bundle-addons/server-ux`

`addons_path` effettivo in `odoo/conf/odoo_conf.yaml`:

- `/mnt/bundle-addons/camajora-addons`
- `/mnt/bundle-addons/connector`
- `/mnt/bundle-addons/queue`
- `/mnt/bundle-addons/rest-framework`
- `/mnt/bundle-addons/server-tools`
- `/mnt/bundle-addons/server-ux`

## Fix infrastrutturali applicati

### Runtime Odoo / Docker

- rimosso `version:` obsoleto da `docker-compose.yml`
- esposto `8069` verso nginx (`8069:80`) invece che verso Odoo diretto
- mantenuto `80:80` per accesso standard
- aggiunto reverse proxy websocket `/websocket` verso la porta evented `8072`

### Config Odoo 17

Aggiornati alias e opzioni legacy in `odoo/conf/odoo.cfg.j2`:

- `longpolling_port` -> `gevent_port`
- `osv_memory_age_limit` -> `transient_age_limit`
- `geoip_database` -> `geoip_city_db`

Questo ha risolto il problema:

- `TypeError: '>' not supported between instances of 'int' and 'str'`

### Script generazione config

In `odoo/scripts/generate_odoo_conf.py`:

- `yaml.load()` -> `yaml.safe_load()`

### Line endings

Aggiunto `.gitattributes` per forzare LF su:

- `*.sh`
- `Dockerfile`
- `*.py`
- `*.yml`
- `*.yaml`

Questo evita regressioni sul problema dell'`entrypoint.sh` con CRLF.

## Compatibilità Odoo 17 applicata ai moduli custom

### Fix generali

Sono stati aggiunti `assets: {}` ai manifest custom che ne erano privi, per compatibilità con la pipeline asset di Odoo 17.

Inoltre l'immagine Docker applica una patch difensiva a:

- `/usr/lib/python3/dist-packages/odoo/addons/base/models/ir_asset.py`

per evitare `KeyError: 'assets'` su moduli che non dichiarano la chiave.

### `base_rest`

`external/rest-framework/base_rest/__manifest__.py` è stato adattato per l'uso nel progetto:

- `version` aggiornata a `17.0.1.0.0`
- `installable = True`

### `multi_step_wizard`

Recuperato da OCA `server-ux` 17.0 e reso disponibile come:

- `external/server-ux/multi_step_wizard`

### `queue_job`

Recuperato da OCA `queue` 17.0 e reso disponibile come:

- `external/queue/queue_job`

### `onchange_helper`

Recuperato da OCA `server-tools` 17.0 e reso disponibile come:

- `external/server-tools/onchange_helper`

## Migrazione moduli `rental*`

Per installare i moduli `rental*` su Odoo 17 sono stati corretti diversi problemi di compatibilità.

### View XML Odoo 17

Sono stati convertiti i vecchi attributi:

- `attrs=...`
- `states=...`

nelle espressioni inline supportate da Odoo 17, per esempio:

- `invisible="state != 'draft'"`
- `invisible="not is_credits"`

File principali corretti:

- `addons/camajora-addons/rental/views/rental_booking.xml`
- `addons/camajora-addons/rental/views/rental_booking_slot.xml`
- `addons/camajora-addons/rental/views/res_partner.xml`
- `addons/camajora-addons/rental_credits/views/product_template.xml`
- `addons/camajora-addons/rental_credits/views/res_partner.xml`
- `addons/camajora-addons/rest_shop/views/sale_order.xml`

### Calendar view

Da `rental/views/rental_booking_slot.xml` sono stati rimossi attributi non più validi su Odoo 17:

- `quick_add`
- `event_open_popup`

### Security legacy

Da `rental/security/res_partner.xml` è stato rimosso il delete del vecchio XML ID:

- `base.res_partner_rule_private_employee`

perché non più disponibile nel core attuale.

### API Python legacy

In `rest_shop/models/sale_order.py` sono stati rimossi i decorator legacy:

- `@api.multi`

### Payment refactor Odoo 17

`rest_shop` usava ancora il vecchio modello pagamenti Odoo pre-17.

Allineamenti applicati:

- `payment.acquirer` -> `payment.provider`
- `acquirer_id` -> `provider_id`
- `acquirer_reference` -> `provider_reference`
- ricerca provider Stripe tramite `code = 'stripe'`
- sostituito l'uso di `INT_CURRENCIES` con `payment.utils.to_minor_currency_units`

File aggiornati:

- `addons/camajora-addons/rest_shop/services/stripe.py`
- `addons/camajora-addons/rest_shop/models/payment_acquirer.py`

### Action/view legacy

Da `rest_shop/views/sale_order.xml` sono stati rimossi o aggiornati:

- `view_type` su `ir.actions.act_window`
- xpath non più valido verso `activities_my`

## Comandi operativi consigliati

## Avvio

Usare **sempre** il plugin moderno:

```bash
docker compose up -d
```

Evitare `docker-compose` v1, che su Linux può generare errori del tipo:

- `KeyError: 'ContainerConfig'`

## Rebuild

```bash
docker compose build odoo odoo-init
docker compose up -d odoo
```

## Installazione moduli su DB esistente

```bash
docker compose --profile init run --rm odoo-init run \
  -d odoo_camajora \
  -u multi_step_wizard,queue_job,onchange_helper,base_rest,api_key_auth,api_base,rental,rental_api,rental_credits,rest_shop,rental_credits_api,rental_kafka,rental_unlock_api,rental_website \
  --stop-after-init \
  --db-filter odoo_camajora
```

## Installazione pulita da zero

```bash
docker compose down
docker volume rm camajora-backend-docker_camajora_pgdata_migration_odoo
docker volume rm camajora-backend-docker_camajora_data_migration
docker compose up -d postgres
docker compose --profile init run --rm odoo-init run \
  -d odoo_camajora \
  -i base,multi_step_wizard,queue_job,onchange_helper,base_rest,api_key_auth,api_base,rental,rental_api,rental_credits,rest_shop,rental_credits_api,rental_kafka,rental_unlock_api,rental_website \
  --without-demo=all \
  --stop-after-init \
  --db-filter odoo_camajora
docker compose up -d odoo
```

## Verifiche rapide

Stato container:

```bash
docker compose ps
```

Stato moduli:

```bash
docker compose exec -T postgres psql -U odoo -d odoo_camajora -Atc \
  "select name, state from ir_module_module where name in \
  ('rental','rental_api','rental_credits','rental_credits_api','rental_kafka','rental_unlock_api','rental_website','rest_shop','queue_job','multi_step_wizard','onchange_helper') \
  order by name;"
```

## Limiti residui / note

- l'installazione dei moduli è verificata
- non tutte le funzionalità business end-to-end sono ancora testate manualmente
- `base_rest` continua a loggare un warning di deprecazione upstream OCA
- possono restare warning minori su campi custom legacy (`track_visibility`, typo parametri, ecc.) che non impediscono bootstrap e installazione

## File principali toccati nella migrazione

- `docker-compose.yml`
- `odoo/conf/odoo.cfg.j2`
- `odoo/conf/odoo_conf.yaml`
- `odoo/conf/web/odoo.conf`
- `odoo/scripts/generate_odoo_conf.py`
- `.gitattributes`
- `addons/camajora-addons/rental/views/rental_booking.xml`
- `addons/camajora-addons/rental/views/rental_booking_slot.xml`
- `addons/camajora-addons/rental/views/res_partner.xml`
- `addons/camajora-addons/rental/security/res_partner.xml`
- `addons/camajora-addons/rental_credits/views/product_template.xml`
- `addons/camajora-addons/rental_credits/views/res_partner.xml`
- `addons/camajora-addons/rest_shop/views/sale_order.xml`
- `addons/camajora-addons/rest_shop/services/stripe.py`
- `addons/camajora-addons/rest_shop/models/payment_acquirer.py`
- `addons/camajora-addons/rest_shop/models/sale_order.py`

