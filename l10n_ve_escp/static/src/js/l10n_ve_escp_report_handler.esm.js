import {registry} from "@web/core/registry";

async function escpReportHandler(action, options, env) {
    if (action.report_type !== "escp") {
        return false;
    }
    const context = action.context || {};
    const activeIds = context.active_ids || (context.active_id ? [context.active_id] : []);
    await env.services.action.doAction(
        {
            type: "ir.actions.act_window",
            name: action.name,
            res_model: "l10n.ve.escp.preview",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_report_id: action.l10n_ve_escp_report_id || false,
                default_report_action_name: action.report_name,
                default_res_model: context.active_model,
                default_res_ids: JSON.stringify(activeIds),
                active_ids: activeIds,
                dialog_size: "extra-large",
            },
        },
        {onClose: options.onClose}
    );
    return true;
}

registry.category("ir.actions.report handlers").add("l10n_ve_escp", escpReportHandler);
