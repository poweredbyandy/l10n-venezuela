from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _get_property_accounts(self, additional_properties):
        return {
            **super()._get_property_accounts(additional_properties),
            "property_account_customer_advance_id": "res.partner",
            "property_account_supplier_advance_id": "res.partner",
        }
