from odoo import models, fields, api,_

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
