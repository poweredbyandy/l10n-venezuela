/** @odoo-module **/

import {
    isTfhkaEnqSts1Operativa,
    isTfhkaEnqSts2SinErrorFiscal,
} from "./tfhka_protocol";

const FLAG_21 = {
    30: {
        maxAmountInt: 14,
        maxAmountDecimal: 2,
        maxPaymentAmountInt: 15,
        maxPaymentAmountDecimal: 2,
        maxQtyInt: 14,
        maxQtyDecimal: 3,
        discInt: 15,
        discDecimal: 2,
    },
    0: {
        maxAmountInt: 8,
        maxAmountDecimal: 2,
        maxPaymentAmountInt: 10,
        maxPaymentAmountDecimal: 2,
        maxQtyInt: 5,
        maxQtyDecimal: 3,
        discInt: 7,
        discDecimal: 2,
    },
    1: {
        maxAmountInt: 7,
        maxAmountDecimal: 3,
        maxPaymentAmountInt: 10,
        maxPaymentAmountDecimal: 2,
        maxQtyInt: 5,
        maxQtyDecimal: 3,
        discInt: 7,
        discDecimal: 2,
    },
    2: {
        maxAmountInt: 6,
        maxAmountDecimal: 4,
        maxPaymentAmountInt: 10,
        maxPaymentAmountDecimal: 2,
        maxQtyInt: 5,
        maxQtyDecimal: 3,
        discInt: 7,
        discDecimal: 2,
    },
};

const TAX_MAP = {
    0: " ",
    1: "!",
    2: '"',
    3: "#",
};

const STATUS_CODES = new Set(["1", "4", "48"]);
let EMULATOR_INVOICE_SEQUENCE = 0;
let EMULATOR_LAST_REPORT_Z = 0;
const EMULATOR_MACHINE_SERIAL = "EMULADOR-TFHKA-001";

function toArray(value) {
    return Array.isArray(value) ? value : [];
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function cleanText(value, max = 127) {
    return String(value || "")
        .slice(0, max)
        .trim()
        .replaceAll("Ñ", "N")
        .replaceAll("ñ", "n");
}

function asNumber(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
}

function normalizePaymentMethod(value) {
    const txt = String(value || "").trim();
    if (!txt) {
        return "01";
    }
    return txt.padStart(2, "0");
}

function maybeDataWrapper(value) {
    if (value && typeof value === "object" && value.data) {
        return value.data;
    }
    return value || {};
}

function mapTaxCodeFromLine(line) {
    const directTax = line.tax ?? line.tax_code ?? line.taxCode;
    if (directTax !== undefined && directTax !== null && String(directTax) !== "") {
        const v = Math.max(0, Math.min(4, parseInt(directTax, 10) || 0));
        return String(v);
    }
    const percent = asNumber(line.tax_percent ?? line.taxPercent ?? line.tax_rate ?? 0, 0);
    if (percent <= 0) {
        return "0";
    }
    if (percent <= 8) {
        return "2";
    }
    if (percent <= 16) {
        return "1";
    }
    return "3";
}

export class TfhkaFiscalMachine {
    constructor(driver, options = {}) {
        this.driver = driver;
        this.commandDelayMs = options.commandDelayMs ?? 200;
        this.s1Parser = options.s1Parser || this._defaultS1Parser.bind(this);
        this.actions = {
            status: this.getStatusMachine.bind(this),
            status1: this.getS1PrinterData.bind(this),
            logger: this.logger.bind(this),
            logger_multi: this.loggerMulti.bind(this),
            programacion: this.programacion.bind(this),
            print_out_invoice: this.printOutInvoice.bind(this),
            print_out_refund: this.printOutRefund.bind(this),
            reprint: this.reprint.bind(this),
            reprint_type: this.reprintType.bind(this),
            reprint_date: this.reprintDate.bind(this),
            print_resume: this.printResume.bind(this),
            test: this.test.bind(this),
            report_x: this.printXReport.bind(this),
            report_z: this.printZReport.bind(this),
            get_last_invoice_number: this.getLastInvoiceNumber.bind(this),
            get_last_out_refund_number: this.getLastOutRefundNumber.bind(this),
            configure_device: this.configureDevice.bind(this),
            pre_invoice: this.preInvoice.bind(this),
            print_debit_note: this.printDebitNote.bind(this),
        };
    }

    async runAction(payload = {}) {
        const action = payload.action;
        if (!action || !this.actions[action]) {
            return { valid: false, message: `Acción no soportada: ${action || ""}` };
        }
        return this.actions[action](payload.data ?? payload, {
            onProgress: payload.onProgress,
        });
    }

    _notifyProgress(options, percent, message) {
        if (typeof options?.onProgress === "function") {
            const bounded = Math.max(0, Math.min(100, Math.round(percent)));
            options.onProgress({ percent: bounded, message });
        }
    }

    async _ensureStatusReady() {
        if (!this.driver || typeof this.driver.readFpStatus !== "function") {
            throw new Error("No hay driver fiscal disponible.");
        }
        const ok = await this.driver.readFpStatus();
        if (!ok) {
            throw new Error(this.driver.estado || "No se pudo leer el estado fiscal.");
        }
        const errorCode = String(this.driver.error ?? "");
        const fiscalSts2 = parseInt(errorCode, 10);
        if (
            Number.isFinite(fiscalSts2) &&
            !isTfhkaEnqSts2SinErrorFiscal(fiscalSts2)
        ) {
            throw new Error(
                this.driver.descripError ||
                    `Estado fiscal STS2 no admite operación (byte ${errorCode})`
            );
        }
        const statusCode = String(this.driver.status ?? "");
        const sts1 = parseInt(statusCode, 10);
        if (
            !STATUS_CODES.has(statusCode) &&
            !(Number.isFinite(sts1) && isTfhkaEnqSts1Operativa(sts1))
        ) {
            throw new Error(
                this.driver.descripStatus ||
                    `Estado impresora STS1 no permitido (${statusCode})`
            );
        }
        return true;
    }

    async _sendCommand(command) {
        const sent = await this.driver.sendCmd(String(command));
        if (!sent) {
            throw new Error(this.driver.estado || `Fallo al enviar comando ${command}`);
        }
        await sleep(this.commandDelayMs);
        return true;
    }

    splitAmount(amount, dec = 2) {
        const factor = 10 ** dec;
        const normalized = (Math.round(asNumber(amount, 0) * factor) / factor).toFixed(dec);
        const parts = normalized.split(".");
        return [parts[0] || "0", parts[1] || "".padEnd(dec, "0")];
    }

    _limitDecimals(value, decimals) {
        const n = asNumber(value, 0);
        const factor = 10 ** decimals;
        return Math.round(n * factor) / factor;
    }

    groupPayments(paymentLines) {
        const grouped = new Map();
        for (const payment of toArray(paymentLines)) {
            const method = normalizePaymentMethod(payment.payment_method ?? payment.paymentMethod);
            const amount = asNumber(payment.amount, 0);
            grouped.set(method, asNumber(grouped.get(method), 0) + amount);
        }
        return [...grouped.entries()].map(([payment_method, amount]) => ({
            payment_method,
            amount: Math.abs(amount),
        }));
    }

    formatInvoiceLine(item, config) {
        const priceUnit = this._limitDecimals(item.price_unit, config.maxAmountDecimal);
        if (priceUnit < 0) {
            return { line: null, discount: Math.abs(priceUnit) };
        }
        const taxValue = TAX_MAP[mapTaxCodeFromLine(item)] || "";
        const code = item.default_code ? `|${item.default_code}|` : item.code ? `|${item.code}|` : "";
        const [amountI, amountD] = this.splitAmount(
            Math.abs(priceUnit),
            config.maxAmountDecimal
        );
        const [qtyI, qtyD] = this.splitAmount(
            this._limitDecimals(item.quantity, config.maxQtyDecimal),
            config.maxQtyDecimal
        );
        const line = [
            taxValue,
            amountI.padStart(config.maxAmountInt, "0"),
            amountD.padStart(config.maxAmountDecimal, "0"),
            qtyI.padStart(config.maxQtyInt, "0"),
            qtyD.padStart(config.maxQtyDecimal, "0"),
            code,
            cleanText(item.name || item.product_name || "", 127),
        ].join("");
        return { line, discount: 0 };
    }

    formatRefundLine(item, config) {
        const priceUnit = this._limitDecimals(item.price_unit, config.maxAmountDecimal);
        if (priceUnit < 0) {
            return { line: null, discount: Math.abs(priceUnit) };
        }
        const taxCode = mapTaxCodeFromLine(item);
        const code = item.default_code ? `|${item.default_code}|` : item.code ? `|${item.code}|` : "";
        const [amountI, amountD] = this.splitAmount(
            Math.abs(priceUnit),
            config.maxAmountDecimal
        );
        const [qtyI, qtyD] = this.splitAmount(
            this._limitDecimals(item.quantity, config.maxQtyDecimal),
            config.maxQtyDecimal
        );
        const line = [
            "d",
            taxCode,
            amountI.padStart(config.maxAmountInt, "0"),
            amountD.padStart(config.maxAmountDecimal, "0"),
            qtyI.padStart(config.maxQtyInt, "0"),
            qtyD.padStart(config.maxQtyDecimal, "0"),
            code,
            cleanText(item.name || item.product_name || "", 127),
        ].join("");
        return { line, discount: 0 };
    }

    formatDebitLine(item, config) {
        const priceUnit = this._limitDecimals(item.price_unit, config.maxAmountDecimal);
        if (priceUnit < 0) {
            return { line: null, discount: Math.abs(priceUnit) };
        }
        const taxCode = mapTaxCodeFromLine(item);
        const code = item.default_code ? `|${item.default_code}|` : item.code ? `|${item.code}|` : "";
        const [amountI, amountD] = this.splitAmount(
            Math.abs(priceUnit),
            config.maxAmountDecimal
        );
        const [qtyI, qtyD] = this.splitAmount(
            this._limitDecimals(item.quantity, config.maxQtyDecimal),
            config.maxQtyDecimal
        );
        const line = [
            "`",
            taxCode,
            amountI.padStart(config.maxAmountInt, "0"),
            amountD.padStart(config.maxAmountDecimal, "0"),
            qtyI.padStart(config.maxQtyInt, "0"),
            qtyD.padStart(config.maxQtyDecimal, "0"),
            code,
            cleanText(item.name || item.product_name || "", 127),
        ].join("");
        return { line, discount: 0 };
    }

    _resolveFlag21(flag21) {
        const key = String(flag21 ?? "30").replace(/^0+(\d)$/, "$1");
        if (FLAG_21[key] !== undefined) {
            return FLAG_21[key];
        }
        return FLAG_21[30];
    }

    _normalizeFlag21Value(flag21) {
        const txt = String(flag21 ?? "30").trim();
        if (txt === "00" || txt === "0") {
            return "00";
        }
        if (txt === "01" || txt === "1") {
            return "01";
        }
        if (txt === "02" || txt === "2") {
            return "02";
        }
        return "30";
    }

    _normalizePartner(partner = {}) {
        return {
            vat: String(partner.vat || partner.rif || "").trim(),
            name: String(partner.name || partner.display_name || "").trim(),
            address: String(partner.address || partner.street || "").trim(),
            phone: String(partner.phone || partner.mobile || "").trim(),
        };
    }

    _normalizeAccountMoveInvoiceLines(move) {
        const lines = move.invoice_lines || move.invoiceLineIds || move.invoice_line_ids || [];
        const out = [];
        for (const line of toArray(lines)) {
            if (line.display_type && line.display_type !== "product") {
                continue;
            }
            out.push({
                default_code: line.default_code || line.code || "",
                name: line.name || line.product_name || "",
                quantity: asNumber(line.quantity, 0),
                price_unit: asNumber(line.price_unit, 0),
                discount: asNumber(line.discount, 0),
                tax: mapTaxCodeFromLine(line),
            });
        }
        return out;
    }

    _normalizeInvoiceFromAccountMove(move, options = {}) {
        const partner = this._normalizePartner(options.partner || move.partner || move.partner_id || {});
        const paymentLines = toArray(options.payment_lines || options.paymentLines || move.payment_lines);
        const data = {
            company_id: options.company_id || move.company_id || move.company || null,
            flag_21: String(options.flag_21 || options.flag21 || move.flag_21 || "30"),
            partner_id: partner,
            invoice_lines: options.invoice_lines || this._normalizeAccountMoveInvoiceLines(move),
            payment_lines: paymentLines,
            info: toArray(options.info || move.info),
            aditional_lines: toArray(
                options.aditional_lines || options.additional_lines || move.aditional_lines
            ),
            has_cashbox: Boolean(options.has_cashbox || move.has_cashbox),
            invoice_affected: options.invoice_affected || move.invoice_affected || null,
            barcode: options.barcode || move.barcode || null,
        };
        return { data };
    }

    normalizeInvoicePayload(input, options = {}) {
        const normalized = maybeDataWrapper(input);
        const configuredFlag21 = options.flag_21 || options.flag21;
        if (normalized.invoice_lines && normalized.payment_lines) {
            return {
                data: {
                    ...normalized,
                    flag_21: this._normalizeFlag21Value(configuredFlag21 || normalized.flag_21),
                },
            };
        }
        if (normalized.move_type || normalized.invoice_line_ids || normalized.invoice_lines) {
            const movePayload = this._normalizeInvoiceFromAccountMove(normalized, options);
            movePayload.data.flag_21 = this._normalizeFlag21Value(
                configuredFlag21 || movePayload.data.flag_21
            );
            return movePayload;
        }
        return {
            data: {
                ...normalized,
                flag_21: this._normalizeFlag21Value(configuredFlag21 || normalized.flag_21),
            },
        };
    }

    validateInvoiceParameter(invoicePayload) {
        const msg = [];
        let valid = true;
        const invoice = this.normalizeInvoicePayload(invoicePayload).data;
        if (!invoice || Object.keys(invoice).length === 0) {
            return { valid: false, message: ["No se recibió información de la factura"] };
        }
        const required = {
            company_id: "No se encontró la empresa",
            partner_id: "No se recibió información del cliente",
            invoice_lines: "No se recibió información de los productos",
            payment_lines: "No se recibió información de los pagos",
        };
        for (const [field, error] of Object.entries(required)) {
            const value = invoice[field];
            if (!value || (Array.isArray(value) && value.length === 0)) {
                valid = false;
                msg.push(error);
            }
        }
        const partner = invoice.partner_id || {};
        if (!partner.vat) {
            valid = false;
            msg.push("El cliente no tiene cédula");
        }
        if (!partner.name) {
            valid = false;
            msg.push("El cliente no tiene nombre");
        }
        for (const line of toArray(invoice.invoice_lines)) {
            if (line.price_unit === undefined) {
                valid = false;
                msg.push("No se encontró el precio del producto");
            }
            if (line.quantity === undefined) {
                valid = false;
                msg.push("No se encontró la cantidad del producto");
            }
            if (!line.name) {
                valid = false;
                msg.push("No se encontró el nombre del producto");
            }
            const tax = parseInt(mapTaxCodeFromLine(line), 10);
            if (!Number.isFinite(tax) || tax < 0 || tax > 4) {
                valid = false;
                msg.push("El impuesto no es válido");
            }
        }
        for (const line of toArray(invoice.payment_lines)) {
            if (line.amount === undefined) {
                valid = false;
                msg.push("No se recibió el monto del pago");
            }
            const paymentMethod = parseInt(normalizePaymentMethod(line.payment_method), 10);
            if (!Number.isFinite(paymentMethod) || paymentMethod < 1 || paymentMethod > 24) {
                valid = false;
                msg.push("El método de pago no es aceptado o no se recibió");
            }
        }
        return { valid, message: msg };
    }

    validateOutRefundParameter(invoicePayload) {
        const msg = [];
        let valid = true;
        const invoice = this.normalizeInvoicePayload(invoicePayload).data;
        if (!invoice || Object.keys(invoice).length === 0) {
            return { valid: false, message: ["No se recibió información de la nota de crédito"] };
        }
        if (!invoice.company_id) {
            valid = false;
            msg.push("No se encontró la empresa");
        }
        if (!invoice.partner_id) {
            return { valid: false, message: ["No se recibió información del cliente"] };
        }
        if (!invoice.invoice_affected) {
            return { valid: false, message: ["No se recibió información de la factura afectada"] };
        }
        const partner = invoice.partner_id || {};
        if (!partner.vat) {
            valid = false;
            msg.push("El cliente no tiene cédula");
        }
        if (!partner.name) {
            valid = false;
            msg.push("El cliente no tiene nombre");
        }
        const affected = invoice.invoice_affected || {};
        if (!affected.number) {
            valid = false;
            msg.push("No se recibió una factura afectada");
        }
        if (!affected.serial_machine) {
            valid = false;
            msg.push("No se recibió el serial de la máquina fiscal");
        }
        if (!affected.date) {
            valid = false;
            msg.push("No se recibió la fecha de la factura afectada");
        }
        if (!toArray(invoice.invoice_lines).length) {
            valid = false;
            msg.push("No se recibió información de los productos");
        }
        if (!toArray(invoice.payment_lines).length) {
            valid = false;
            msg.push("No se recibió información de los pagos");
        }
        return { valid, message: msg };
    }

    prepareInvoiceData(invoicePayload, options = {}) {
        try {
            const { data: invoice } = this.normalizeInvoicePayload(invoicePayload, options);
            const config = this._resolveFlag21(invoice.flag_21);
            const cmd = [];
            const partner = this._normalizePartner(invoice.partner_id || {});
            cmd.push(`iR*${partner.vat}`);
            cmd.push(`iS*${cleanText(partner.name, 120)}`);
            let nextIndex = 0;
            if (partner.address) {
                const firstLine = partner.address.slice(0, 30);
                cmd.push(`i${String(nextIndex).padStart(2, "0")}Direccion:${firstLine}`);
                nextIndex += 1;
                const remaining = partner.address.slice(30, 70);
                if (remaining) {
                    cmd.push(`i${String(nextIndex).padStart(2, "0")}${remaining}`);
                    nextIndex += 1;
                }
            }
            if (partner.phone) {
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}Telefono:${cleanText(partner.phone, 30)}`
                );
                nextIndex += 1;
            }
            for (const info of toArray(invoice.info)) {
                cmd.push(`i${String(nextIndex).padStart(2, "0")}${cleanText(info, 127)}`);
                nextIndex += 1;
            }
            let discount = 0;
            for (const item of toArray(invoice.invoice_lines)) {
                const { line, discount: lineDiscount } = this.formatInvoiceLine(item, config);
                if (line) {
                    cmd.push(line);
                }
                if (lineDiscount) {
                    discount += lineDiscount;
                }
                if (asNumber(item.discount, 0) > 0) {
                    const [amountI, amountD] = this.splitAmount(
                        this._limitDecimals(item.discount, config.discDecimal),
                        config.discDecimal
                    );
                    cmd.push(
                        `p-${amountI.padStart(config.discInt, "0")}${amountD.padStart(
                            config.discDecimal,
                            "0"
                        )}`
                    );
                }
            }
            cmd.push("3");
            const paymentLines = this.groupPayments(invoice.payment_lines);
            for (const payment of paymentLines) {
                if (payment.amount > 0) {
                    const [amountI, amountD] = this.splitAmount(
                        this._limitDecimals(payment.amount, config.maxPaymentAmountDecimal),
                        config.maxPaymentAmountDecimal
                    );
                    cmd.push(
                        `2${payment.payment_method}${amountI.padStart(
                            config.maxPaymentAmountInt,
                            "0"
                        )}${amountD}`
                    );
                }
            }
            if (invoice.has_cashbox) {
                cmd.push("w");
            }
            cmd.push("101");
            for (const [index, line] of toArray(invoice.aditional_lines).entries()) {
                cmd.push(`i${String(index).padStart(2, "0")}${cleanText(line, 127)}`);
            }
            cmd.push("199");
            return { valid: true, cmd, discount, payment_lines: paymentLines };
        } catch (error) {
            return { valid: false, message: error.message || String(error) };
        }
    }

    prepareOutRefundData(invoicePayload, options = {}) {
        try {
            const { data: invoice } = this.normalizeInvoicePayload(invoicePayload, options);
            const config = this._resolveFlag21(invoice.flag_21);
            const affected = invoice.invoice_affected || {};
            const partner = this._normalizePartner(invoice.partner_id || {});
            const cmd = [
                `iF*${String(affected.number || "").padStart(8, "0")}`,
                `iD*${String(affected.date || "")}`,
                `iI*${String(affected.serial_machine || "")}`,
                `iR*${partner.vat}`,
                `iS*${cleanText(partner.name, 120)}`,
            ];
            let nextIndex = 1;
            if (partner.address) {
                const firstLine = partner.address.slice(0, 30);
                cmd.push(`i${String(nextIndex).padStart(2, "0")}Direccion:${firstLine}`);
                nextIndex += 1;
                const remaining = partner.address.slice(30, 70);
                if (remaining) {
                    cmd.push(`i${String(nextIndex).padStart(2, "0")}${remaining}`);
                    nextIndex += 1;
                }
            }
            if (partner.phone) {
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}Telefono:${cleanText(partner.phone, 30)}`
                );
                nextIndex += 1;
            }
            for (const info of toArray(invoice.info)) {
                cmd.push(`i${String(nextIndex).padStart(2, "0")}${cleanText(info, 127)}`);
                nextIndex += 1;
            }
            let discountAmount = 0;
            for (const item of toArray(invoice.invoice_lines)) {
                const { line, discount } = this.formatRefundLine(item, config);
                if (line) {
                    cmd.push(line);
                }
                if (discount) {
                    discountAmount += discount;
                }
            }
            cmd.push("3");
            if (discountAmount > 0) {
                const [amountI, amountD] = this.splitAmount(
                    this._limitDecimals(discountAmount, config.discDecimal),
                    config.discDecimal
                );
                cmd.push(
                    `q-${amountI.padStart(config.discInt, "0")}${amountD.padStart(
                        config.discDecimal,
                        "0"
                    )}`
                );
            }
            const paymentLines = this.groupPayments(invoice.payment_lines);
            for (const payment of paymentLines) {
                if (payment.amount > 0) {
                    const [amountI, amountD] = this.splitAmount(
                        this._limitDecimals(payment.amount, config.maxPaymentAmountDecimal),
                        config.maxPaymentAmountDecimal
                    );
                    cmd.push(
                        `2${payment.payment_method}${amountI.padStart(
                            config.maxPaymentAmountInt,
                            "0"
                        )}${amountD}`
                    );
                }
            }
            if (invoice.has_cashbox) {
                cmd.push("w");
            }
            cmd.push("101");
            for (const [index, line] of toArray(invoice.aditional_lines).entries()) {
                cmd.push(`i${String(index).padStart(2, "0")}${cleanText(line, 127)}`);
            }
            cmd.push("199");
            return { valid: true, cmd, payment_lines: paymentLines };
        } catch (error) {
            return { valid: false, message: error.message || String(error) };
        }
    }

    prepareDebitNoteData(invoicePayload, options = {}) {
        try {
            const { data: invoice } = this.normalizeInvoicePayload(invoicePayload, options);
            const config = this._resolveFlag21(invoice.flag_21);
            const affected = invoice.invoice_affected || {};
            const partner = this._normalizePartner(invoice.partner_id || {});
            const cmd = [
                `iR*${partner.vat}`,
                `iS*${cleanText(partner.name, 120)}`,
                `iF*${String(affected.number || "").padStart(8, "0")}`,
                `iI*${String(affected.serial_machine || "")}`,
                `iD*${String(affected.date || "")}`,
            ];

            let nextIndex = 0;
            if (partner.address) {
                const firstLine = partner.address.slice(0, 30);
                cmd.push(`i${String(nextIndex).padStart(2, "0")}Direccion:${firstLine}`);
                nextIndex += 1;
                const remaining = partner.address.slice(30, 70);
                if (remaining) {
                    cmd.push(`i${String(nextIndex).padStart(2, "0")}${remaining}`);
                    nextIndex += 1;
                }
            }
            if (partner.phone) {
                cmd.push(
                    `i${String(nextIndex).padStart(2, "0")}Telefono:${cleanText(partner.phone, 30)}`
                );
                nextIndex += 1;
            }
            for (const info of toArray(invoice.info)) {
                cmd.push(`i${String(nextIndex).padStart(2, "0")}${cleanText(info, 127)}`);
                nextIndex += 1;
            }

            let discountAmount = 0;
            for (const item of toArray(invoice.invoice_lines)) {
                const { line, discount } = this.formatDebitLine(item, config);
                if (line) {
                    cmd.push(line);
                }
                if (discount) {
                    discountAmount += discount;
                }
                if (asNumber(item.discount, 0) > 0) {
                    const [amountI, amountD] = this.splitAmount(
                        this._limitDecimals(item.discount, config.discDecimal),
                        config.discDecimal
                    );
                    cmd.push(
                        `p-${amountI.padStart(config.discInt, "0")}${amountD.padStart(
                            config.discDecimal,
                            "0"
                        )}`
                    );
                }
            }

            cmd.push("3");

            if (discountAmount > 0) {
                const [amountI, amountD] = this.splitAmount(
                    this._limitDecimals(discountAmount, config.discDecimal),
                    config.discDecimal
                );
                cmd.push(
                    `q-${amountI.padStart(config.discInt, "0")}${amountD.padStart(
                        config.discDecimal,
                        "0"
                    )}`
                );
            }

            const paymentLines = this.groupPayments(invoice.payment_lines);
            for (const payment of paymentLines) {
                if (payment.amount > 0) {
                    const [amountI, amountD] = this.splitAmount(
                        this._limitDecimals(payment.amount, config.maxPaymentAmountDecimal),
                        config.maxPaymentAmountDecimal
                    );
                    cmd.push(
                        `2${payment.payment_method}${amountI.padStart(
                            config.maxPaymentAmountInt,
                            "0"
                        )}${amountD}`
                    );
                }
            }

            if (invoice.has_cashbox) {
                cmd.push("w");
            }

            cmd.push("101");
            for (const [index, line] of toArray(invoice.aditional_lines).entries()) {
                cmd.push(`i${String(index).padStart(2, "0")}${cleanText(line, 127)}`);
            }
            cmd.push("199");

            return { valid: true, cmd, payment_lines: paymentLines };
        } catch (error) {
            return { valid: false, message: error.message || String(error) };
        }
    }

    async sendInvoiceCommands(commandPayload, options = {}) {
        try {
            const cmd = toArray(commandPayload?.cmd || commandPayload);
            const start = options.progressStart ?? 0;
            const end = options.progressEnd ?? 100;
            const span = end - start;
            this._notifyProgress(options, start, "Enviando comandos...");
            const skipStatus =
                Boolean(commandPayload?.use_emulator) ||
                Boolean(commandPayload?.useEmulator);
            if (!skipStatus) {
                await this._ensureStatusReady();
            }
            const msg = [];
            for (let index = 0; index < cmd.length; index++) {
                const command = cmd[index];
                const sent = await this.driver.sendCmd(String(command));
                if (!sent && !["101", "199"].includes(String(command))) {
                    msg.push(`Fallo al enviar comando: ${command}`);
                    await this.driver.sendCmd("199");
                    return { valid: false, message: msg, continue: false };
                }
                await sleep(this.commandDelayMs);
                const progressIndex = index + 1;
                const ratio = cmd.length ? progressIndex / cmd.length : 1;
                this._notifyProgress(
                    options,
                    start + ratio * span,
                    `Imprimiendo... ${progressIndex}/${cmd.length} comandos`
                );
            }
            return { valid: true, msg, continue: true };
        } catch (error) {
            return { valid: false, message: error.message || String(error), continue: false };
        }
    }

    _defaultS1Parser(raw) {
        const text = String(raw || "");
        const groups = text.match(/\d+/g) || [];
        const number = groups.length ? groups[groups.length - 1] : null;
        return {
            raw: text,
            LastInvoiceNumber: number,
            LastCreditNoteNumber: number,
            LastDebitNoteNumber: number,
            DailyClosureCounter: null,
            RegisteredMachineNumber: null,
        };
    }

    _toIntOrNull(value) {
        if (value === undefined || value === null || value === "") {
            return null;
        }
        const n = parseInt(String(value), 10);
        return Number.isFinite(n) ? n : null;
    }

    _isEmulatorMode(invoicePayload) {
        return Boolean(invoicePayload?.use_emulator || invoicePayload?.data?.use_emulator);
    }

    _nextEmulatorInvoiceSequence(baseValue = null) {
        const base = this._toIntOrNull(baseValue);
        if (base !== null && base > EMULATOR_INVOICE_SEQUENCE) {
            EMULATOR_INVOICE_SEQUENCE = base;
        }
        EMULATOR_INVOICE_SEQUENCE += 1;
        return EMULATOR_INVOICE_SEQUENCE;
    }

    _nextEmulatorReportZ(baseClosureCounter = null) {
        const base = this._toIntOrNull(baseClosureCounter);
        if (base !== null) {
            const nextFromS1 = base + 1;
            if (nextFromS1 > EMULATOR_LAST_REPORT_Z) {
                EMULATOR_LAST_REPORT_Z = nextFromS1;
            } else {
                EMULATOR_LAST_REPORT_Z += 1;
            }
        } else {
            EMULATOR_LAST_REPORT_Z += 1;
        }
        return EMULATOR_LAST_REPORT_Z;
    }

    async getS1PrinterData() {
        if (!this.driver || typeof this.driver.uploadStatusCmdToString !== "function") {
            return null;
        }
        const result = await this.driver.uploadStatusCmdToString("S1");
        if (!result?.ok || !result.content) {
            return null;
        }
        return this.s1Parser(result.content);
    }

    async finalizeInvoice() {
        const s1 = await this.getS1PrinterData();
        return {
            valid: true,
            data: {
                sequence: s1?.LastInvoiceNumber || null,
                serial_machine: s1?.RegisteredMachineNumber || null,
                mf_reportz:
                    s1?.DailyClosureCounter !== null && s1?.DailyClosureCounter !== undefined
                        ? asNumber(s1.DailyClosureCounter, 0) + 1
                        : null,
            },
            message: "Factura impresa correctamente",
            raw_status: s1?.raw || null,
        };
    }

    async finalizeOutRefund() {
        const s1 = await this.getS1PrinterData();
        return {
            valid: true,
            data: {
                sequence: s1?.LastCreditNoteNumber || null,
                serial_machine: s1?.RegisteredMachineNumber || null,
                mf_reportz:
                    s1?.DailyClosureCounter !== null && s1?.DailyClosureCounter !== undefined
                        ? asNumber(s1.DailyClosureCounter, 0) + 1
                        : null,
            },
            message: "Nota de crédito impresa correctamente",
            raw_status: s1?.raw || null,
        };
    }

    async finalizeDebitNote() {
        const s1 = await this.getS1PrinterData();
        return {
            valid: true,
            data: {
                sequence: s1?.LastDebitNoteNumber || null,
                serial_machine: s1?.RegisteredMachineNumber || null,
                mf_reportz:
                    s1?.DailyClosureCounter !== null && s1?.DailyClosureCounter !== undefined
                        ? asNumber(s1.DailyClosureCounter, 0) + 1
                        : null,
            },
            message: "Nota de débito impresa correctamente",
            raw_status: s1?.raw || null,
        };
    }

    async printOutInvoice(invoicePayload, options = {}) {
        this._notifyProgress(options, 0, "Imprimiendo...");
        const validation = this.validateInvoiceParameter(invoicePayload);
        if (!validation.valid) {
            return validation;
        }
        const isEmulator = this._isEmulatorMode(invoicePayload);
        this._notifyProgress(options, 10, "Consultando S1 inicial...");
        const preS1 = await this.getS1PrinterData();
        const preSequence = this._toIntOrNull(preS1?.LastInvoiceNumber);
        const prepared = this.prepareInvoiceData(invoicePayload, options);
        if (!prepared.valid) {
            return prepared;
        }
        prepared.use_emulator = isEmulator;
        const sent = await this.sendInvoiceCommands(prepared, {
            ...options,
            progressStart: 20,
            progressEnd: 80,
        });
        if (!sent.valid) {
            return sent;
        }
        this._notifyProgress(options, 90, "Consultando S1 final...");
        const postS1 = await this.getS1PrinterData();
        let postSequence = this._toIntOrNull(postS1?.LastInvoiceNumber);
        let serialMachine =
            postS1?.RegisteredMachineNumber || preS1?.RegisteredMachineNumber || null;
        let reportZ =
            postS1?.DailyClosureCounter !== null &&
            postS1?.DailyClosureCounter !== undefined
                ? asNumber(postS1.DailyClosureCounter, 0) + 1
                : preS1?.DailyClosureCounter !== null &&
                    preS1?.DailyClosureCounter !== undefined
                  ? asNumber(preS1.DailyClosureCounter, 0) + 1
                  : null;

        if (isEmulator) {
            if (postSequence === null) {
                postSequence = this._nextEmulatorInvoiceSequence(preSequence);
            } else {
                this._nextEmulatorInvoiceSequence(postSequence);
            }
            if (!serialMachine) {
                serialMachine = EMULATOR_MACHINE_SERIAL;
            }
            if (reportZ === null) {
                const closureCounter =
                    postS1?.DailyClosureCounter ?? preS1?.DailyClosureCounter ?? null;
                reportZ = this._nextEmulatorReportZ(closureCounter);
            } else {
                this._nextEmulatorReportZ(reportZ - 1);
            }
        }

        if (preSequence !== null && postSequence !== null && postSequence <= preSequence) {
            return {
                valid: false,
                message:
                    "No se imprimio el documento fiscal. El S1 mantiene el mismo correlativo.",
                data: {
                    sequence_before: preSequence,
                    sequence_after: postSequence,
                },
            };
        }

        if (!isEmulator && preSequence === null && postSequence === null) {
            return {
                valid: false,
                message:
                    "No se pudo validar la impresion fiscal: S1 no devolvio correlativo antes ni despues.",
            };
        }

        this._notifyProgress(options, 100, "Imprimiendo... 100%");

        return {
            valid: true,
            data: {
                sequence: postSequence ?? preSequence ?? null,
                serial_machine: serialMachine,
                mf_reportz: reportZ,
            },
            message: "Factura impresa correctamente",
            raw_status: {
                pre_s1: preS1?.raw || null,
                post_s1: postS1?.raw || null,
            },
        };
    }

    async printOutRefund(invoicePayload, options = {}) {
        this._notifyProgress(options, 0, "Imprimiendo...");
        const validation = this.validateOutRefundParameter(invoicePayload);
        if (!validation.valid) {
            return validation;
        }
        const prepared = this.prepareOutRefundData(invoicePayload, options);
        if (!prepared.valid) {
            return prepared;
        }
        prepared.use_emulator = Boolean(
            invoicePayload?.use_emulator || invoicePayload?.data?.use_emulator
        );
        const sent = await this.sendInvoiceCommands(prepared, {
            ...options,
            progressStart: 10,
            progressEnd: 90,
        });
        if (!sent.valid) {
            return sent;
        }
        this._notifyProgress(options, 100, "Imprimiendo... 100%");
        return this.finalizeOutRefund();
    }

    async printDebitNote(invoicePayload, options = {}) {
        this._notifyProgress(options, 0, "Imprimiendo...");
        const validation = this.validateOutRefundParameter(invoicePayload);
        if (!validation.valid) {
            return validation;
        }
        const prepared = this.prepareDebitNoteData(invoicePayload, options);
        if (!prepared.valid) {
            return prepared;
        }
        prepared.use_emulator = Boolean(
            invoicePayload?.use_emulator || invoicePayload?.data?.use_emulator
        );
        const sent = await this.sendInvoiceCommands(prepared, {
            ...options,
            progressStart: 10,
            progressEnd: 90,
        });
        if (!sent.valid) {
            return sent;
        }
        this._notifyProgress(options, 100, "Imprimiendo... 100%");
        return this.finalizeDebitNote();
    }

    async logger(data) {
        await this._ensureStatusReady();
        await this._sendCommand(String(maybeDataWrapper(data)));
        return { valid: true };
    }

    async loggerMulti(data) {
        for (const line of toArray(maybeDataWrapper(data))) {
            await this._sendCommand(String(line));
        }
        return { valid: true };
    }

    async configureDevice(data) {
        await this._ensureStatusReady();
        const payload = maybeDataWrapper(data);
        if (payload.flag_21) {
            await this._sendCommand(`PJ21${payload.flag_21}`);
        }
        if (payload.flag_24) {
            await this._sendCommand(`PJ24${payload.flag_24}`);
        }
        if (payload.show_version) {
            await this._sendCommand(`PJ77${payload.show_version}`);
        }
        await this._sendCommand("PJ6300");
        const paymentMethods = [
            "PE01EFECTIVO 01",
            "PE02EFECTIVO 02",
            "PE03PAGO MOVIL 01",
            "PE04PAGO MOVIL 02",
            "PE05PAGO MOVIL 03",
            "PE06PAGO MOVIL 04",
            "PE07TRANSFERENCIA 01 ",
            "PE08TRANSFERENCIA 02",
            "PE09TRANSFERENCIA 03",
            "PE10TRANSFERENCIA 04",
            "PE11PDV 01 ",
            "PE12PDV 02",
            "PE13PDV 03",
            "PE14PDV 04",
            "PE15CREDITO 01",
            "PE16CREDITO 02",
            "PE19DIVISA 02",
            "PE20DIVISA 01",
            "PE21ZELLE",
        ];
        for (const line of paymentMethods) {
            await this._sendCommand(line);
        }
        return { valid: true };
    }

    async configureMachineFlag21(flag21, options = {}) {
        const normalizedFlag = this._normalizeFlag21Value(flag21);
        this._notifyProgress(options, 0, "Imprimiendo...");
        await this._sendCommand(`PJ21${normalizedFlag}`);
        this._notifyProgress(options, 30, "Imprimiendo... 30%");
        await this._sendCommand("PJ5001");
        this._notifyProgress(options, 60, "Imprimiendo... 60%");
        await this._sendCommand("PJ1701");
        this._notifyProgress(options, 85, "Imprimiendo... 85%");
        await this._sendCommand("D");
        this._notifyProgress(options, 100, "Imprimiendo... 100%");
        return {
            valid: true,
            message: `Configuración fiscal enviada con FLAG_21=${normalizedFlag}.`,
            flag_21: normalizedFlag,
        };
    }

    async test() {
        await this._ensureStatusReady();
        await this._sendCommand("7");
        await this._sendCommand("800");
        await this._sendCommand("80$Binaural Test");
        await this._sendCommand("80!Documento de pruebas");
        await this._sendCommand("810");
        return { valid: true, message: "Test impreso correctamente." };
    }

    async printResume(data) {
        await this._ensureStatusReady();
        const payload = maybeDataWrapper(data);
        const from = String(payload.resume_range_from || "");
        const to = String(payload.resume_range_to || "");
        await this._sendCommand(`I2S${from}${to}`);
        return { valid: true, message: "Resumen impreso correctamente." };
    }

    async reprintDate(data) {
        await this._ensureStatusReady();
        const payload = maybeDataWrapper(data);
        const mode = payload.mode || "Rs";
        const from = String(payload.reprint_range_from || "").padStart(7, "0");
        const to = String(payload.reprint_range_to || "").padStart(7, "0");
        await this._sendCommand(`${mode}${from}${to}`);
        return { valid: true, message: "Reimpresión por fecha enviada." };
    }

    async reprintType(data) {
        await this._ensureStatusReady();
        const payload = maybeDataWrapper(data);
        const mode = payload.mode || "R@";
        const from = String(payload.reprint_range_from || "").padStart(7, "0");
        const to = String(payload.reprint_range_to || "").padStart(7, "0");
        await this._sendCommand(`${mode}${from}${to}`);
        return { valid: true, message: "Reimpresión por tipo enviada." };
    }

    async reprint(data) {
        await this._ensureStatusReady();
        const payload = maybeDataWrapper(data);
        let mode = "";
        if (payload.type === "out_invoice") {
            mode = "RF";
        } else if (payload.type === "out_refund") {
            mode = "RC";
        }
        if (!mode) {
            return { valid: false, message: "Datos no válidos" };
        }
        const number = String(payload.mf_number || "").padStart(7, "0");
        await this._sendCommand(`${mode}${number}${number}`);
        return { valid: true };
    }

    async printXReport() {
        await this._ensureStatusReady();
        await this._sendCommand("I0X");
        return { valid: true, message: "Reporte X impreso correctamente." };
    }

    async printZReport() {
        await this._ensureStatusReady();
        await this._sendCommand("I0Z");
        return { valid: true, message: "Reporte Z impreso correctamente." };
    }

    async programacion() {
        await this._ensureStatusReady();
        await this._sendCommand("D");
        return { valid: true, message: "Programación impresa correctamente." };
    }

    preInvoice(invoicePayload) {
        const validation = this.validateInvoiceParameter(invoicePayload);
        if (!validation.valid) {
            return validation;
        }
        return { valid: true, message: "Factura validada." };
    }

    async getLastInvoiceNumber() {
        const s1 = await this.getS1PrinterData();
        return {
            valid: true,
            data: {
                sequence: s1?.LastInvoiceNumber || null,
                serial_machine: s1?.RegisteredMachineNumber || null,
                number: s1?.LastInvoiceNumber || null,
                report_z:
                    s1?.DailyClosureCounter !== null && s1?.DailyClosureCounter !== undefined
                        ? asNumber(s1.DailyClosureCounter, 0) + 1
                        : null,
            },
            raw_status: s1?.raw || null,
        };
    }

    async getLastOutRefundNumber() {
        const s1 = await this.getS1PrinterData();
        return {
            valid: true,
            data: {
                sequence: s1?.LastCreditNoteNumber || null,
                serial_machine: s1?.RegisteredMachineNumber || null,
                number: s1?.LastCreditNoteNumber || null,
                report_z:
                    s1?.DailyClosureCounter !== null && s1?.DailyClosureCounter !== undefined
                        ? asNumber(s1.DailyClosureCounter, 0) + 1
                        : null,
            },
            raw_status: s1?.raw || null,
        };
    }

    async getStatusMachine() {
        await this._ensureStatusReady();
        return {
            valid: true,
            message: `Estado de la impresora: ${this.driver.descripStatus || this.driver.status || ""}`,
            data: {
                status: this.driver.status,
                error: this.driver.error,
                descripStatus: this.driver.descripStatus,
                descripError: this.driver.descripError,
                erroValid: this.driver.erroValid,
            },
        };
    }

    split_amount(amount, dec = 2) {
        return this.splitAmount(amount, dec);
    }

    group_payments(paymentLines) {
        return this.groupPayments(paymentLines);
    }

    format_invoice_line(item, config) {
        return this.formatInvoiceLine(item, config);
    }

    format_refund_line(item, config) {
        return this.formatRefundLine(item, config);
    }

    prepare_invoice_data(invoicePayload, options = {}) {
        return this.prepareInvoiceData(invoicePayload, options);
    }

    prepare_out_refund_data(invoicePayload, options = {}) {
        return this.prepareOutRefundData(invoicePayload, options);
    }

    prepare_debit_note_data(invoicePayload, options = {}) {
        return this.prepareDebitNoteData(invoicePayload, options);
    }

    validate_invoice_parameter(invoicePayload) {
        return this.validateInvoiceParameter(invoicePayload);
    }

    validate_out_refund_parameter(invoicePayload) {
        return this.validateOutRefundParameter(invoicePayload);
    }

    send_invoice_commands(commandPayload) {
        return this.sendInvoiceCommands(commandPayload);
    }

    print_out_invoice(invoicePayload, options = {}) {
        return this.printOutInvoice(invoicePayload, options);
    }

    print_out_refund(invoicePayload, options = {}) {
        return this.printOutRefund(invoicePayload, options);
    }

    print_debit_note(invoicePayload, options = {}) {
        return this.printDebitNote(invoicePayload, options);
    }

    print_resume(data) {
        return this.printResume(data);
    }

    reprint_date(data) {
        return this.reprintDate(data);
    }

    reprint_type(data) {
        return this.reprintType(data);
    }

    print_x_report() {
        return this.printXReport();
    }

    print_z_report() {
        return this.printZReport();
    }

    get_last_invoice_number() {
        return this.getLastInvoiceNumber();
    }

    get_last_out_refund_number() {
        return this.getLastOutRefundNumber();
    }

    get_status_machine() {
        return this.getStatusMachine();
    }
}

export function createTfhkaFiscalMachine(driver, options = {}) {
    return new TfhkaFiscalMachine(driver, options);
}

export { FLAG_21, TAX_MAP };
