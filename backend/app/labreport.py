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


def extract(text: str):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
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
            if not m:
                continue
            value, rest = float(m.group(1)), after[m.end():m.end() + 22]
            factor, conf = 1, "medium"
            for pat, mult in units.items():
                if pat and re.match(r"\s*(?:" + pat + ")", rest, re.I):
                    factor, conf = mult, "high"
                    break
            if factor is None:  # HbA1c given in mmol/mol
                value, factor = value / 10.929 + 2.15, 1
            v = round(value * factor, 2)
            ref = re.search(r"(?:\bref(?:erence)?\b|\brange\b)[^\d<>≥≤]{0,12}((?:[<>≥≤]=?)?\s*\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?)", line, re.I)
            plausible = lo <= v <= hi
            found[field] = {"field": field, "value": v, "unit": unit, "target": target, "line": line[:160], "confidence": conf if plausible else "check",
                            "plausible": plausible, "reference": ref.group(1).strip() if ref else None}
            used.add((i, field))
            break
    d = DATE.search(text)
    return {"values": list(found.values()), "date": _iso(d.group(1)) if d else None,
            "kind": "semen" if any(f["target"] == "semen" for f in found.values()) else "labs" if found else None,
            "note": "Check every value against your report before saving. Values marked 'check' look unusual."}
