import {DashboardKanbanRenderer} from "@account/views/account_dashboard_kanban/account_dashboard_kanban_renderer";
import {InvoiceDashboard} from "../../components/invoice_dashboard/invoice_dashboard.esm";
import {accountDashboardKanbanView} from "@account/views/account_dashboard_kanban/account_dashboard_kanban_view";
import {registry} from "@web/core/registry";

export class JournalDashboardKanbanRenderer extends DashboardKanbanRenderer {
    static components = {
        ...DashboardKanbanRenderer.components,
        InvoiceDashboard,
    };
    static template = "l10n_ve_journal_dashboard.DashboardKanbanRenderer";
}

registry.category("views").add(
    "account_dashboard_kanban",
    {
        ...accountDashboardKanbanView,
        Renderer: JournalDashboardKanbanRenderer,
    },
    {force: true}
);
