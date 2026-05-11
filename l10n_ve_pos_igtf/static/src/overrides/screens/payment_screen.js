import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod) {
        const result = await super.addNewPaymentLine(...arguments);
        this.currentOrder?.l10n_ve_pos_updateIgtf?.();
        return result;
    },

    updateSelectedPaymentline(amount = false) {
        super.updateSelectedPaymentline(...arguments);
        this.currentOrder?.l10n_ve_pos_updateIgtf?.();
    },

    toggleIsToInvoice() {
        super.toggleIsToInvoice(...arguments);
        this.currentOrder?.l10n_ve_pos_updateIgtf?.();
    },
});
