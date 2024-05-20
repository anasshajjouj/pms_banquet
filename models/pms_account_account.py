from odoo import models, fields

class PmsAccount(models.Model):
    _name = 'pms_account.account'
    _description = 'Guest account'

    name = fields.Char(string="Account Name")