# Copyright 2021 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class FsImage(models.Model):
    _inherit = "fs.image"

    resource_relation_ids = fields.One2many(
        "resource.image.relation", inverse_name="image_id", string="Resources"
    )
