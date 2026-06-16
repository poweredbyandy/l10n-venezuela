import {PaymentScreen} from "@point_of_sale/app/screens/payment_screen/payment_screen";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(PaymentScreen.prototype, {
    get isVenezuelaPos() {
        return isVenezuelaCompany(this.pos);
    },
    get l10nVeInvoiceTitle() {
        return _t("Invoice");
    },
    get l10nVeInvoiceJournalDisplayName() {
        return this.pos.config.l10n_ve_invoice_journal_display_name || "";
    },
    async afterOrderValidation() {
        if (isVenezuelaCompany(this.pos)) {
            this.pos.showScreen("ReceiptScreen");
            if (!this.pos.config.module_pos_restaurant) {
                this.pos.checkPreparationStateAndSentOrderInPreparation(
                    this.currentOrder
                );
            }
            return;
        }
        await super.afterOrderValidation(...arguments);
    },
    toggleIsToInvoice() {
        if (isVenezuelaCompany(this.pos)) {
            return;
        }
        super.toggleIsToInvoice(...arguments);
    },
    shouldDownloadInvoice() {
        if (isVenezuelaCompany(this.pos)) {
            return false;
        }
        return super.shouldDownloadInvoice(...arguments);
    },
    get l10nVeShowPaymentEmissionPanel() {
        return (
            this.isVenezuelaPos &&
            this.currentOrder.is_to_invoice() &&
            Boolean(this.pos.config.l10n_ve_invoice_journal_emission_medium)
        );
    },
    get l10nVeJournalEmissionMedium() {
        return this.pos.config.l10n_ve_invoice_journal_emission_medium || "";
    },
    get l10nVeNextFreeControlNumber() {
        return this.pos.config.l10n_ve_pos_next_free_control_number || "";
    },
    get l10nVeLabelNextControl() {
        return _t("Next control number");
    },
    get l10nVeLabelFiscalInvoiceNo() {
        return _t("Fiscal invoice number");
    },
    get l10nVeLabelFiscalSerial() {
        return _t("Fiscal machine serial");
    },
    get l10nVeLabelFiscalZ() {
        return _t("Z report number");
    },
    get l10nVeLabelControlNumber() {
        return _t("Control number");
    },
    get l10nVeDash() {
        return "—";
    },
    get l10nVeNextFreeControlNumberDisplay() {
        return this.l10nVeNextFreeControlNumber || this.l10nVeDash;
    },
    get l10nVeLabelAmountWithoutTaxes() {
        return _t("Amount without taxes");
    },
    get l10nVeAmountWithoutTaxesDisplay() {
        if (!this.currentOrder) {
            return this.env.utils.formatCurrency(0);
        }
        return this.env.utils.formatCurrency(this.currentOrder.get_total_without_tax());
    },
});
