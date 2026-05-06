import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(OrderSummary.prototype, {
    _veResolveComboParent(line) {
        return line.combo_parent_id || line;
    },
    _veNumpadDecreaseLineQty(root) {
        const q = root.get_quantity();
        if (this.pos.isProductQtyZero(q)) {
            this.numberBuffer.reset();
            return;
        }
        let newQ;
        if (q > 0) {
            newQ = q - 1;
        } else {
            newQ = q + 1;
        }
        const remove =
            this.pos.isProductQtyZero(newQ) ||
            (q > 0 && newQ < 0) ||
            (q < 0 && newQ > 0);
        if (remove) {
            this.currentOrder.removeOrderline(root);
        } else {
            const result = root.set_quantity(newQ, Boolean(root.combo_line_ids?.length));
            for (const cl of root.combo_line_ids ?? []) {
                cl.set_quantity(newQ, true);
            }
            if (result !== true) {
                this.dialog.add(AlertDialog, result);
            }
        }
        this.numberBuffer.reset();
    },
    _veIsZeroQty(val) {
        if (val === "remove") {
            return false;
        }
        const numVal =
            typeof val === "number"
                ? val
                : parseFloat(String(val ?? "").replace(",", "."));
        if (Number.isNaN(numVal)) {
            return false;
        }
        return this.pos.isProductQtyZero(numVal);
    },
    handleOrderLineQuantityChange(selectedLine, buffer, currentQuantity, lastId) {
        if (
            isVenezuelaCompany(this.pos) &&
            !selectedLine.refunded_orderline_id &&
            this._veIsZeroQty(buffer)
        ) {
            this.numberBuffer.reset();
            this.currentOrder.removeOrderline(this._veResolveComboParent(selectedLine));
            return;
        }
        return super.handleOrderLineQuantityChange(...arguments);
    },
    async updateQuantityNumber(newQuantity) {
        if (
            isVenezuelaCompany(this.pos) &&
            newQuantity !== null &&
            this.pos.isProductQtyZero(newQuantity)
        ) {
            const selectedLine = this.currentOrder.get_selected_orderline();
            if (selectedLine && !selectedLine.refunded_orderline_id) {
                this.currentOrder.removeOrderline(this._veResolveComboParent(selectedLine));
            }
            return true;
        }
        return await super.updateQuantityNumber(...arguments);
    },
    _setValue(val) {
        const { numpadMode } = this.pos;
        const selectedLine = this.currentOrder.get_selected_orderline();
        if (selectedLine) {
            const root = this._veResolveComboParent(selectedLine);
            if (
                numpadMode === "quantity" &&
                isVenezuelaCompany(this.pos) &&
                !root.refunded_orderline_id
            ) {
                if (val === "" || val === "remove") {
                    this._veNumpadDecreaseLineQty(root);
                    return;
                }
                if (this._veIsZeroQty(val)) {
                    this.currentOrder.removeOrderline(root);
                    this.numberBuffer.reset();
                    return;
                }
            }
        }
        return super._setValue(...arguments);
    },
    async setLinePrice(line, price) {
        if (isVenezuelaCompany(this.pos)) {
            this.pos.notification.add(
                _t("Changing the price from the Point of Sale is not allowed."),
                { type: "warning" }
            );
            return;
        }
        return await super.setLinePrice(...arguments);
    },
});