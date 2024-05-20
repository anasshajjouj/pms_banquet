from odoo import models, fields, api,_
from odoo.exceptions import UserError,ValidationError
import logging


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

