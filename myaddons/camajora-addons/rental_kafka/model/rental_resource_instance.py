from odoo import api, fields, models, _
from ..producer.location_producer import InstanceMessageProducer
import logging

_logger = logging.getLogger(__name__)


class RentalResourceInstance(models.Model):
    _inherit = 'rental.resource.instance'

    @api.model_create_multi
    def create(self, vals_list):
        _logger.debug("Test kafka send:%s", vals_list)
        resource_instances = super().create(vals_list)

        for resource_instance in resource_instances:
            resource = self.env['rental.resource'].search([('id', '=', resource_instance.resource_id.id)])
            location = resource.location_id
            configuration = location.kafka_configuration

            _logger.debug("Test kafka send: resource %s", resource)
            _logger.debug("Test kafka send: location %s", location)
            _logger.debug("Test kafka send: configuration %s", configuration)

            producer = InstanceMessageProducer(configuration, resource_instance, location, resource)
            producer.sendToKafka()
        return resource_instances
