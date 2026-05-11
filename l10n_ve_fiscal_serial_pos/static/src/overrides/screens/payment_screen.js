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

patch(PaymentScreen.prototype, {
    _l10nVeFiscalSerialNeedsPrint() {
        if (!isVenezuelaCompany(this.pos)) {
            return false;
        }
        if (this.pos.config.l10n_ve_invoice_journal_emission_medium !== "fiscal_machine") {
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

        const fiscalSerial = this.env.services.l10n_ve_fiscal_serial;
        if (!fiscalSerial) {
            this.notification.add(
                _t("El servicio de máquina fiscal no está disponible en el POS."),
                { type: "danger" }
            );
            return false;
        }
        if (!fiscalSerial.isSupported()) {
            this.notification.add(
                _t(
                    "Web Serial no está disponible. Use Chrome o Edge con HTTPS para imprimir fiscalmente desde el POS."
                ),
                { type: "danger" }
            );
            return false;
        }

        const orderId = this.currentOrder.id;
        let payload;
        try {
            payload = await this.pos.data.call(
                "pos.order",
                "l10n_ve_fiscal_serial_check_print_move",
                [[orderId]]
            );
        } catch (error) {
            const msg =
                error?.data?.message ||
                error?.message ||
                String(error || _t("No se pudo preparar la impresión fiscal."));
            this.notification.add(msg, { type: "danger" });
            return false;
        }

        const printAction = payload?.l10n_ve_print_action || "print_out_invoice";
        const data = { ...payload };
        delete data.l10n_ve_print_action;

        this.notification.add(
            _t("Seleccione la máquina fiscal en el cuadro de puertos del navegador."),
            { type: "warning" }
        );

        let driver;
        let blocked = false;
        const ui = this.env.services.ui;
        const setProgress = (percent, message) => {
            const pct = Math.max(0, Math.min(100, Math.round(percent)));
            if (blocked) {
                ui.unblock();
                blocked = false;
            }
            ui.block({ message: `${message || _t("Imprimiendo fiscalmente")} ${pct}%` });
            blocked = true;
        };

        try {
            setProgress(0, _t("Imprimiendo fiscalmente"));
            driver = fiscalSerial.createTfhkaFiscal();
            const opened = await driver.openFpCtrl({ baudRate: 9600, parity: "even" });
            if (!opened) {
                throw new Error(driver.estado || _t("No fue posible abrir el puerto serial."));
            }
            setProgress(20, _t("Imprimiendo fiscalmente"));
            const machine = fiscalSerial.createTfhkaFiscalMachine(driver);
            const response = await machine.runAction({
                action: printAction,
                data,
                onProgress: ({ percent, message }) => {
                    setProgress(percent, message || _t("Imprimiendo fiscalmente"));
                },
            });
            if (!response?.valid) {
                throw new Error(response?.message || _t("Falló la impresión fiscal."));
            }
            setProgress(95, _t("Imprimiendo fiscalmente"));
            await this.pos.data.call("pos.order", "l10n_ve_fiscal_serial_register_print_result", [
                [orderId],
                response,
            ]);
            setProgress(100, _t("Imprimiendo fiscalmente"));
            this.notification.add(response.message || _t("Impresión fiscal completada."), {
                type: "success",
            });
            return true;
        } catch (error) {
            const msg =
                error?.data?.message ||
                error?.data?.arguments?.[0] ||
                error?.message ||
                String(error || _t("Error en impresión fiscal."));
            console.error("[l10n_ve_fiscal_serial_pos] Error impresión fiscal POS:", error);
            this.notification.add(msg, { type: "danger" });
            return false;
        } finally {
            if (driver) {
                try {
                    await driver.closeFpCtrl();
                } catch {
                    // ignore close errors
                }
            }
            if (blocked) {
                ui.unblock();
            }
        }
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
