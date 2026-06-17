/** @odoo-module **/

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { l10nVeFiscalSerialExecuteReport } from "@l10n_ve_fiscal_serial/fiscal_serial/fiscal_serial_report";
import { l10nVeFiscalSerialPosIsFiscalMachine } from "../../fiscal_serial_pos_print";

patch(ClosePosPopup.prototype, {
    get l10nVeShowFiscalReportX() {
        return l10nVeFiscalSerialPosIsFiscalMachine(this.pos);
    },
    async l10nVePrintXReport() {
        await l10nVeFiscalSerialExecuteReport({
            env: this.env,
            action: "report_x",
            logTag: "[l10n_ve_fiscal_serial_pos]",
        });
    },
});
