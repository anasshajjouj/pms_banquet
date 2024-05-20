from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging


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
    # cancellation_policy_id = fields.Many2one('pms.cancel.policy', string="Cancellation Policy")

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

