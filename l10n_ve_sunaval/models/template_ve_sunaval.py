from odoo import _, models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("ve_sunaval")
    def _get_ve_sunaval_template_data(self):
        return {
            "name": _("SUNAVAL"),
            "sequence": 40,
            "code_digits": "3",
            "property_account_receivable_id": "account_144860100001",
            "property_account_payable_id": "account_27201010000101",
            "property_account_expense_categ_id": "account_44999010000001",
            "property_account_income_categ_id": "account_5399901",
        }

    @template("ve_sunaval", "res.company")
    def _get_ve_sunaval_res_company(self):
        return {
            self.env.company.id: {
                "account_fiscal_country_id": "base.ve",
                "cash_account_code_prefix": "111010100",
                "bank_account_code_prefix": "113010101",
                "transfer_account_code_prefix": "1860301",
                "transfer_account_id": "account_186030100001",
                "account_journal_suspense_account_id": "account_186020100001",
                "default_cash_difference_income_account_id": "account_276010100001",
                "default_cash_difference_expense_account_id": "account_186010100001",
                "income_currency_exchange_account_id": "account_532980107",
                "expense_currency_exchange_account_id": "account_432980107",
                "account_journal_early_pay_discount_loss_account_id": (
                    "account_44999010000001"
                ),
                "account_journal_early_pay_discount_gain_account_id": (
                    "account_5399901"
                ),
                "tax_calculation_rounding_method": "round_globally",
                "account_sale_tax_id": "tax1sale",
                "account_purchase_tax_id": "tax1purchase",
            },
        }

    @template("ve_sunaval", "account.journal")
    def _get_ve_sunaval_account_journal(self):
        return {
            "bank": {"default_account_id": "account_11301010101101"},
            "cash": {"default_account_id": "account_111010100001"},
        }
