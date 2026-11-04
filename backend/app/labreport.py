"""Reads a semen-analysis or hormone report (PDF text, pasted text, or text from an on-phone photo scan) and
extracts values with units, the matching line, and a plausibility check. Nothing is saved here: the man confirms
or corrects every value first, and the original file is never stored."""
import io
import re

NUM = r"(\d+(?:[.,]\d+)?)"

# field: (labels, unit patterns -> multiplier to the app's unit, plausible range in app unit, app unit, target)
FIELDS = {
    "volume_ml": (["semen volume", "volume", "الحجم"], {r"ml": 1}, (0, 15), "mL", "semen"),
    "concentration_m_per_ml": (["sperm concentration", "concentration", "sperm count per ml", "density", "التركيز"],
                               {r"(?:x\s*)?10\^?6\s*/\s*ml|million\s*/\s*ml|m\s*/\s*ml|mill\s*/\s*ml": 1}, (0, 400), "M/mL", "semen"),
    "total_count_m": (["total sperm count", "total count", "total sperm number"], {r"(?:x\s*)?10\^?6|million|m\b": 1}, (0, 2000), "M", "semen"),
    "progressive_motility_pct": (["progressive motility", "progressive", r"\bpr\b", r"a\s*\+\s*b"], {r"%": 1}, (0, 100), "%", "semen"),
    "total_motility_pct": (["total motility", "motility", r"pr\s*\+\s*np", "الحركة"], {r"%": 1}, (0, 100), "%", "semen"),
    "normal_forms_pct": (["normal forms", "normal morphology", "morphology", "الأشكال الطبيعية"], {r"%": 1}, (0, 100), "%", "semen"),
    "vitality_pct": (["vitality", "live sperm", "viability"], {r"%": 1}, (0, 100), "%", "semen"),
    "ph": ([r"\bph\b"], {"": 1}, (5, 10), "", "semen"),
    "abstinence_days": (["abstinence", "days of abstinence"], {r"days?|d\b": 1}, (0, 60), "days", "semen"),
    "testosterone": (["total testosterone", "testosterone", "تستوستيرون"], {r"nmol\s*/\s*l": 1, r"ng\s*/\s*dl": 1 / 28.84, r"ng\s*/\s*ml": 3.467}, (0.1, 70), "nmol/L", "labs"),
    "fsh": ([r"\bfsh\b", "follicle stimulating"], {r"m?iu\s*/\s*m?l|u\s*/\s*l": 1}, (0, 150), "IU/L", "labs"),
    "lh": ([r"\blh\b", "luteinizing", "luteinising"], {r"m?iu\s*/\s*m?l|u\s*/\s*l": 1}, (0, 150), "IU/L", "labs"),
    "hba1c": (["hba1c", "glycated", "a1c"], {r"%": 1, r"mmol\s*/\s*mol": None}, (3, 20), "%", "labs"),
    "vitamin_d": (["25-oh vitamin d", "vitamin d", "25 hydroxy", "فيتامين د"], {r"ng\s*/\s*ml": 1, r"nmol\s*/\s*l": 1 / 2.496}, (1, 200), "ng/mL", "labs"),
}
DATE = re.compile(r"(?:collect(?:ed|ion)|sample|report(?:ed)?|date)[^\d]{0,20}(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2})", re.I)


def pdf_text(raw: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    if len(reader.pages) > 20:
        raise ValueError("Report too long")
    return "\n".join(p.extract_text() or "" for p in reader.pages)


def _iso(d):
    if re.match(r"\d{4}-\d{2}-\d{2}", d):
        return d
    a, b, y = re.split(r"[/.-]", d)
    y = ("20" + y) if len(y) == 2 else y
    return f"{y}-{int(b):02d}-{int(a):02d}"  # UAE reports use day/month/year


RANGE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)(?![\d.])")
BOUND = re.compile(r"(>=|<=|≥|≤|>|<)\s*(\d+(?:\.\d+)?)")
FLAG = re.compile(r"(?:^|\s)(h|l|high|low|\*)(?=\s|$)", re.I)
HEADER = re.compile(r"\b(result|value)\b.*\b(unit|units|reference|range|normal)\b", re.I)
TIME = re.compile(r"(?:collect\w*|sample|specimen)[^\n\d]{0,25}(\d{1,2})[:.](\d{2})", re.I)
FASTING = re.compile(r"\b(non[- ]?fasting|fasting)\b", re.I)


def _reference(tail, factor):
    """The lab's own range for this line, converted to the app unit. Kept as written too, because ranges differ between labs."""
    r = RANGE.search(tail)
    if r:
        lo, hi = float(r.group(1)) * factor, float(r.group(2)) * factor
        if lo < hi:
            return {"low": round(lo, 2), "high": round(hi, 2), "text": r.group(0).strip()}
    b = BOUND.search(tail)
    if b:
        v = round(float(b.group(2)) * factor, 2)
        return {"low": v, "high": None, "text": b.group(0)} if b.group(1) in (">", ">=", "≥") else {"low": None, "high": v, "text": b.group(0)}
    return None


def extract(text: str):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    table = any(HEADER.search(ln) for ln in lines)
    found, used = {}, set()
    for field, (labels, units, (lo, hi), unit, target) in FIELDS.items():
        for i, line in enumerate(lines):
            low = line.lower()
            label = next((lb for lb in labels if re.search(lb if lb.startswith("\\") or "\\" in lb else re.escape(lb), low)), None)
            if not label or (i, field) in used:
                continue
            # avoid 'total motility' matching the progressive field and vice versa
            if field == "total_motility_pct" and "progressive" in low and "total" not in low:
                continue
            if field == "concentration_m_per_ml" and "total" in low:
                continue
            if field == "testosterone" and "free" in low:
                continue
            lm = re.search(label if "\\" in label else re.escape(label), low)
            after = low[lm.end():].replace(",", ".")
            m = re.search(NUM, after)
            split = False
            if not m and i + 1 < len(lines) and re.match(r"\s*" + NUM, lines[i + 1]):
                # table cells extracted onto separate lines: label, then value, unit and range below
                after, split = lines[i + 1].lower().replace(",", "."), True
                m = re.search(NUM, after)
            if not m:
                continue
            value, rest = float(m.group(1)), after[m.end():m.end() + 22]
            factor, unit_found = 1, False
            for pat, mult in units.items():
                if pat and re.match(r"\s*(?:" + pat + ")", rest, re.I):
                    factor, unit_found = mult, True
                    break
            hba1c_mmol = factor is None
            if hba1c_mmol:  # HbA1c given in mmol/mol
                value, factor = value / 10.929 + 2.15, 1
            v = round(value * factor, 2)
            tail = after[m.end():]
            ref = None if hba1c_mmol else _reference(re.sub(r"^\s*[^\d<>≥≤]{0,14}", " ", tail), factor)
            if not ref:
                kw = re.search(r"(?:\bref(?:erence)?\b|\brange\b|\bnormal\b)(.*)", line, re.I)
                ref = _reference(kw.group(1), factor) if kw and not hba1c_mmol else None
            flag = FLAG.search(tail)
            plausible = lo <= v <= hi
            score = 0.35 + 0.3 * unit_found + 0.15 * bool(ref) + 0.1 * table + 0.1 * (len(label) > 6) - 0.15 * split
            score = round(min(score, 1.0) if plausible else min(score, 0.3), 2)
            found[field] = {"field": field, "value": v, "unit": unit, "target": target, "line": line[:160] + (" | " + lines[i + 1][:60] if split else ""),
                            "confidence": "check" if not plausible else "high" if score >= 0.75 else "medium" if score >= 0.5 else "low",
                            "score": score, "plausible": plausible, "reference": ref["text"] if ref else None, "ref": ref,
                            "lab_flag": {"h": "high", "high": "high", "l": "low", "low": "low", "*": "flagged"}[flag.group(1).lower()] if flag else None}
            used.add((i, field))
            break
    d = DATE.search(text)
    tm, fa = TIME.search(text), FASTING.search(text)
    context = {}
    if "abstinence_days" in found:
        context["abstinence_days"] = found["abstinence_days"]["value"]
    if tm and 0 <= int(tm.group(1)) < 24:
        context["time"] = f"{int(tm.group(1)):02d}:{tm.group(2)}"
    if fa:
        context["fasting"] = not fa.group(1).lower().startswith("non")
    return {"values": list(found.values()), "date": _iso(d.group(1)) if d else None, "context": context, "table": table,
            "kind": "semen" if any(f["target"] == "semen" for f in found.values()) else "labs" if found else None,
            "note": "Check every value against your report before saving. Values marked 'check' look unusual."}
