from odoo import api, fields, models

# Canonical mapping from the deprecated ``type.person`` catalog to the new
# axes: (l10n_ve_person_type, l10n_ve_islr_category). Used by the concept
# line seeding, the 18.0.1.8.0 migrations and the legacy matcher fallback.
# See l10n_ve_withholding/readme/DEPRECATED.md and docs/adr/0001.
TYPE_PERSON_MAP = {
    "l10n_ve_withholding.type_person_l10n_ve_withholding": (
        "pn_resident",
        "standard",
    ),
    "l10n_ve_withholding.type_person_two_l10n_ve_withholding": (
        "pn_non_resident",
        "standard",
    ),
    "l10n_ve_withholding.type_person_three_l10n_ve_withholding": (
        "pj_domiciled",
        "standard",
    ),
    "l10n_ve_withholding.type_person_four_l10n_ve_withholding": (
        "pj_non_domiciled",
        "standard",
    ),
    "l10n_ve_withholding.type_person_five_l10n_ve_withholding": (
        "pj_non_domiciled",
        "financial_institution",
    ),
    "l10n_ve_withholding.type_person_six_l10n_ve_withholding": (
        "pj_non_domiciled",
        "other",
    ),
    "l10n_ve_withholding.type_person_seven_l10n_ve_withholding": (
        "pj_domiciled",
        "radio_broadcaster",
    ),
}


class TypePerson(models.Model):
    _name = "type.person"
    _description = "Type Person"
    _order = "sequence, id"
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Description", required=True, store=True)
    state = fields.Boolean(default=True, string="Active?", store=True)

    @api.model
    def _l10n_ve_table_exists(self):
        self.env.cr.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = %s)",
            [self._table],
        )
        return bool(self.env.cr.fetchone()[0])

    @api.model
    def _get_default_type_person_id(self):
        if not self._l10n_ve_table_exists():
            return False
        type_person = self.search([("state", "=", True)], order="sequence, id", limit=1)
        return type_person.id
