import logging

from odoo import _
from odoo.addons.component.core import Component
from odoo.addons.base_rest.components.service import to_int
from odoo.exceptions import UserError
from werkzeug.exceptions import NotFound

_logger = logging.getLogger(__name__)


class CartService(Component):
    _inherit = 'base.rest.private.service'
    _name = 'shop.cart.service'
    _usage = 'cart'
    _collection = 'base.rest.private.shop.services'

    def add_item(self, **params):
        cart = self._get()
        self._add_item(cart, params)
        return self._to_json(cart)

    def clear(self, **params):
        cart = self._get()
        cart = self._clear_cart(cart)
        return self._to_json(cart)

    def send_order(self):
        """Change state to 'review'
        Used in confirmed cart
        """
        cart = self._get()
        cart.write({'state': 'review'})
        return self._to_json(cart)

    # PRIVATE  METHODS

    def _serialize(self, record):
        data = {}

        data["id"] = record.id
        data["state"] = record.state
        data["name"] = record.name
        data["partner_id"] = record.partner_id.id
        data["partner_name"] = record.partner_id.name
        data["company_name"] = record.partner_id.parent_id.name if record.partner_id.parent_id else None
        data["billing_street"] = record.partner_id.street or None
        data["billing_city"] = record.partner_id.city or None
        data["billing_state"] = record.partner_id.state_id.name if record.partner_id.state_id else None
        data["billing_country"] = record.partner_id.country_id.name if record.partner_id.country_id else None
        data["date"] = record.date_order
        data["note"] = record.note
        data["lines"] = self._serialize_lines(record)
        data["amount"] = {
            "tax": record.amount_tax,
            "untaxed": record.amount_untaxed,
            "total": record.amount_total,
        }
        _logger.error(data)
        return data

    def _serialize_one_line(self, line):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")

        data = {
            "id": line.id,
            "product": line.sudo().name,
            "image": "%s/website/image/product.product/%s/image/200x0" % (base_url, line.sudo().product_id.id),
            "variant": ",".join([a.name for a in line.sudo().product_id.product_template_attribute_value_ids]),
            "amount": {
                "price": line.price_unit,
                "untaxed": line.price_subtotal,
                "tax": line.price_tax,
                "total": line.price_total,
            },
            "qty": line.product_uom_qty
        }

        return data

    def _serialize_lines(self, cart):
        items = []
        for line in cart.order_line:
            items.append(self._serialize_one_line(line))
        return {
            "items": items,
            "count": sum([item["qty"] for item in items]) if items else 0,
            "amount": {
                "tax": sum([item["amount"]["tax"] for item in items]),
                "untaxed": sum([item["amount"]["untaxed"] for item in items]),
                "total": sum([item["amount"]["total"] for item in items]),
            },
        }

    def _serialize_amounts(self, cart):
        amounts = []
        return amounts

    def _get_object_schema(self):
        return {
            "id": {"type": "integer", "required": True, "empty": False, "nullable": False},
            "state": {"type": "string", "required": True, "empty": False, "nullable": False},
            "name": {"type": "string", "required": True, "empty": False, "nullable": False},
            "partner_id": {"type": "integer", "required": True, "empty": False, "nullable": False},
            "partner_name": {"type": "string", "required": True, "empty": False, "nullable": False},
            "company_name": {"type": "string", "required": False, "empty": True, "nullable": True},
            "billing_street": {"type": "string", "required": False, "empty": True, "nullable": True},
            "billing_city": {"type": "string", "required": False, "empty": True, "nullable": True},
            "billing_state": {"type": "string", "required": False, "empty": True, "nullable": True},
            "billing_country": {"type": "string", "required": False, "empty": True, "nullable": True},
            "date": {"type": "date", "required": True, "empty": False, "nullable": False},
            "note": {"type": "string", "required": False, "empty": True, "nullable": True},
            "amount": {
                "type": "dict",
                "schema": {
                    "tax": {"type": "float", "required": False, "empty": True, "nullable": True},
                    "untaxed": {"type": "float", "required": False, "empty": True, "nullable": True},
                    "total": {"type": "float", "required": False, "empty": True, "nullable": True},
                }},
            "lines": {
                "type": "dict",
                "schema": {
                    "amount": {
                        "type": "dict",
                        "schema": {
                            "tax": {"type": "float", "required": False, "empty": True, "nullable": True},
                            "untaxed": {"type": "float", "required": False, "empty": True, "nullable": True},
                            "total": {"type": "float", "required": False, "empty": True, "nullable": True},
                        }},
                    "count": {"type": "float", "required": False, "empty": True, "nullable": True},
                    "items": {
                        "type": "list",
                        "schema": {
                            "type": "dict",
                            "schema": {
                                "id": {"type": "integer", "required": True, "empty": False, "nullable": False},
                                "product": {"type": "string", "required": True, "empty": False, "nullable": False},
                                "is_reward": {"type": "boolean", "required": False},
                                "image": {"type": "string", "required": False, "empty": True, "nullable": True},
                                "variant": {"type": "string", "required": True, "empty": True, "nullable": True},
                                "qty": {"type": "float", "required": False, "empty": True, "nullable": True},
                                "amount": {
                                    "type": "dict",
                                    "schema": {
                                        "price": {"type": "float", "required": False, "empty": True, "nullable": True},
                                        "tax": {"type": "float", "required": False, "empty": True, "nullable": True},
                                        "untaxed": {"type": "float", "required": False, "empty": True, "nullable": True},
                                        "total": {"type": "float", "required": False, "empty": True, "nullable": True},
                                    }},
                            }
                        }
                    }
                }}

        }

    def _get(self):
        """
        :return: sale.order recordset (cart)
        """

        query = "SELECT 1 FROM sale_order WHERE state IN ('draft', 'review') AND typology = 'cart' AND partner_id = %s FOR UPDATE"
        self.env.cr.execute(query, [self.env.user.partner_id.id])
        cart = self.env["sale.order"].sudo().search([
            ('state', 'in', ['draft', 'review']),
            ('typology', '=', 'cart'),
            ('partner_id', '=', self.env.user.partner_id.id)
        ])

        for c in cart:
            _logger.error("REMOVING OLD CART")
            c.sudo().unlink()

        return self._create_empty_cart()

    def _create_empty_cart(self):
        vals = self._prepare_cart()
        return self.env["sale.order"].sudo().create(vals)

    def _prepare_cart(self):
        partner = self.env.user.partner_id
        vals = {
            "typology": "cart",
            "partner_id": partner.id,
            "partner_shipping_id": partner.id,
            "partner_invoice_id": partner.id,
            "user_id": False,
        }

        return vals

    def _prepare_cart_item(self, params, cart):
        return {
            "product_id": params["product_id"],
            "product_uom_qty": params["item_qty"],
            "order_id": cart.id,
        }

    def _add_item(self, cart, params):
        product = self.env["product.product"].sudo().browse(params["product_id"])
        if False:
            raise UserError(_("Product %s is not allowed") % product.name)
        if cart.state != 'draft':
            raise UserError(_("You can't add item in this cart"))

        if not self._variant_is_available(product):
            raise UserError(_("Product %s is not available") % product.name)

        existing_item = self._check_existing_cart_item(cart, params)

        if existing_item:
            qty = existing_item.product_uom_qty + params["item_qty"]
            self._upgrade_cart_item_quantity(cart, existing_item, qty)
        else:
            vals = self._prepare_cart_item(params, cart)
            self.env["sale.order.line"].sudo().create(vals)

    def _get_cart_item(self, cart, params, raise_if_not_found=True):
        # We search the line based on the item id and the cart id
        # indeed the item_id information is given by the
        # end user (untrusted data) and the cart id by the
        # locomotive server (trusted data)
        if cart.state != 'draft':
            raise UserError(_("You can't get items from this cart"))

        item = cart.mapped("order_line").filtered(
            lambda l, id_=params["item_id"]: l.id == id_
        )
        if not item and raise_if_not_found:
            raise NotFound("No cart item found with id %s" % params["item_id"])
        return item

    def _update_item(self, cart, params, item=False):
        if cart.state != 'draft':
            raise UserError(_("You can't update items from this cart"))

        if not item:
            item = self._get_cart_item(cart, params, raise_if_not_found=False)
        if item:
            self._upgrade_cart_item_quantity(cart, item, params["item_qty"])
            return
        # The item id is maybe the one from a previous cart.
        line_id = params["item_id"]
        line = self.env["sale.order.line"].search(
            [
                ("id", "=", line_id),
                ("order_id.partner_id", "=", cart.partner_id.id),
            ]
        )
        if line:
            # silently create a new line on the new cart from the previous
            # line. This case could occurs if the customer click on the add
            # button from within an old session still open in its browser
            add_item_params = self._prepare_add_item_params_from_line(line)
            add_item_params["item_qty"] = params["item_qty"]
            self._add_item(cart, add_item_params)
            return params["item_qty"]
        raise NotFound("No cart item found with id %s" % params["item_id"])

    def _upgrade_cart_item_quantity(self, cart, item, product_qty):
        item.sudo().write({"product_uom_qty": product_qty})

    def _clear_cart(self, cart):
        """
        Remove items from given cart.
        :param cart: sale.order recordset
        :return: sale.order recordset
        """
        if cart.state != 'draft':
            raise UserError(_("State cart error"))

        cart.sudo().write({"order_line": [(5, False, False)]})
        return cart

    def _check_existing_cart_item(self, cart, params):
        product_id = params["product_id"]
        order_lines = cart.sudo().order_line
        return order_lines.filtered(
            lambda l, p=product_id: l.product_id.id == product_id
        )

    def _delete_item(self, cart, params):
        if cart.state != 'draft':
            raise UserError(_("You can't delete items from this cart"))
        item = self._get_cart_item(cart, params, raise_if_not_found=False)
        if item:
            item.sudo().unlink()

    def _variant_is_available(self, product):
        return True  # Should be overridden

    ################
    #  VALIDATORS  #
    ################

    def _validator_return_search(self):
        return self._validator_return_get()

    def _validator_add_item(self):
        return {
            "product_id": {
                "coerce": to_int,
                "required": True,
                "type": "integer",
            },
            "item_qty": {"coerce": float, "required": True, "type": "float"},
        }

    def _validator_update_item(self):
        return {
            "item_id": {"coerce": to_int, "required": True, "type": "integer"},
            "item_qty": {"coerce": float, "required": True, "type": "float"},
        }

    def _validator_remove_item(self):
        return {
            "item_id": {"coerce": to_int, "required": True, "type": "integer"}
        }

    def _validator_clear(self):
        return {}
