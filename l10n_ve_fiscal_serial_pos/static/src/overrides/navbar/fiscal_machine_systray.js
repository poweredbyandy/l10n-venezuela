/** @odoo-module **/

import { Component, onMounted, onWillStart, useEffect, useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { CONNECTION_STATUS } from "@l10n_ve_fiscal_serial/fiscal_connection/fiscal_connection_service";
import {
    l10nVeFiscalSerialPosGetFiscalMachineId,
    l10nVeFiscalSerialPosGetInvoiceJournal,
    l10nVeFiscalSerialPosIsFiscalMachine,
} from "../../fiscal_serial_pos_print";

export class PosFiscalMachineSystray extends Component {
    static template = "l10n_ve_fiscal_serial_pos.PosFiscalMachineSystray";
    static components = { Dropdown };
    static props = {};

    setup() {
        this.pos = usePos();
        this.connection = useService("l10n_ve_fiscal_connection");
        this.state = useState(this.connection.state);
        onWillStart(async () => {
            await this.connection.bootstrap();
            await this._syncMachineFromJournal();
        });
        onMounted(() => {
            void this.connection.refreshAuthorization();
        });
        useEffect(
            () => {
                void this._syncMachineFromJournal();
            },
            () => [
                this.pos.selectedOrderUuid,
                l10nVeFiscalSerialPosGetInvoiceJournal(this.pos)?.id || false,
                l10nVeFiscalSerialPosGetFiscalMachineId(this.pos) || false,
            ]
        );
    }

    async _syncMachineFromJournal() {
        if (!l10nVeFiscalSerialPosIsFiscalMachine(this.pos)) {
            return;
        }
        const machineId = l10nVeFiscalSerialPosGetFiscalMachineId(this.pos);
        if (machineId && this.connection.setPrimaryMachine) {
            await this.connection.setPrimaryMachine(machineId);
        }
    }

    get statusLabel() {
        switch (this.state.status) {
            case CONNECTION_STATUS.CONNECTING:
                return "Comprobando…";
            case CONNECTION_STATUS.CONNECTED:
                return this.state.portOpen ? "Conectada" : "Verificada";
            case CONNECTION_STATUS.ERROR:
                return this.state.portOpen ? "Sin respuesta" : "Sin conexión";
            case CONNECTION_STATUS.UNSUPPORTED:
                return "No compatible";
            case CONNECTION_STATUS.IDLE:
                return this.state.portAuthorized ? "Autorizada" : "Desconectada";
            default:
                return "";
        }
    }

    get portStatusLabel() {
        if (this.state.portOpen) {
            return "Abierto";
        }
        if (this.state.portAuthorized) {
            return "Cerrado (autorizado)";
        }
        return "Cerrado (sin autorizar)";
    }

    get statusClass() {
        switch (this.state.status) {
            case CONNECTION_STATUS.CONNECTING:
                return "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-warning";
            case CONNECTION_STATUS.CONNECTED:
                return "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-success";
            case CONNECTION_STATUS.ERROR:
                return this.state.portOpen
                    ? "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-warning"
                    : "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-danger";
            case CONNECTION_STATUS.UNSUPPORTED:
                return "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-danger";
            case CONNECTION_STATUS.IDLE:
                return this.state.portAuthorized
                    ? "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-warning"
                    : "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-muted";
            default:
                return "o_l10n_ve_fiscal_systray_dot o_l10n_ve_fiscal_systray_dot-muted";
        }
    }

    get lastCheckLabel() {
        if (!this.state.lastCheckAt) {
            return "Sin comprobación ENQ reciente";
        }
        return new Date(this.state.lastCheckAt).toLocaleString();
    }

    async onDropdownOpened() {
        await this.connection.loadSystrayData();
        await this._syncMachineFromJournal();
        if (this.state.visible && this.state.machine) {
            await this.connection.checkConnection();
        }
    }

    async onCheckConnection() {
        await this._syncMachineFromJournal();
        await this.connection.checkConnection();
    }

    async onConnect() {
        await this._syncMachineFromJournal();
        await this.connection.connect();
    }
}

Navbar.components = {
    ...Navbar.components,
    PosFiscalMachineSystray,
};

patch(Navbar.prototype, {
    get showFiscalMachineSystray() {
        void this.pos.selectedOrderUuid;
        const order = this.pos.get_order();
        void order?.invoice_journal_id?.id;
        void order?.invoice_journal_id?.l10n_ve_emission_medium;
        void order?.invoice_journal_id?.l10n_ve_fiscal_machine_id;
        return l10nVeFiscalSerialPosIsFiscalMachine(this.pos);
    },
});
