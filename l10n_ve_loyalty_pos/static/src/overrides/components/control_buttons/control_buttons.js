/** @odoo-module **/

import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(ControlButtons.prototype, {
    _l10nVeCompanyIsVenezuela() {
        return isVenezuelaCompany(this.pos);
    },

    async onClickL10nVeGlobalDiscount() {
        const order = this.pos.get_order();
        if (!order || !this._l10nVeCompanyIsVenezuela()) {
            return;
        }

        const action = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Global discount"),
            list: [
                {
                    id: "add_fixed",
                    item: { action: "add", discountType: "fixed" },
                    label: _t("Add fixed amount"),
                },
                {
                    id: "add_percent",
                    item: { action: "add", discountType: "percentage" },
                    label: _t("Add percentage"),
                },
                {
                    id: "remove",
                    item: { action: "remove" },
                    label: _t("Remove a discount"),
                },
            ],
        });
        if (!action) {
            return;
        }

        if (action.action === "remove") {
            await this._l10nVeRemoveGlobalDiscount(order);
            return;
        }
        await this._l10nVeAddGlobalDiscount(order, action.discountType);
    },

    _l10nVeGetDiscountReasons() {
        const model = this.pos.models["l10n.ve.discount.reason"];
        const reasons = model?.getAll ? model.getAll() : [];
        const seen = new Set();
        return reasons
            .filter((reason) => reason.active !== false)
            .sort((a, b) => (a.sequence || 0) - (b.sequence || 0) || a.id - b.id)
            .filter((reason) => {
                const key = (reason.name || "").trim().toLowerCase();
                if (!key || seen.has(key)) {
                    return false;
                }
                seen.add(key);
                return true;
            });
    },

    async _l10nVeAddGlobalDiscount(order, discountType) {
        const reasons = this._l10nVeGetDiscountReasons();
        let reasonName = _t("Global discount");
        let reasonId = false;
        if (reasons.length) {
            const reason = await makeAwaitable(this.dialog, SelectionPopup, {
                title: _t("Discount reason"),
                list: reasons.map((reason) => ({
                    id: reason.id,
                    item: reason,
                    label: reason.name,
                })),
            });
            if (!reason) {
                return;
            }
            reasonName = reason.name;
            reasonId = reason.id;
        }

        const isPercentage = discountType === "percentage";
        const input = await makeAwaitable(this.dialog, NumberPopup, {
            title: isPercentage ? _t("Discount percentage") : _t("Discount amount"),
            startingValue: isPercentage ? 10 : 0,
        });
        if (input === undefined || input === null || input === "") {
            return;
        }
        const value = Math.abs(parseFloat(String(input).replace(",", ".")));
        if (Number.isNaN(value) || value <= 0) {
            this.dialog.add(AlertDialog, {
                title: _t("Invalid discount"),
                body: _t("Enter a value greater than zero."),
            });
            return;
        }

        const result = order._l10nVeApplyManualGlobalDiscount({
            amount: isPercentage ? 0 : value,
            discountType: isPercentage ? "percentage" : "fixed",
            percentage: isPercentage ? value / 100 : 0,
            name: reasonName,
            reasonId,
        });
        if (result !== true) {
            this.dialog.add(AlertDialog, {
                title: _t("Global discount"),
                body: result,
            });
        }
    },

    async _l10nVeRemoveGlobalDiscount(order) {
        const groups = order.taxTotals?.l10n_ve_global_discount_lines || [];
        if (!groups.length) {
            this.dialog.add(AlertDialog, {
                title: _t("Global discount"),
                body: _t("There are no global discounts to remove."),
            });
            return;
        }
        const selected = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Remove discount"),
            list: groups.map((group) => ({
                id: group.id,
                item: group,
                label: `${group.name}: ${this.env.utils.formatCurrency(group.amount)}`,
            })),
        });

        if (!selected) {
            return;
        }
        order._l10nVeRemoveGlobalDiscountGroup(selected.id);
    },
});
