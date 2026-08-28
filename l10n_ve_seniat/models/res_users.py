from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        return super(
            ResUsers, self.with_context(skip_l10n_ve_taxpayer_type_country=True)
        ).create(vals_list)
