# Copyright 2020 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID
from odoo.addons.base_rest.components.service import skip_secure_response
from odoo.addons.component.core import Component
from odoo.exceptions import MissingError


class ResourceImageService(Component):
    _inherit = 'resource.image.service'

    @skip_secure_response
    def get(self, _id, model):
        """
        Get mode image
        """
        if model == 'resource.image.relation':
            return self._get_gallery_image_response(_id)
        return super().get(_id, model)

    def _get_gallery_image_response(self, _id):
        env = self.env(user=SUPERUSER_ID)
        relation = env['resource.image.relation'].browse(_id).exists()
        attachment = relation.image.attachment if relation and relation.image else None

        if not attachment:
            raise MissingError('Image not found')

        stream = env['ir.binary']._get_image_stream_from(attachment)
        stream.public = True
        return stream.get_response()
