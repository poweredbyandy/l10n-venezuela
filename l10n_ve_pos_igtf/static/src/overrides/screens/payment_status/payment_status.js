import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenStatus.prototype, {
    get l10nVePosShowIgtfFooter() {
        const order = this.props.order;
        return Boolean(
            order.company?.l10n_ve_igtf_feature_active &&
                order.is_to_invoice() &&
                order.igtf_amount
        );
    },
});
