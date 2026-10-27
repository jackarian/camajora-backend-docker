# Import SSC resources (ssc-server-iot Flyway V1__init.sql) into the rental module.
#
# Creates or updates (idempotent, via __import__.ssc_* xmlids): availabilities from
# resource_policy, one resource type per SSC resource type, the location from
# networklocation/ssc/door_opener and the resources with their instance.
# Address, coordinates, contacts, owner and credit cost are placeholders set only
# when a record is created: complete them from the backend, re-runs keep them.
#
# Usage (SSC_SQL_PATH defaults to /tmp/V1__init.sql):
#   docker compose run --rm --no-deps -T \
#     -v ~/git/ssc-server-iot/src/main/resources/db/migration/V1__init.sql:/tmp/V1__init.sql:ro \
#     odoo shell -d odoo_camajora < odoo/scripts/import_ssc.py
import os
import re

SQL_PATH = os.environ.get('SSC_SQL_PATH', '/tmp/V1__init.sql')
TABLES = {'networklocation', 'ssc', 'door_opener', 'resource', 'resource_policy', 'resource_door_connection'}
PLACEHOLDER = 'DA COMPLETARE'


def parse_values(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c in ' ,':
            i += 1
        elif c == "'":
            j, buf = i + 1, []
            while True:
                if s[j] == "'" and j + 1 < len(s) and s[j + 1] == "'":
                    buf.append("'"); j += 2
                elif s[j] == "'":
                    break
                else:
                    buf.append(s[j]); j += 1
            out.append(''.join(buf)); i = j + 1
        else:
            m = re.match(r"[^,]+", s[i:])
            tok = m.group(0).strip(); i += m.end()
            if tok == 'NULL': out.append(None)
            elif tok in ('true', 'false'): out.append(tok == 'true')
            elif re.fullmatch(r'-?\d+', tok): out.append(int(tok))
            elif re.fullmatch(r'-?\d+\.\d+', tok): out.append(float(tok))
            else: out.append(tok)
    return out


rows = {t: [] for t in TABLES}
pattern = re.compile(r"^INSERT INTO public\.(\w+) \(([^)]*)\) VALUES \((.*)\);\s*$")
for line in open(SQL_PATH, encoding='utf-8'):
    m = pattern.match(line)
    if m and m.group(1) in TABLES:
        cols = [c.strip() for c in m.group(2).split(',')]
        rows[m.group(1)].append(dict(zip(cols, parse_values(m.group(3)))))


def upsert(name, model, vals, create_only=None):
    xmlid = f'__import__.ssc_{name}'
    rec = env.ref(xmlid, raise_if_not_found=False)
    if rec:
        rec.write(vals)
        return rec, 'updated'
    rec = env[model].create(dict(vals, **(create_only or {})))
    env['ir.model.data'].create({'module': '__import__', 'name': f'ssc_{name}', 'model': model,
                                 'res_id': rec.id, 'noupdate': True})
    return rec, 'created'


def hours(text):
    def to_float(hm):
        h, m = hm.strip().split(':')
        return int(h) + int(m) / 60
    start, end = text.split('-')
    return to_float(start), to_float(end)


DAYS = {'1-7': 'lun-dom', '1-5': 'lun-ven'}
report = []

# Availabilities from resource_policy
availability = {}
for p in rows['resource_policy']:
    start, end = hours(p['hour_of_day'])
    days = DAYS.get(p['day_of_week'].replace(' ', ''), p['day_of_week'])
    rec, op = upsert(f"policy_{p['id']}", 'rental.availability', {
        'name': p['policy_description'],
        'description': f"{days}, {p['hour_of_day']}" + ('' if p['weekend_available'] else ', no weekend'),
        'starthour': start,
        'endhour': end,
    })
    availability[p['id']] = rec
    report.append(f"availability {op}: {rec.name} ({start:g}-{end:g})")

# Resource type: every SSC resource has type CABINA
policies = {r['policy'] for r in rows['resource']}
assert len(policies) == 1, f'resources use different policies: {policies}'
policy_id = next(iter(policies))
types = {}
for type_code in sorted({r['type'] for r in rows['resource']}):
    rec, op = upsert(f"type_{type_code.lower()}", 'rental.resource.type', {
        'name': type_code.capitalize(),
        'description': f'Importata da SSC (type {type_code})',
        'availability_id': availability[policy_id].id,
        'duration_id': env.ref('rental.rental_duration_hourly').id,
    })
    types[type_code] = rec
    report.append(f"type {op}: {rec.name}")

# Location from networklocation + ssc + its door opener
owner = env['res.users'].browse(2).partner_id
italy = env.ref('base.it')
padova = env['res.country.state'].search([('country_id', '=', italy.id), ('code', '=', 'PD')], limit=1)
locations = {}
for nl in rows['networklocation']:
    ssc = next((s for s in rows['ssc'] if s['location_id'] == nl['id']), {})
    door = next((d for d in rows['door_opener'] if d['location'] == nl['id']), {})
    resources = [r for r in rows['resource'] if r['ssc'] == ssc.get('id')]
    rec, op = upsert(f"location_{nl['id']}", 'rental.location', {
        'name': nl['title'],
        'description': f"{ssc.get('name', '')} - {ssc.get('location', '')}",
        'hotspot_name': nl['hotspot_tag'] or '',
        'scc_address': ssc.get('ip_address') or '',
        'scc_endpoint_open_door': door.get('path') or '',
        'scc_endpoint_open_door_protocol': door.get('proto') or '',
        'scc_endpoint_open_door_port': str(door['port']) if door.get('port') else '',
        'ip_device_door_opening': door.get('address') or '',
        'scc_endpoint_resource_activation': nl['ip_address'],
        'scc_endpoint_resource_activation_port': str(nl['ip_port_service'] or ''),
        'opened_from': min(hours(f"{r['start_time_limit'][:5]}-{r['end_time_limit'][:5]}")[0] for r in resources),
        'opened_to': max(hours(f"{r['start_time_limit'][:5]}-{r['end_time_limit'][:5]}")[1] for r in resources),
    }, create_only={
        'partner_id': owner.id,
        'address': PLACEHOLDER,
        'postal_code': '00000',
        'city': 'Padova',
        'state_id': padova.id,
        'country_id': italy.id,
        'latitudo': 0.0,
        'longitudo': 0.0,
    })
    locations[ssc.get('id')] = rec
    report.append(f"location {op}: {rec.name}")

# Resources
with_door = {c['resource'] for c in rows['resource_door_connection']}
for r in sorted(rows['resource'], key=lambda r: r['id']):
    rec, op = upsert(f"resource_{r['id']}", 'rental.resource', {
        'name': r['reference'],
        'description': f"SSC tag {r['tag']}",
        'type_id': types[r['type']].id,
        'location_id': locations[r['ssc']].id,
        'active': r['is_active'],
        'door_present': r['id'] in with_door,
        'modbus_group': r['bus_group_id'],
        'modbus_id': r['output_id'],
        'modbus_plugin': r['driver_type'],
        'api_url': r['url'],
        'api_key': r['api_key'] or False,
        'api_path': r['resource'],
        'plugin_type': r['plugintype'],
    }, create_only={
        'credit_cost': 1,  # must be > 0, set the real cost from the backend
    })
    report.append(f"resource {op}: {rec.name} [{rec.code}] instances={len(rec.instances_ids)} door={rec.door_present}")

env.cr.commit()
print('\n'.join('IMPORT ' + line for line in report))
