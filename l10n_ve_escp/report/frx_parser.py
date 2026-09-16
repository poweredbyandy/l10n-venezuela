import struct

OBJ_HEADER = 1
OBJ_LABEL = 5
OBJ_LINE = 6
OBJ_RECT = 7
OBJ_FIELD = 8
OBJ_BAND = 9

BAND_CODES = {
    0: "title",
    1: "page_header",
    2: "column_header",
    3: "column_header",
    4: "detail",
    5: "page_footer",
    6: "page_footer",
    7: "page_footer",
    8: "summary",
}
BAND_BAR_FRU = 2083.33
PIXEL_FRU = 10000.0 / 96.0
SNAP_TOLERANCE_FRU = PIXEL_FRU / 2.0


def _dbf_fields(data):
    fields = []
    pos = 32
    while data[pos] != 0x0D:
        name = data[pos : pos + 11].split(b"\0")[0].decode("latin-1")
        fields.append((name, chr(data[pos + 11]), data[pos + 16]))
        pos += 32
    return fields


def _memo_reader(memo):
    if not memo or len(memo) < 8:
        return lambda idx: ""
    block = struct.unpack(">H", memo[6:8])[0] or 64

    def read(idx):
        if not idx:
            return ""
        off = idx * block
        if off + 8 > len(memo):
            return ""
        _kind, length = struct.unpack(">II", memo[off : off + 8])
        return memo[off + 8 : off + 8 + length].decode("cp1252", errors="replace")

    return read


def parse_frx(frx_bytes, frt_bytes=None):
    """Return the FoxPro report records as a list of dicts.

    Each dict has at least OBJTYPE, OBJCODE, EXPR, VPOS, HPOS, HEIGHT, WIDTH,
    FONTFACE, FONTSTYLE, FONTSIZE, PICTURE and NAME. Positions are in FRU
    (1/10000 inch) relative to the top of the designer layout.
    """
    if len(frx_bytes) < 32:
        raise ValueError("FRX file too short")
    nrec, hdr_len, rec_len = struct.unpack("<IHH", frx_bytes[4:12])
    fields = _dbf_fields(frx_bytes)
    read_memo = _memo_reader(frt_bytes)
    records = []
    for index in range(nrec):
        start = hdr_len + index * rec_len
        rec = frx_bytes[start : start + rec_len]
        if len(rec) < rec_len or rec[0:1] == b"*":
            continue
        out = {}
        pos = 1
        for name, ftype, flen in fields:
            raw = rec[pos : pos + flen]
            pos += flen
            if ftype == "C":
                out[name] = raw.decode("cp1252", errors="replace").rstrip()
            elif ftype in ("N", "F"):
                text = raw.strip()
                try:
                    out[name] = float(text) if text else 0.0
                except ValueError:
                    out[name] = 0.0
            elif ftype == "L":
                out[name] = raw in (b"T", b"t", b"Y", b"y")
            elif ftype == "M":
                idx = struct.unpack("<I", raw)[0] if flen == 4 else int(raw.strip() or 0)
                out[name] = read_memo(idx)
            elif ftype == "I":
                out[name] = struct.unpack("<i", raw)[0]
            else:
                out[name] = raw
        records.append(out)
    return records


def frx_layout(records):
    """Split records in bands with objects positioned relative to each band.

    Returns (page_width_fru, bands) where bands is an ordered list of dicts
    {type, height_fru, objects: [record with rel_vpos]}.
    """
    page_width = 85000.0
    bands = []
    for rec in records:
        if int(rec.get("OBJTYPE", 0)) == OBJ_HEADER:
            page_width = float(rec.get("WIDTH") or page_width)
        elif int(rec.get("OBJTYPE", 0)) == OBJ_BAND:
            bands.append(
                {
                    "type": BAND_CODES.get(int(rec.get("OBJCODE", 0)), "page_header"),
                    "code": int(rec.get("OBJCODE", 0)),
                    "height_fru": float(rec.get("HEIGHT") or 0.0),
                    "objects": [],
                }
            )
    top = 0.0
    for band in bands:
        band["top_fru"] = top
        top += band["height_fru"] + BAND_BAR_FRU
    for rec in records:
        objtype = int(rec.get("OBJTYPE", 0))
        if objtype not in (OBJ_LABEL, OBJ_FIELD, OBJ_LINE, OBJ_RECT):
            continue
        vpos = float(rec.get("VPOS") or 0.0)
        target = None
        for band in bands:
            lower = band["top_fru"] - SNAP_TOLERANCE_FRU
            upper = band["top_fru"] + band["height_fru"] + BAND_BAR_FRU - SNAP_TOLERANCE_FRU
            if lower <= vpos < upper:
                target = band
                break
        if target is None and bands:
            target = min(bands, key=lambda b: abs(b["top_fru"] - vpos))
        if target is None:
            continue
        item = dict(rec)
        item["rel_vpos"] = max(0.0, vpos - target["top_fru"])
        target["objects"].append(item)
    return page_width, bands
