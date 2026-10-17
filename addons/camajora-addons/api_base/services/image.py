# Copyright 2020 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID
from odoo.addons.base_rest.components.service import skip_secure_response
from odoo.addons.component.core import AbstractComponent
from odoo.exceptions import MissingError


class BaseImageService(AbstractComponent):
    _inherit = 'base.rest.service'
    _name = 'base.rest.public.image'
    _collection = 'base.rest.public.services'
    _expose_model = None

    @skip_secure_response
    def _get_image_response(self, _id, model):
        env = self.env(user=SUPERUSER_ID)
        record = env[model].browse(_id).exists()

        if not record:
            raise MissingError('Image not found')

        stream = env['ir.binary']._get_image_stream_from(record, 'image')
        stream.public = True
        return stream.get_response()

    def _validator_get(self):
        return {
            'model': {'type': 'string', 'required': True},
        }
