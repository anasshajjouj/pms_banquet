from odoo import models, fields, api,_


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