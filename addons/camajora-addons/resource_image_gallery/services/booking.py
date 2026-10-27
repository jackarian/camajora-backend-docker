import logging

from odoo.addons.component.core import Component

_logger = logging.getLogger(__name__)


class BookingService(Component):
    _inherit = 'booking.service'

    def _serialize_one_slot(self, line):
        serialized = super()._serialize_one_slot(line)

        gallery = line.resource_instance_id.resource_id._get_gallery_urls()
        if gallery:
            serialized['image'] = gallery[0]

        return serialized
