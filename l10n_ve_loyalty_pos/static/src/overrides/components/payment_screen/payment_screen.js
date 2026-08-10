/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

function isPayLaterNoJournal(paymentMethod) {
    return Boolean(paymentMethod) && paymentMethod.type === "pay_later";
}

patch(PaymentScreen.prototype, {
    _l10nVeOrderHasPayLaterRefundCredit(order) {
        if (!order || order.get_total_with_tax() >= 0) {
            return false;
        }
        return (order.payment_ids || []).some((payment) =>
            isPayLaterNoJournal(payment.payment_method_id)
        );
    },

    async addNewPaymentLine(paymentMethod) {
        const order = this.currentOrder;
        if (
            isVenezuelaCompany(this.pos) &&
            order &&
            isPayLaterNoJournal(paymentMethod) &&
            order.get_total_with_tax() < 0
        ) {
            if (!order.get_partner()) {
                this.notification.add(
                    _t("Select a customer to credit the eWallet on refund."),
                    { type: "warning" }
                );
                const partner = await this.pos.selectPartner();
                if (!partner) {
                    return false;
                }
            }
            this.notification.add(
                _t("This credit payment will be added to the customer eWallet."),
                { type: "info" }
            );
        }
        return await super.addNewPaymentLine(...arguments);
    },

    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const partner = order?.get_partner?.();
        const shouldRefreshEwallet =
            isVenezuelaCompany(this.pos) &&
            this._l10nVeOrderHasPayLaterRefundCredit(order) &&
            partner;

        await super.validateOrder(...arguments);

        if (shouldRefreshEwallet && typeof this.pos._l10nVeRefreshPartnerEwalletCards === "function") {
            await this.pos._l10nVeRefreshPartnerEwalletCards(partner.id);
            if (typeof this.pos.updateRewards === "function") {
                this.pos.updateRewards();
            }
        }
    },
});
