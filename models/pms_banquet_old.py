from odoo import models, fields, api,_
from odoo.exceptions import UserError,ValidationError
import logging

class PmsAccount(models.Model):
    _name = 'pms_account.account'
    _description = 'Guest account'

    name = fields.Char(string="Account Name")



class PmsBanquet(models.Model):
    _name = "pms.banquet"

    name = fields.Char(string="Banquet Name")
    start_time = fields.Float(string="Start Time")
    end_time = fields.Float(string="End Time")
    partner_id = fields.Many2one('res.partner', string='Partner')
    account_id = fields.Many2one('pms_account.account', string="Account")
    event_banquet_id = fields.Many2one('event.event', string="Event banquet")
    banquet_elements = fields.One2many('pms.banquet.details', 'banquet', string="Banquet Element")
    banquet_events = fields.One2many('pms.banquet.event', 'banquet', string="Banquet Event")
    total_kit_banquet = fields.Float(related='banquet_events.total_kit_banquet', readonly=False)
    state = fields.Selection([('draft', 'Draft'),
                              ('quotation', 'Quotation'),
                              ('sent', 'Sent'),
                              ('confirmed', 'Confirmed'),
                              ('done', 'Checked in'),
                              ('noshow', 'No show'),
                              ('cancel', 'Canceled')], default='draft', string="Banquet State")
    sale_order_ids = fields.One2many('sale.order', 'banquet_id', string="Order")
    order_count = fields.Integer(compute='count_orders', String="Order")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.user.company_id.currency_id,
                                  string="Currency", readonly=True, required=True)
    currency_symbol = fields.Char(related='currency_id.symbol')
    total_price_banquet = fields.Float(compute='get_total_price')
    description = fields.Char(string="Banquet Description")
    duration = fields.Integer(compute='get_total_days', string="Days")
    total_pax = fields.Integer(compute='get_total_pax', string="Pax")
    is_grouped = fields.Boolean(string="Group Account")
    cancellation_policy_id = fields.Many2one('pms.cancel.policy', string="Cancellation Policy")

    def get_total_pax(self):
        for rec in self:
            total_pax = 0
            for event in rec.banquet_events:
                total_pax += event.max_pax
            rec.total_pax = total_pax

    def print_quotation(self):
        return self.env.ref('pms_banquet.banquet_order_report').report_action(self)

    
    def get_total_days(self):
        for rec in self:
            for event in self.banquet_events:
                rec.duration += event.nbr_days

    @api.depends('total_kit_banquet')
    def get_total_price(self):
        for rec in self:
            total_price_banquet = 0.0
            for detail in rec.banquet_events:
                total_price_banquet += detail.total_kit_banquet
            rec.total_price_banquet = total_price_banquet

    def get_details_order(self):
        if not self.banquet_events.banquet_details:
            raise ValidationError(_("You need to complete information before make order !"))
        else:
            list_vals = []
            for event in self.banquet_events:
                price_per_person = event.price_event * event.nbr_days
                description = event.category_event_id.name + '\n' + '  From   ' + str(
                    event.checkin_date) + '   To    ' + str(
                    event.checkout_date) + '           ' + '(' + str(
                    event.nbr_days) + 'Days' + ')' + '\n' + '   Minimum Participants :    ' + str(
                    event.min_pax) + '\n' + 'Price Per Person :  ' + str(price_per_person) + str(self.currency_symbol)
                list_vals.append((0, 0, {'name': description,
                                         'display_type': 'line_section',
                                         }))
                amenities = ', '.join(amenities.name for amenities in event.amenities_id)
                desc = '\n' + amenities + '\n' + str(event.room_price) + ' ' + str(self.currency_symbol)
                list_vals.append((0, 0, {'product_id': event.room_type.product_id.id,
                                         'price_unit': event.room_price * event.nbr_days,
                                         'product_uom_qty': event.max_pax,
                                         'product_uom': event.room_type.product_id.uom_id.id,
                                         'name': desc,
                                         }))
                for kit in event.banquet_details:
                    description = kit.kit_banquet.name + ':\n'
                    desc = ', '.join(served.name for served in kit.kit_banquet.how_served)
                    description += kit.kit_banquet.category_id.name + '-' + desc + ':\n'
                    description += str(kit.kit_banquet.start_time) + '--->' + str(kit.kit_banquet.end_time) + ':\n'
                    for product_pack in kit.product_pack:
                        if product_pack.product_quantity > 1:
                            desc = product_pack.name + '  (' + str(product_pack.product_quantity) + ')'
                        else:
                            desc = product_pack.name
                        description += desc + ', '
                    description += '\n' + str(kit.net_price) + '  ' + str(self.currency_symbol) + ':\n'
                    # description += 'Price Per Person :' + str(event.price_event) + str(self.currency_symbol)
                    list_vals.append((0, 0, {'product_id': kit.product_id.id,
                                             'product_uom_qty': event.max_pax,
                                             'discount': kit.discount,
                                             'product_uom': kit.product.uom_id.id,
                                             'price_unit': kit.net_price * event.nbr_days,
                                             'name': description,
                                             }))
            logging.info('## list_vals: %s' % list_vals)
            return list_vals

    def get_details_optional_product(self):
        list_vals = []
        for event in self.banquet_events:
            for supp in event.supplement_ids:
                description = supp.name + ':\n'
                list_vals.append((0, 0, {'product_id': supp.product_id.id,
                                         'name': supp.product_id.name,
                                         'quantity': supp.quantity,
                                         'price_unit': supp.price_unit,
                                         'uom_id': supp.uom_id.id, }))
        logging.info('## list_vals ( optional ): %s' % list_vals)
        return list_vals

    def make_order_lines(self):
        self.ensure_one()
        # Cancel old quotations
        for bq in self.sale_order_ids:
            bq.action_cancel()
        # Create sale order details
        order = self.get_details_order()
        optional_product = self.get_details_optional_product()
        self.write({'state': 'quotation'})
        action = self.env.ref("sale.action_orders").read()[0]
        action['views'] = [(self.env.ref("sale.view_order_form").id, "form")]
        action['view_mode'] = 'form'
        action['context'] = {
            'default_banquet_id': self.id,
            'default_partner_id': self.partner_id.id,
            'default_order_line': order,
            'default_sale_order_option_ids': optional_product,
        }
        return action

    def confirm_order(self):
        self.ensure_one()
        for bq in self.sale_order_ids:
            if bq.state == 'draft':
                bq.action_confirm()
        self.write({'state': 'confirmed'})
        self.banquet_events.write({'event_state': 'confirmed'})

    def cancel_order(self):
        self.ensure_one()
        for bq in self.sale_order_ids:
            bq.action_cancel()
        self.write({'state': 'draft'})
        self.banquet_events.write({'event_state': 'draft'})

    def count_orders(self):
        for rec in self:
            rec.order_count = len(rec.sale_order_ids)

    
    def dummy(self):
        return True

    
    def action_show_orders(self):
        self.ensure_one()
        tree_id = self.env.ref('sale.view_quotation_tree_with_onboarding').id
        form_id = self.env.ref('sale.view_order_form').id
        return {
            'name': _('Orders created'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree , form',
            'res_model': 'sale.order',
            'views': [(tree_id, 'tree'), (form_id, 'form')],
            'target': 'current',
            'domain': [('id', 'in', self.sale_order_ids.ids)],
        }


class PmsBanquetDetails(models.Model):
    _name = "pms.banquet.details"

    @api.depends('discount')
    def get_net_price(self):
        for rec in self:
            rec.net_price = rec.list_price - (rec.list_price * rec.discount / 100)

    @api.depends('net_price', 'max_pax')
    def get_total_price(self):
        for rec in self:
            rec.total = rec.net_price * rec.max_pax

    def get_banquet_details_total(self):
        for rec in self:
            rec.banquet_details_total += rec.total

    name = fields.Char(string="Name")
    banquet = fields.Many2one('pms.banquet', string="Banquet")
    banquet_event = fields.Many2one('pms.banquet.event', string="Banquet Event")
    max_pax = fields.Integer(related='banquet_event.max_pax', string="Pax")
    room_price = fields.Float(related='banquet_event.room_price', string="Room Price")
    description = fields.Char(related='banquet_event.description', string="Event Description")
    checkin_date = fields.Date(related='banquet_event.checkin_date', string="Event checkin_date")
    checkout_date = fields.Date(related='banquet_event.checkout_date', string="Event checkout_date")
    pax = fields.Integer(related='banquet_event.max_pax', string="Event minimum Participants")
    kit_banquet = fields.Many2one('pms.bq.banquetkit', string="Kit banquet")
    kit_banquet_category = fields.Many2one(related='kit_banquet.category_id', string="Kit banquet Category",
                                           readonly=False)
    product_id = fields.Many2one('product.product', string="Product", domain=[('type_prod', '=', 'banquet')])
    product = fields.Many2one('product.template', string="Product ", domain=[('type_prod', '=', 'banquet')])
    product_pack = fields.One2many(related='product.wk_product_pack', string="Products kit", readonly=False)
    list_price = fields.Float(related='product.lst_price', string="Price", readonly=False)
    standard_price = fields.Float(related='product.standard_price', string="Cost", readonly=False)
    discount = fields.Float(string="Discount (%)")
    net_price = fields.Float(compute='get_net_price', store=True)
    total = fields.Float(compute='get_total_price', store=True)
    banquet_details_total = fields.Float(compute='get_banquet_details_total', store=True)


class PmsBanquetEvent(models.Model):
    _name = "pms.banquet.event"
    _rec_name = "category_event_id"

    
    def duplicate_line(self):
        for rec in self:
            #         # domain = [('id', '=', rec.id)]
            #         # default = rec.search_read(domain)
            dup_event = rec.copy()

    
    def reservation_schedule(self):
        calendar_view_id = self.env.ref('pms_banquet.view_banquet_reservation_calendar').id
        domain = [('id', '=', self.id)]
        action = {'type': 'ir.actions.act_window',
                  'domain': domain,
                  'views': [(calendar_view_id, 'calendar'), (False, 'form')],
                  'name': _('Banquet Reservation'),
                  'res_model': 'pms.banquet.event'}
        return action

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
    room_type = fields.Many2one('pms.room.type', string='Room')
    room_price = fields.Float(related='room_type.list_price', string='Room Price', readonly=False)
    class_room_id = fields.Many2one(related='room_type.class_room_id', string='Class Room')
    amenities_id = fields.Many2many('pms.room.amenities', domain=[('room_amenity_type_id', '=', 'Banquet')],
                                    string='Amenities')
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


class PmsKitBanquet(models.Model):
    _name = "pms.bq.banquetkit"

    @api.depends('banquet_kit_details')
    def get_total_price(self):
        for rec in self:
            total_kit_banquet = 0.0
            for detail in rec.banquet_kit_details:
                total_kit_banquet += detail.total_price
            rec.total_kit_banquet = total_kit_banquet

    name = fields.Char(string="Commercial Name")
    category_id = fields.Many2one('pms.bq.category', string="Category", domain="[('type', '=', 'catalog')]")
    start_time = fields.Float(string="Start")
    end_time = fields.Float(string="End")
    how_served = fields.Many2many('pms.banquet.service', string="Recommendation")
    banquet_kit_details = fields.One2many('pms.bq.banquetkit.details', 'kit_banquet', string="Details Kit Banquet")
    total_details = fields.Float(related='banquet_kit_details.total_price', store=True)
    total_kit_banquet = fields.Float(compute='get_total_price', string="Total Price")
    active = fields.Boolean(string="Active", default=True)
    image_banquet_kit = fields.Binary(string="Banquet Kit Image")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.user.company_id.currency_id,
                                  string="Currency", readonly=True, required=True)
    currency_symbol = fields.Char(related='currency_id.symbol')
    is_cafe = fields.Boolean(string="Pause Cafe")
    is_breakfast = fields.Boolean(string="Petit Dejeuner")


class PmsKitBanquetDetails(models.Model):
    _name = "pms.bq.banquetkit.details"

    @api.depends('product')
    
    def get_total_price(self):
        for rec in self:
            total = 0.0
            for detail in rec.product:
                total += detail.list_price
            rec.total_price = total

    kit_banquet = fields.Many2one('pms.bq.banquetkit', string="Kit banquet")
    variant = fields.Boolean(string="Variant")
    product = fields.Many2one('product.template', string="Product ", domain=[('type_prod', '=', 'banquet')])
    product_pack = fields.One2many(related='product.wk_product_pack', string="Products kit", readonly=False)
    list_price = fields.Float(related='product.lst_price', string="Price", readonly=False)
    standard_price = fields.Float(related='product.standard_price', string="Cost", readonly=False)
    total_price = fields.Float(compute='get_total_price', string="Total Price")
    product_id = fields.Many2one('product.product', string="Kit ", domain=[('type_prod', '=', 'banquet')])


class PmsBanquetHowServed(models.Model):
    _name = "pms.banquet.service"

    name = fields.Char(string="Recommendation")

# class BanquetSupplement(models.Model):
#     _name = "pms.bq.supplement"
#
#     def get_total_price(self):
#         for rec in self:
#             rec.total += rec.price_unit * rec.qte
#
#     total = fields.Float(compute='get_total_price', string="Total")
#     event_id = fields.Many2one('pms.banquet.event', string="Event")
#     product_id = fields.Many2one('product.product', string="Supplements")
#     name = fields.Char(related='product_id.name', string="Description")
#     qte = fields.Integer(string="Quantity", default=1, required=1)
#     price_unit = fields.Float(related='product_id.lst_price', string="Price Unit")

# access_pms_bq_supplement_user,pms_bq.supplement,model_pms_bq_supplement,pms_reservation.group_hotel_user,1,1,1,0
# access_pms_bq_supplement_manager,pms_bq.supplement,model_pms_bq_supplement,pms_reservation.group_hotel_manager,1,1,1,1
