"""Garment check: care-label parsing and a groin-heat index. Fit drives the score (grade B evidence);
fibre modifies it (grade C/D); microplastic/BPA concerns are a precautionary note only."""
import re

FIBRES = {
    "linen": (1.0, ["linen", "flax", "كتان"], "natural"),
    "hemp": (0.95, ["hemp"], "natural"),
    "cotton": (0.9, ["cotton", "coton", "algodon", "algodón", "baumwolle", "قطن"], "natural"),
    "lyocell": (0.85, ["lyocell", "tencel"], "cellulosic"),
    "modal": (0.85, ["modal"], "cellulosic"),
    "viscose": (0.8, ["viscose", "rayon", "bamboo", "cupro", "فسكوز"], "cellulosic"),
    "silk": (0.7, ["silk", "حرير"], "natural"),
    "wool": (0.7, ["wool", "merino", "cashmere", "صوف"], "natural"),
    "polypropylene": (0.4, ["polypropylene"], "synthetic"),
    "polyester": (0.3, ["polyester", "poly", "pes", "pet", "microfiber", "microfibre", "بوليستر"], "synthetic"),
    "nylon": (0.3, ["nylon", "polyamide", "pa", "نايلون"], "synthetic"),
    "acrylic": (0.3, ["acrylic"], "synthetic"),
    "elastane": (0.2, ["elastane", "spandex", "lycra", "ea", "el", "إيلاستين", "سباندكس"], "synthetic"),
    "pu": (0.05, ["polyurethane", "pu", "pvc", "vinyl"], "synthetic"),
}
GARMENTS = {"underwear": 1.0, "wizar": 0.9, "shorts": 0.8, "trousers": 0.7, "kandura": 0.25, "top": 0.05}
FIT = {"tight": 1.0, "regular": 0.6, "loose": 0.3}


def _match(word):
    for key, (_, names, _) in FIBRES.items():
        for n in names:
            if (len(n) <= 3 and word == n) or (len(n) > 3 and n in word):
                return key
    return None


def parse(text):
    toks = []
    for m in re.finditer(r"(\d{1,3}(?:[.,]\d+)?)\s*%|[^\W\d_]+", text.lower()):
        toks.append({"pct": float(m.group(1).replace(",", "."))} if m.group(1) else {"w": m.group(0)})
    first_pct = next((i for i, t in enumerate(toks) if "pct" in t), -1)
    first_fibre = next((i for i, t in enumerate(toks) if "w" in t and _match(t["w"])), -1)
    name_first = first_fibre != -1 and first_fibre < first_pct
    used, found = set(), {}

    def seek(i, step):
        j = i
        while 0 <= j < len(toks) and "pct" not in toks[j]:
            k = _match(toks[j]["w"])
            if k and j not in used:
                return j, k
            j += step
        return None

    for i, t in enumerate(toks):
        if "pct" not in t:
            continue
        hit = (seek(i - 1, -1) or seek(i + 1, 1)) if name_first else (seek(i + 1, 1) or seek(i - 1, -1))
        if hit:
            used.add(hit[0])
            found[hit[1]] = found.get(hit[1], 0) + t["pct"]
    if not found:
        k = _match(text.lower().strip())
        if k:
            found[k] = 100.0
    return found


def assess(text, garment="underwear", fit="regular", hot_climate=True):
    comp = parse(text)
    total = sum(comp.values())
    if not total:
        return {"ok": False, "message": "Could not read a fibre composition, e.g. '95% cotton 5% elastane'."}
    breath = sum(FIBRES[k][0] * p / total for k, p in comp.items())
    synthetic = sum(p / total for k, p in comp.items() if FIBRES[k][2] == "synthetic")
    prox, f = GARMENTS.get(garment, 0.7), FIT.get(fit, 0.6)
    score = round(min(1, prox * (0.65 * f + 0.35 * (1 - breath)) * (1.1 if hot_climate else 1)) * 100)
    verdict = "good" if score < 30 else "okay" if score < 55 else "caution"
    notes = []
    if fit == "tight" and prox >= 0.7:
        notes.append({"grade": "B", "key": "fit", "refs": ["minguez2018", "durairajanayagam2015"]})
    if synthetic >= 0.5 and prox >= 0.7:
        notes.append({"grade": "D", "key": "breathability", "refs": ["durairajanayagam2015"]})
    if comp.get("polyester") and prox >= 0.7:
        notes.append({"grade": "C", "key": "polyester_static", "refs": ["shafik1992", "shafik1993"]})
    if synthetic >= 0.5 and prox >= 0.7:
        notes.append({"grade": "D", "key": "microplastics", "refs": ["ceh2022", "hu2024", "defalco2019"]})
    if breath >= 0.8 and (fit != "tight" or prox < 0.7):
        notes.append({"grade": "B", "key": "good_choice", "refs": ["minguez2018"]})
    if garment == "kandura":
        notes.append({"grade": "B", "key": "kandura", "refs": ["durairajanayagam2015"]})
    swaps = []
    if verdict != "good":
        if fit == "tight":
            swaps.append("looser_cut")
        if synthetic >= 0.5:
            swaps.append("natural_fibre")
        if garment == "shorts":
            swaps.append("change_after_gym")
    return {"ok": True, "composition": comp, "breathability": round(breath, 2), "synthetic": round(synthetic, 2),
            "score": score, "verdict": verdict, "notes": notes, "swaps": swaps}
