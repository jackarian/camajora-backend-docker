# Copyright 2020 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _


class RentalBookingSlot(models.Model):
    _inherit = 'rental.booking.slot'

    credit_cost = fields.Integer(related='resource_instance_id.resource_id.credit_cost', readonly=True,
                                 string=_('Credit Cost'), store=True)
    credit_total = fields.Integer(string=_('Total'), compute='_compute_total', store=True)

    @api.depends('credit_cost', 'total_hours')
    def _compute_total(self):
        for record in self:
            # hourly credit cost, rounded up per slot
            record.credit_total = -(-record.credit_cost * record.total_hours // 3600)
