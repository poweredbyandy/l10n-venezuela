from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    municipality_id = fields.Many2one("res.country.municipality", "Municipality")
    parish_id = fields.Many2one("res.country.parish", "Parish")

    @api.onchange("municipality_id")
    def _onchange_municipality_id(self):
        self.parish_id = False

    @api.onchange("state_id")
    def _onchange_state_id(self):
        self.municipality_id = False
        self.parish_id = False
