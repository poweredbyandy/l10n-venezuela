from collections import OrderedDict

from odoo import api, models

L10N_VE_SKIP_STOCK_PICKING_UNBIND = "l10n_ve_skip_stock_picking_unbind"
_L10N_VE_DISPATCH_GUIDE_REPORT_NAME = "l10n_ve_stock.report_dispatch_guide"
_L10N_VE_DISPATCH_GUIDE_XMLID = "l10n_ve_stock.action_report_l10n_ve_dispatch_guide"


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get(L10N_VE_SKIP_STOCK_PICKING_UNBIND):
            records._l10n_ve_unbind_stock_picking_report_bindings()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get(L10N_VE_SKIP_STOCK_PICKING_UNBIND):
            self._l10n_ve_unbind_stock_picking_report_bindings()
        return res

    def _l10n_ve_is_dispatch_guide_report(self, report):
        return (report.report_name or "") == _L10N_VE_DISPATCH_GUIDE_REPORT_NAME

    def _l10n_ve_is_blocked_picking_report_for_ve_outgoing(self, report):
        if report.model != "stock.picking" or report.report_type != "qweb-pdf":
            return False
        return not self._l10n_ve_is_dispatch_guide_report(report)

    def _l10n_ve_get_ve_outgoing_pickings(self, pickings):
        return pickings.filtered(
            lambda picking: picking._l10n_ve_is_ve_outgoing_dispatch_guide_picking()
        )

    def _l10n_ve_should_use_only_dispatch_guide_reports(self, pickings):
        return bool(pickings) and len(
            self._l10n_ve_get_ve_outgoing_pickings(pickings)
        ) == len(pickings)

    def _l10n_ve_get_dispatch_guide_report(self):
        return self.env.ref(_L10N_VE_DISPATCH_GUIDE_XMLID, raise_if_not_found=False)

    def _l10n_ve_unbind_stock_picking_report_bindings(self):
        picking_model = self.env["ir.model"]._get("stock.picking")
        if not picking_model:
            return
        to_clear = self.sudo().filtered(
            lambda report: report.binding_model_id == picking_model
            and report.binding_type == "report"
            and not self._l10n_ve_is_dispatch_guide_report(report)
        )
        if to_clear:
            to_clear.with_context(**{L10N_VE_SKIP_STOCK_PICKING_UNBIND: True}).write(
                {"binding_model_id": False}
            )

    @api.model
    def _l10n_ve_unbind_all_stock_picking_report_bindings(self):
        picking_model = self.env["ir.model"]._get("stock.picking")
        if not picking_model:
            return
        self.env["ir.actions.report"].sudo().search(
            [
                ("binding_model_id", "=", picking_model.id),
                ("binding_type", "=", "report"),
            ]
        )._l10n_ve_unbind_stock_picking_report_bindings()

    def _l10n_ve_dispatch_guide_available_for_pickings(self, pickings):
        dispatch_report = self._l10n_ve_get_dispatch_guide_report()
        if not dispatch_report:
            return False
        ve_outgoing = pickings.filtered(
            lambda picking: picking._l10n_ve_is_ve_outgoing_dispatch_guide_picking()
        )
        if not ve_outgoing:
            return False
        return all(
            picking._l10n_ve_dispatch_guide_print_available() for picking in ve_outgoing
        )

    def get_valid_action_reports(self, model, record_ids):
        valid_ids = super().get_valid_action_reports(model, record_ids)
        if model != "stock.picking" or not record_ids:
            return valid_ids
        pickings = self.env["stock.picking"].browse(record_ids)
        dispatch_report = self._l10n_ve_get_dispatch_guide_report()
        if dispatch_report:
            available = self._l10n_ve_dispatch_guide_available_for_pickings(pickings)
            if dispatch_report.id in valid_ids and not available:
                valid_ids = [
                    report_id
                    for report_id in valid_ids
                    if report_id != dispatch_report.id
                ]
            elif (
                dispatch_report.id not in valid_ids
                and available
                and self._l10n_ve_should_use_only_dispatch_guide_reports(pickings)
            ):
                valid_ids = [*valid_ids, dispatch_report.id]
        if not valid_ids:
            return valid_ids
        if not self._l10n_ve_should_use_only_dispatch_guide_reports(pickings):
            return valid_ids
        blocked_report_ids = {
            report.id
            for report in self.browse(valid_ids)
            if self._l10n_ve_is_blocked_picking_report_for_ve_outgoing(report)
        }
        return [
            report_id for report_id in valid_ids if report_id not in blocked_report_ids
        ]

    def report_action(self, docids, data=None, config=True):
        if self._l10n_ve_is_dispatch_guide_report(self):
            if isinstance(docids, models.Model):
                pickings = docids
            elif isinstance(docids, int):
                pickings = self.env["stock.picking"].browse([docids])
            elif isinstance(docids, list):
                pickings = self.env["stock.picking"].browse(docids)
            else:
                pickings = self.env["stock.picking"]
            if pickings and not self._l10n_ve_dispatch_guide_available_for_pickings(
                pickings
            ):
                return {"type": "ir.actions.act_window_close"}
        if (
            self.model == "stock.picking"
            and self._l10n_ve_is_blocked_picking_report_for_ve_outgoing(self)
        ):
            if isinstance(docids, models.Model):
                pickings = docids
            elif isinstance(docids, int):
                pickings = self.env["stock.picking"].browse([docids])
            elif isinstance(docids, list):
                pickings = self.env["stock.picking"].browse(docids)
            else:
                pickings = self.env["stock.picking"]
            if self._l10n_ve_should_use_only_dispatch_guide_reports(pickings):
                dispatch_report = self._l10n_ve_get_dispatch_guide_report()
                if dispatch_report:
                    return dispatch_report.report_action(
                        docids, data=data, config=config
                    )
        return super().report_action(docids, data=data, config=config)

    def get_paperformat(self):
        paperformat_id = self.env.context.get("l10n_ve_dispatch_guide_paperformat_id")
        if paperformat_id:
            return self.env["report.paperformat"].browse(paperformat_id)
        return super().get_paperformat()

    def _l10n_ve_should_apply_dispatch_guide_paperformat(self, report_ref, res_ids):
        if not res_ids:
            return False
        report = self._get_report(report_ref)
        return report.report_name == _L10N_VE_DISPATCH_GUIDE_REPORT_NAME

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        if not self._l10n_ve_should_apply_dispatch_guide_paperformat(
            report_ref, res_ids
        ):
            return super()._render_qweb_pdf_prepare_streams(
                report_ref, data, res_ids=res_ids
            )
        pickings = self.env["stock.picking"].browse(res_ids)
        paperformat_by_picking = {
            picking.id: picking._l10n_ve_dispatch_guide_paperformat().id
            for picking in pickings
        }
        paperformat_ids = set(paperformat_by_picking.values())
        if not paperformat_ids:
            return super()._render_qweb_pdf_prepare_streams(
                report_ref, data, res_ids=res_ids
            )
        if len(paperformat_ids) == 1 and len(paperformat_by_picking) == len(res_ids):
            return super(
                IrActionsReport,
                self.with_context(
                    l10n_ve_dispatch_guide_paperformat_id=next(iter(paperformat_ids))
                ),
            )._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)
        collected_streams = OrderedDict()
        for res_id in res_ids:
            paperformat_id = paperformat_by_picking.get(res_id)
            ctx = (
                {"l10n_ve_dispatch_guide_paperformat_id": paperformat_id}
                if paperformat_id
                else {}
            )
            sub_streams = super(
                IrActionsReport, self.with_context(**ctx)
            )._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=[res_id])
            collected_streams[res_id] = sub_streams[res_id]
        return collected_streams

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        if report.report_name == _L10N_VE_DISPATCH_GUIDE_REPORT_NAME:
            pickings = self.env["stock.picking"].browse(res_ids or [])
            pickings.l10n_ve_dispatch_guide_report_check()
        pdf, rep_type = super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        if report.report_name == _L10N_VE_DISPATCH_GUIDE_REPORT_NAME:
            pickings = self.env["stock.picking"].browse(res_ids or [])
            to_mark = pickings.filtered(
                lambda p: p.company_id.account_fiscal_country_id.code == "VE"
                and not p.l10n_ve_dispatch_guide_original_printed
            )
            if to_mark:
                to_mark.sudo().write({"l10n_ve_dispatch_guide_original_printed": True})
        return pdf, rep_type
