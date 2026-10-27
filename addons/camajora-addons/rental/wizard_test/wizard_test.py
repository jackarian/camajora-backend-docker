from odoo import api, fields, models, _
import logging
from odoo.exceptions import ValidationError
from datetime import datetime, time, timedelta
import math
import decimal
from decimal import Decimal
import pytz

timezone = pytz.timezone('Europe/Rome')
_logger = logging.getLogger(__name__)

decimal.getcontext().rounding = decimal.ROUND_HALF_EVEN


class MyWizard(models.TransientModel):
    _name = 'my.wizard'
    _description = 'Rental Booking Wizard'
    _inherit = ['multi.step.wizard.mixin']

    location = fields.Many2one(
        comodel_name='rental.location',
        name="Location",
        required=True,
        ondelete='cascade',
        default=lambda self: self._default_project_id(),
    )
    location_id = fields.Integer(string=_('Id'), default=lambda self: self._default_project_id())

    resource_id = fields.Many2one('rental.resource', string=_('Resources'),
                                  default=lambda self: self._default_resource())
    credit_cost = fields.Integer(string=_('Credit Cost'),
                                 readonly=True, compute='_compute_credits_cost', store=True)
    credit_left = fields.Integer(string=_('Credit Left'),
                                 readonly=True, compute='_compute_credits_available')

    credits_used = fields.Integer(string=_('Credits Used'),
                                  readonly=True, compute='_compute_credits_used', store=True)

    instances_ids = fields.Many2one('rental.resource.instance', string=_('Instances'),
                                    default=lambda self: self._default_resource_instance(),
                                    required=True)

    name = fields.Char(string=_('SKU'))

    # Campi per la creazione di una prenotazione
    user_id = fields.Many2one('res.partner', string=_('User'), required=True)
    date = fields.Date(string=_('Date'), default=lambda self: fields.Date.today())
    duration_id = fields.Many2one('rental.duration', string=_('Duration'), required=True)

    duration = fields.Selection(related='duration_id.type', string=_('Duration Type'))

    start_date = fields.Date(string=_('Start Date'), required=True)
    end_date = fields.Date(string=_('End Date'), required=False)
    start_time = fields.Float(string=_('Start Time'), required=False)
    end_time = fields.Float(string=_('End Time'), required=False)

    half_day_type = fields.Selection([
        ('morning', _('09:00 - 14:00')),
        ('afternoon', _('14:00 - 19:00')),
        ('day', _('09:00 - 19:00')),
    ], string=_('Half Day'), default='morning', required=False)

    total_hours = fields.Integer(string=_('Total Hours'), readonly=True, compute='_compute_range', store=True)
    dt_start = fields.Datetime(string=_('Booking From'), readonly=True, compute='_compute_range', store=True)
    dt_end = fields.Datetime(string=_('Booking To'), readonly=True, compute='_compute_range', store=True)

    # Stati finali
    token = fields.Char(string=_('Secret Token'), readonly=True)
    qr_code = fields.Binary(string=_('QR Code'), readonly=True)
    booking_id = fields.Integer(string=_('Booking ID'))

    @api.depends(
        'duration',
        'start_date',
        'end_date',
        'start_time',
        'end_time',
        'half_day_type'
    )
    def _compute_range(self):
        for record in self:
            slot_range = compute_range(
                record.duration,
                record.start_date,
                record.end_date,
                record.start_time,
                record.end_time,
                record.half_day_type,
                record.resource_id.availability_id.starthour,
                record.resource_id.availability_id.endhour,
            )
            record.total_hours = slot_range['total_hours']
            record.dt_start = slot_range['dt_start']
            record.dt_end = slot_range['dt_end']

        _logger.debug("Date limit calculated:%s", slot_range)

    @api.depends(
        'resource_id'
    )
    def _compute_credits_cost(self):
        for record in self:
            record.credit_cost = record.resource_id.credit_cost

    @api.depends(
        'location'
    )
    def _compute_credits_available(self):
        for record in self:
            record.credit_left = record.location.partner_id.credits

    @api.depends(
        'total_hours',
        'resource_id'
    )
    def _compute_credits_used(self):
        slot = 3600
        for record in self:
            credit_cost = 0
            credit_cost += (
                    self.total_hours *
                    (self.resource_id.credit_cost / slot)  # hourly credit cost
                # applicare sconto
            )
            credit_cost = int(math.ceil(credit_cost))
            record.credits_used = credit_cost

    @api.constrains('instances_ids', 'dt_start', 'dt_end')
    def _check_dates(self):

        sql_check = """
                    select COUNT(*) from rental_booking_slot rbs 
                          where id != %s and resource_instance_id = %s 
                    and ((dt_start <= %s AND dt_end >= %s)
                    or (dt_start <= %s AND dt_end >= %s)
                    or (dt_start <= %s AND dt_end >= %s)
                    or (dt_start >= %s AND dt_end <= %s));"""

        for record in self:
            # Starting date must be prior to the ending date
            dt_start = record.dt_start
            dt_end = record.dt_end
            if dt_end < dt_start:
                raise ValidationError(_('The ending date must not be prior to the starting date.'))

            self.env.cr.execute(sql_check, (record.id, record.instances_ids.id,
                                            record.dt_start, record.dt_start,
                                            record.dt_end, record.dt_end,
                                            record.dt_start, record.dt_end,
                                            record.dt_start, record.dt_end))

            reservetion_found = self.env.cr.fetchone()[0]
            _logger.debug('Reservation found: %s', reservetion_found)

            if reservetion_found > 0:
                raise ValidationError(_('You can not have an overlap between two booking slots of the same resource.\n'
                                        'Please correct the start and/or end dates of your booking slot.'))

    @api.depends('booking_id')
    def _compute_unlock_link(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.app.url')

        for record in self:
            record.unlock_link = '{}/api/v1/unlock/?token={}&sku={}'.format(
                base_url,
                record.booking_id.token,
                record.instances_ids.code,
            )

    @api.model
    def _selection_state(self):
        return [
            ('start', 'Start'),
            ('error', 'Error'),
            ('final', 'Final'),
        ]

    @api.model
    def _default_project_id(self):

        _logger.debug('active id is %s', self.env.context.get('active_id'))
        resource = self.env['rental.resource'].search([('id', '=', self.env.context.get('active_id'))])
        return resource.location_id

    @api.model
    def _default_resource(self):
        selected_ids = self.env.context.get('active_ids', [])
        selected_records = self.env['rental.resource'].browse(selected_ids)
        return selected_records

    @api.model
    def _default_resource_instance(self):
        instances = self.env['rental.resource.instance'].search(
            [('resource_id', '=', self.env.context.get('active_id'))])
        return instances[0]

    def state_exit_start(self):

        owner = self.location.partner_id

        if owner.credits < self.credits_used:
            raise ValidationError('Not enough credits')

        owner.sudo().write({
            'credits': owner.credits - self.credits_used
        })

        slot = {
            'partner_id': self.user_id.id,
            'owner_id': self.location.partner_id.id,
            'duration_id': self.duration_id.id,
            'resource_instance_id': self.instances_ids.id,
            'resource_id': self.resource_id.id,
            'location_id': self.location_id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'half_day_type': self.half_day_type,
            'total_hours': self.total_hours,
            'dt_start': self.dt_start,
            'dt_end': self.dt_end,
            'credit_total': self.credits_used,
            'credit_cost': self.credit_cost
        }

        pronation = {
            'name': 'random',
            'date': self.start_date,
            'user_id': self.user_id.id,
            'rent_channel': 'main_site',
            'state': 'confirmed',
            'slot_ids': [
                (0, 0, slot)
            ]
        }

        booking = self.env['rental.booking'].create(pronation)
        '''self.env.cr.commit()'''
        self.booking_id = booking.slot_ids[0].id
        self.send_mail()
        self.state = 'final'

    def send_mail(self):
        _logger.debug("Invia email Reservation slot :%s", self.booking_id)
        template_ids = self.env.ref('rental.reservation_confirm_email').id
        if template_ids:
            self.env['mail.template'].browse(template_ids).send_mail(self.booking_id, force_send=True)

    def state_exit_error(self):
        self.state = 'error'

    @api.model
    def _compute_current_id(self):
        _logger.debug("Computing id")
        return self.env.context.get('active_id')


def conv_flot_totime(t):
    hour, minute = divmod(t, 1)
    minute *= 60
    return int(hour), int(minute)


def conv_time_float(value):
    vals = value.split(':')
    t, hours = divmod(float(vals[0]), 24)
    t, minutes = divmod(float(vals[1]), 60)
    minutes = minutes / 60.0
    return hours + minutes


def second_between_time(start, end):
    ds = timedelta(hours=start.hour, minutes=start.minute)
    de = timedelta(hours=end.hour, minutes=end.minute)
    delta = de - ds
    return delta.total_seconds()


def compute_range(duration, start_date, end_date, start_time, end_time, half_day_type,
                  start_available, end_available):
    duration = duration or 'hourly'
    start_date = start_date or fields.Date.today()
    end_date = end_date or fields.Date.today()
    """ Conversione delle date in formato float passata dall'applicazione"""
    start_time_hour, start_time_minute = conv_flot_totime(float(start_time or 0))
    end_time_hour, end_time_minute = conv_flot_totime(float(end_time or 0))

    start_time_reservation = time(start_time_hour, start_time_minute)
    end_time_reservation = time(end_time_hour, end_time_minute)

    half_day_type = half_day_type or 'morning'
    day_hours = 0
    dt_start = None
    dt_end = None
    shour, sminute = conv_flot_totime(start_available or 9)
    ehour, eminute = conv_flot_totime(end_available or 9)
    location_start = time(shour, sminute)
    location_end = time(ehour, eminute)
    secondi_giornalieri_location = second_between_time(location_start, location_end)

    if duration == 'hourly':
        day_hours = second_between_time(start_time_reservation, end_time_reservation)
        dt_start = datetime.combine(start_date, start_time_reservation)
        dt_end = datetime.combine(start_date, end_time_reservation)

    elif duration == 'half_daily':

        tmp_start = None
        tmp_end = None
        if half_day_type == 'morning':
            tmp_start = time(shour, sminute)
            tmp_end = time(13, 59)
        if half_day_type == 'afternoon':
            tmp_start = time(14, 0)
            tmp_end = time(ehour, eminute)
        if half_day_type == 'day':
            tmp_start = time(shour, sminute)
            tmp_end = time(ehour, eminute)
        day_hours = second_between_time(tmp_start, tmp_end)
        dt_start = datetime.combine(start_date, tmp_start)
        dt_end = datetime.combine(start_date, tmp_end)

    elif duration == 'daily':
        day_hours = secondi_giornalieri_location
        dt_start = datetime.combine(start_date, time(shour, sminute))
        dt_end = datetime.combine(end_date, time(ehour, eminute))

    elif duration == 'weekly':
        day_hours = secondi_giornalieri_location
        dt_start = datetime.combine(get_monday(start_date), time(shour, sminute))
        dt_end = datetime.combine(get_sunday(end_date), time(ehour, eminute))

    elif duration == 'monthly':
        day_hours = secondi_giornalieri_location
        dt_start = datetime.combine(start_date.replace(day=1), time(shour, sminute))
        dt_end = datetime.combine(last_day_of_month(start_date), time(ehour, eminute))

    number_of_days = (dt_end - dt_start).days + 1

    total_hours = number_of_days * day_hours
    dt_start = timezone.localize(dt_start).astimezone(pytz.utc).replace(tzinfo=None)
    dt_end = timezone.localize(dt_end).astimezone(pytz.utc).replace(tzinfo=None)

    return {'total_hours': total_hours, 'dt_start': dt_start, 'dt_end': dt_end}


def last_day_of_month(any_day):
    next_month = any_day.replace(day=28) + timedelta(days=4)  # this will never fail
    return next_month - timedelta(days=next_month.day)


def get_monday(day):
    return day - timedelta(days=(day.weekday() % 7))


def get_sunday(day):
    return day + timedelta(days=(6 - (day.weekday() % 7)))
