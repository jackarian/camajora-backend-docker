import logging
import stripe

from odoo import Command, _
from odoo.addons.payment import utils as payment_utils
from odoo.addons.component.core import Component
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)

STRIPE_TRANSACTION_STATUSES = {
    "canceled": "cancel",
    "processing": "pending",
    "requires_action": "pending",
    "requiresauthorization": "pending",
    "requirescapture": "pending",
    "requiresconfirmation": "pending",
    "requirespaymentmethod": "pending",
    "succeeded": "done",
}


class PaymentService(Component):
    _inherit = 'base.rest.private.service'
    _name = 'shop.payment.service'
    _usage = 'stripe'
    _collection = 'base.rest.private.shop.services'

    @property
    def stripe_backend(self):
        provider = self.env['payment.provider'].sudo().search([
            ('code', '=', "stripe")
        ])
        return provider[0]

    def config(self):
        return {
            "stripe_pub_key": self.stripe_backend.stripe_publishable_key
        }

    def initialize(self, **params):
        stripe.api_key = self.stripe_backend.stripe_secret_key

        domain = [
            ('id', '=', params['cart_id']),
            ('state', '=', 'draft')
        ]

        order_id = self.env['sale.order'].sudo().search(domain)

        if not order_id:
            raise UserError("Cart not found")

        try:
            vals = {
                "amount": order_id.amount_total,
                "currency_id": order_id.currency_id.id,
                "partner_id": order_id.partner_id.id,
                "provider_id": self.stripe_backend.id,
                "payment_method_id": self._get_stripe_payment_method().id,
                "operation": "online_direct",
                "sale_order_ids": [Command.set(order_id.ids)],
                "reference":  "%s-%s" % (order_id.name, self.env["ir.sequence"].sudo().next_by_code("stripe.transaction.reference"))
            }

            transaction = self.env['payment.transaction'].sudo().create(vals)
            intent = self._prepare_stripe_intent(order_id, transaction)
            transaction.write({
                'provider_reference': intent.id,
            })
            return {"client_secret": intent.client_secret}
        except Exception as e:
            raise UserError(str(e))

    def confirm(self, **params):
        transaction = self._get_stripe_transaction_from_intent(params['intent_id'])
        intent = self._confirm_stripe_intent(transaction, params['intent_id'])
        _logger.info("Stripe intent %s status %s", intent.id, intent.status)

        if intent.status == "succeeded":
            if transaction.state != 'done':
                transaction.sudo()._set_done()
                transaction.sudo()._finalize_post_processing()
        else:
            transaction.sudo().write({
                'state': STRIPE_TRANSACTION_STATUSES.get(intent.status, 'pending')
            })

        return self._generate_stripe_response(intent, **params)

    #######################################
    # PRIVATE METHODS                     #
    #######################################

    def _get_stripe_private_key(self, transaction):
        return self.stripe_backend.stripe_secret_key

    def _get_stripe_payment_method(self):
        method = self.stripe_backend.with_context(active_test=False).payment_method_ids.filtered(
            lambda m: m.code == 'card'
        )[:1]
        if not method:
            raise UserError(_("No card payment method configured for Stripe"))
        return method

    def _get_or_create_stripe_customer(self, order_id):
        stripe_customer = None

        if order_id.partner_id:
            if order_id.partner_id.stripe_id:
                try:
                    stripe_customer = stripe.Customer.retrieve(order_id.partner_id.stripe_id)
                except Exception:
                    pass

        if not stripe_customer:
            stripe_customer = stripe.Customer.create(
                name=order_id.partner_id.name,
                email=order_id.partner_id.email if order_id.partner_id.email else None
            )
            order_id.partner_id.write({
                "stripe_id": stripe_customer['id']
            })

        return stripe_customer['id'] if stripe_customer else None

    def _get_formatted_amount(self, currency, amount):
        """
        The expected amount format by Stripe
        :param amount: float
        :return: int
        """
        res = int(payment_utils.to_minor_currency_units(amount, currency))
        return res

    def _get_stripe_transaction_from_intent(self, intent_id):
        """
        Retrieve the transaction from intent string
        :param intent: string
        :return: payment.transaction
        """
        transaction = self.env["payment.transaction"].sudo().search(
            [
                ("provider_reference", "=", intent_id),
                ("provider_id.code", "=", "stripe"),
            ],
            limit=1,
        )
        return transaction

    def _prepare_stripe_intent(self, order_id, transaction):
        """
        Prepare a StripeIntent with payment.transaction data
        :param tx_data:
        :param stripe_payment_method_id:
        :return: StripeIntent
        """
        metadata = {"reference": transaction.reference, "order": order_id.name}
        currency = transaction.currency_id
        customer = self._get_or_create_stripe_customer(order_id)

        intent = stripe.PaymentIntent.create(
            amount=self._get_formatted_amount(currency, transaction.amount),
            currency=currency.name,
            customer=customer,
            description=transaction.reference,
            metadata=metadata,
            api_key=self._get_stripe_private_key(transaction),
        )

        return intent

    def _confirm_stripe_intent(self, transaction, stripe_payment_intent_id):
        """
        Confirm the Stripe Intent and return it
        :param stripe_payment_intent_id:
        :return: StripeIntent
        """
        return stripe.PaymentIntent.retrieve(
            stripe_payment_intent_id,
            api_key=self._get_stripe_private_key(transaction),
        )

    def _generate_stripe_response(self, intent, **params):
        """
        This is the message returned to client
        :param intent: StripeIntent (None means error)
        :param payable: invader.payable record
        :return: dict
        """
        data = {
            "success": False,
            "error": None,
            "requires_action": False,
            "payment_intent_client_secret": None
        }

        if intent:
            if (
                intent.status == "requires_action"
                and intent.next_action.type == "use_stripe_sdk"
            ):
                # Tell the client to handle the action
                data.update({
                    "requires_action": True,
                    "payment_intent_client_secret": intent.client_secret,
                })
            elif intent.status == "succeeded":
                # The payment didn’t need any additional actions and completed!
                data.update({"success": True})
            elif intent.status == "canceled":
                data.update({"error": _("Payment canceled."), "success": False})
            else:
                _logger.error("Unexpected intent status: %s", intent)
                data.update({"error": _("Payment Error"), "success": False})

        return data

    #######################################
    # VALIDATORS                          #
    #######################################

    def _validator_initialize(self):
        return {
            "cart_id": {"type": "integer", "required": True}
        }

    def _validator_return_initialize(self):
        return {
            "client_secret": {"type": "string", "required": True}
        }

    def _validator_confirm(self):
        return {
            "intent_id": {"type": "string", "required": True}
        }

    def _validator_return_confirm(self):
        return {
            "success": {"type": "boolean", "required": False},
            "error": {"type": "string", "required": False, "nullable": True},
            "requires_action": {"type": "boolean", "required": False},
            "payment_intent_client_secret": {"type": "string", "required": False, "nullable": True}
        }

    def _validator_config(self):
        return {}

    def _validator_return_config(self):
        return {
            "stripe_pub_key": {"type": "string", "required": True}
        }
