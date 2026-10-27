# Copyright 2021 Metadonors Srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResourceImageRelation(models.Model):
    _name = "resource.image.relation"
    _inherit = "fs.image.relation.mixin"
    _description = "Resource Image Relation"

    resource_id = fields.Many2one("rental.resource", required=True, ondelete="cascade")
    tag_id = fields.Many2one("image.tag", domain=[("apply_on", "=", "resource")])
