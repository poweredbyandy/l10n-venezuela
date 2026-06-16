import {PosStore} from "@point_of_sale/app/store/pos_store";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

function isRifLike(value) {
    const term = (value || "").trim();
    if (!term) {
        return false;
    }
    if (/^[VEJPGC]/i.test(term) && /\d/.test(term)) {
        return true;
    }
    const digits = term.replace(/\D/g, "");
    return /^[\d.\-\sVEJPGC]+$/i.test(term) && digits.length >= 6;
}

patch(PosStore.prototype, {
    async allowProductCreation() {
        if (isVenezuelaCompany(this)) {
            return false;
        }
        return await super.allowProductCreation(...arguments);
    },
    async editProduct(product) {
        if (!product && isVenezuelaCompany(this)) {
            this.notification.add(
                _t("Creating products from the Point of Sale is not allowed."),
                {type: "warning"}
            );
            return;
        }
        return await super.editProduct(...arguments);
    },
    async setDiscountFromUI(line, val) {
        if (isVenezuelaCompany(this)) {
            const n =
                typeof val === "number"
                    ? val
                    : parseFloat(String(val ?? "").replace(",", "."));
            if (!Number.isNaN(n) && n >= 100) {
                this.notification.add(_t("A discount of 100% is not allowed."), {
                    type: "warning",
                });
                return;
            }
        }
        return await super.setDiscountFromUI(...arguments);
    },
    editPartnerContext(partner) {
        const context = super.editPartnerContext(...arguments);
        if (partner || !isVenezuelaCompany(this)) {
            return context;
        }

        const query = (this.l10n_ve_partner_create_query || "").trim();
        if (!query) {
            return context;
        }

        if (isRifLike(query)) {
            return {
                ...context,
                default_name: query,
                default_vat: query,
            };
        }

        return {
            ...context,
            default_name: query,
        };
    },
});
