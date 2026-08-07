/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { createFiscalSerialAuditLogger } from "@l10n_ve_fiscal_serial/fiscal_serial/fiscal_serial_audit";
import { TfhkaWebSerialTransport } from "@l10n_ve_fiscal_serial/fiscal_serial/tfhka_transport_webserial";

export function l10nVeFiscalSerialPosGetInvoiceJournal(pos) {
    const order = typeof pos.get_order === "function" ? pos.get_order() : null;
    return order?.invoice_journal_id || pos.config?.invoice_journal_id || false;
}

export function l10nVeFiscalSerialPosGetEmissionMedium(pos) {
    const journal = l10nVeFiscalSerialPosGetInvoiceJournal(pos);
    return (
        journal?.l10n_ve_emission_medium ||
        pos.config?.l10n_ve_invoice_journal_emission_medium ||
        ""
    );
}

export function l10nVeFiscalSerialPosGetFiscalMachineId(pos) {
    const journal = l10nVeFiscalSerialPosGetInvoiceJournal(pos);
    if (!journal) {
        return false;
    }
    const machine = journal.l10n_ve_fiscal_machine_id;
    if (!machine) {
        return false;
    }
    if (typeof machine === "object") {
        return Number(machine.id) || false;
    }
    return Number(machine) || false;
}

export function l10nVeFiscalSerialPosIsFiscalMachine(pos) {
    const country =
        pos.company?.country_id?.code || pos.company?.account_fiscal_country_id?.code;
    return country === "VE" && l10nVeFiscalSerialPosGetEmissionMedium(pos) === "fiscal_machine";
}

export function l10nVeFiscalSerialPosGetFiscalMachine(pos) {
    const journal = l10nVeFiscalSerialPosGetInvoiceJournal(pos);
    const machine = journal?.l10n_ve_fiscal_machine_id;
    if (!machine) {
        return false;
    }
    if (typeof machine === "object") {
        return machine;
    }
    const machineId = Number(machine) || 0;
    if (!machineId) {
        return false;
    }
    return pos.models?.["l10n.ve.fiscal.machine"]?.get?.(machineId) || false;
}

export function l10nVeFiscalSerialPosIncrementCounter(value, minWidth = 8) {
    const digits = String(value || "").replace(/\D/g, "");
    if (!digits) {
        return false;
    }
    const width = Math.max(digits.length, minWidth);
    return String(Number.parseInt(digits, 10) + 1).padStart(width, "0");
}

export function l10nVeFiscalSerialPosLastNumberForPlaceholders(pos, machine) {
    const order = typeof pos.get_order === "function" ? pos.get_order() : null;
    if (order && typeof order._isRefundOrder === "function" && order._isRefundOrder()) {
        return machine.last_credit_note_number;
    }
    return machine.last_invoice_number;
}

export function l10nVeFiscalSerialPosGetNextPlaceholders(pos) {
    const machine = l10nVeFiscalSerialPosGetFiscalMachine(pos);
    if (!machine) {
        return {
            serial: false,
            invoice_number: false,
            report_z: false,
        };
    }
    return {
        serial: (machine.registered_serial || "").trim() || false,
        invoice_number: l10nVeFiscalSerialPosIncrementCounter(
            l10nVeFiscalSerialPosLastNumberForPlaceholders(pos, machine),
            8
        ),
        report_z: l10nVeFiscalSerialPosIncrementCounter(
            machine.daily_closure_counter,
            4
        ),
    };
}

export function l10nVeFiscalSerialPosSyncMachineCounters(pos, response) {
    const machine = l10nVeFiscalSerialPosGetFiscalMachine(pos);
    if (!machine?.update || !response?.data) {
        return;
    }
    const d = response.data;
    const vals = {};
    const sequence = d.sequence !== undefined && d.sequence !== null ? String(d.sequence) : false;
    if (sequence) {
        const order = typeof pos.get_order === "function" ? pos.get_order() : null;
        const isRefund =
            order && typeof order._isRefundOrder === "function" && order._isRefundOrder();
        if (isRefund) {
            vals.last_credit_note_number = sequence;
        } else {
            vals.last_invoice_number = sequence;
        }
    }
    if (d.serial_machine !== undefined && d.serial_machine !== null && d.serial_machine !== "") {
        vals.registered_serial = String(d.serial_machine);
    }
    if (d.mf_reportz !== undefined && d.mf_reportz !== null) {
        const zDigits = String(d.mf_reportz).replace(/\D/g, "");
        if (zDigits) {
            vals.daily_closure_counter = zDigits;
        }
    }
    if (Object.keys(vals).length) {
        machine.update(vals);
    }
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
    const connection = env.services.l10n_ve_fiscal_connection;
    const notification = env.services.notification;
    const orm = env.services.orm;
    const ui = env.services.ui;

    if (!fiscalSerial || !connection) {
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
    const machineConfig = data.fiscal_machine || {};

    const progressLabel =
        printAction === "reprint"
            ? _t("Reimprimiendo fiscalmente")
            : _t("Imprimiendo fiscalmente");

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
        auditLogger = createFiscalSerialAuditLogger(orm, {
            source:
                printAction === "print_out_refund"
                    ? "refund_print"
                    : printAction === "print_debit_note"
                      ? "debit_note"
                      : printAction === "reprint"
                        ? "reprint"
                        : "invoice_print",
            moveId: data.move_id || false,
            machineId: machineConfig.machine_id || false,
        });
        if (!machineConfig.machine_id) {
            throw new Error(
                _t(
                    "El diario de facturación no tiene máquina fiscal configurada."
                )
            );
        }
        await connection.setPrimaryMachine(machineConfig.machine_id);
        const authorized = await TfhkaWebSerialTransport.resolvePort(machineConfig, {
            requestPort: false,
        });
        const needPortPicker = !authorized.port && !connection.state.portOpen;
        if (needPortPicker) {
            notification.add(
                _t("Seleccione la máquina fiscal en el cuadro de puertos del navegador."),
                { type: "warning" }
            );
        }
        const driver = await connection.borrowDriver({
            machine: machineConfig,
            requestPort: needPortPicker,
        });
        borrowed = true;
        auditLogger.attachDriver(driver);
        setProgress(15, progressLabel);
        if (machineConfig.machine_id) {
            const verification = await fiscalSerial.verifyConnectedFiscalMachine(
                driver,
                machineConfig,
                {
                    parseTfhkaS1StatusResponse: fiscalSerial.parseTfhkaS1StatusResponse,
                }
            );
            if (verification.training_mode || verification.emulator_mode) {
                notification.add(verification.message, { type: "warning" });
            }
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
        if (printAction !== "reprint") {
            l10nVeFiscalSerialPosSyncMachineCounters(pos, response);
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
