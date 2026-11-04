"""Semen result interpretation against WHO 2021 (6th ed.) lower reference limits (5th centile)."""

WHO_2021 = {
    "volume_ml": 1.4,
    "concentration_m_per_ml": 16,
    "total_count_m": 39,
    "total_motility_pct": 42,
    "progressive_motility_pct": 30,
    "vitality_pct": 54,
    "normal_forms_pct": 4,
}

# home tests and their published cut-offs
HOME_TESTS = {
    "yo": {"name": "YO Home Sperm Test", "measure": "motile sperm concentration", "cutoff": 6},
    "spermcheck": {"name": "SpermCheck Fertility", "measure": "sperm concentration", "cutoff": 20},
    "other": {"name": "Other home test", "measure": "kit-specific", "cutoff": None},
}


def interpret_lab(r):
    """r: dict with any of WHO_2021 keys (+ optional ph, abstinence_days)."""
    findings, inputs = [], []
    g = lambda k: r.get(k) if r.get(k) not in ("", None) else None
    conc, vol = g("concentration_m_per_ml"), g("volume_ml")
    total = g("total_count_m") or (conc * vol if conc is not None and vol is not None else None)
    pr, tm, morph = g("progressive_motility_pct"), g("total_motility_pct"), g("normal_forms_pct")

    if conc is not None and conc == 0:
        findings.append(("azoospermia", "No sperm seen in the sample", "high"))
        inputs.append(("azoospermia", 1.0, "Lab: no sperm seen", "lab"))
    elif conc is not None and conc < 5:
        findings.append(("severe_oligo", f"Concentration {conc} M/mL (well below 16)", "high"))
        inputs.append(("low_count", 1.0, f"Lab: concentration {conc} M/mL", "lab"))
    elif (conc is not None and conc < WHO_2021["concentration_m_per_ml"]) or (total is not None and total < WHO_2021["total_count_m"]):
        findings.append(("oligo", f"Count below reference (concentration {conc}, total {total and round(total)})", "moderate"))
        inputs.append(("low_count", 0.7, "Lab: count below WHO reference", "lab"))
    if pr is not None and pr < WHO_2021["progressive_motility_pct"] or tm is not None and tm < WHO_2021["total_motility_pct"]:
        findings.append(("astheno", f"Motility below reference (progressive {pr}%, total {tm}%)", "moderate"))
        inputs.append(("low_motility", 0.7, "Lab: motility below WHO reference", "lab"))
    if morph is not None and morph < WHO_2021["normal_forms_pct"]:
        findings.append(("terato", f"Normal forms {morph}% (reference ≥ 4%)", "low"))
        inputs.append(("abn_morph", 0.5, "Lab: morphology below reference", "lab"))
    if vol is not None and vol < WHO_2021["volume_ml"]:
        low_ph = g("ph") is not None and g("ph") < 7.2
        findings.append(("low_volume", f"Volume {vol} mL (reference ≥ 1.4)" + ("; low pH suggests possible obstruction" if low_ph else ""),
                         "high" if low_ph else "moderate"))
        inputs.append(("low_volume", 0.7, "Lab: low semen volume", "lab"))

    abst = g("abstinence_days")
    notes = []
    if abst is not None and not 2 <= abst <= 7:
        notes.append("Abstinence outside 2–7 days can change results; a repeat may be needed.")
    if findings:
        notes.append("One result is not enough. Results vary a lot; any abnormal result is confirmed with a repeat test about 3 months later.")
    return {"source": "lab", "findings": findings, "normal": not findings, "notes": notes, "graph_inputs": inputs,
            "reference": "WHO 2021 lower reference limits"}


def interpret_home_quantitative(r, kit="yo"):
    """Smartphone devices that report numbers (e.g. YO 3.0: total sperm concentration, motility %,
    progressive motility %, motile and progressively motile sperm concentration). Interpreted with the
    same WHO limits as a lab, but the result is marked as a home screen and down-weighted."""
    lab_like = {"concentration_m_per_ml": r.get("concentration_m_per_ml"),
                "total_motility_pct": r.get("total_motility_pct"),
                "progressive_motility_pct": r.get("progressive_motility_pct")}
    out = interpret_lab(lab_like)
    msc = r.get("motile_conc_m_per_ml")
    if msc not in (None, "") and msc < 6:
        out["findings"].append(("home_below", f"Motile sperm concentration {msc} M/mL (device cut-off 6)", "moderate"))
        out["graph_inputs"].append(("low_count", 0.6, "Home device: low motile sperm concentration", "home_test"))
    out["graph_inputs"] = [(n, round(v * 0.8, 2), reason.replace("Lab", "Home device"), "home_test")
                           for n, v, reason, _ in out["graph_inputs"]]
    out["source"] = "home_test"
    out["kit"] = HOME_TESTS.get(kit, HOME_TESTS["other"])["name"]
    out["normal"] = not out["findings"]
    out["notes"] = ["Home devices measure count and movement only (not shape, volume or DNA). Confirm any low result in a lab."] + \
        [n for n in out["notes"] if n.startswith("One result")]
    out["values"] = r
    return out


def interpret_home(kit, result, value=None):
    t = HOME_TESTS.get(kit, HOME_TESTS["other"])
    below = result == "below" or (value is not None and t["cutoff"] is not None and value < t["cutoff"])
    inputs = [("low_count", 0.6, f"Home test ({t['name']}) below its cut-off", "home_test")] if below else []
    return {"source": "home_test", "kit": t["name"], "normal": not below,
            "findings": [("home_below", f"{t['name']}: below the kit cut-off", "moderate")] if below else [],
            "notes": ["Home tests check only part of a semen analysis. A normal home result does not rule things out, "
                      "and a low one should be confirmed in a lab."],
            "graph_inputs": inputs}
