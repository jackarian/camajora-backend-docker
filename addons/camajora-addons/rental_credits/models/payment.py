# Copyright 2020 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from odoo import api, models

log = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _reconcile_after_done(self):
        res = super()._reconcile_after_done()
        for trans in self.filtered(lambda t: t.sale_order_ids):
            for sale_order_id in trans.sale_order_ids:
                self._generate_credit_order(sale_order_id)
        return res

    def _generate_credit_order(self, sale_order_id):
        """
            This method is called upon payment of an order.
            It checks every single line of the sale order and if it finds a credit package
            assign the number of credits to the buyer.
        """
        credits_to_add = 0

        for line in sale_order_id.order_line:
            if line.product_id.product_tmpl_id.is_credits:
                credits_to_add = credits_to_add + (
                        line.product_id.product_tmpl_id.credits_value * int(line.product_uom_qty)
                )

        sale_order_id.partner_id.write({
            'credits': sale_order_id.partner_id.credits + credits_to_add
        })
