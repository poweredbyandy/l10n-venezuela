import { registry } from "@web/core/registry";
import {
    createTfhkaFiscal,
    encodeLatin1,
    PrinterStatus,
    SVPrinterData,
    TfhkaFiscal,
} from "./tfhka_serial";
import {
    formatWebSerialError,
    TfhkaWebSerialTransport,
} from "./tfhka_transport_webserial";
import { getSampleHkaInvoiceLines } from "./tfhka_invoice_samples";

export const l10nVeFiscalSerialService = {
    dependencies: [],
    start() {
        return {
            createTfhkaFiscal,
            TfhkaFiscal,
            PrinterStatus,
            SVPrinterData,
            TfhkaWebSerialTransport,
            encodeLatin1,
            formatWebSerialError,
            getSampleHkaInvoiceLines,
            isSupported: () => TfhkaWebSerialTransport.isSupported(),
        };
    },
};

registry.category("services").add("l10n_ve_fiscal_serial", l10nVeFiscalSerialService);
registry.category("l10n_ve_fiscal_serial").add("TfhkaFiscal", TfhkaFiscal);
