from odoo import _, fields, models
from odoo.exceptions import UserError

from ..report.invoice_values import line_context, move_context

FRX_EXPRESSION_MAP = {
    "alltrim(nombrecli)": "partner_name",
    "iif(isdigit(subst( RIF,1,1)),alltrim( RIF),alltrim( RIF))": "partner_vat",
    "alltrim( email )": "partner_email",
    "alltrim( telefonos)": "partner_phone",
    "alltrim( direccion)": "partner_address",
    "alltrim(codcliente)": "client_code",
    "alltrim( vendedor)": "seller",
    "xDocFac": "doc_title",
    "documento": "invoice_number",
    "emision": "emission",
    'padl(_pageno,3,"0")': "'%03d' % page",
    "nRegistro1+\":\"": "'R.I.F. :'",
    "marca": "pl.brand",
    "REFERENCIA": "pl.ref",
    "cantidad": "pl.qty",
    "preciounit": "pl.price_unit",
    "preciounit*cantidad": "pl.subtotal",
    'iif(preciofin=0,"", codigo)': "pl.code",
    "factorreferencial": "exchange_rate",
    "totalfinal": "tot.comp.payable",
    "totalfinal/factorreferencial": "tot.doc.payable",
    "totneto+totimpuest": "tot.comp.invoice",
    "(totneto+totimpuest)/factorreferencial": "tot.doc.invoice",
    "totimpuest": "tot.comp.vat",
    "totimpuest/factorreferencial": "tot.doc.vat",
    "(baseimpo1+baseimpo2+baseimpo3)": "tot.comp.vat_base",
    "(baseimpo1+baseimpo2+baseimpo3)/factorreferencial": "tot.doc.vat_base",
    "totbruto+sinimpuest-totdescuen": "tot.comp.subtotal",
    "(totbruto+sinimpuest-totdescuen)/factorreferencial": "tot.doc.subtotal",
    "totdescuen": "tot.comp.discount",
    "totdescuen/factorreferencial": "tot.doc.discount",
    "totbruto-sinimpuest": "tot.comp.gross",
    "(totbruto-sinimpuest)/factorreferencial": "tot.doc.gross",
    "(sinimpuest-percibido)": "tot.comp.exempt",
    "(sinimpuest-percibido)/factorreferencial": "tot.doc.exempt",
    "tIGTF": "tot.comp.igtf",
    "tIGTF/factorreferencial": "tot.doc.igtf",
    "bIGTF": "tot.comp.igtf_base",
    "(bIGTF/factorreferencial)": "tot.doc.igtf_base",
    '"Monto en "+monnacsimb2': "doc_currency.name if dual_currency else ''",
    '"Monto en "+simbolomoneda': "comp_currency.name if dual_currency else doc_currency.name",
    'IIf( escredito=1, "CREDITO a "+transform(vence-emision,"9999")+" Dias","CONTADO")': "payment_term",
    'horadocum+iif(ampm = 1,"AM","PM")': "''",
    "UPPER(nSelEmpresa)": "upper(company.name)",
    'alltrim(nnomfiscal1)+": "+ alltrim(nrif)': "'RIF: ' + (company.vat or '')",
    'iif(formafis = 4,alltrim(nombre1),alltrim(nombre1)+iif(baseimpo5 > 0, " (P)",iif(timpueprc = 0, " (E)",iif(timpueprc = 16, " (G)",iif(timpueprc = 8, " (R)",iif(timpueprc = 31, " (A)", " "))))))': "pl.desc",
    '"Descuento"+STR((totdescuen*100/totbruto),6,2)+"% (-):"': "('Descuento %s (-):' % discount_percent).replace('  ', ' ')",
    'iif(formafis = 4,"Base Imponible 0%","Exento (+):")': "'Exento (+):'",
    '"Son: "+alltrim(simbolomoneda)+"  "+ StringMonto(  iif(factorcamb=0, totalfinal,iif(multi_div=1,totalfinal / factorcamb, totalfinal * factorcamb)))': "amount_words",
}


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_escp_is_continuous_eligible(self):
        self.ensure_one()
        return (
            self.company_id.account_fiscal_country_id.code == "VE"
            and self.move_type in ("out_invoice", "out_refund")
            and self.l10n_ve_journal_emission_medium == "free"
            and self.journal_id.l10n_ve_free_form_print_medium == "continuous"
        )

    def _l10n_ve_escp_report(self):
        self.ensure_one()
        report = self.journal_id.l10n_ve_escp_report_id
        if not report:
            report = self.env.ref(
                "l10n_ve_invoice_escp.l10n_ve_escp_report_invoice",
                raise_if_not_found=False,
            )
        return report if report and report.model == self._name else False

    def _l10n_ve_get_free_form_continuous_print_action(self):
        res = super()._l10n_ve_get_free_form_continuous_print_action()
        if res:
            return res
        self.ensure_one()
        if not self._l10n_ve_escp_is_continuous_eligible():
            return False
        report = self._l10n_ve_escp_report()
        if not report:
            raise UserError(
                _(
                    "No hay un reporte ESC/P para facturas. Cree uno en "
                    "Contabilidad > Configuración > Reportes ESC/P y asígnelo al diario."
                )
            )
        return report._preview_action(self)

    def action_print_pdf(self):
        self.ensure_one()
        if self._l10n_ve_escp_is_continuous_eligible():
            self._l10n_ve_check_invoice_print_allowed()
            return self._l10n_ve_get_free_form_continuous_print_action()
        return super().action_print_pdf()

    def _l10n_ve_escp_check_print(self, report):
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_refund"):
            return
        if self.state not in ("posted", "cancel"):
            raise UserError(_("Solo documentos confirmados pueden imprimirse por USB."))
        if not self._l10n_ve_escp_is_continuous_eligible():
            raise UserError(
                _(
                    "Este documento no está en un diario con forma "
                    "libre y papel continuo."
                )
            )
        self.env[
            "ir.actions.report"
        ]._l10n_ve_check_block_invoice_pdf_before_digital_sent(
            "account.report_invoice_with_payments",
            self.ids,
            {},
        )

    def _l10n_ve_escp_after_print(self, report):
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_refund"):
            return
        if not self.l10n_ve_invoice_original_printed:
            write_vals = {"l10n_ve_invoice_original_printed": True}
            if (
                self.l10n_ve_journal_emission_medium == "fiscal_machine"
                and not self.l10n_ve_invoice_date
            ):
                write_vals["l10n_ve_invoice_date"] = fields.Datetime.now()
            self.sudo().write(write_vals)

    def _l10n_ve_escp_layout_params(self, report):
        self.ensure_one()
        book = self._l10n_ve_fiscal_book()
        if not book:
            return {}
        params = {}
        if book.l10n_ve_escp_invoice_margin_lines is not None:
            params["margin_top_lines"] = book.l10n_ve_escp_invoice_margin_lines
        if book.l10n_ve_max_invoice_lines:
            params["detail_rows"] = book.l10n_ve_max_invoice_lines
        return params

    def _l10n_ve_escp_eval_context(self, report):
        self.ensure_one()
        return move_context(self)

    def _l10n_ve_escp_line_eval_context(self, report, line):
        self.ensure_one()
        return line_context(self, line)

    def _l10n_ve_escp_frx_expression_map(self):
        return dict(FRX_EXPRESSION_MAP)
