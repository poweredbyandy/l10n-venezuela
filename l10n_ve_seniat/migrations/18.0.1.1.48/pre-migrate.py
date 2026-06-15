_XML_ID_RENAMES = [
    ("view_account_book_tree", "account_book_view_list"),
    ("view_account_book_form", "account_book_view_form"),
    ("action_account_book", "account_book_action"),
    ("view_res_country_municipality_tree", "res_country_municipality_view_list"),
    ("view_res_country_municipality_form", "res_country_municipality_view_form"),
    ("action_res_country_municipality", "res_country_municipality_action"),
    ("view_res_country_parish_tree", "res_country_parish_view_list"),
    ("view_res_country_parish_form", "res_country_parish_view_form"),
    ("action_res_country_parish", "res_country_parish_action"),
    ("action_seniat_companies", "res_company_action_seniat"),
    ("view_invoice_tree", "account_move_view_list"),
    ("view_tax_form_inherit_l10n_ve", "account_tax_view_form"),
    ("view_account_payment_form_l10n_ve", "account_payment_view_form"),
    ("view_currency_form_l10n_ve_chatter", "res_currency_view_form_chatter"),
    ("view_currency_rate_form_l10n_ve", "res_currency_rate_view_form"),
    ("view_currency_form_l10n_ve_rate_list", "res_currency_view_form_rate_list"),
    ("view_account_move_reversal_form_l10n_ve", "account_move_reversal_view_form"),
    ("view_account_debit_note_form_l10n_ve", "account_debit_note_view_form"),
    (
        "product_template_tree_l10n_ve_sale_tax",
        "product_template_view_list_l10n_ve_sale_tax",
    ),
    (
        "product_template_form_l10n_ve_sale_tax",
        "product_template_view_form_l10n_ve_sale_tax",
    ),
    (
        "product_product_form_l10n_ve_sale_tax",
        "product_product_view_form_l10n_ve_sale_tax",
    ),
    (
        "view_l10n_ve_book_folio_void_wizard_form",
        "l10n_ve_book_folio_void_wizard_view_form",
    ),
    ("menu_seniat_account_book", "account_book_menu"),
    ("account_book_company_rule", "account_book_rule_company"),
    ("account_book_section_company_rule", "account_book_section_rule_company"),
    ("account_book_document_company_rule", "account_book_document_rule_company"),
    ("l10n_ve_book_folio_void_company_rule", "l10n_ve_book_folio_void_rule_company"),
]


def migrate(cr, version):
    for old_name, new_name in _XML_ID_RENAMES:
        cr.execute(
            """
            UPDATE ir_model_data
               SET name = %s
             WHERE module = 'l10n_ve_seniat'
               AND name = %s
            """,
            (new_name, old_name),
        )
