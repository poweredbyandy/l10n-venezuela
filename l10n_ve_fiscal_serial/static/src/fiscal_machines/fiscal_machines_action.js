/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";

const TFHKA_COMMAND_DELAY_MS = 200;

const PHASE = {
    DISCONNECTED: "disconnected",
    CONNECTING: "connecting",
    CONNECTED: "connected",
    ERROR: "error",
};

export class FiscalMachinesAction extends Component {
    static template = "l10n_ve_fiscal_serial.FiscalMachinesAction";
    static components = { Layout };
    static props = ["*"];

    setup() {
        this.fiscalSerial = useService("l10n_ve_fiscal_serial");
        this.notification = useService("notification");
        this.state = useState({
            phase: PHASE.DISCONNECTED,
            busy: false,
            estado: "",
            commandText: "",
            lastCmdResult: "",
            logLines: [],
            serialBaud: "9600",
            serialParity: "even",
            fpStatus: "",
            fpError: "",
            fpDescripStatus: "",
            fpDescripError: "",
            fpLrcValid: null,
        });
        this.driver = null;
    }

    get display() {
        return { controlPanel: {} };
    }

    get statusLabel() {
        switch (this.state.phase) {
            case PHASE.CONNECTING:
                return "Conectando…";
            case PHASE.CONNECTED:
                return "Puerto abierto";
            case PHASE.ERROR:
                return "Error";
            default:
                return "Desconectado";
        }
    }

    get statusClass() {
        switch (this.state.phase) {
            case PHASE.CONNECTING:
                return "bg-warning text-dark";
            case PHASE.CONNECTED:
                return "bg-success";
            case PHASE.ERROR:
                return "bg-danger";
            default:
                return "bg-secondary";
        }
    }

    get canSendCommands() {
        return (
            this.state.phase === PHASE.CONNECTED &&
            !this.state.busy &&
            this.driver !== null
        );
    }

    get isSendDisabled() {
        return this.state.busy || !this.canSendCommands;
    }

    get logDisplayText() {
        if (!this.state.logLines.length) {
            return "Pulse «Abrir conexión»; aquí aparecerán los pasos. La misma información sale en la consola (F12) con el prefijo [l10n_ve_fiscal_serial].";
        }
        return this.state.logLines.join("\n");
    }

    get fpStatusHex() {
        const n = parseInt(this.state.fpStatus, 10);
        if (Number.isNaN(n)) {
            return "";
        }
        return n.toString(16).toUpperCase();
    }

    get fpMachineLine() {
        if (this.state.phase !== PHASE.CONNECTED) {
            return "";
        }
        if (this.state.fpStatus === "" && this.state.fpError === "") {
            return "";
        }
        const hx = this.fpStatusHex ? `0x${this.fpStatusHex}` : "—";
        const lrc =
            this.state.fpLrcValid === true
                ? "válido"
                : this.state.fpLrcValid === false
                  ? "no válido"
                  : "—";
        return `Estado: ${this.state.fpStatus || "—"} (${hx}) — ${this.state.fpDescripStatus || "—"} · Error: ${this.state.fpError || "—"} — ${this.state.fpDescripError || "—"} · LRC: ${lrc}`;
    }

    _resetFpStatusFields() {
        this.state.fpStatus = "";
        this.state.fpError = "";
        this.state.fpDescripStatus = "";
        this.state.fpDescripError = "";
        this.state.fpLrcValid = null;
    }

    _syncFpStatusFromDriver() {
        if (!this.driver) {
            this._resetFpStatusFields();
            return;
        }
        const st = this.driver.status;
        const er = this.driver.error;
        this.state.fpStatus =
            st != null && String(st) !== "" ? String(st) : "";
        this.state.fpError =
            er != null && String(er) !== "" ? String(er) : "";
        this.state.fpDescripStatus = this.driver.descripStatus || "";
        this.state.fpDescripError = this.driver.descripError || "";
        this.state.fpLrcValid =
            typeof this.driver.erroValid === "boolean"
                ? this.driver.erroValid
                : null;
    }

    _log(line) {
        const stamp = new Date().toISOString().split("T")[1].slice(0, 12);
        const entry = `[${stamp}] ${line}`;
        console.info("[l10n_ve_fiscal_serial]", entry);
        const next = [...this.state.logLines, entry];
        this.state.logLines = next.slice(-24);
    }

    async onOpenConnection() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.phase = PHASE.CONNECTING;
        this.state.estado = "Esperando puerto y comprobación ENQ…";
        this.state.logLines = [];
        this._log("Inicio: comprobar Web Serial API");
        try {
            if (!this.fiscalSerial.isSupported()) {
                this.state.phase = PHASE.ERROR;
                this.state.estado =
                    "Este navegador no expone Web Serial. Use Chrome o Edge y acceda por HTTPS.";
                this._log("ERROR: Web Serial no disponible");
                this.notification.add(this.state.estado, { type: "danger" });
                return;
            }
            this._log("Web Serial OK. Se abrirá el selector de puerto del navegador");
            this.driver = this.fiscalSerial.createTfhkaFiscal();
            const baud = parseInt(this.state.serialBaud, 10) || 9600;
            const parity = this.state.serialParity === "none" ? "none" : "even";
            this._log(
                `openFpCtrl baud=${baud} parity=${parity} — elija el adaptador USB-Serie`
            );
            const ok = await this.driver.openFpCtrl({
                baudRate: baud,
                parity,
            });
            if (ok) {
                this._resetFpStatusFields();
                this._log("openFpCtrl: OK — leyendo estado fiscal (ENQ, 5 bytes)…");
                const stOk = await this.driver.readFpStatus();
                this._syncFpStatusFromDriver();
                this.state.phase = PHASE.CONNECTED;
                this.state.estado =
                    this.driver.estado ||
                    (stOk
                        ? "Listo. Puerto abierto; estado y error fiscal leídos (ENQ)."
                        : "Puerto abierto; la lectura ENQ de estado no devolvió 5 bytes válidos. Revise paridad/baudios o pulse «Estado impresora (ENQ)».");
                this._log(
                    stOk
                        ? `ENQ inicial: estado=${this.driver.status} error=${this.driver.error} LRC=${this.driver.erroValid}`
                        : `ENQ inicial: fallo — ${this.driver.estado || "sin detalle"}`
                );
                this.notification.add("Puerto abierto.", { type: "success" });
            } else {
                this.state.phase = PHASE.ERROR;
                const detail =
                    this.driver.estado ||
                    "No se pudo completar la conexión con la impresora fiscal.";
                this.state.estado = detail;
                this._log(`openFpCtrl: fallo — ${detail}`);
                this.notification.add(detail, { type: "danger" });
                this.driver = null;
            }
        } catch (e) {
            this.state.phase = PHASE.ERROR;
            const detail = this.fiscalSerial.formatWebSerialError(e);
            this.state.estado = detail;
            this._log(`EXCEPCIÓN: ${detail}`);
            this.notification.add(detail, { type: "danger" });
            this._resetFpStatusFields();
            this.driver = null;
        } finally {
            this.state.busy = false;
        }
    }

    async onCloseConnection() {
        if (this.state.busy || !this.driver) {
            return;
        }
        this.state.busy = true;
        this._log("Cerrando puerto…");
        try {
            await this.driver.closeFpCtrl();
            this.state.phase = PHASE.DISCONNECTED;
            this.state.estado = "";
            this.state.lastCmdResult = "";
            this._resetFpStatusFields();
            this.driver = null;
            this._log("Puerto cerrado");
            this.notification.add("Puerto cerrado.", { type: "success" });
        } catch (e) {
            const msg = e.message || String(e);
            this._log(`ERROR al cerrar: ${msg}`);
            this.notification.add(msg, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async onSendCommand() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    { type: "warning" }
                );
            }
            return;
        }
        const raw = this.state.commandText ?? "";
        const normalized = raw.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
        const lines = normalized.split("\n").filter((l) => l.length > 0);
        if (!lines.length) {
            this.notification.add("Indique al menos un comando.", { type: "warning" });
            return;
        }
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._log(`Enviar ${lines.length} línea(s) de comando`);
        try {
            let okCount = 0;
            for (const line of lines) {
                this._log(`sendCmd: «${line.length > 80 ? line.slice(0, 80) + "…" : line}»`);
                const sent = await this.driver.sendCmd(line);
                if (sent) {
                    okCount += 1;
                    this._log(`Línea ${okCount}: ACK OK`);
                } else {
                    const errDetail = `Error en comando. Estado driver: ${this.driver.estado || "NAK/sin ACK"}`;
                    this.state.lastCmdResult = errDetail;
                    this._log(`ERROR: ${errDetail}`);
                    this.notification.add(errDetail, { type: "danger" });
                    return;
                }
            }
            this.state.lastCmdResult = `Enviados ${okCount} comando(s) en Latin-1 (OK).`;
            this._log("Todos los comandos respondieron ACK");
            this.notification.add("Comando(s) enviado(s).", { type: "success" });
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`EXCEPCIÓN envío: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async onSendSampleInvoice() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    { type: "warning" }
                );
            }
            return;
        }
        const lines = this.fiscalSerial.getSampleHkaInvoiceLines();
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._log(`Secuencia de prueba: ${lines.length} línea(s) (pausa ${TFHKA_COMMAND_DELAY_MS} ms entre líneas)`);
        try {
            let okCount = 0;
            for (let i = 0; i < lines.length; i++) {
                if (i > 0) {
                    await new Promise((r) => setTimeout(r, TFHKA_COMMAND_DELAY_MS));
                }
                const line = lines[i];
                this._log(`sendCmd: «${line.length > 80 ? line.slice(0, 80) + "…" : line}»`);
                const sent = await this.driver.sendCmd(line);
                if (sent) {
                    okCount += 1;
                    this._log(`Línea ${okCount}: ACK OK`);
                } else {
                    const errDetail = `Error en secuencia de prueba. Estado driver: ${this.driver.estado || "NAK/sin ACK"}`;
                    this.state.lastCmdResult = errDetail;
                    this._log(`ERROR: ${errDetail}`);
                    this.notification.add(errDetail, { type: "danger" });
                    return;
                }
            }
            this.state.lastCmdResult = `Secuencia de prueba: ${okCount} comando(s) enviados. Si la factura no cierra en el equipo, añada totales, pagos y cierre según el manual (p. ej. 199).`;
            this._log("Secuencia de prueba completada (ACK en todas las líneas)");
            this.notification.add("Secuencia de prueba enviada.", { type: "success" });
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`EXCEPCIÓN secuencia: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async onReadFpStatusEnq() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    { type: "warning" }
                );
            }
            return;
        }
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._log("Consulta estado TFHKA: ENQ (0x05) — respuesta 5 bytes STX, estado, error, ETX, LRC");
        try {
            const ok = await this.driver.readFpStatus();
            this._syncFpStatusFromDriver();
            const st = this.driver.status;
            const er = this.driver.error;
            const valid = this.driver.erroValid;
            const ds = this.driver.descripStatus || "";
            const de = this.driver.descripError || "";
            if (ok) {
                const line = `ENQ OK — estado=${st} (${ds}); error=${er} (${de}); LRC válido=${valid}`;
                this.state.lastCmdResult = line;
                if (this.driver.estado) {
                    this.state.estado = this.driver.estado;
                }
                this._log(line);
                this.notification.add("Estado leído (ENQ).", { type: "success" });
            } else {
                const detail =
                    this.driver.estado ||
                    `ENQ sin 5 bytes válidos (estado=${st}, error=${er}). Revise COM, paridad y cable.`;
                this.state.lastCmdResult = detail;
                this.state.estado = detail;
                this._log(`ERROR estado ENQ: ${detail}`);
                this.notification.add(detail, { type: "danger" });
            }
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`EXCEPCIÓN ENQ: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async onSendProbeSeven() {
        if (!this.canSendCommands) {
            if (this.state.phase !== PHASE.CONNECTED) {
                this.notification.add(
                    "Conecte primero con «Abrir conexión» y espere el estado «Puerto abierto».",
                    { type: "warning" }
                );
            }
            return;
        }
        this.state.busy = true;
        this.state.lastCmdResult = "";
        this._log("Prueba HKA: sendCmd «7» (comando mínimo del ejemplo de prueba del manual/driver)");
        try {
            const sent = await this.driver.sendCmd("7");
            if (sent) {
                this.state.lastCmdResult =
                    "Comando «7» respondió ACK. El enlace de comandos enmarcados funciona; si fallan las líneas i*, revise estado fiscal y secuencia del documento en el manual.";
                this._log("ACK en comando 7");
                this.notification.add("Comando 7: ACK OK.", { type: "success" });
            } else {
                const errDetail = `Prueba «7»: ${this.driver.estado || "sin ACK"}`;
                this.state.lastCmdResult = errDetail;
                this._log(`ERROR: ${errDetail}`);
                this.notification.add(errDetail, { type: "danger" });
            }
        } catch (e) {
            this.state.lastCmdResult = e.message || String(e);
            this._log(`EXCEPCIÓN: ${this.state.lastCmdResult}`);
            this.notification.add(this.state.lastCmdResult, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("actions").add("l10n_ve_fiscal_serial_fiscal_machines", FiscalMachinesAction);
