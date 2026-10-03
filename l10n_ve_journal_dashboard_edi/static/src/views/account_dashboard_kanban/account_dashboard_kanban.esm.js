import {EdiInvoiceDashboard} from "../../components/invoice_dashboard/invoice_dashboard.esm";
import {JournalDashboardKanbanRenderer} from "@l10n_ve_journal_dashboard/views/account_dashboard_kanban/account_dashboard_kanban.esm";
import {accountDashboardKanbanView} from "@account/views/account_dashboard_kanban/account_dashboard_kanban_view";
import {registry} from "@web/core/registry";

export class EdiDashboardKanbanRenderer extends JournalDashboardKanbanRenderer {
    static components = {
        ...JournalDashboardKanbanRenderer.components,
        EdiInvoiceDashboard,
    };
    static template = "l10n_ve_journal_dashboard_edi.DashboardKanbanRenderer";
}

registry.category("views").add(
    "account_dashboard_kanban",
    {
        ...accountDashboardKanbanView,
        Renderer: EdiDashboardKanbanRenderer,
    },
    {force: true}
);
