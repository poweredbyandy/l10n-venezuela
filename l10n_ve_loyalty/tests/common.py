# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


class L10nVeLoyaltyCommon(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id = [
            Command.link(
                cls.env.ref("l10n_ve_loyalty.group_l10n_ve_global_discount").id
            )
        ]
        sale_price_group = cls.env.ref(
            "pba_sale_price_group.group_pba_edit_sale_price",
            raise_if_not_found=False,
        )
        if sale_price_group:
            cls.env.user.write({"groups_id": [(4, sale_price_group.id)]})
