# Copyright 2019 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, AccessError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    typology = fields.Selection(
        [("sale", "Sale"), ("cart", "Cart")],
        default="sale"
    )
    state = fields.Selection(
        selection_add=[('review', 'Review'), ('sent',)],
        ondelete={'review': 'set default'},
    )

    @api.multi
    def action_confirm_cart(self):
        for record in self:
            if record.typology == "sale":
                # cart is already confirmed
                continue
            record.write({"typology": "sale", "state": 'review'})

        return True

    @api.multi
    def _review_order(self):
        """
            Change the state order to 'review'
        """
        self.state = "review"

    @api.multi
    def action_accept_order(self):
        """
            Accept order from review state
        """
        self.state = "sent"
        self.force_quotation_send()

    @api.multi
    def action_back_draft(self):
        """
            Order return in draft state from review
        """
        orders = self.filtered(lambda s: s.state == 'draft')
        return orders.write({
            'state': 'draft',
        })

    @api.multi
    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for record in self:
            if record.typology != "sale":
                record.typology = "sale"
        return res
