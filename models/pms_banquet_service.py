from odoo import models, fields, api,_
# from odoo.exceptions import UserError,ValidationError
# import logging
class PmsBanquetHowServed(models.Model):
    _name = "pms.banquet.service"

    name = fields.Char(string="Recommendation")