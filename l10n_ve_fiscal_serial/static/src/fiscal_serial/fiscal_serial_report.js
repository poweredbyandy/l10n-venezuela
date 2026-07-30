/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { createFiscalSerialAuditLogger } from "./fiscal_serial_audit";
import { TfhkaWebSerialTransport } from "./tfhka_transport_webserial";

const REPORT_LABELS = {
    report_x: _t("Reporte X"),
    report_z: _t("Reporte Z"),
};

export async function l10nVeFiscalSerialExecuteReport({
    env,
    action,
    logTag = "[l10n_ve_fiscal_serial]",
}) {
    const fiscalSerial = env.services.l10n_ve_fiscal_serial;
    const connection = env.services.l10n_ve_fiscal_connection;
    const notification = env.services.notification;
    const ui = env.services.ui;
    const progressLabel = REPORT_LABELS[action] || _t("Imprimiendo reporte fiscal");

    if (!fiscalSerial || !connection) {
        notification.add(
            _t("El servicio de máquina fiscal no está disponible."),
            { type: "danger" }
        );
        return false;
    }
    if (!fiscalSerial.isSupported()) {
        notification.add(
            _t(
                "Web Serial no está disponible. Use Chrome o Edge con HTTPS para imprimir desde el navegador."
            ),
            { type: "danger" }
        );
        return false;
    }

    let borrowed = false;
    let auditLogger;
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
        auditLogger = createFiscalSerialAuditLogger(env.services.orm, {
            source: "report",
        });
        const authorized = await TfhkaWebSerialTransport.resolvePort(
            {},
            { requestPort: false }
        );
        if (!authorized.port && !connection.state.portOpen) {
            notification.add(
                _t("Seleccione la máquina fiscal en el cuadro de puertos del navegador."),
                { type: "warning" }
            );
        }
        const driver = await connection.borrowDriver({ requestPort: true });
        borrowed = true;
        auditLogger.attachDriver(driver);
        setProgress(50, progressLabel);
        const machine = fiscalSerial.createTfhkaFiscalMachine(driver);
        const response = await machine.runAction({ action, data: {} });
        if (!response?.valid) {
            throw new Error(response?.message || _t("No se pudo imprimir el reporte fiscal."));
        }
        setProgress(100, progressLabel);
        notification.add(response.message || `${progressLabel} ${_t("completado.")}`, {
            type: "success",
        });
        return true;
    } catch (error) {
        const msg =
            error?.data?.message ||
            error?.data?.arguments?.[0] ||
            error?.message ||
            String(error || _t("Error al imprimir el reporte fiscal."));
        console.error(`${logTag} Error reporte fiscal:`, error);
        notification.add(msg, { type: "danger" });
        return false;
    } finally {
        if (borrowed) {
            await connection.releaseDriver({ close: false });
        }
        if (auditLogger) {
            await auditLogger.flush();
        }
        if (blocked) {
            ui.unblock();
        }
    }
}
