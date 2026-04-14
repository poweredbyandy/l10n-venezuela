# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import controllers
from . import models
from . import wizard


def post_init_hook(env):
    env["ir.actions.server"]._l10n_ve_unbind_all_account_move_bindings()
