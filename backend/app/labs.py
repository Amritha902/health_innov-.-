"""Optional prior blood results. Thresholds:
- Total testosterone: < 12 nmol/L low-borderline, < 8 nmol/L clearly low (EAU 2024)
- FSH > 7.6 IU/L: suggests impaired sperm production (EAU 2024)
- LH: pattern with low testosterone separates primary (testicular) from secondary (pituitary / steroid) causes;
  upper reference ~8.6 IU/L used as a typical lab limit (lab-specific ranges vary)
- HbA1c: >= 6.5% diabetes, 5.7-6.4% pre-diabetes (ADA 2024)
- Vitamin D (25-OH): < 20 ng/mL deficient, 20-29 insufficient (Holick 2011)
"""

LH_UPPER = 8.6


def interpret(r):
    findings, inputs, done = [], [], []
    t = r.get("testosterone")
    if t is not None and r.get("testosterone_unit") == "ng/dL":
        t = round(t / 28.84, 1)
    fsh, lh, a1c, vd = r.get("fsh"), r.get("lh"), r.get("hba1c"), r.get("vitamin_d")
    if r.get("vitamin_d_unit") == "nmol/L" and vd is not None:
        vd = round(vd / 2.496, 1)
    date = r.get("date")

    if t is not None:
        done.append(("Total testosterone", f"{t} nmol/L", date))
        if t < 8:
            findings.append(("t_low", f"Testosterone {t} nmol/L (clearly low, < 8)", "high", ["eau2024"]))
            inputs.append(("hypogonadism", 1.0, f"Lab: testosterone {t} nmol/L", "lab"))
        elif t < 12:
            findings.append(("t_borderline", f"Testosterone {t} nmol/L (borderline, < 12) — repeat in the morning", "moderate", ["eau2024"]))
            inputs.append(("hypogonadism", 0.6, f"Lab: testosterone {t} nmol/L", "lab"))
        if t < 12 and lh is not None:
            kind = "primary (testicular)" if lh > LH_UPPER else "secondary (pituitary, steroids, weight, sleep apnoea)"
            findings.append(("t_pattern", f"Pattern suggests {kind} cause (LH {lh} IU/L)", "moderate", ["eau2024"]))
    if fsh is not None:
        done.append(("FSH", f"{fsh} IU/L", date))
        if fsh > 7.6:
            findings.append(("fsh_high", f"FSH {fsh} IU/L (> 7.6) suggests reduced sperm production", "high" if fsh > 12 else "moderate", ["eau2024"]))
            inputs.append(("low_count", 0.6 if fsh <= 12 else 0.8, f"Lab: FSH {fsh} IU/L", "lab"))
    if lh is not None:
        done.append(("LH", f"{lh} IU/L", date))
    if a1c is not None:
        done.append(("HbA1c", f"{a1c}%", date))
        if a1c >= 6.5:
            findings.append(("a1c_dm", f"HbA1c {a1c}% (diabetes range)", "moderate", ["ada2024"]))
            inputs.append(("diabetes", 1.0, f"Lab: HbA1c {a1c}%", "lab"))
        elif a1c >= 5.7:
            findings.append(("a1c_pre", f"HbA1c {a1c}% (pre-diabetes range)", "low", ["ada2024"]))
            inputs.append(("diabetes", 0.5, f"Lab: HbA1c {a1c}%", "lab"))
    if vd is not None:
        done.append(("Vitamin D (25-OH)", f"{vd} ng/mL", date))
        if vd < 20:
            findings.append(("vd_low", f"Vitamin D {vd} ng/mL (deficient)", "low", ["holick2011"]))
            inputs.append(("vitd_def", 1.0, f"Lab: vitamin D {vd} ng/mL", "lab"))
        elif vd < 30:
            inputs.append(("vitd_def", 0.5, f"Lab: vitamin D {vd} ng/mL", "lab"))
    return {"findings": findings, "graph_inputs": inputs, "already_done": done, "values": r}
