from . import models


def post_init_hook(env):
    env["l10n_ve.default.account"]._ensure_default_accounts_menu()
