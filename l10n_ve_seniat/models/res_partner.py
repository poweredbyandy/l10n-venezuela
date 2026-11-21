import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

_logger = logging.getLogger(__name__)

VE_CODE = "VE"
VE_VAT_FIRST_LETTERS = frozenset("VEJCPG")

# RIF "kind" prefixes recognized by the SENIAT: letter + 6 to 10 digits.
L10N_VE_RIF_KIND_RE = re.compile(r"^([VEJCPG])([0-9]{6,10})$", re.IGNORECASE)

L10N_VE_PERSON_NATURE_SELECTION = [
    ("natural", "Persona Natural"),
    ("legal", "Persona Jurídica"),
]

L10N_VE_PERSON_TYPE_SELECTION = [
    ("pn_resident", "PN Residente"),
    ("pn_non_resident", "PN No Residente"),
    ("pj_domiciled", "PJ Domiciliada"),
    ("pj_non_domiciled", "PJ No Domiciliada"),
]

L10N_VE_TAX_RESIDENCE_SELECTION = [
    ("resident", "Residente / Domiciliado"),
    ("non_resident", "No residente / No domiciliado"),
]


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _l10n_ve_fiscal_locks_apply(self):
        country = self.env.company.account_fiscal_country_id
        return bool(country and country.code == VE_CODE)

    def _l10n_ve_override_locked_partner_fields(self):
        return self.env.user.has_group(
            "l10n_ve_seniat.group_l10n_ve_override_locked_master_data"
        )

    def _l10n_ve_lock_partner_fiscal_data_enabled(self):
        return self.env.company.l10n_ve_lock_partner_fiscal_data

    def _l10n_ve_has_posted_accounting_activity(self):
        self.ensure_one()
        commercial = self.commercial_partner_id
        return bool(
            self.env["account.move.line"]
            .sudo()
            .search(
                [
                    ("partner_id", "child_of", commercial.id),
                    ("parent_state", "=", "posted"),
                ],
                limit=1,
            )
        )

    def _l10n_ve_check_fiscal_lock_on_write(self, partners, vals):
        if (
            self._l10n_ve_fiscal_locks_apply()
            and self._l10n_ve_lock_partner_fiscal_data_enabled()
            and not self._l10n_ve_override_locked_partner_fields()
            and {"name", "vat"} & vals.keys()
        ):
            for partner in partners:
                if partner._l10n_ve_has_posted_accounting_activity():
                    raise UserError(
                        _(
                            "Cannot change the name or VAT of contact “%(name)s” "
                            "because it already has posted accounting entries, "
                            "invoices or related records. Ask a settings administrator "
                            "to apply the change."
                        )
                        % {"name": partner.display_name}
                    )

    def _l10n_ve_effective_country_for_write(self, vals):
        self.ensure_one()
        if "country_id" in vals:
            cid = vals["country_id"]
            if not cid:
                return self.env["res.country"]
            return self.env["res.country"].browse(cid)
        return self.country_id

    def _l10n_ve_taxpayer_country(self):
        self.ensure_one()
        if self.country_id:
            return self.country_id
        if not self.is_company:
            return self.env["res.country"]
        company = (
            self.env["res.company"]
            .sudo()
            .search([("partner_id", "=", self.id)], limit=1)
        )
        if not company:
            return self.env["res.country"]
        return company.country_id or company.account_fiscal_country_id

    @api.model
    def _l10n_ve_normalize_vat_leading_prefix(self, vat):
        if vat in (False, None):
            return vat
        if not isinstance(vat, str):
            vat = str(vat)
        stripped = vat.strip()
        if not stripped or stripped == "/":
            return vat
        if stripped[0].upper() in VE_VAT_FIRST_LETTERS:
            return stripped
        return f"V{stripped}"

    def _l10n_ve_write_vat_prefix_batches(self, vals):
        if self.env.context.get("skip_l10n_ve_vat_auto_prefix"):
            return None
        if "country_id" in vals and "vat" not in vals:
            nc = (
                self.env["res.country"].browse(vals["country_id"])
                if vals["country_id"]
                else self.env["res.country"]
            )
            if nc.code == VE_CODE:
                by_vat = {}
                for p in self:
                    if not p.vat:
                        continue
                    nv = self._l10n_ve_normalize_vat_leading_prefix(p.vat)
                    if nv != p.vat:
                        by_vat.setdefault(nv, self.browse())
                        by_vat[nv] |= p
                if not by_vat:
                    return None
                batches = []
                done = self.browse()
                for nv, recs in by_vat.items():
                    batches.append((recs, {**vals, "vat": nv}))
                    done |= recs
                rest = self - done
                if rest:
                    batches.append((rest, dict(vals)))
                return batches

        if "vat" not in vals or vals.get("vat") in (False, None):
            return None

        ve = self.filtered(
            lambda p: p._l10n_ve_effective_country_for_write(vals).code == VE_CODE
        )
        nve = self - ve
        if not ve:
            return None

        nv = self._l10n_ve_normalize_vat_leading_prefix(vals["vat"])
        if nve:
            return [
                (ve, {**vals, "vat": nv}),
                (nve, dict(vals)),
            ]
        vals["vat"] = nv
        return None

    def write(self, vals):
        vals = dict(vals)
        if "country_id" in vals:
            country = (
                self.env["res.country"].browse(vals["country_id"])
                if vals.get("country_id")
                else self.env["res.country"]
            )
            if not country or country.code != VE_CODE:
                vals["taxpayer_type"] = False
        batches = self._l10n_ve_write_vat_prefix_batches(vals)
        if batches is None:
            batches = [(self, vals)]
        final_batches = []
        for recs, batch_vals in batches:
            final_batches.extend(self._l10n_ve_tax_residence_batches(recs, batch_vals))
        if len(final_batches) == 1:
            recs, batch_vals = final_batches[0]
            self._l10n_ve_check_fiscal_lock_on_write(recs, batch_vals)
            return super(ResPartner, recs).write(batch_vals)

        res = True
        for recs, batch_vals in final_batches:
            self._l10n_ve_check_fiscal_lock_on_write(recs, batch_vals)
            res &= super(ResPartner, recs).write(batch_vals)
        return res

    def _l10n_ve_tax_residence_batches(self, recs, vals):
        """Split a write batch by the tax residence derived from RIF/country.

        The user's manual choice is respected: the residence is only
        recalculated when `vat`/`country_id` change without an explicit
        `l10n_ve_tax_residence` in vals (the web client sends it together
        when the user touched it on the form).
        """
        if (
            self.env.context.get("skip_l10n_ve_tax_residence_auto")
            or "l10n_ve_tax_residence" in vals
            or ("vat" not in vals and "country_id" not in vals)
            or not recs
        ):
            return [(recs, vals)]

        # RIF kinds E/P drive the residence uniformly for the whole batch.
        uniform = False
        if "vat" in vals:
            kind = self._l10n_ve_rif_kind_from_vat(vals.get("vat"))
            if kind == "E":
                uniform = "resident"
            elif kind == "P":
                uniform = "non_resident"

        groups = {}
        unchanged = self.browse()
        for partner in recs:
            if uniform:
                derived = uniform
            else:
                vat = vals["vat"] if "vat" in vals else partner.vat
                if "country_id" in vals:
                    country = (
                        self.env["res.country"].browse(vals["country_id"])
                        if vals.get("country_id")
                        else self.env["res.country"].browse()
                    )
                else:
                    country = partner.country_id
                derived = self._l10n_ve_derive_tax_residence_from(vat, country)
            if partner.l10n_ve_tax_residence == derived:
                unchanged |= partner
                continue
            groups.setdefault(derived, self.browse())
            groups[derived] |= partner
        out = [(unchanged, dict(vals))] if unchanged else []
        for derived, group in groups.items():
            out.append((group, {**vals, "l10n_ve_tax_residence": derived}))
        return out

    def _prepare_create_values(self, vals_list):
        vals_list = super()._prepare_create_values(vals_list)
        skip_prefix = self.env.context.get("skip_l10n_ve_vat_auto_prefix")
        for vals in vals_list:
            country = self._l10n_ve_country_from_vals(vals)
            if country.code != VE_CODE:
                vals["taxpayer_type"] = False
            if skip_prefix:
                continue
            if country.code != VE_CODE or vals.get("vat") in (False, None):
                continue
            vals["vat"] = self._l10n_ve_normalize_vat_leading_prefix(vals["vat"])
        if self.env.context.get("skip_l10n_ve_tax_residence_auto"):
            return vals_list
        for vals in vals_list:
            if "l10n_ve_tax_residence" in vals:
                continue
            country = self._l10n_ve_country_from_vals(vals)
            vals["l10n_ve_tax_residence"] = self._l10n_ve_derive_tax_residence_from(
                vals.get("vat"), country
            )
        return vals_list

    def _l10n_ve_country_from_vals(self, vals):
        cid = vals.get("country_id")
        if cid:
            return self.env["res.country"].browse(cid)
        return self.env["res.country"]

    def _default_res_country(self):
        return self.env.company.country_id.id or False

    def _default_vat(self):
        return False

    @api.depends(
        "complete_name",
        "email",
        "vat",
        "state_id",
        "country_id",
        "commercial_company_name",
    )
    @api.depends_context(
        "show_address",
        "partner_show_db_id",
        "address_inline",
        "show_email",
        "show_vat",
        "lang",
        "l10n_ve_display_name_vat_first",
    )
    def _compute_display_name(self):
        if (
            not self.env.context.get("l10n_ve_display_name_vat_first")
            or not self._l10n_ve_fiscal_locks_apply()
        ):
            return super()._compute_display_name()
        for partner in self:
            name = partner.with_context(lang=self.env.lang)._get_complete_name()
            if partner._context.get("show_address"):
                name = name + "\n" + partner._display_address(without_company=True)
            name = re.sub(r"\s+\n", "\n", name)
            if partner._context.get("partner_show_db_id"):
                name = f"{name} ({partner.id})"
            if partner._context.get("address_inline"):
                splitted_names = name.split("\n")
                name = ", ".join([n for n in splitted_names if n.strip()])
            if partner._context.get("show_email") and partner.email:
                name = f"{name} <{partner.email}>"
            vat = (partner.vat or "").strip()
            if vat and vat != "/":
                partner.display_name = f"{vat} - {name.strip()}"
            else:
                partner.display_name = name.strip()

    taxpayer_type = fields.Selection(
        [
            ("ordinary", "Ordinary"),
            ("formal", "Formal"),
            ("special", "Special"),
        ],
    )

    # ``l10n_ve_person_nature`` (natural/legal) is derived from the RIF and is
    # deliberately NOT editable: when the RIF lies, the RIF must be fixed.
    # ``l10n_ve_tax_residence`` is the single user choice the RIF cannot
    # answer (resident vs domiciled is a label switch on the same axis).
    # ``l10n_ve_person_type`` is the read-only combination of both, and the
    # ISLR exceptions live apart in ``l10n_ve_islr_category``
    # (l10n_ve_withholding). See docs/adr/0001 and
    # l10n_ve_withholding/readme/DEPRECATED.md for the legacy mapping.
    l10n_ve_person_nature = fields.Selection(
        L10N_VE_PERSON_NATURE_SELECTION,
        string="Person Nature",
        compute="_compute_l10n_ve_person_nature",
        store=True,
        precompute=True,
        tracking=False,
    )
    l10n_ve_tax_residence = fields.Selection(
        L10N_VE_TAX_RESIDENCE_SELECTION,
        string="Tax Residence",
        tracking=False,
        help=(
            "Residencia (personas naturales) o domicilio (personas "
            "jurídicas) del contacto frente a impuestos venezolanos."
        ),
    )
    l10n_ve_person_type = fields.Selection(
        L10N_VE_PERSON_TYPE_SELECTION,
        string="Person Type",
        compute="_compute_l10n_ve_person_type",
        store=True,
        precompute=True,
        tracking=False,
    )
    l10n_ve_tax_residence_name = fields.Char(
        string="Residence",
        compute="_compute_l10n_ve_tax_residence_name",
    )

    @api.model
    def _l10n_ve_rif_kind_from_vat(self, vat):
        """Return the RIF kind letter (V/E/J/C/P/G) of a VAT-like string.

        Only a full letter+digits match counts as a RIF kind, so foreign
        identifiers ("GB123456789") never fake a kind.
        """
        cleaned = re.sub(r"[^A-Za-z0-9]", "", vat or "").upper()
        if not cleaned:
            return False
        match = L10N_VE_RIF_KIND_RE.match(cleaned)
        return match.group(1).upper() if match else False

    def _l10n_ve_derive_person_nature(self):
        self.ensure_one()
        kind = self._l10n_ve_rif_kind_from_vat(self.vat)
        if kind in ("V", "E", "P"):
            return "natural"
        if kind in ("J", "G", "C"):
            return "legal"
        return "legal" if self.is_company else "natural"

    def _l10n_ve_fallback_country(self):
        country = self.env.company.country_id
        return country if country and country.code == VE_CODE else self.env[
            "res.country"
        ]

    def _l10n_ve_derive_tax_residence_from(self, vat, country):
        """Derive the default tax residence from a VAT and a country.

        Art. 2 Ley ISLR / Providencia administrativa: residentes y
        domiciliados tributan de forma distinta a no residentes y no
        domiciliados. El pasaporte (P) no implica residencia, pero se toma
        como default "no residente" editable; el extranjero con cédula (E)
        se trata como residente.
        """
        kind = self._l10n_ve_rif_kind_from_vat(vat)
        if kind == "E":
            return "resident"
        if kind == "P":
            return "non_resident"
        effective_country = country or self._l10n_ve_fallback_country()
        if effective_country and effective_country.code == VE_CODE:
            return "resident"
        return "non_resident"

    def _l10n_ve_derive_tax_residence(self):
        self.ensure_one()
        return self._l10n_ve_derive_tax_residence_from(
            self.vat, self.country_id or self._l10n_ve_fallback_country()
        )

    @api.depends("vat", "is_company")
    def _compute_l10n_ve_person_nature(self):
        for partner in self:
            partner.l10n_ve_person_nature = partner._l10n_ve_derive_person_nature()

    @api.depends("l10n_ve_person_nature", "l10n_ve_tax_residence")
    def _compute_l10n_ve_person_type(self):
        for partner in self:
            # A missing stored residence (e.g. mid-upgrade rows) falls back
            # to the derived default so the type is never garbage.
            residence = (
                partner.l10n_ve_tax_residence
                or partner._l10n_ve_derive_tax_residence()
            )
            if partner.l10n_ve_person_nature == "legal":
                partner.l10n_ve_person_type = (
                    "pj_domiciled"
                    if residence == "resident"
                    else "pj_non_domiciled"
                )
            else:
                partner.l10n_ve_person_type = (
                    "pn_resident"
                    if residence == "resident"
                    else "pn_non_resident"
                )

    @api.depends("l10n_ve_person_nature", "l10n_ve_tax_residence")
    def _compute_l10n_ve_tax_residence_name(self):
        for partner in self:
            residence = partner.l10n_ve_tax_residence
            if not residence:
                partner.l10n_ve_tax_residence_name = False
            elif partner.l10n_ve_person_nature == "legal":
                partner.l10n_ve_tax_residence_name = (
                    _("Domiciliada")
                    if residence == "resident"
                    else _("No Domiciliada")
                )
            else:
                partner.l10n_ve_tax_residence_name = (
                    _("Residente") if residence == "resident" else _("No Residente")
                )

    def action_l10n_ve_recompute_tax_residence(self):
        """Reset the manual residence choice back to the RIF/country default."""
        for partner in self:
            partner.l10n_ve_tax_residence = partner._l10n_ve_derive_tax_residence()
        return True

    # TODO: prefix_vat isn't used anywhere
    prefix_vat = fields.Char(string="Prefix vat", compute="_compute_vat_prefix")
    country_id = fields.Many2one("res.country", default=_default_res_country)
    vat = fields.Char(default=_default_vat)

    @api.depends("vat")
    def _compute_vat_prefix(self):
        for record in self:
            if record.vat:
                match = re.match(r"([VEJPG])([0-9]+)", record.vat, re.IGNORECASE)
                if match:
                    record.prefix_vat = match.group(1).upper()
                    continue
            record.prefix_vat = False

    @api.onchange("country_id")
    def _onchange_country_id_clear_taxpayer_type(self):
        if self.country_id and self.country_id.code != VE_CODE:
            self.taxpayer_type = False

    @api.onchange("vat", "country_id")
    def _onchange_l10n_ve_vat_auto_prefix(self):
        if not self.country_id or self.country_id.code != VE_CODE:
            return
        if not self.vat:
            return
        nv = self._l10n_ve_normalize_vat_leading_prefix(self.vat)
        if nv != self.vat:
            self.vat = nv

    @api.onchange("vat", "country_id")
    def _onchange_l10n_ve_tax_residence(self):
        """Recalculate the residence suggestion when RIF/country change.

        The user can still pick the other option right after: the choice is
        kept on save and only revisited on the next vat/country change.
        """
        self.l10n_ve_tax_residence = self._l10n_ve_derive_tax_residence_from(
            self.vat, self.country_id
        )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if not self._l10n_ve_fiscal_locks_apply():
            return values
        name_val = values.get("name")
        if not name_val or not isinstance(name_val, str):
            return values
        term = name_val.strip()
        if not term or not self._l10n_ve_create_search_term_is_rif_like(term):
            return values
        if "vat" in fields_list:
            values["vat"] = term
        if "name" in fields_list:
            values["name"] = False
        return values

    @api.model
    def _l10n_ve_vat_search_variants(self, value):
        if not value:
            return []
        variants = {value}
        compact = re.sub(r"[\s\-_.]", "", value)
        if compact:
            variants.add(compact)
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 5:
            variants.add(digits)
        return list(variants)

    @api.model
    def _l10n_ve_create_search_term_is_rif_like(self, term):
        if not term:
            return False
        if self.check_vat_ve(term):
            return True
        if re.match(r"^[VEJPGCvecjpg]", term, re.I):
            if len(term) > 1 and term[1].isalpha():
                return False
            if re.search(r"\d", term):
                return True
        if (
            re.fullmatch(r"[\d.\-\sVEJPGCvecjpg]+", term, re.I)
            and len(re.sub(r"\D", "", term)) >= 6
        ):
            return True
        return False

    @api.model
    def _l10n_ve_name_search_should_query_vat_first(self, term):
        if not term or not self._l10n_ve_fiscal_locks_apply():
            return False
        t = term.strip()
        if self._l10n_ve_create_search_term_is_rif_like(t):
            return True
        digits = re.sub(r"\D", "", t)
        return len(digits) >= 5

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if not self._l10n_ve_fiscal_locks_apply():
            return domain
        if not value or not str(value).strip():
            return domain
        if operator in expression.NEGATIVE_TERM_OPERATORS:
            return domain
        variant_domains = [
            [("vat", "ilike", v)]
            for v in self._l10n_ve_vat_search_variants(str(value).strip())
        ]
        return expression.OR([domain, *variant_domains])

    @api.model
    @api.readonly
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = list(args or [])
        search_mode = self.env.context.get("res_partner_search_mode")
        if not self._l10n_ve_fiscal_locks_apply():
            if search_mode == "customer":
                args = [("customer_rank", ">=", 1)] + args
            elif search_mode == "supplier":
                args = [("supplier_rank", ">=", 1)] + args

        name_stripped = (name or "").strip()
        if not limit:
            limit = 100

        if not name_stripped or not self._l10n_ve_name_search_should_query_vat_first(
            name_stripped
        ):
            return super().name_search(name, args=args, operator=operator, limit=limit)

        vat_terms = self._l10n_ve_vat_search_variants(name_stripped)
        vat_domain = expression.OR([[("vat", "ilike", v)] for v in vat_terms])
        domain = expression.AND([vat_domain, args]) if args else vat_domain
        vat_ids = self.search(domain, limit=limit).ids

        standard = super().name_search(name, args=args, operator=operator, limit=limit)

        if not vat_ids:
            return standard

        seen = set()
        out = []
        for partner in self.browse(vat_ids):
            out.append((partner.id, partner.sudo().display_name))
            seen.add(partner.id)
            if len(out) >= limit:
                return out
        for pair in standard:
            if pair[0] not in seen:
                out.append(pair)
                seen.add(pair[0])
                if len(out) >= limit:
                    break
        return out

    @api.constrains("country_id", "taxpayer_type")
    def _check_taxpayer_type_country(self):
        if self.env.context.get("skip_l10n_ve_taxpayer_type_country"):
            return
        for rec in self:
            if not rec.taxpayer_type:
                continue
            country = rec._l10n_ve_taxpayer_country()
            if not country or country.code != VE_CODE:
                raise ValidationError(
                    _(
                        "The taxpayer type can only be set for Venezuelan partners "
                        "(country code 'VE')."
                    )
                )
