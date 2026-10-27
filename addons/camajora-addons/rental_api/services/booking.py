import logging
from datetime import datetime, time, timedelta
from odoo import _
from odoo.addons.base_rest.components.service import to_int
from odoo.addons.component.core import Component
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)
date_format = '%Y-%m-%dT%H:%M:%S'


def conv_flot_totime(t):
    hour, minute = divmod(t, 1)
    minute *= 60
    return int(hour), int(minute)


def second_between_time(start, end):
    ds = timedelta(hours=start.hour, minutes=start.minute)
    de = timedelta(hours=end.hour, minutes=end.minute)
    delta = de - ds
    return delta.total_seconds()


def format_total_hour(seconds):
    seconds = 0 if seconds is None else seconds
    ore, mi = divmod(float(seconds), 3600)
    m, s = divmod(float(mi), 60)
    return str(int(ore)) + ":" + str(int(m))


class BookingService(Component):
    _inherit = 'base.rest.private.service'
    _name = 'booking.service'
    _usage = 'booking'
    _description = 'Camajora private services: booking operations'

    def search(self):
        """
        Get current cart or create one if not found
        """
        cart = self._get()
        return self._to_json(cart)

    def add_item(self, **params):
        """
        Add a booking slot to current cart
        """
        cart = self._get()
        self._add_item(cart, params)
        return self._to_json(cart)

    def remove_item(self, **params):
        """
        Remove a booking slot from current cart
        """
        cart = self._get()
        self._delete_item(cart, params)
        return self._to_json(cart)

    def clear(self, **params):
        """
        Remove all booking slots from current cart
        """
        cart = self._get()
        cart = self._clear_cart(cart)
        return self._to_json(cart)

    def confirm(self):
        """
        Set current cart state to 'confirmed'
        WITHOUT CHECKING CREDITS!!
        """
        cart = self._get()
        cart.write({'state': 'confirmed'})
        return self._to_json(cart)

    def get_confirmed(self):
        """
        Get all user's confirmed orders
        """
        booking_ids = self.env['rental.booking'].sudo().search([
            ('state', 'in', ['confirmed']),
            ('user_id', '=', self.env.user.partner_id.id)
        ])
        return self._to_json(booking_ids, many=True)

    # PRIVATE  METHODS

    def _serialize(self, record):
        data = {'id': record.id, 'state': record.state, 'name': record.name, 'user_id': record.user_id.id,
                'user_name': record.user_id.name, 'date': record.date, 'token': record.token,
                'lines': self._serialize_slots(record)}

        _logger.error('Serialized cart:')
        _logger.error(data)
        return data

    def _serialize_slots(self, cart):
        items = []
        for slot in cart.slot_ids:
            items.append(self._serialize_one_slot(slot))

        return {'count': cart.slot_count, 'items': items}

    def _serialize_one_slot(self, line):
        image = '{}/api/v1/public/images/{}?model=rental.resource.type'.format(
            self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
            line.resource_instance_id.resource_id.type_id.id,
        )

        return {
            'id': line.id,
            'name': line.resource_instance_id.resource_id.name,
            'sku': line.name,
            'total_hours': line.total_hours,
            'total_hours_formatted': format_total_hour(line.total_hours),
            'image': image,
            'dt_start': line.dt_start,
            'dt_end': line.dt_end,
            'start_date': line.start_date,
            'end_date': line.end_date,
            'start_time': line.start_time,
            'end_time': line.end_time,
        }

    @staticmethod
    def _get_object_schema():
        return {
            'id': {'type': 'integer', 'required': True, 'empty': False, 'nullable': False},
            'state': {'type': 'string', 'required': True, 'empty': False, 'nullable': False},
            'name': {'type': 'string', 'required': True, 'empty': False, 'nullable': False},
            'user_id': {'type': 'integer', 'required': True, 'empty': False, 'nullable': False},
            'user_name': {'type': 'string', 'required': True, 'empty': False, 'nullable': False},
            'date': {'type': 'date', 'required': True, 'empty': False, 'nullable': False},
            'token': {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            'lines': {
                'type': 'dict',
                'schema': {
                    'count': {'type': 'float', 'required': False, 'empty': True, 'nullable': True},
                    'items': {
                        'type': 'list',
                        'schema': {
                            'type': 'dict',
                            'schema': {
                                'id': {'type': 'integer', 'required': True},
                                'sku': {'type': 'string', 'required': True},
                                'name': {'type': 'string', 'required': True},
                                'total_hours': {'type': 'integer', 'required': True},
                                'total_hours_formatted': {'type': 'string', 'required': True},
                                'image': {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
                                'dt_start': {'type': 'datetime', 'required': True},
                                'dt_end': {'type': 'datetime', 'required': True},
                                'start_date': {'type': 'date', 'required': True},
                                'end_date': {'type': 'date', 'required': True},
                                'start_time': {'type': 'float', 'required': True},
                                'end_time': {'type': 'float', 'required': True},
                            }
                        }
                    }
                }
            }
        }

    def _get(self, create_if_not_found=True):
        # lock the partner row so concurrent requests don't create two carts: NOWAIT makes
        # the other requests fail with LockNotAvailable, Odoo retries them in a new transaction
        self.env.cr.execute(
            'SELECT 1 FROM res_partner WHERE id = %s FOR UPDATE NOWAIT',
            [self.env.user.partner_id.id]
        )

        cart = self.env['rental.booking'].sudo().search([
            ('state', 'in', ['draft']),
            ('user_id', '=', self.env.user.partner_id.id)
        ])

        if cart:
            return cart[0]

        _logger.error('CART NOT FOUND')
        if create_if_not_found:
            return self._create_empty_cart()

    def _create_empty_cart(self):
        return self.env['rental.booking'].sudo().create({
            'user_id': self.env.user.partner_id.id
        })

    def _add_item(self, cart, params):
        if cart.state != 'draft':
            raise UserError(_('You can\'t add item in this cart'))

        resource_id = self.env['rental.resource'].sudo().search([('id', '=', params['resource_id'])])
        if not resource_id:
            raise UserError(_('Resource not found'))

        duration_id = self.env['rental.duration'].sudo().search([('type', '=', params['duration'])])
        if not duration_id:
            raise UserError(_('Duration not found'))

        resource_instance_id = resource_id.get_best_instance_match(
            resource_id.availability_id.starthour,
            resource_id.availability_id.endhour,
            **params)

        self.env['rental.booking.slot'].sudo().create({
            'booking_id': cart.id,
            'resource_instance_id': resource_instance_id,
            'duration_id': duration_id.id,
            'start_date': params['start_date'],
            'end_date': params['end_date'],
            'start_time': params['start_time'],
            'end_time': params['end_time'],
            'half_day_type': params['half_day_type'],
        })

    @staticmethod
    def _clear_cart(cart):
        if cart.state != 'draft':
            raise UserError(_('State cart error'))

        cart.sudo().write({'slot_ids': [(5, False, False)]})
        return cart

    def _delete_item(self, cart, params):
        if cart.state != 'draft':
            raise UserError(_('You can\'t delete items from this cart'))

        slot_id = self.env['rental.booking.slot'].sudo().search([
            ('id', '=', params['slot_id']),
            ('booking_id', '=', cart.id),
        ])

        if slot_id:
            slot_id.sudo().unlink()

    # VALIDATORS

    def _validator_return_search(self):
        return self._validator_return_get()

    @staticmethod
    def _validator_add_item():
        return {
            'resource_id': {
                'type': 'integer',
                'coerce': to_int,
                'required': True,
            },
            'duration': {'type': 'string', 'required': True},
            'start_date': {'type': 'string', 'required': True},
            'end_date': {'type': 'string', 'required': False, 'nullable': True},
            'start_time': {'type': 'string', 'required': False, 'nullable': True},
            'end_time': {'type': 'string', 'required': False, 'nullable': True},
            'half_day_type': {'type': 'string', 'required': False, 'nullable': True},  # FIXME LIMIT TO POTENTIAL
        }

    @staticmethod
    def _validator_remove_item():
        return {
            'slot_id': {'type': 'integer', 'coerce': to_int, 'required': True}
        }

    @staticmethod
    def _validator_clear(self):
        return {}

    @staticmethod
    def _validator_confirm():
        return {}

    @staticmethod
    def _validator_get_confirmed():
        return {}

    def prevent_price(self, **params):
        res_id = params.pop("resource_id")
        strstart = params.pop("datetime_start")
        strend = params.pop("datetime_end")
        slot = 3600
        dateStart = datetime.strptime(strstart, date_format)
        dateEnd = datetime.strptime(strend, date_format)

        if dateEnd < dateStart:
            raise ValidationError(_('The ending date must not be prior to the starting date.'))

        resource_id = self.env['rental.resource'].sudo().search([('id', '=', res_id)])

        if resource_id is None:
            raise ValidationError(_('Resource not found with specified id.'))

        costo_al_secondo = (resource_id.credit_cost / slot)
        shour, sminute = conv_flot_totime(resource_id.availability_id.starthour or 9)
        ehour, eminute = conv_flot_totime(resource_id.availability_id.endhour or 19)
        location_start = time(shour, sminute)
        location_end = time(ehour, eminute)
        secondi_giornalieri_location = second_between_time(location_start, location_end)
        secondi_prenotazione = second_between_time(dateStart, dateEnd)
        number_of_days = (dateEnd - dateStart).days + 1

        if number_of_days > 1:
            price = number_of_days * secondi_giornalieri_location * costo_al_secondo
        else:
            price = number_of_days * secondi_prenotazione * costo_al_secondo

        return {'price': price}

    @staticmethod
    def _validator_prevent_price():
        return {
            "resource_id": {"type": "integer", "required": True},
            "datetime_start": {"type": "string", "required": True},
            "datetime_end": {"type": "string", "required": True}
        }

    @staticmethod
    def _validator_return_prevent_price():
        return {
            "price": {"type": "float", "required": True},
        }
