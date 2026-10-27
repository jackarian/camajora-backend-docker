import logging
from odoo.addons.component.core import Component

_logger = logging.getLogger(__name__)


class JobOffersProductsService(Component):
    _inherit = 'base.rest.private.service'
    _name = 'products.service'
    _usage = 'products'
    _collection = 'base.rest.private.shop.services'

    def search(self, **params):
        product_ids = self._retrieve_products(**params)
        return self._to_json(product_ids, many=True)

    def _get_object_schema(self):
        return {
            'id': {'type': 'integer', 'required': False},
            'name': {'type': 'string', 'required': False},
            'description': {'type': 'string', 'required': False},
            'code': {'type': 'string', 'required': False},
            'price': {'type': 'float', 'required': False},
            'credits': {'type': 'integer', 'required': False},
            'image': {'type': 'string', 'required': False},
            'is_available': {'type': 'boolean', "required": False},
            'variants': {
                "type": 'list',
                "schema": {
                    "type": "dict",
                    "schema": {
                        'id': {'type': 'integer', 'required': False},
                        'name': {'type': 'string', 'required': False},
                        'code': {'type': 'string', 'required': False},
                        'price': {'type': 'float', 'required': False},
                        'is_available': {'type': 'boolean', "required": False},
                    }
                }
            }
        }

    def _serialize_variant(self, variant, pricelist):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")

        data = {}
        data['id'] = variant.id
        name = ""
        for attribute_id in variant.product_template_attribute_value_ids:
            name += "%s" % (attribute_id.name)
        data['name'] = name
        data['code'] = variant.default_code
        data['price'] = self._get_price(pricelist, variant)
        data['image'] = "%s/website/image/product.product/%s/image/500x0" % (base_url, variant.id)
        data['image_small'] = "%s/website/image/product.product/%s/image/200x0" % (base_url, variant.id)
        data['is_available'] = self._variant_is_available(variant)

        return data

    def _serialize(self, record):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        data = {}
        data['id'] = record.id
        data['name'] = record.name
        data['description'] = record.description_sale or record.description or ''
        data['code'] = record.default_code or ''
        data['variants'] = []
        data['image'] = "%s/website/image/product.template/%s/image" % (base_url, record.id)
        data['image_small'] = "%s/website/image/product.template/%s/image/200x200" % (base_url, record.id)

        pricelist = self.env.user.partner_id.sudo().property_product_pricelist

        data['price'] = self._get_price(pricelist, record)

        data['credits'] = record.credits_value

        variant_ids = self.env['product.product'].sudo().search([
            ('product_tmpl_id', '=', record.id)
        ])
        for variant_id in variant_ids:
            data['variants'].append(self._serialize_variant(variant_id, pricelist))

        data['is_available'] = self._is_available(variant_ids)

        if len(data['variants']) == 1:
            variant = data['variants'][0]
            data['id'] = variant['id']
            data['price'] = variant['price']
            data['code'] = variant['code'] or ''
            data['variants'] = []

        return data

    # PRIVATE METHODS

    def _get_price(self, pricelist, product):
        if not pricelist:
            return product.list_price
        return pricelist._get_product_price(product, 1.0)

    def _retrieve_products(self, **params):
        domain = []
        return self.env['product.template'].sudo().search(
            domain,
            offset=params.get("offset", 0),
            limit=params.get("limit", 50))

    def _is_available(self, variant_ids):
        return True

    def _variant_is_available(self, variant):
        return True
