import logging
import re
import unicodedata

_logger = logging.getLogger(__name__)


def _fold_lower(s):
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFD", s)
    stripped = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return stripped.lower()


def _normalize_label(cell_text):
    t = re.sub(r"\s+", " ", (cell_text or "").strip())
    t = t.rstrip(":").strip()
    return _fold_lower(t)


def extract_table_key_values(tree):
    pairs = {}
    for tr in tree.xpath("//table//tr"):
        tds = tr.xpath("./td")
        if len(tds) < 2:
            continue
        parts_k = " ".join(tds[0].xpath(".//text()"))
        parts_v = " ".join(tds[1].xpath(".//text()"))
        key = _normalize_label(parts_k)
        val = re.sub(r"\s+", " ", parts_v).strip()
        if key and val:
            pairs[key] = val
    return pairs


def enrich_from_key_values(parsed, kv):
    if not kv:
        return parsed
    for label, value in kv.items():
        if "tipo" in label and "contribuyente" in label and "condicion" not in label:
            parsed["seniat_tipo_contribuyente_label"] = value
        elif "tipo" in label and "persona" in label:
            parsed["seniat_tipo_persona_label"] = value
        elif "%" in label and "retencion" in label.replace("ó", "o"):
            parsed["seniat_retencion_pct_label"] = value
        elif "retencion" in label.replace("ó", "o") and "%" in value:
            parsed["seniat_retencion_pct_label"] = value
    parsed["seniat_table_kv"] = kv
    return parsed


def rif_from_seniat_text(*chunks):
    blob = " ".join(c for c in chunks if c)
    m = re.search(r"\b([JGPVE]\d{9})\b", blob, re.I)
    if m:
        return m.group(1).upper()
    m = re.search(r"\b([JGPVE]\s*\d{9})\b", re.sub(r"\s+", "", blob), re.I)
    if m:
        return re.sub(r"\s+", "", m.group(1)).upper()
    return ""


def extract_retention_percent_from_text(*texts):
    blob = " ".join(t for t in texts if t)
    if not blob:
        return None
    for pat in (
        r"retenci[oó]n\s+del\s+(\d+)\s*%",
        r"del\s+(\d+)\s*%\s*del\s+impuesto",
        r"(\d+)\s*%\s*del\s+impuesto\s+causado",
        r"(\d+)\s*%\s*del\s+impuesto",
    ):
        m = re.search(pat, blob, re.I)
        if m:
            val = int(m.group(1))
            if val in (75, 100):
                return val
    for m in re.finditer(r"\b(\d{2,3})\s*%", blob):
        val = int(m.group(1))
        if val in (75, 100):
            return val
    return None


def map_taxpayer_type_selection(text):
    if not text:
        return False
    t = _fold_lower(text)
    if "contribuyente especial" in t or "especial del iva" in t:
        return "special"
    if "formal" in t:
        return "formal"
    if "ordinario" in t:
        return "ordinary"
    return False


def withholding_type_from_percent(env, pct):
    if pct not in (75, 100):
        return False
    Type = env["account.withholding.type"].sudo()
    row = Type.search(
        [("state", "=", True), ("value", "=", float(pct))],
        limit=1,
    )
    return row


# Rules mapping the portal's "tipo de persona" text to the new axes:
# tax residence (shared axis: residente/domiciliada) and the ISLR category
# for the exceptions that are not derivable from RIF/country. The old
# type_person_id mapping was removed with the column deprecation
# (l10n_ve_withholding/readme/DEPRECATED.md).
PERSON_TYPE_TEXT_RULES = (
    (("instituciones financieras",), {"l10n_ve_islr_category": "financial_institution", "l10n_ve_tax_residence": "non_resident"}),
    (("emisora de radio", "domicili"), {"l10n_ve_islr_category": "radio_broadcaster", "l10n_ve_tax_residence": "resident"}),
    (("radio", "domicili"), {"l10n_ve_islr_category": "radio_broadcaster", "l10n_ve_tax_residence": "resident"}),
    (("otras personas juridicas",), {"l10n_ve_islr_category": "other", "l10n_ve_tax_residence": "non_resident"}),
    (("no residente",), {"l10n_ve_tax_residence": "non_resident"}),
    (("no domicili",), {"l10n_ve_tax_residence": "non_resident"}),
    (("residente",), {"l10n_ve_tax_residence": "resident"}),
    (("domicili",), {"l10n_ve_tax_residence": "resident"}),
)


def person_type_vals_from_seniat_text(seniat_text):
    if not seniat_text:
        return {}
    folded = _fold_lower(seniat_text)
    vals = {}
    for keywords, rule_vals in PERSON_TYPE_TEXT_RULES:
        if all(k in folded for k in keywords):
            vals.update(rule_vals)
            break
    return vals


def partner_vals_from_seniat_parsed(env, parsed):
    vals = {}
    tipo_txt = " ".join(
        filter(
            None,
            [
                parsed.get("seniat_tipo_contribuyente_label"),
                parsed.get("condicion"),
            ],
        )
    )
    tt = map_taxpayer_type_selection(tipo_txt)
    if tt:
        vals["taxpayer_type"] = tt

    pct = extract_retention_percent_from_text(
        parsed.get("seniat_retencion_pct_label"),
        parsed.get("condicion"),
        parsed.get("retencion"),
        parsed.get("raw_table3"),
    )
    if pct is not None:
        wt = withholding_type_from_percent(env, pct)
        if wt:
            vals["withholding_type_id"] = wt.id

    persona_txt = parsed.get("seniat_tipo_persona_label") or ""
    if persona_txt:
        vals.update(person_type_vals_from_seniat_text(persona_txt))

    if vals:
        _logger.info(
            "l10n_ve_vat_seniat mapeo portal -> partner vals=%s kv=%s",
            vals,
            parsed.get("seniat_table_kv"),
        )
    else:
        _logger.info(
            "l10n_ve_vat_seniat mapeo portal sin coincidencias kv=%s "
            "tipo_txt=%r persona=%r",
            parsed.get("seniat_table_kv"),
            tipo_txt[:200] if tipo_txt else "",
            persona_txt,
        )
    return vals
