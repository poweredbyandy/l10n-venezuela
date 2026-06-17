/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import {
    l10nVeFiscalSerialPosExecutePrint,
    l10nVeFiscalSerialPosIsFiscalMachine,
} from "../../fiscal_serial_pos_print";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(PaymentScreen.prototype, {
    _l10nVeFiscalSerialNeedsPrint() {
        if (!isVenezuelaCompany(this.pos)) {
            return false;
        }
        if (!l10nVeFiscalSerialPosIsFiscalMachine(this.pos)) {
            return false;
        }
        const order = this.currentOrder;
        if (!order?.is_to_invoice()) {
            return false;
        }
        return Boolean(order.raw?.account_move);
    },

    _l10nVeFiscalSerialPrintSucceededForCurrentOrder() {
        const uuid = this.currentOrder?.uuid;
        if (!uuid) {
            return false;
        }
        this._l10nVeFiscalSerialPrintOkByOrderUuid =
            this._l10nVeFiscalSerialPrintOkByOrderUuid || {};
        return Boolean(this._l10nVeFiscalSerialPrintOkByOrderUuid[uuid]);
    },

    _l10nVeFiscalSerialMarkPrintSucceeded() {
        const uuid = this.currentOrder?.uuid;
        if (!uuid) {
            return;
        }
        this._l10nVeFiscalSerialPrintOkByOrderUuid =
            this._l10nVeFiscalSerialPrintOkByOrderUuid || {};
        this._l10nVeFiscalSerialPrintOkByOrderUuid[uuid] = true;
    },

    _l10nVeFiscalSerialAwaitingFiscalPrint() {
        return (
            this._l10nVeFiscalSerialNeedsPrint() &&
            !this._l10nVeFiscalSerialPrintSucceededForCurrentOrder()
        );
    },

    async validateOrder(isForceValidate) {
        if (
            this.currentOrder.is_paid() &&
            this._l10nVeFiscalSerialAwaitingFiscalPrint()
        ) {
            const ok = await this._l10nVeFiscalSerialPrintAfterSync();
            if (ok) {
                this._l10nVeFiscalSerialMarkPrintSucceeded();
                return super.afterOrderValidation(true);
            }
            return;
        }
        return super.validateOrder(isForceValidate);
    },

    async _l10nVeFiscalSerialPrintAfterSync() {
        if (!this._l10nVeFiscalSerialNeedsPrint()) {
            return true;
        }
        return l10nVeFiscalSerialPosExecutePrint({
            pos: this.pos,
            env: this.env,
            orderId: this.currentOrder.id,
            order: this.currentOrder,
        });
    },

    async afterOrderValidation(...args) {
        if (this._l10nVeFiscalSerialNeedsPrint()) {
            const ok = await this._l10nVeFiscalSerialPrintAfterSync();
            if (!ok) {
                return;
            }
            this._l10nVeFiscalSerialMarkPrintSucceeded();
        }
        return super.afterOrderValidation(...args);
    },
});
