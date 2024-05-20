from odoo import models, fields, api,_
from odoo.exceptions import UserError,ValidationError
import logging


class PmsBanquetEvent(models.Model):
    _name = "pms.banquet.event"
    _rec_name = "category_event_id"

    
    def duplicate_line(self):
        for rec in self:
            #         # domain = [('id', '=', rec.id)]
            #         # default = rec.search_read(domain)
            dup_event = rec.copy()

    
    # def reservation_schedule(self):
    #     calendar_view_id = self.env.ref('pms_banquet.view_banquet_reservation_calendar').id
    #     domain = [('id', '=', self.id)]
    #     action = {'type': 'ir.actions.act_window',
    #               'domain': domain,
    #               'views': [(calendar_view_id, 'calendar'), (False, 'form')],
    #               'name': _('Banquet Reservation'),
    #               'res_model': 'pms.banquet.event'}
    #     return action

    def generate_kit_banquets(self):
        rec_bq_details = self.env['pms.banquet.details']
        for rec in self:
            for kit in rec.kit_banquets:
                for bq_detail in kit.banquet_kit_details:
                    rec_bq_details.create({'name': bq_detail.product.name,
                                           'banquet': self.banquet.id,
                                           'banquet_event': self.id,
                                           'kit_banquet': kit.id,
                                           'product': bq_detail.product.id,
                                           'product_id': bq_detail.product_id.id, })

    @api.depends('room_price', 'banquet_details.net_price')
    def get_price_event(self):
        for rec in self:
            price_event = 0.0
            for detail in rec.banquet_details:
                price_event += detail.net_price
            rec.price_event = price_event + rec.room_price

    @api.depends('price_kit_banquet', 'nbr_days')
    def get_total_price(self):
        for rec in self:
            rec.total_kit_banquet += rec.price_kit_banquet * rec.nbr_days

    @api.depends('banquet_details_total', 'price_event', 'max_pax')
    def get_price_kit_banquet(self):
        for rec in self:
            for detail in rec.banquet_details:
                rec.price_kit_banquet = detail.banquet_details_total + (rec.price_event * rec.max_pax)

    
    def dummy(self):
        return True

    @api.depends('checkin_date', 'checkout_date')
    def compute_duration(self):
        for rec in self:
            if rec.checkout_date and rec.checkin_date:
                nbr_days = (rec.checkout_date - rec.checkin_date).days
                rec.nbr_days = nbr_days + 1

    account_id = fields.One2many('pms_account.account', 'event_id', string="Account")
    price_event = fields.Float(compute='get_price_event', string="Event Price", readonly=False, store=True)
    banquet_details = fields.One2many('pms.banquet.details', 'banquet_event', string="Benefits")
    banquet_details_total = fields.Float(related='banquet_details.banquet_details_total', store=True)
    category_event_id = fields.Many2one('event.type', string="Event Category")
    category_event_name = fields.Char(related='category_event_id.name', string="Event Category")
    banquet = fields.Many2one('pms.banquet', string="Banquet", ondelete='cascade')
    banquet_name = fields.Char(related='banquet.name', string="Banquet Name")
    banquet_state = fields.Selection(related='banquet.state', string="Banquet State")
    partner_id = fields.Many2one(related='banquet.partner_id', string="Partner", store=True)
    name = fields.Char(string="Name")
    description = fields.Char(string="Description")
    checkin_date = fields.Date(string="Checkin_Date")
    checkout_date = fields.Date(string="Checkout_Date")
    arrival_time = fields.Float(string="Arrival time")
    departure_time = fields.Float(string="Departure time")
    # room_type = fields.Many2one('pms.room.type', string='Room')
    room_price = fields.Float(related='room_type.list_price', string='Room Price', readonly=False)
    class_room_id = fields.Many2one(related='room_type.class_room_id', string='Class Room')
    # amenities_id = fields.Many2many('pms.room.amenities', domain=[('room_amenity_type_id', '=', 'Banquet')],
    #                                 string='Amenities')
    min_pax = fields.Integer(string="Minimum Participants")
    max_pax = fields.Integer(string="Maximum Participants")
    kit_banquets = fields.Many2many('pms.bq.banquetkit', string="Selection Kit Banquet")
    event_state = fields.Selection([('draft', 'Draft'),
                                    ('quotation', 'Quotation'),
                                    ('sent', 'Sent'),
                                    ('confirmed', 'Confirmed'),
                                    ('done', 'Checked in'),
                                    ('noshow', 'No show'),
                                    ('cancel', 'Canceled')], default='draft', string="Event State")
    total_kit_banquet = fields.Float(compute='get_total_price', string="Total Kit Banquet", readonly=False)
    price_kit_banquet = fields.Float(compute='get_price_kit_banquet', string="Price kit banquet", readonly=False)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.user.company_id.currency_id,
                                  string="Currency", readonly=True, required=True)
    currency_symbol = fields.Char(related='currency_id.symbol')
    nbr_days = fields.Integer(compute="compute_duration", string="Day Number", default=1, readonly=False, store=True)
    supplement_ids = fields.One2many('sale.order.option', 'event_id')
    payment_ids = fields.One2many('account.payment', 'event_id', string="Payments", copy=False, readonly=True)

    
    def action_create_banquet_account(self):
        account_obj = self.env['pms_account.account']
        invoice_mode = self.partner_id and self.partner_id.default_invoicing_mode_id.id or False
        vals = {
            # 'reservation_id': self.id,
            'banquet_account': True,
            'event_id': self.id,
            'guest_to_invoice': self.partner_id.id,
            'how_to_charge': invoice_mode,
            'adult_number': self.max_pax,
            'event_nbr_day': self.nbr_days,
        }

        if self.banquet.is_grouped:
            if not self.banquet.account_id:
                # create group account
                vals['group_account'] = True
                desc = self.env['ir.sequence'].next_by_code(
                    'pms_banquet.account.group_banquet') + '/' + self.banquet.name
                vals['name'] = desc
                vals['checkin_date'] = self.checkin_date
                vals['checkout_date'] = self.checkout_date
                self.banquet.account_id = account_obj.with_context(mail_create_nosubscribe=True).create(vals)

            vals['parent_id'] = self.banquet.account_id.id
        vals['group_account'] = False
        vals['checkin_date'] = self.checkin_date
        vals['checkout_date'] = self.checkout_date
        vals['duration'] = self.nbr_days
        vals['name'] = self.env['ir.sequence'].next_by_code(
            'pms_banquet.account.banquet') + '/' + self.category_event_id.name
        account_id = account_obj.create(vals)

        self.generate_event_charges(account_id)

    def generate_event_charges(self, account_id):
        tmp_date = self.checkin_date
        while tmp_date <= self.checkout_date:
            # add room line
            account_id.add_line({
                'product_id': self.room_type.product_id.id,
                'product_uom_qty': self.max_pax,
                'price_unit': self.room_price,
                'date': tmp_date
            })

            # add event details
            for charge in self.banquet_details:
                vals = {
                    'product_id': charge.product_id.id,
                    'product_uom_qty': charge.max_pax,
                    'price_unit': charge.list_price,
                    'discount': charge.discount,
                    # 'section_id': ,
                    # 'tag': 'FEES',
                    'date': tmp_date

                }
                account_id.add_line(vals)
            tmp_date = tmp_date + timedelta(days=1)

    
    def _check_checkin_date(self):
        business_day = self.env['pms.property.settings'].get_property_setting('business_day')
        for rec in self:
            if rec.checkin_date > business_day:
                raise ValidationError(_(
                    'The Check-in date is %s days from now (%s). till then you can not proceed with the check_in!!:'
                    % ((rec.checkin_date - rec.get_default_business_day()).days, rec.checkin_date)))

    def get_default_business_day(self):
        business_day = self.env['pms.property.settings'].get_property_setting('business_day')
        if business_day:
            return business_day
        else:
            return fields.Date.today()

    
    def act_open_banquet_account(self):
        self._check_checkin_date()
        vals = {
            'name': _('Check-in'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': self.env.ref('pms_banquet.view_open_banquet_account_form').id,
            'context': {'default_event_id': self.id},
            'res_model': 'pms.bq.open.account',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
        return vals

