from odoo import fields
from odoo.tools.mail import html2plaintext
from odoo.tools.misc import formatLang

TOTAL_KEYS = (
    "exempt",
    "gross",
    "discount",
    "subtotal",
    "vat_base",
    "vat",
    "invoice",
    "igtf_base",
    "igtf",
    "payable",
)


class Namespace(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as err:
            raise AttributeError(name) from err


def money(env, amount, currency):
    return formatLang(env, amount or 0.0, currency_obj=currency)


def _group_has_rate(env, group):
    taxes = env["account.tax"].browse(group.get("involved_tax_ids", []))
    return any(taxes.mapped("amount"))


def tax_totals_groups(move):
    totals = move.tax_totals or {}
    all_groups = [
        group
        for subtotal in totals.get("subtotals", [])
        for group in subtotal.get("tax_groups", [])
    ]
    vat_groups = [
        g for g in all_groups if g.get("id") != -1 and _group_has_rate(move.env, g)
    ]
    exempt_groups = [
        g for g in all_groups if g.get("id") != -1 and not _group_has_rate(move.env, g)
    ]
    igtf_groups = [g for g in all_groups if g.get("id") == -1]
    vat_group = vat_groups[0] if vat_groups else {}
    igtf_group = igtf_groups[0] if igtf_groups else {}
    return totals, vat_group, igtf_group, exempt_groups


def _group_base(group, suffix):
    return group.get(
        "display_base_amount" + suffix, group.get("base_amount" + suffix, 0.0)
    )


def totals_values(totals, vat_group, igtf_group, exempt_groups, suffix):
    exempt = sum(_group_base(g, suffix) for g in exempt_groups)
    subtotal = totals.get("base_amount" + suffix, 0.0)
    if totals.get("l10n_ve_show_global_discount"):
        gross = totals.get("l10n_ve_subtotal_gross" + suffix, subtotal)
        discount = totals.get("l10n_ve_global_discount_amount" + suffix, 0.0)
    else:
        gross = subtotal
        discount = 0.0
    total = totals.get("total_amount" + suffix, 0.0)
    invoice_total = totals.get("l10n_ve_igtf_total_without_igtf" + suffix, total)
    return {
        "exempt": exempt,
        "gross": gross,
        "discount": discount,
        "subtotal": subtotal,
        "vat_base": _group_base(vat_group, suffix),
        "vat": vat_group.get("tax_amount" + suffix, 0.0),
        "invoice": invoice_total,
        "igtf_base": _group_base(igtf_group, suffix),
        "igtf": igtf_group.get("tax_amount" + suffix, 0.0),
        "payable": total,
    }


def totals_namespace(move):
    """Formatted totals in document (doc) and company (comp) currency.

    With a single currency ``doc`` values are empty strings and ``comp``
    holds the amounts in the document currency, so the right column of the
    pre-printed form always shows the figures.
    """
    env = move.env
    doc_currency = move.currency_id
    comp_currency = move.company_currency_id
    dual = comp_currency != doc_currency
    totals, vat_group, igtf_group, exempt_groups = tax_totals_groups(move)
    doc_values = totals_values(totals, vat_group, igtf_group, exempt_groups, "_currency")
    comp_values = totals_values(totals, vat_group, igtf_group, exempt_groups, "")
    doc = Namespace()
    comp = Namespace()
    doc_amount = Namespace()
    comp_amount = Namespace()
    for key in TOTAL_KEYS:
        doc_amount[key] = doc_values[key]
        comp_amount[key] = comp_values[key] if dual else doc_values[key]
        if dual:
            doc[key] = money(env, doc_values[key], doc_currency)
            comp[key] = money(env, comp_values[key], comp_currency)
        else:
            doc[key] = ""
            comp[key] = money(env, doc_values[key], doc_currency)
    return Namespace(doc=doc, comp=comp, doc_amount=doc_amount, comp_amount=comp_amount)


def vat_percent(move):
    _totals, vat_group, _igtf_group, _exempt_groups = tax_totals_groups(move)
    tokens = [
        token
        for token in vat_group.get("group_name", "").replace(":", " ").split()
        if "%" in token
    ]
    return tokens[0] if tokens else "16%"


def igtf_percent(move):
    value = move.l10n_ve_report_igtf_percent()
    return f"{str(value).replace('.', ',')}%"


def discount_percent(move):
    totals, _vat_group, _igtf_group, _exempt_groups = tax_totals_groups(move)
    if totals.get("l10n_ve_show_global_discount") and totals.get(
        "l10n_ve_global_discount_percentage"
    ):
        return "%.2f%%" % (totals["l10n_ve_global_discount_percentage"] * 100.0)
    return ""


def product_lines(move):
    return [
        line
        for line in move.l10n_ve_report_invoice_lines()
        if line.display_type == "product"
    ]


def document_title(move):
    if move.move_type == "out_refund" and move.reversed_entry_id:
        return "NOTA DE CREDITO"
    if move.move_type == "out_invoice" and move.debit_origin_id:
        return "NOTA DE DEBITO"
    if move.move_type == "out_invoice":
        return "FACTURA"
    return "DOCUMENTO"


def document_label(move):
    if move.move_type == "out_refund":
        return "Nota de Credito:"
    if move.move_type == "out_invoice" and move.debit_origin_id:
        return "Nota de Debito:"
    return "Factura:"


def invoice_number(move):
    raw = (move.l10n_ve_invoice_number or move.name or "").strip()
    if "/" in raw:
        raw = raw.rsplit("/", 1)[-1]
    return raw


def emission(move):
    dt = move.l10n_ve_invoice_date
    if dt:
        dt = fields.Datetime.context_timestamp(move, dt)
        return dt.strftime("%d/%m/%Y %I:%M%p")
    if move.invoice_date:
        return move.invoice_date.strftime("%d/%m/%Y")
    return ""


def partner_name(move):
    partner = move.partner_id
    name = partner.name or ""
    if move.l10n_ve_on_behalf_of_third_party and move.l10n_ve_third_party_partner_id:
        name = move.l10n_ve_third_party_partner_id.name or name
    return name


def partner_phone(partner):
    return (partner.mobile or partner.phone or "").strip()


def partner_address(partner):
    addr = (partner._display_address(without_company=True) or "").replace("\n", ", ")
    parts = [part.strip() for part in addr.split(",")]
    return ", ".join(part for part in parts if part)


def seller(move):
    user = move.invoice_user_id
    if not user:
        return ""
    return (user.partner_id.ref or user.name or "").strip()


def payment_term(move):
    term = move.invoice_payment_term_id
    if not term:
        return ""
    name = (term.name or "").strip()
    if name:
        return name
    return html2plaintext(term.note or "").replace("\n", " ").strip()


def stamp(move):
    if move.state == "cancel":
        return "ANULADA"
    if move.l10n_ve_invoice_original_printed:
        return "COPIA SIN DERECHO A CREDITO FISCAL"
    return ""


def amount_words(move):
    currency = move.currency_id
    words = currency.with_context(lang=move.partner_id.lang or "es_VE").amount_to_text(
        move.amount_total
    )
    return f"Son: {currency.symbol or currency.name} {words}".strip()


def qty_display(qty):
    qty = qty or 0.0
    if qty == int(qty):
        return f"{qty:.0f}"
    return f"{qty:.2f}"


def product_ref(product):
    if not product:
        return ""
    return (getattr(product, "internal_code", None) or product.barcode or "").strip()


def product_brand(product):
    if not product:
        return ""
    brand = getattr(product, "product_brand_id", False)
    return (brand.name or "").strip() if brand else ""


def move_context(move):
    partner = move.partner_id
    origin = move.debit_origin_id or move.reversed_entry_id
    products = product_lines(move)
    return {
        "doc_title": document_title(move),
        "doc_label": document_label(move),
        "invoice_number": invoice_number(move),
        "emission": emission(move),
        "partner_name": partner_name(move),
        "partner_vat": partner.vat or "",
        "partner_email": partner.email or "",
        "partner_phone": partner_phone(partner),
        "partner_address": partner_address(partner),
        "client_code": partner.ref or "",
        "seller": seller(move),
        "payment_term": payment_term(move),
        "origin_document": origin.name if origin else "",
        "stamp": stamp(move),
        "exchange_rate": move.l10n_ve_report_exchange_rate_display() or "",
        "amount_words": amount_words(move),
        "count_articles": str(len(products)),
        "count_qty": str(int(round(sum(line.quantity or 0.0 for line in products)))),
        "vat_percent": vat_percent(move),
        "igtf_percent": igtf_percent(move),
        "discount_percent": discount_percent(move),
        "doc_currency": move.currency_id,
        "comp_currency": move.company_currency_id,
        "dual_currency": move.currency_id != move.company_currency_id,
        "tot": totals_namespace(move),
        "product_lines": products,
    }


def line_context(move, line):
    product = line.product_id
    currency = move.currency_id
    comp_currency = move.company_currency_id
    return {
        "pl": Namespace(
            code=product.default_code if product else "",
            desc=line.l10n_ve_report_line_description(),
            ref=product_ref(product),
            brand=product_brand(product),
            qty=qty_display(line.quantity),
            price_unit=money(move.env, line.price_unit, currency),
            subtotal=money(move.env, line.price_subtotal, currency),
            price_unit_company_currency=money(
                move.env, line.price_unit_company_currency, comp_currency
            ),
            price_subtotal_currency=money(
                move.env, line.price_subtotal_currency, comp_currency
            ),
            subtotal_company_currency=money(
                move.env, line.subtotal_company_currency, comp_currency
            ),
        )
    }
