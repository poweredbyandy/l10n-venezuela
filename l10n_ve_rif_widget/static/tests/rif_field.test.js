import { expect, test } from "@odoo/hoot";
import { press, queryAllTexts, queryOne } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import { defineModels, fields, models, mountView, onRpc } from "@web/../tests/web_test_helpers";

import "@l10n_ve_rif_widget/js/rif_field";

class Partner extends models.Model {
    _name = "res.partner";
    _inherit = [];

    name = fields.Char();
    vat = fields.Char();

    _records = [
        { id: 1, display_name: "first", name: "first", vat: "V187989538" },
        { id: 2, display_name: "dotted", name: "dotted", vat: "J-12.345.678-9" },
        { id: 3, display_name: "empty", name: "empty", vat: false },
    ];
}
defineModels([Partner]);

const FORM_ARCH = /* xml */ `
    <form>
        <sheet>
            <group>
                <field name="vat" widget="l10n_ve_rif"/>
            </group>
        </sheet>
    </form>
`;

const kindInput = () => queryOne(".o_l10n_ve_rif_kind");
const digitsInput = () => queryOne(".o_l10n_ve_rif_number");

/**
 * Simulate typing in an input: set the value and fire the input event.
 */
function typeIn(input, value) {
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
}

test("rif widget: readonly shows the kind and digits joined by a dash", async () => {
    await mountView({
        type: "form",
        resModel: "res.partner",
        resId: 1,
        arch: `
            <form>
                <sheet>
                    <group>
                        <field name="vat" widget="l10n_ve_rif" readonly="1"/>
                    </group>
                </sheet>
            </form>
        `,
    });

    expect(".o_l10n_ve_rif_kind").toHaveCount(0, { message: "no kind input in readonly" });
    expect(".o_l10n_ve_rif_number").toHaveCount(0, { message: "no digits input in readonly" });
    expect(".o_field_widget[name=vat]").toHaveText("V-187989538", {
        message: "readonly value is displayed with the customary dash",
    });
});

test("rif widget: two separate inputs, autocomplete disabled", async () => {
    await mountView({ type: "form", resModel: "res.partner", resId: 1, arch: FORM_ARCH });

    expect(".o_l10n_ve_rif_kind").toHaveCount(1, { message: "kind input is rendered" });
    expect(".o_l10n_ve_rif_number").toHaveCount(1, { message: "digits input is rendered" });
    expect(kindInput()).toHaveValue("V", { message: "kind input holds the record kind" });
    expect(digitsInput()).toHaveValue("187989538", {
        message: "digits input holds the record digits",
    });
    expect(kindInput()).toHaveAttribute("autocomplete", "off");
    expect(digitsInput()).toHaveAttribute("autocomplete", "off");
});

test("rif widget: dotted RIF is split without breaking its style", async () => {
    await mountView({ type: "form", resModel: "res.partner", resId: 2, arch: FORM_ARCH });

    expect(kindInput()).toHaveValue("J");
    expect(digitsInput()).toHaveValue("12.345.678-9", {
        message: "dotted digits are shown untouched",
    });
});

test("rif widget: focusing the kind input opens the dropdown with all kinds", async () => {
    await mountView({ type: "form", resModel: "res.partner", resId: 3, arch: FORM_ARCH });

    expect(".o_l10n_ve_rif_dropdown").toHaveCount(0, { message: "dropdown is closed" });

    kindInput().focus();
    await animationFrame();

    expect(".o_l10n_ve_rif_dropdown").toHaveCount(1, { message: "dropdown opens on focus" });
    expect(queryAllTexts(".o_l10n_ve_rif_option")).toEqual(["V", "E", "J", "C", "P", "G"]);
});

test("rif widget: dropdown is keyboard navigable and Enter selects", async () => {
    await mountView({ type: "form", resModel: "res.partner", resId: 3, arch: FORM_ARCH });

    kindInput().focus();
    await animationFrame();

    await press("ArrowDown");
    await press("ArrowDown");
    expect(queryOne(".o_l10n_ve_rif_option_active").textContent.trim()).toBe("J");

    await press("Enter");
    await animationFrame();

    expect(kindInput()).toHaveValue("J", { message: "Enter picks the active option" });
    expect(".o_l10n_ve_rif_dropdown").toHaveCount(0, { message: "dropdown is closed" });
    expect(document.activeElement).toBe(digitsInput(), {
        message: "focus continues in the digits input, no extra Enter needed",
    });
});

test("rif widget: typing a kind letter advances to the digits input", async () => {
    await mountView({ type: "form", resModel: "res.partner", resId: 3, arch: FORM_ARCH });

    kindInput().focus();
    typeIn(kindInput(), "E");
    await animationFrame();

    expect(kindInput()).toHaveValue("E", { message: "letter is uppercased and kept" });
    expect(document.activeElement).toBe(digitsInput(), {
        message: "typing the letter continues in the digits input",
    });

    typeIn(digitsInput(), "28493778");
    await animationFrame();
    expect(digitsInput()).toHaveValue("28493778");
});

test("rif widget: kind and digits are saved without the dash", async () => {
    expect.assertions(1);
    await mountView({ type: "form", resModel: "res.partner", resId: 3, arch: FORM_ARCH });

    onRpc("web_save", ({ args }) => {
        expect(args[1].vat).toBe("V28493778", {
            message: "value stored in the record keeps the compact format",
        });
    });

    kindInput().focus();
    typeIn(kindInput(), "V");
    await animationFrame();
    typeIn(digitsInput(), "28493778");
    await animationFrame();
    digitsInput().blur();
    await animationFrame();

    queryOne(".o_form_button_save").click();
    await animationFrame();
});

test("rif widget: dotted RIF keeps its dash on save", async () => {
    expect.assertions(1);
    await mountView({ type: "form", resModel: "res.partner", resId: 2, arch: FORM_ARCH });

    onRpc("web_save", ({ args }) => {
        expect(args[1].vat).toBe("J-12.345.678-9", {
            message: "dotted RIF style is preserved",
        });
    });

    typeIn(digitsInput(), "12.345.678-9");
    await animationFrame();
    digitsInput().blur();
    await animationFrame();

    queryOne(".o_form_button_save").click();
    await animationFrame();
});

test("rif widget: incomplete state is not flagged as invalid nor saved", async () => {
    await mountView({ type: "form", resModel: "res.partner", resId: 3, arch: FORM_ARCH });

    // pick a kind from the dropdown with no digits at all
    kindInput().focus();
    await animationFrame();
    await press("ArrowDown");
    await press("ArrowDown");
    await press("Enter");
    await animationFrame();

    expect(".o_field_invalid").toHaveCount(0, {
        message: "an incomplete RIF must not look like a required/invalid field",
    });

    // leaving the widget with an incomplete state restores the record kind
    queryOne(".o_l10n_ve_rif").dispatchEvent(
        new FocusEvent("focusout", { bubbles: true, relatedTarget: document.body })
    );
    await animationFrame();

    expect(kindInput()).toHaveValue("", {
        message: "kind input is restored from the record when left incomplete",
    });
});

test("rif widget: letters are not allowed in the digits input", async () => {
    await mountView({ type: "form", resModel: "res.partner", resId: 3, arch: FORM_ARCH });

    digitsInput().focus();
    typeIn(digitsInput(), "28a49b77c8x");
    await animationFrame();

    expect(digitsInput()).toHaveValue("2849778", {
        message: "letters typed in the digits input are dropped",
    });

    typeIn(digitsInput(), "12.345.678-9");
    await animationFrame();
    expect(digitsInput()).toHaveValue("12.345.678-9", {
        message: "dots and dashes of the dotted RIF style are kept",
    });
});

test("rif widget: clearing the digits clears the RIF instead of restoring it", async () => {
    await mountView({ type: "form", resModel: "res.partner", resId: 1, arch: FORM_ARCH });

    // user clears the digits and moves to the kind input
    digitsInput().focus();
    typeIn(digitsInput(), "");
    kindInput().focus();
    await animationFrame();

    expect(digitsInput()).toHaveValue("", {
        message: "the old digits must not be restored while editing",
    });
    expect(".o_field_invalid").toHaveCount(0, { message: "no invalid marking" });
});

test("rif widget: backspace at the start of the digits input jumps to the kind", async () => {
    await mountView({ type: "form", resModel: "res.partner", resId: 3, arch: FORM_ARCH });

    digitsInput().focus();
    digitsInput().setSelectionRange(0, 0);
    await animationFrame();

    await press("Backspace");
    await animationFrame();

    expect(document.activeElement).toBe(kindInput(), {
        message: "backspace at the start of digits moves the focus to the kind input",
    });
});

test("rif widget: entering empty digits jumps to the kind input", async () => {
    await mountView({ type: "form", resModel: "res.partner", resId: 3, arch: FORM_ARCH });

    digitsInput().focus();
    digitsInput().dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
    await animationFrame();

    expect(document.activeElement).toBe(kindInput(), {
        message: "an empty RIF starts by typing the kind letter",
    });
});

test("rif widget: clearing both inputs saves an empty value", async () => {
    expect.assertions(1);
    await mountView({ type: "form", resModel: "res.partner", resId: 1, arch: FORM_ARCH });

    onRpc("web_save", ({ args }) => {
        expect(args[1].vat).toBe(false, { message: "clearing the widget empties the field" });
    });

    typeIn(kindInput(), "");
    typeIn(digitsInput(), "");
    await animationFrame();
    digitsInput().blur();
    await animationFrame();

    queryOne(".o_form_button_save").click();
    await animationFrame();
});
