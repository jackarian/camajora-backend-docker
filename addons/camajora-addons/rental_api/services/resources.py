# Copyright 2020 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.component.core import Component

import calendar
import datetime
import logging
import pytz

_logger = logging.getLogger(__name__)
timezone = pytz.timezone('Europe/Rome')


def _conv_flot_totime(t):
    hour, minute = divmod(t, 1)
    minute *= 60
    return str(int(hour)) + ':' + str(int(minute))


def filterResource(resources_ids, minPrice, maxPrice):
    if not minPrice and not maxPrice:
        return resources_ids
    elif minPrice and maxPrice:
        return list(filter(lambda r: (r.credit_cost >= minPrice) and (r.credit_cost <= maxPrice),
                           resources_ids))
    elif maxPrice:
        return list(filter(lambda r: (r.credit_cost <= maxPrice),
                           resources_ids))
    elif minPrice:
        return list(filter(lambda r: (r.credit_cost >= minPrice),
                           resources_ids))


def checkPriceInput(price):
    if not price:
        return None
    else:
        return int(price) if price.isdigit() else None


class ResourceService(Component):
    _inherit = 'base.rest.public.service'
    _name = 'resource.service'
    _usage = 'resources'
    _description = 'Camajora public services: get all resources'

    # OPERATIONS

    def get(self, _id):
        """
        Get Resource by ID
        """
        resource_id = self.env['rental.resource'].sudo().search([('id', '=', _id)])

        return self._to_json(resource_id)

    def category(self, **params):
        category = params['id']
        domain = [('instances_ids', '!=', False), ('type_id.category_id.id', '=', category if category else -100)]
        resource_ids = self.env['rental.resource'].sudo().search(domain)
        return self._to_json(resource_ids, many=True)

    def _validator_category(self):
        return {
            "id": {"type": "integer", "required": True},
        }

    def resourcetype(self, **params):
        resourceType = params['id']
        domain = [('instances_ids', '!=', False), ('type_id.id', '=', resourceType if resourceType else -100)]
        resource_ids = self.env['rental.resource'].sudo().search(domain)
        return self._to_json(resource_ids, many=True)

    def _validator_resourcetype(self):
        return {
            "id": {"type": "integer", "required": True},
        }

    def search(self, **params):
        """
        Get all Resources
        """
        where_search_value = params.pop("where", None)
        from_search_value = params.pop("from", None)
        to_search_value = params.pop("to", None)
        what_search_value = params.pop("what", None)
        minPrice = params.pop("minPrice", None)
        maxPrice = params.pop("maxPrice", None)
        minPriceInt = checkPriceInput(minPrice)
        maxPriceInt = checkPriceInput(maxPrice)
        domain = [('instances_ids', '!=', False)]

        if where_search_value:
            domain.append('|')
            domain.append('|')
            domain.append('|')
            domain.append(('location_id.name', 'ilike', where_search_value))
            domain.append(('location_id.address', 'ilike', where_search_value))
            domain.append(('location_id.city', 'ilike', where_search_value))
            domain.append(('location_id.state_id.name', 'ilike', where_search_value))

        if what_search_value:
            domain.append(('type_id.name', 'ilike', what_search_value))

        resource_ids = self.env['rental.resource'].sudo().search(domain)

        if from_search_value and to_search_value:
            free_resources_ids = []

            chunks = from_search_value.split('/')
            target_start = datetime.datetime(int(chunks[2]), int(chunks[1]), int(chunks[0]), 0, 0)

            chunks = to_search_value.split('/')
            target_end = datetime.datetime(int(chunks[2]), int(chunks[1]), int(chunks[0]), 23, 59)

            utc_target_start = timezone.localize(target_start).astimezone(pytz.utc).replace(tzinfo=None)
            utc_target_end = timezone.localize(target_end).astimezone(pytz.utc).replace(tzinfo=None)

            for resource in resource_ids:
                if resource.is_free(utc_target_start, utc_target_end):
                    free_resources_ids.append(resource)

            return self._to_json(filterResource(free_resources_ids, minPriceInt, maxPriceInt), many=True)

        return self._to_json(filterResource(resource_ids, minPriceInt, maxPriceInt), many=True)

    # SERIALIZERS

    def _serialize(self, resource_id):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        resource_image_url = '{}/api/v1/public/images/{}?model=rental.resource.type'.format(
            base_url,
            resource_id.type_id.id,
        )

        return {
            'name': resource_id.name,
            'code': resource_id.code,
            'location': resource_id.location_id.name,
            'location_id': resource_id.location_id.id,
            'location_address': resource_id.location_id.address or "",
            'location_postal_code': resource_id.location_id.postal_code or "",
            'location_city': resource_id.location_id.city or "",
            'location_state': resource_id.location_id.state_id.name if resource_id.location_id.state_id else "",
            'location_state_code': resource_id.location_id.state_id.code if resource_id.location_id.state_id else "",
            'location_country': resource_id.location_id.country_id.name if resource_id.location_id.country_id else "",
            'location_state_id': resource_id.location_id.state_id.id,
            'location_country_id': resource_id.location_id.country_id.id,
            'type': resource_id.type_id.category_id.name or "",
            'category_id': resource_id.type_id.category_id.id,
            'description': resource_id.description if resource_id.description else "",
            'image': resource_image_url or "",
            'image_gallery': [],
            'performance': resource_id.type_id.performance_id.name or "",
            'credit_cost': resource_id.credit_cost,
            'setup': resource_id.type_id.setup_id.name or "",
            'size': resource_id.type_id.size_id.name,
            'instance_count': resource_id.instance_count,
            'instances': self._serialize_instances(resource_id),
            'availability_start': _conv_flot_totime(resource_id.availability_id.starthour),
            'availability_end': _conv_flot_totime(resource_id.availability_id.endhour),
        }

    def _serialize_instances(self, resource_id):
        return [self._serialize_instance(instance_id) for instance_id in resource_id.instances_ids]

    def _serialize_instance(self, instance_id):
        return {
            'id': instance_id.id,
            'code': instance_id.code
        }

    # VALIDATORS

    def _validator_search(self):
        return {
            "where": {"type": "string", "required": False},
            "from": {"type": "string", "required": False},
            "to": {"type": "string", "required": False},
            "what": {"type": "string", "required": False},
            "minPrice": {"type": "string", "required": False},
            "maxPrice": {"type": "string", "required": False},
        }

    def _get_object_schema(self):
        return {
            'name': {'type': 'string', 'required': True, 'empty': False},
            'code': {'type': 'string', 'required': True, 'empty': False},
            'location': {'type': 'string', 'required': True, 'empty': False},
            'location_id': {'type': 'integer', 'required': True},
            'location_address': {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            'location_postal_code': {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            'location_city': {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            'location_state': {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            'location_state_code': {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            'location_country': {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            'location_state_id': {'type': 'integer', 'required': False, 'empty': True, 'nullable': True},
            'location_country_id': {'type': 'integer', 'required': False, 'empty': True, 'nullable': True},
            'type': {'type': 'string', 'required': True, 'empty': False},
            'category_id': {'type': 'integer', 'required': True},
            'description': {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            'image': {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            'image_gallery': {'type': 'list', 'schema': {'type': 'string'}},
            'performance': {'type': 'string', 'required': True, 'empty': False},
            'credit_cost': {'type': 'float', 'required': True, 'empty': False},
            'setup': {'type': 'string', 'required': True, 'empty': False},
            'size': {'type': 'string', 'required': True, 'empty': False},
            'instance_count': {'type': 'integer', 'required': True},
            'instances': {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'id': {'type': 'integer', 'required': True},
                        'code': {'type': 'string', 'required': True},
                    }
                }
            },
            'availability_start': {'type': 'string', 'required': True},
            'availability_end': {'type': 'string', 'required': True}
        }
