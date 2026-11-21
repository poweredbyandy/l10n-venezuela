/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useInputField } from "@web/views/fields/input_field_hook";

import { Component, useEffect, useRef, useState } from "@odoo/owl";

/**
 * RIF/CI kinds accepted by the SENIAT (l10n_ve_base_vat regex).
 */
export const RIF_KINDS = ["V", "E", "J", "C", "P", "G"];

/**
 * RIF/CI field widget.
 *
 * The value is stored without the kind separator (e.g. "V28493778", as
 * validated by l10n_ve_base_vat). For edition it is presented as two separate
 * inputs: the kind letter (with a datalist of V/E/J/C/P/G, still freely
 * typable) and the digits, joined by a dash. Anything that does not start
 * with a kind letter falls back to the digits input alone.
 */
export class RifField extends Component {
    static template = "l10n_ve_rif_widget.RifField";
    static props = {
        ...standardFieldProps,
        placeholder: { type: String, optional: true },
    };

    setup() {
        this.kinds = RIF_KINDS;
        this.kindInput = useRef("kindInput");
        this.kindOpen = useState({ value: false });
        this.kindIndex = useState({ value: 0 });
        this.kindTyped = useState({ value: "" });

        this.input = useInputField({
            getValue: () => this.digitsDisplay,
            parse: (value) => this.parse(value),
        });

        // Keep the kind input in sync with the record (onchange/save) without
        // clobbering what the user is currently typing.
        useEffect(
            (el) => {
                if (el && document.activeElement !== el) {
                    el.value = this.kindDisplay;
                    this.kindTyped.value = this.kindDisplay;
                }
            },
            () => [this.kindInput.el, this.rawValue]
        );
    }

    /**
     * Value stored in the record, as typed/served by the model.
     *
     * @returns {string}
     */
    get rawValue() {
        return this.props.record.data[this.props.name] || "";
    }

    /**
     * Kind letter of the stored value ("" when none).
     *
     * @returns {string}
     */
    get kindDisplay() {
        const kind = this.rawValue.trim()[0];
        return RIF_KINDS.includes(kind?.toUpperCase()) ? kind.toUpperCase() : "";
    }

    /**
     * Part of the stored value shown in the digits input: everything after
     * the kind letter, or the whole value when there is no kind letter.
     *
     * @returns {string}
     */
    get digitsDisplay() {
        const trimmed = this.rawValue.trim();
        if (this.kindDisplay) {
            return trimmed.slice(1).replace(/^[ \-]/, "");
        }
        return trimmed;
    }

    /**
     * Value shown in readonly mode.
     *
     * @returns {string}
     */
    get displayValue() {
        if (this.kindDisplay && this.digitsDisplay) {
            return `${this.kindDisplay}-${this.digitsDisplay}`;
        }
        return this.rawValue;
    }

    /**
     * Value saved to the record: kind letter (uppercased) + digits, without
     * the separator for compact values ("V28493778"). Dotted RIFs keep their
     * original style ("J-12.345.678-9").
     *
     * Incomplete states (kind without digits, or digits without kind) do not
     * raise: the record keeps its previous value and the widget UI is restored
     * on focus out, instead of flagging the field as invalid (which visually
     * looks like a wrongly required field).
     *
     * @param {string} digitsValue - content of the digits input
     * @returns {string}
     */
    parse(digitsValue) {
        const kind = this.kindInput.el ? this.kindInput.el.value.trim().toUpperCase() : "";
        const digits = (digitsValue || "").trim().replace(/^-/, "");
        if (!kind && !digits) {
            return "";
        }
        if (!digits) {
            // Kind set, digits cleared: the RIF is considered cleared, the
            // previous value must not be restored while editing.
            return "";
        }
        if (!kind) {
            // Digits without a kind: no change is committed to the record.
            return this.props.record.data[this.props.name] || "";
        }
        return digits.includes(".") ? `${kind}-${digits}` : kind + digits;
    }

    /**
     * Kind input: keep a single valid kind letter, uppercased. Anything else
     * clears the box so it can be retyped.
     */
    onKindInput(ev) {
        const el = ev.target;
        const last = el.value.slice(-1).toUpperCase();
        el.value = RIF_KINDS.includes(last) ? last : "";
        this.kindIndex.value = 0;
        this.kindTyped.value = el.value;
        if (el.value) {
            // Kind letter set: continue typing in the digits input right away,
            // no Enter needed.
            this.kindOpen.value = false;
            if (this.input.el) {
                this.input.el.focus();
            }
        }
    }

    /**
     * Options shown in the kind dropdown: all kinds, or those matching what
     * has been typed so far.
     */
    get kindOptions() {
        const typed = this.kindTyped.value.trim().toUpperCase();
        return RIF_KINDS.filter((kind) => !typed || kind.startsWith(typed));
    }

    /**
     * Focusing the kind input opens the dropdown right away.
     */
    onKindFocus() {
        const el = this.kindInput.el;
        this.kindTyped.value = el ? el.value : "";
        this.kindIndex.value = 0;
        this.kindOpen.value = true;
    }

    /**
     * Close the dropdown when the focus leaves the widget, and restore the
     * kind input when left in an incomplete state (letter without digits or
     * digits without letter).
     */
    onWidgetFocusout(ev) {
        if (!ev.currentTarget.contains(ev.relatedTarget)) {
            this.kindOpen.value = false;
            const kindEl = this.kindInput.el;
            const digitsEl = this.input.el;
            if (kindEl && digitsEl && !kindEl.value !== !digitsEl.value) {
                kindEl.value = this.kindDisplay;
                this.kindTyped.value = this.kindDisplay;
            }
        }
    }

    /**
     * Keyboard navigation of the kind dropdown: arrows move, Enter picks,
     * Escape closes. Typing a letter directly still works.
     */
    onKindKeydown(ev) {
        if (["ArrowDown", "ArrowUp"].includes(ev.key)) {
            ev.preventDefault();
            const options = this.kindOptions;
            if (!options.length) {
                return;
            }
            this.kindOpen.value = true;
            const delta = ev.key === "ArrowDown" ? 1 : -1;
            this.kindIndex.value =
                (this.kindIndex.value + delta + options.length) % options.length;
        } else if (ev.key === "Enter" && this.kindOpen.value) {
            ev.preventDefault();
            const options = this.kindOptions;
            if (options.length) {
                this.selectKind(options[Math.min(this.kindIndex.value, options.length - 1)]);
            }
        } else if (ev.key === "Escape") {
            this.kindOpen.value = false;
        }
    }

    /**
     * Pick a kind from the dropdown: set it, commit the record and continue
     * typing in the digits input.
     */
    async selectKind(kind) {
        const el = this.kindInput.el;
        if (!el) {
            return;
        }
        el.value = kind;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        this.kindOpen.value = false;
        await this.onKindChange();
        if (this.input.el) {
            this.input.el.focus();
        }
    }

    /**
     * Digits input: only digits are allowed (plus the dots and dashes of the
     * dotted RIF style). Anything else is dropped, preserving the caret.
     */
    onDigitsInput(ev) {
        const el = ev.target;
        const value = el.value;
        const filtered = value.replace(/[^\d.-]/g, "");
        if (filtered === value) {
            return;
        }
        const caret = el.selectionStart ?? value.length;
        const removedBeforeCaret = value.slice(0, caret).replace(/[^\d.-]/g, "").length;
        el.value = filtered;
        el.setSelectionRange(removedBeforeCaret, removedBeforeCaret);
    }

    /**
     * Pressing backspace at the very start of the digits input moves the
     * focus to the kind input, as if both were a single field.
     */
    onDigitsKeydown(ev) {
        if (ev.key === "Backspace" && ev.target.selectionStart === 0 && ev.target.selectionEnd === 0) {
            ev.preventDefault();
            const kindEl = this.kindInput.el;
            if (kindEl) {
                kindEl.focus();
                const pos = kindEl.value.length;
                kindEl.setSelectionRange(pos, pos);
            }
        }
    }

    /**
     * Entering an empty digits input (no kind, no digits) sends the focus to
     * the kind input, since the kind letter is what gets typed first.
     */
    onDigitsFocus(ev) {
        const kindEl = this.kindInput.el;
        if (kindEl && !ev.target.value && !kindEl.value) {
            kindEl.focus();
        }
    }

    /**
     * Commit the record when the kind is changed directly (the input field
     * hook only listens to the digits input).
     */
    async onKindChange() {
        try {
            const value = this.parse(this.input?.el ? this.input.el.value : "");
            if ((value || false) !== (this.props.record.data[this.props.name] || false)) {
                await this.props.record.update({ [this.props.name]: value });
            } else {
                this.input.el.value = this.digitsDisplay;
            }
        } catch {
            this.props.record.setInvalidField(this.props.name);
        }
    }
}

export const rifField = {
    component: RifField,
    supportedTypes: ["char"],
    extractProps: ({ attrs }) => ({
        placeholder: attrs.placeholder,
    }),
};

registry.category("fields").add("l10n_ve_rif", rifField);
