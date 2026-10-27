from odoo.addons.component.core import Component
import logging

_logger = logging.getLogger(__name__)


class BookingSlotsService(Component):
    _inherit = 'booking.slots.service'

    def _serialize(self, record):
        serialized = super()._serialize(record)
        gallery = record.resource_instance_id.resource_id._get_gallery_urls()
        if gallery:
            serialized['image'] = gallery[0]
        return serialized
