/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

export function l10nVeFiscalSerialPosIsFiscalMachine(pos) {
    const country =
        pos.company?.country_id?.code || pos.company?.account_fiscal_country_id?.code;
    return (
        country === "VE" &&
        pos.config.l10n_ve_invoice_journal_emission_medium === "fiscal_machine"
    );
}

export function l10nVeFiscalSerialPosSyncOrderFiscalFields(order, response) {
    if (!order?.update || !response?.data || typeof order.update !== "function") {
        return;
    }
    const d = response.data;
    const vals = {};
    if (d.sequence !== undefined && d.sequence !== null) {
        vals.l10n_ve_pos_fiscal_invoice_number = String(d.sequence);
    }
    if (d.serial_machine !== undefined && d.serial_machine !== null && d.serial_machine !== "") {
        vals.l10n_ve_pos_fiscal_serial = String(d.serial_machine);
    }
    if (d.mf_reportz !== undefined && d.mf_reportz !== null) {
        vals.l10n_ve_pos_fiscal_report_z = String(d.mf_reportz);
    }
    if (Object.keys(vals).length) {
        order.update(vals);
    }
}

export async function l10nVeFiscalSerialPosExecutePrint({
    pos,
    env,
    orderId,
    order,
    logTag = "[l10n_ve_fiscal_serial_pos]",
}) {
    const fiscalSerial = env.services.l10n_ve_fiscal_serial;
    const notification = env.services.notification;
    const ui = env.services.ui;

    if (!fiscalSerial) {
        notification.add(
            _t("El servicio de máquina fiscal no está disponible en el POS."),
            { type: "danger" }
        );
        return false;
    }
    if (!fiscalSerial.isSupported()) {
        notification.add(
            _t(
                "Web Serial no está disponible. Use Chrome o Edge con HTTPS para imprimir fiscalmente desde el POS."
            ),
            { type: "danger" }
        );
        return false;
    }

    let payload;
    try {
        payload = await pos.data.call(
            "pos.order",
            "l10n_ve_fiscal_serial_pos_fiscal_action_payload",
            [[orderId]]
        );
    } catch (error) {
        const msg =
            error?.data?.message ||
            error?.message ||
            String(error || _t("No se pudo preparar la impresión fiscal."));
        notification.add(msg, { type: "danger" });
        return false;
    }

    const printAction = payload?.l10n_ve_print_action || "print_out_invoice";
    const data = { ...payload };
    delete data.l10n_ve_print_action;

    const progressLabel =
        printAction === "reprint" ? _t("Reimprimiendo fiscalmente") : _t("Imprimiendo fiscalmente");

    notification.add(
        _t("Seleccione la máquina fiscal en el cuadro de puertos del navegador."),
        { type: "warning" }
    );

    let driver;
    let blocked = false;
    const setProgress = (percent, message) => {
        const pct = Math.max(0, Math.min(100, Math.round(percent)));
        if (blocked) {
            ui.unblock();
            blocked = false;
        }
        ui.block({ message: `${message || progressLabel} ${pct}%` });
        blocked = true;
    };

    try {
        setProgress(0, progressLabel);
        driver = fiscalSerial.createTfhkaFiscal();
        const opened = await driver.openFpCtrl({ baudRate: 9600, parity: "even" });
        if (!opened) {
            throw new Error(driver.estado || _t("No fue posible abrir el puerto serial."));
        }
        setProgress(20, progressLabel);
        const machine = fiscalSerial.createTfhkaFiscalMachine(driver);
        const response = await machine.runAction({
            action: printAction,
            data,
            onProgress: ({ percent, message }) => {
                setProgress(percent, message || progressLabel);
            },
        });
        if (!response?.valid) {
            throw new Error(response?.message || _t("Falló la impresión fiscal."));
        }
        try {
            await driver.closeFpCtrl();
        } catch {
        }
        driver = null;
        setProgress(95, progressLabel);
        if (printAction !== "reprint") {
            await pos.data.call("pos.order", "l10n_ve_fiscal_serial_register_print_result", [
                [orderId],
                response,
            ]);
        }
        if (order) {
            l10nVeFiscalSerialPosSyncOrderFiscalFields(order, response);
        }
        setProgress(100, progressLabel);
        notification.add(
            response.message ||
                (printAction === "reprint"
                    ? _t("Reimpresión fiscal completada.")
                    : _t("Impresión fiscal completada.")),
            { type: "success" }
        );
        return true;
    } catch (error) {
        const msg =
            error?.data?.message ||
            error?.data?.arguments?.[0] ||
            error?.message ||
            String(error || _t("Error en impresión fiscal."));
        console.error(`${logTag} Error impresión fiscal POS:`, error);
        notification.add(msg, { type: "danger" });
        return false;
    } finally {
        if (driver) {
            try {
                await driver.closeFpCtrl();
            } catch {
            }
        }
        if (blocked) {
            ui.unblock();
        }
    }
}
