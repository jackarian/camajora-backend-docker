# Copyright 2020 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.component.core import Component

import logging
_logger = logging.getLogger(__name__)


class ResourceService(Component):
    _inherit = 'resource.service'

    def _serialize(self, resource_id):
        serialized = super()._serialize(resource_id)

        gallery = resource_id._get_gallery_urls()
        if gallery:
            serialized['image'] = gallery[0]

        serialized['image_gallery'] = gallery

        return serialized

    def _get_object_schema(self):
        schema = super()._get_object_schema()

        schema['image_gallery'] = {
            'type': 'list',
            'schema': {
                'type': 'string', 'required': False, 'empty': True, 'nullable': True
            }
        }

        return schema
