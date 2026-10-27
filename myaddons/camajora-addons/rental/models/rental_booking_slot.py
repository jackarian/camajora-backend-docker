# Copyright 2020 Metadonors srl
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, time, timedelta
import pytz
import logging

timezone = pytz.timezone('Europe/Rome')

_logger = logging.getLogger(__name__)


class RentalBookingSlot(models.Model):
    _name = 'rental.booking.slot'
    _description = 'Rental Booking Slot'
    """ :(
    _sql_constraints = [(
        'no_overlap',
        'EXCLUDE USING gist (resource_instance_id WITH =, tsrange(dt_start, dt_end) WITH &&)',
        _('Overlapping slots')  # CREATE EXTENSION btree_gist;
    )]
    """
    name = fields.Char(related='resource_instance_id.code', string=_('SKU'))
    partner_id = fields.Many2one(related="booking_id.user_id", store=True, string=_("Customer"))
    booking_id = fields.Many2one('rental.booking', string=_('Booking'), required=True, ondelete='cascade')
    resource_instance_id = fields.Many2one('rental.resource.instance', string=_('Resource Instance'), required=True)
    resource_id = fields.Many2one('rental.resource', related="resource_instance_id.resource_id", store=True,
                                  string=_('Resource'))
    location_id = fields.Many2one('rental.location', related="resource_id.location_id", store=True,
                                  string=_('Location'))
    owner_id = fields.Many2one('res.partner', related="resource_id.location_id.partner_id", store=True,
                               string=_('Owner'))
    duration_id = fields.Many2one('rental.duration', string=_('Duration'), required=True)
    state = fields.Selection(related="booking_id.state", string="State")
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
    formatted_total_hours = fields.Char(string=_('Total Hours Formatted'), readonly=True,
                                        compute='_compute_formatted_total_hours', store=False)
    unlock_link = fields.Char(string=_('Unlock Link'), readonly=True, compute='_compute_unlock_link')

    @api.model
    def search(self, args, offset=0, limit=None, order=None):
        backend = self.env.context.get('backend')

        if backend is not None:
            current_owner = self.env['res.partner'].search([('id', '=', self.env.user.partner_id.id)])

            if current_owner:
                args = [] if args is None else args.copy()
                if current_owner.parent_id is not None:
                    args.append(('owner_id', 'in', [current_owner.id, current_owner.parent_id.id]))
                else:
                    args.append(('owner_id', '=', current_owner.id))

        return super(RentalBookingSlot, self).search(args, offset, limit, order)

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

    @api.depends('total_hours')
    def _compute_formatted_total_hours(self):
        for record in self:
            record.formatted_total_hours = format_total_hour(record.total_hours)

    @api.constrains('resource_instance_id', 'dt_start', 'dt_end')
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

            self.env.cr.execute(sql_check, (record.id, record.resource_instance_id.id,
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
                record.resource_instance_id.code,
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if str(vals.get('end_date')) == 'False':
                vals['end_date'] = vals.get('start_date')

        records = super().create(vals_list)
        if any(record.start_date < fields.Date.today() for record in records):
            raise ValidationError(_('The starting date must not be in the past.'))
        return records


# ------------


def last_day_of_month(any_day):
    next_month = any_day.replace(day=28) + timedelta(days=4)  # this will never fail
    return next_month - timedelta(days=next_month.day)


def get_monday(day):
    return day - timedelta(days=(day.weekday() % 7))


def get_sunday(day):
    return day + timedelta(days=(6 - (day.weekday() % 7)))


def format_total_hour(seconds):
    seconds = 0 if seconds is None else seconds
    ore, mi = divmod(float(seconds), 3600)
    m, s = divmod(float(mi), 60)
    return str(int(ore)) + ":" + str(int(m))


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
        dt_end = datetime.combine(last_day_of_month(end_date), time(ehour, eminute))

    number_of_days = (dt_end - dt_start).days + 1

    total_hours = number_of_days * day_hours
    dt_start = timezone.localize(dt_start).astimezone(pytz.utc).replace(tzinfo=None)
    dt_end = timezone.localize(dt_end).astimezone(pytz.utc).replace(tzinfo=None)

    return {'total_hours': total_hours, 'dt_start': dt_start, 'dt_end': dt_end}
