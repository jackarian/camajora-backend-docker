# Copyright 2021 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class RentalResource(models.Model):
    _inherit = "rental.resource"

    image_ids = fields.One2many(
        "resource.image.relation", inverse_name="resource_id", string="Images"
    )

    def _get_gallery_urls(self):
        """Public URLs of the gallery images, in gallery order"""
        self.ensure_one()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        return [
            "{}/api/v1/public/images/{}?model=resource.image.relation".format(base_url, image.id)
            for image in self.image_ids
        ]
