export const STX = 0x02;
export const ETX = 0x03;
export const ENQ = 0x05;
export const ACK = 0x06;
export const NAK = 0x15;

export function encodeLatin1(str) {
    const out = [];
    for (const ch of str) {
        const cp = ch.codePointAt(0);
        if (cp < 256) {
            out.push(cp);
        } else {
            out.push(0x3f);
        }
    }
    return new Uint8Array(out);
}

export function encodeLatin15ish(str) {
    return encodeLatin1(str);
}

export function decodeLatin15ish(bytes) {
    let s = "";
    for (let i = 0; i < bytes.length; i++) {
        s += String.fromCharCode(bytes[i]);
    }
    return s;
}

export function doXorCommand(sCMD) {
    const body = encodeLatin1(sCMD);
    let x = 0;
    for (let i = 0; i < body.length; i++) {
        x ^= body[i];
    }
    x ^= ETX;
    return String.fromCharCode(x & 0xff);
}

export function buildSendCmdFrame(sCMD) {
    const body = encodeLatin1(sCMD);
    let x = 0;
    for (let i = 0; i < body.length; i++) {
        x ^= body[i];
    }
    x ^= ETX;
    const xorByte = x & 0xff;
    const frame = new Uint8Array(1 + body.length + 1 + 1);
    frame[0] = STX;
    frame.set(body, 1);
    frame[1 + body.length] = ETX;
    frame[1 + body.length + 1] = xorByte;
    return frame;
}

export function buildQueryBytes(chars) {
    if (typeof chars === "string") {
        return encodeLatin15ish(chars);
    }
    const out = new Uint8Array(chars.length);
    for (let i = 0; i < chars.length; i++) {
        out[i] = typeof chars[i] === "string" ? chars[i].charCodeAt(0) : chars[i];
    }
    return out;
}
