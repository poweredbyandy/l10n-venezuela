import {InvoiceDashboard} from "@l10n_ve_journal_dashboard/components/invoice_dashboard/invoice_dashboard.esm";
import {UnsentDashboard} from "../unsent_dashboard/unsent_dashboard.esm";

export class EdiInvoiceDashboard extends InvoiceDashboard {
    static components = {
        ...InvoiceDashboard.components,
        UnsentDashboard,
    };
}
