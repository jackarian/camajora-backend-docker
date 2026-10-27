# Copyright 2020 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    fiscal_code = fields.Char(string=_('Fiscal Code'), required=False)
    invoice_recipient_code = fields.Char(string=_('Invoice Recipient Code'), required=False)
    pec_address = fields.Char(string=_('PEC Address'), required=False)
    is_owner = fields.Boolean(
        string=_('Is Owner'),
        compute="_compute_is_owner",
        store=True
    )

    is_superuser = fields.Boolean(
        string=_('Is Superuser'),
        compute="_compute_is_superuser",
        store=False
    )

    booking_ids = fields.One2many(
        'rental.booking',
        'user_id',
        string=_("Bookings"))

    booking_count = fields.Integer(
        compute="_compute_booking_count",
        string=_("Total Bookings"))

    booking_slot_ids = fields.One2many(
        'rental.booking.slot',
        'partner_id',
        string=_("Booking Slots"))

    booking_slot_count = fields.Integer(
        compute="_compute_booking_count",
        string=_("Total Bookings Slots"))

    booking_users = fields.Many2many(
        'res.partner',
        string=_('Booking Users'),
        compute="_compute_booking_users"
    )

    def action_slots(self):
        pass

    def action_booking_slots(self):
        pass

    @api.depends('booking_ids', 'booking_ids.slot_ids')
    def _compute_booking_count(self):
        for record in self:
            record.booking_count = len(record.booking_ids.filtered(lambda b: b.state == 'confirmed'))
            record.booking_slot_count = len(record.booking_slot_ids.filtered(lambda b: b.state == 'confirmed'))

    @api.depends('user_ids.groups_id')
    def _compute_is_owner(self):
        for record in self:
            try:
                record.is_owner = record.user_ids and (
                        self.env.ref("rental.group_rental_owner")
                        in record.user_ids[0].groups_id
                )
            except:
                record.is_owner = False

    @api.depends('user_ids.groups_id')
    def _compute_is_superuser(self):
        for record in self:
            try:
                record.is_superuser = record.user_ids and (
                        self.env.ref("rental.group_rental_superuser")
                        in record.user_ids[0].groups_id
                )
            except:
                record.is_superuser = False

    def _compute_booking_users(self):
        for record in self:
            booking_users = self.env['res.partner'].search([
                ('booking_ids.slot_ids.resource_instance_id.resource_id.partner_id.id', '=', record.id)
            ])
            record.booking_users = [(6, 0, booking_users.ids)]
