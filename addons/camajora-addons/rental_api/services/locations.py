# Copyright 2020 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.component.core import Component


def _conv_flot_totime(t):
    hour, minute = divmod(t, 1)
    minute *= 60
    return str(int(hour)) + ':' + str(int(minute))


class LocationService(Component):
    _inherit = 'base.rest.public.service'
    _name = "location.service"
    _usage = "locations"
    _description = "Camajora public services: get all locations"

    # OPERATIONS

    def get(self, _id):
        """
        Get Location by ID
        """
        location_id = self.env["rental.location"].sudo().search([("id", "=", _id)])

        return self._to_json(location_id)

    def search(self, offset=0, limit=None, **params):
        """
        Get all Locations
        """
        location_ids = (
            self.env["rental.location"].sudo().search([], offset=offset, limit=limit)
        )

        return self._to_json(location_ids, many=True, offset=offset)

    # SERIALIZERS

    def _serialize(self, location_id):
        return {
            "name": location_id.name,
            "address": location_id.address or "",
            "postal_code": location_id.postal_code or "",
            "city": location_id.city or "",
            "state": location_id.state_id.name if location_id.state_id else "",
            "state_code": location_id.state_id.code if location_id.state_id else "",
            "country": location_id.country_id.name if location_id.country_id else "",
            "state_id": location_id.state_id.id,
            "country_id": location_id.country_id.id,
            "opened_from": _conv_flot_totime(location_id.opened_from),
            "opened_to": _conv_flot_totime(location_id.opened_to),
            "lat": location_id.latitudo,
            "long": location_id.longitudo,
            "hotspot_name": location_id.hotspot_name,
            "scc_address": location_id.scc_address,
            "contact_email_ref": location_id.contact_email_ref,
            "contact_mobile_ref": location_id.contact_mobile_ref,
            "contact_name_ref": location_id.contact_name_ref,
            "endpoint_opener": self.buildEndpoint(location_id),
            "resources": self._serialize_resources(location_id.resource_ids)
        }

    def _serialize_resources(self, resources):
        return [self._serialize_resource(resource_id) for resource_id in resources]

    def _serialize_resource(self, resource_id):
        return {
            'id': resource_id.id,
            'name': resource_id.name,
            'code': resource_id.code,
            'type': resource_id.type_id.category_id.name or "",
            'category_id': resource_id.type_id.category_id.id,
            'description': resource_id.description if resource_id.description else "",
            'performance': resource_id.type_id.performance_id.name or "",
            'credit_cost': resource_id.credit_cost,
            'setup': resource_id.type_id.setup_id.name or "",
            'size': resource_id.type_id.size_id.name,
            'instance_count': resource_id.instance_count,
            'instances': self._serialize_instances(resource_id)
        }

    def _serialize_instances(self, resource_id):
        return [self._serialize_instance(instance_id) for instance_id in resource_id.instances_ids]

    def _serialize_instance(self, instance_id):
        return {
            'id': instance_id.id,
            'code': instance_id.code
        }

    def buildEndpoint(self, location_id):
        return location_id.scc_endpoint_open_door_protocol \
               + '://' + location_id.scc_address \
               + ':' + location_id.scc_endpoint_open_door_port \
               + location_id.scc_endpoint_open_door

    # VALIDATORS

    def _get_object_schema(self):
        return {
            "name": {"type": "string", "required": True, "empty": False},
            "address": {"type": "string", "required": False, "empty": True},
            "postal_code": {"type": "string", "required": False, "empty": True},
            "city": {"type": "string", "required": False, "empty": True},
            "state": {"type": "string", "required": False, "empty": True},
            "state_code": {"type": "string", "required": False, "empty": True},
            "country": {"type": "string", "required": False, "empty": True},
            "state_id": {'type': 'integer', 'required': False, 'empty': True},
            "country_id": {'type': 'integer', 'required': False, 'empty': True},
            "opened_from": {'type': 'string', 'required': True, 'empty': False},
            "opened_to": {'type': 'string', 'required': True, 'empty': False},
            "lat": {'type': 'float', 'required': True, 'empty': False},
            "long": {'type': 'float', 'required': True, 'empty': False},
            "hotspot_name": {'type': 'string', 'required': True, 'empty': False},
            "scc_address": {'type': 'string', 'required': True, 'empty': False},
            "contact_email_ref": {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            "contact_mobile_ref": {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            "contact_name_ref": {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
            "endpoint_opener": {'type': 'string', 'required': True, 'empty': False},
            "resources": {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'id': {'type': 'integer', 'required': True, 'empty': False},
                        'name': {'type': 'string', 'required': True, 'empty': False},
                        'code': {'type': 'string', 'required': True, 'empty': False},
                        'type': {'type': 'string', 'required': True, 'empty': False},
                        'category_id': {'type': 'integer', 'required': True},
                        'description': {'type': 'string', 'required': False, 'empty': True, 'nullable': True},
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
                        }
                    }
                }
            }
        }
