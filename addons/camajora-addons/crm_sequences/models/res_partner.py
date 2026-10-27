# Copyright 2020 Metadonors srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    code = fields.Char(
        string=_('Code'),
        readonly=True
    )

    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for record in self:
            name = u'[{}] {}'.format(record.code, record.name)
            result.append((record.id, name))
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['code'] = self.env['ir.sequence'].next_by_code('res.partner')
        return super(ResPartner, self).create(vals_list)

    def _cron_update_missing_codes(self, *args, **kwargs):
        partner_ids = self.env['res.partner'].search([
            ('code', '=', False)
        ])

        for partner_id in partner_ids:
            code = self.env['ir.sequence'].next_by_code('res.partner')
            partner_id.write({'code': code})
