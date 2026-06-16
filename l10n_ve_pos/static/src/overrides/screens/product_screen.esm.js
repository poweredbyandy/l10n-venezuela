import {ProductScreen} from "@point_of_sale/app/screens/product_screen/product_screen";
import {patch} from "@web/core/utils/patch";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(ProductScreen.prototype, {
    getNumpadButtons() {
        const buttons = super.getNumpadButtons(...arguments);
        if (!isVenezuelaCompany(this.pos)) {
            return buttons;
        }
        return buttons.map((button) =>
            button.value === "price" ? {...button, disabled: true} : button
        );
    },
    onNumpadClick(buttonValue) {
        if (isVenezuelaCompany(this.pos) && buttonValue === "price") {
            return;
        }
        return super.onNumpadClick(...arguments);
    },
});
