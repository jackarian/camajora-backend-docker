# Copyright 2020 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import qrcode
import random
import uuid

from io import BytesIO
from odoo import api, fields, models, _


class RentalBooking(models.Model):
    _name = 'rental.booking'
    _description = 'Rental Booking'

    name = fields.Char(string=_('SKU'), readonly=True)
    date = fields.Date(string=_('Date'), default=lambda self: fields.Date.today())
    user_id = fields.Many2one('res.partner', string=_('User'))

    rent_channel = fields.Selection([
        ('main_site', _('Main Site')),
        ('phone', _('Phone')),
        ('external_site', _('External Site')),
        ('location', _('Location')),
        ('app', _('App')),
    ], string=_('Rent Channel'), default='main_site')

    slot_ids = fields.One2many('rental.booking.slot', 'booking_id', string=_('Slots'))
    slot_count = fields.Integer(string=_('Total Slots'), compute='_compute_slot_count')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, store=True, default='draft')

    token = fields.Char(string=_('Secret Token'), readonly=True)
    qr_code = fields.Binary(string=_('QR Code'), readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('rental.booking.sku')
            vals['token'] = self._generate_token()
            vals['qr_code'] = self._generate_qr_code(vals['token'])
        return super().create(vals_list)

    @api.model
    def search(self, args, offset=0, limit=None, order=None):

        backend = self.env.context.get('backend')

        if backend is not None:
            current_owner = self.env['res.partner'].search([('id', '=', self.env.user.partner_id.id)])

            if current_owner:
                args = [] if args is None else args.copy()
                args.append(('slot_ids.location_id.partner_id', '=', current_owner.id))

        return super(RentalBooking, self).search(args, offset, limit, order)

    def _compute_slot_count(self):
        for record in self:
            count = self.env['rental.booking.slot'].search(
                [('booking_id', '=', record.id)]
            )
            record.slot_count = len(count)

    def action_confirm(self):
        return self.write({'state': 'confirmed'})

    def action_cancel(self):
        return self.write({'state': 'cancelled'})

    @staticmethod
    def _generate_token():
        """
        create a token for coupon (lenght 48)

        :returns: token (str)
        """
        random_number = random.randint(0000000000000000, 9999999999999999)
        token = "%s%s" % (str(uuid.uuid4()).replace("-", ""), str(random_number))
        return token

    @staticmethod
    def _generate_qr_code(token):
        img = qrcode.make(token)
        buffered = BytesIO()
        img.save(buffered, format='PNG')
        return base64.b64encode(buffered.getvalue())
