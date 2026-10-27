# Copyright 2020 Metadonors srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import pytz

from odoo import fields
from odoo.addons.component.core import Component
from odoo.exceptions import MissingError

SSC_TIMEZONE = pytz.timezone('Europe/Rome')


class UnlockService(Component):
    _inherit = 'base.rest.private.service'
    _name = 'unlock.service'
    _usage = 'unlock'
    _description = 'Camajora private services: unlock Resource by token'

    def create(self, token):
        """
        Get booking slot informations from booking token
        """
        return self._to_json(self._get_slots(token))

    def search(self, itemid, key=None):
        """
        Get the booking slot for a token in the format of the SSC server
        (GET ?key=&itemid=<token>): a single slot, with local Europe/Rome dates
        """
        slots = self._get_slots(itemid)
        slot = slots.filtered(lambda s: s.dt_end >= fields.Datetime.now())[:1] or slots[:1]
        data = self._serialize(slot)
        for name in ('dt_start', 'dt_end'):
            data[name] = pytz.utc.localize(data[name]).astimezone(SSC_TIMEZONE).strftime('%Y-%m-%dT%H:%M:%S')
        return {
            'count': len(slots),
            'results': data,
        }

    # PRIVATE METHODS

    def _get_slots(self, token):
        booking_slot_ids = self.env['rental.booking.slot'].sudo().search([
            ('booking_id.state', '=', 'confirmed'),
            ('booking_id.token', '=', token),
        ])

        if not booking_slot_ids:
            raise MissingError('Invalid or expired token')

        return booking_slot_ids

    def _to_json(self, payload):
        data = payload or []
        return {
            'count': len(data),
            'results': [self._serialize(record_id) for record_id in data],
        }

    def _serialize(self, record):
        data = {}
        data['dt_start'] = record.dt_start
        data['dt_end'] = record.dt_end
        data['resource_sku'] = record.resource_instance_id.code
        data['user_id'] = record.booking_id.user_id.id
        data['email'] = record.booking_id.user_id.email
        data['location_id'] = record.resource_instance_id.resource_id.location_id.id
        return data

    # VALIDATORS

    def _validator_create(self):
        return {
            'token': {'type': 'string', 'required': True, 'empty': False},
        }

    def _validator_search(self):
        return {
            'itemid': {'type': 'string', 'required': True, 'empty': False},
            'key': {'type': 'string', 'required': False},
        }

    def _validator_return_search(self):
        return {
            'count': {'type': 'integer', 'required': True},
            'results': {
                'type': 'dict',
                'required': True,
                'schema': {
                    'dt_start': {'type': 'string', 'required': True},
                    'dt_end': {'type': 'string', 'required': True},
                    'resource_sku': {'type': 'string', 'required': True},
                    'user_id': {'type': 'integer', 'required': True},
                    'email': {'type': 'string', 'required': True},
                    'location_id': {'type': 'integer', 'required': True},
                },
            },
        }

    def _validator_return_create(self):
        return {
            'count': {'type': 'integer', 'required': True},
            'results': {
                'type': 'list',
                'required': True,
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'dt_start': {'type': 'datetime', 'required': True},
                        'dt_end': {'type': 'datetime', 'required': True},
                        'resource_sku': {'type': 'string', 'required': True},
                        'user_id': {'type': 'integer', 'required': True},
                        'email': {'type': 'string', 'required': True},
                        'location_id': {'type': 'integer', 'required': True},
                    }
                },
            },
        }
