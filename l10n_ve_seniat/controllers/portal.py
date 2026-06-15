# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.account.controllers.portal import PortalAccount


class PortalAccountL10nVeSeniat(PortalAccount):
    @http.route(
        ["/my/invoices/<int:invoice_id>"],
        type="http",
        auth="public",
        website=True,
    )
    def portal_my_invoice_detail(
        self,
        invoice_id,
        access_token=None,
        report_type=None,
        download=False,
        **kw,
    ):
        try:
            invoice_sudo = self._document_check_access(
                "account.move", invoice_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")
        if invoice_sudo.state != "posted":
            return request.redirect("/my")
        if (
            invoice_sudo.country_code == "VE"
            and invoice_sudo.move_type in ("out_invoice", "out_refund")
            and not invoice_sudo._l10n_ve_allows_invoice_portal_view()
        ):
            return request.redirect("/my")
        if (
            download
            and report_type == "pdf"
            and invoice_sudo.country_code == "VE"
            and invoice_sudo.move_type in ("out_invoice", "out_refund")
            and not invoice_sudo._l10n_ve_allows_invoice_pdf_download()
        ):
            return request.redirect("/my")
        return super().portal_my_invoice_detail(
            invoice_id,
            access_token=access_token,
            report_type=report_type,
            download=download,
            **kw,
        )
