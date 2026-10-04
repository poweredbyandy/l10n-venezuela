# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCurrencyRate(models.Model):
    _name = "res.currency.rate"
    _inherit = ["res.currency.rate", "mail.thread"]

    rate = fields.Float(tracking=True)
