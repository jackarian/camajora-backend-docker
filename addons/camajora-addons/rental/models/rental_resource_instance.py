# Copyright 2020 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class RentalResourceInstance(models.Model):
    _name = 'rental.resource.instance'
    _description = 'Rental Resource Instance'

    name = fields.Char(string=_('Name'), readonly=True, default=lambda self: _('New'), compute='_compute_name')
    code = fields.Char(string=_('SKU'), readonly=True)
    active = fields.Boolean(default=True, string=_('Active'))

    resource_id = fields.Many2one('rental.resource', string=_('Resource'), required=True, ondelete='cascade')
    equipments_ids = fields.Many2many('rental.resource.equipment', string=_('Equipments'))

    booking_slots_ids = fields.One2many(
        'rental.booking.slot', 'resource_instance_id', string=_('Booking Slots')
    )

    booking_slots_count = fields.Integer(string=_('Total Slots'), compute='_compute_booking_slots_count', store=True)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        current_owner = self.env['res.partner'].sudo().search([('id', '=', self.env.user.partner_id.id)])
        args = [] if args is None else args.copy()
        args += [('resource_id.partner_id.id', '=', current_owner.id)]

        default_resource_id = self.env.context.get('default_resource_id')
        _logger.debug("default_resource_id :%s", default_resource_id)
        if default_resource_id is not None:
            args.append(('resource_id', '=', default_resource_id))

        return super(RentalResourceInstance, self).name_search(name, args, operator, limit)

    def _compute_name(self):
        for record in self:
            record.name = ' '.join([
                record.resource_id.name,
                record.code
            ])

    @api.depends('booking_slots_ids')
    def _compute_booking_slots_count(self):
        for record in self:
            record.booking_slots_count = len(record.booking_slots_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['code'] = self.env['ir.sequence'].next_by_code('rental.resource.instance.code')
        return super().create(vals_list)

