/** @odoo-module */

import {Component, onWillStart, useState} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {useService} from "@web/core/utils/hooks";

export class SeniatInvoiceDashboard extends Component {
    static template = "l10n_ve_seniat.SeniatInvoiceDashboard";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            visible: false,
            monthLabel: "",
            items: [],
            dispatchEmail: {
                available: false,
                canSend: false,
                lastSentLabel: false,
            },
            sendingDispatchEmail: false,
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        const data = await this.orm.call(
            "account.journal",
            "get_l10n_ve_invoice_dashboard",
            []
        );
        this.state.visible = data.visible;
        this.state.monthLabel = data.month_label || "";
        this.state.items = data.items || [];
        this.state.dispatchEmail = {
            available: data.dispatch_email?.available || false,
            canSend: data.dispatch_email?.can_send || false,
            lastSentLabel: data.dispatch_email?.last_sent_label || false,
        };
    }

    async openItem(itemKey) {
        const action = await this.orm.call(
            "account.journal",
            "action_l10n_ve_invoice_dashboard_open",
            [itemKey]
        );
        return this.actionService.doAction(action);
    }

    async sendDispatchEmail(ev) {
        ev.stopPropagation();
        if (this.state.sendingDispatchEmail) {
            return;
        }
        this.state.sendingDispatchEmail = true;
        try {
            const result = await this.orm.call(
                "account.journal",
                "action_l10n_ve_send_unfactured_dispatch_guides_email",
                []
            );
            this.state.dispatchEmail.lastSentLabel = result.last_sent_label || false;
            this.state.dispatchEmail.canSend = result.can_send;
            this.notification.add(result.message || _t("Correo enviado."), {
                type: "success",
            });
        } catch (error) {
            this.notification.add(error.message || _t("No se pudo enviar el correo."), {
                type: "danger",
            });
        } finally {
            this.state.sendingDispatchEmail = false;
        }
    }
}
