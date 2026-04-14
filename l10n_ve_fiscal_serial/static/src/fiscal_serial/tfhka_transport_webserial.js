export function formatWebSerialError(err) {
    if (!err) {
        return "Error desconocido.";
    }
    const name = err.name || "";
    const msg = (err.message && String(err.message).trim()) || "";
    const base = msg || String(err);
    if (name === "AbortError") {
        return "Selección de puerto cancelada.";
    }
    if (name === "NotAllowedError") {
        return "Permiso denegado para acceder al puerto serie.";
    }
    if (name === "NotFoundError") {
        return `Dispositivo no encontrado: ${base}`;
    }
    if (name === "SecurityError") {
        return `Web Serial bloqueado: use HTTPS y un origen permitido. ${base}`;
    }
    if (name === "InvalidStateError") {
        return `Puerto en estado inválido (puede estar abierto en otra pestaña). ${base}`;
    }
    if (name === "NetworkError") {
        return `Error de comunicación en el puerto serie: ${base}`;
    }
    return base || name || "Error desconocido.";
}

function mergeUint8Arrays(chunks) {
    let n = 0;
    for (const c of chunks) {
        n += c.length;
    }
    const out = new Uint8Array(n);
    let o = 0;
    for (const c of chunks) {
        out.set(c, o);
        o += c.length;
    }
    return out;
}

export class TfhkaWebSerialTransport {
    constructor() {
        this.port = null;
    }

    static isSupported() {
        return typeof navigator !== "undefined" && "serial" in navigator;
    }

    async requestPort(filters = []) {
        if (!TfhkaWebSerialTransport.isSupported()) {
            throw new Error("Web Serial API no disponible en este navegador.");
        }
        return navigator.serial.requestPort({ filters });
    }

    async open(serialPort, options = {}) {
        if (this.port) {
            await this.close();
        }
        await serialPort.open({
            baudRate: options.baudRate ?? 9600,
            dataBits: options.dataBits ?? 8,
            stopBits: options.stopBits ?? 1,
            parity: options.parity ?? "even",
            bufferSize: options.bufferSize ?? 512,
            flowControl: options.flowControl ?? "none",
        });
        this.port = serialPort;
    }

    async close() {
        if (!this.port) {
            return;
        }
        try {
            await this.port.close();
        } catch {
        }
        this.port = null;
    }

    isOpen() {
        return !!(this.port && this.port.readable && this.port.writable);
    }

    async writeBytes(bytes, options = {}) {
        if (!this.isOpen()) {
            throw new Error("Puerto serie cerrado.");
        }
        const postMs = options.postWriteDelayMs ?? 35;
        const writer = this.port.writable.getWriter();
        try {
            await writer.write(bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes));
        } finally {
            writer.releaseLock();
        }
        await new Promise((r) => setTimeout(r, postMs));
    }

    async drainInput(maxTotalMs = 200) {
        if (!this.isOpen()) {
            return;
        }
        const deadline = Date.now() + maxTotalMs;
        while (Date.now() < deadline) {
            const chunk = await this.readSome({
                byteTimeout: 12,
                totalTimeout: 45,
                maxLen: 512,
            });
            if (chunk.length === 0) {
                break;
            }
        }
    }

    async readSome(options = {}) {
        if (!this.isOpen()) {
            return new Uint8Array(0);
        }
        const byteTimeout = options.byteTimeout ?? 20;
        const totalTimeout = options.totalTimeout ?? 1000;
        const maxLen = options.maxLen ?? 512;
        const reader = this.port.readable.getReader();
        const chunks = [];
        let total = 0;
        const start = Date.now();
        let lastData = Date.now();
        try {
            while (Date.now() - start < totalTimeout && total < maxLen) {
                const wait = Math.min(
                    byteTimeout,
                    Math.max(1, start + totalTimeout - Date.now())
                );
                const result = await Promise.race([
                    reader.read(),
                    new Promise((resolve) =>
                        setTimeout(() => resolve({ timeout: true }), wait)
                    ),
                ]);
                if (result && result.timeout) {
                    if (total > 0 && Date.now() - lastData >= byteTimeout) {
                        break;
                    }
                    continue;
                }
                const { value, done } = result;
                if (done) {
                    break;
                }
                if (value && value.length) {
                    chunks.push(value);
                    total += value.length;
                    lastData = Date.now();
                } else if (total > 0 && Date.now() - lastData >= byteTimeout) {
                    break;
                }
            }
        } finally {
            reader.releaseLock();
        }
        return mergeUint8Arrays(chunks);
    }

    async readOneByte(timeoutMs) {
        if (!this.isOpen()) {
            return null;
        }
        const reader = this.port.readable.getReader();
        try {
            const readPromise = reader.read();
            const result = await Promise.race([
                readPromise,
                new Promise((resolve) =>
                    setTimeout(() => resolve({ timeout: true }), timeoutMs)
                ),
            ]);
            if (result && result.timeout) {
                try {
                    await reader.cancel();
                } catch {
                }
                try {
                    await readPromise;
                } catch {
                }
                return null;
            }
            const { value } = result;
            if (value && value.length) {
                return value[0];
            }
            return null;
        } finally {
            reader.releaseLock();
        }
    }

    async setSignals(signals) {
        if (this.port && typeof this.port.setSignals === "function") {
            await this.port.setSignals(signals);
        }
    }
}
