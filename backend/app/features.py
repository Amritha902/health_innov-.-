"""Turns answers, wearable summaries and test results into graph inputs.

Every input carries its provenance (which question / sensor / instrument produced it), so the
explanation shown to a clinician can say exactly why a node was switched on.
"""


def _num(a, k, default=None):
    v = a.get(k)
    if v in (None, "", "skip"):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _is(a, k, *vals):
    return a.get(k) in vals


def bmi(a):
    h, w = _num(a, "height_cm"), _num(a, "weight_kg")
    return round(w / (h / 100) ** 2, 1) if h and w else None


def waist_cutoff(background):
    # IDF 2006: Europid / Middle Eastern / African >= 94 cm; South & East Asian >= 90 cm
    return 90 if background in ("south_asian", "east_asian") else 94


def instruments(a):
    out = {}
    if a.get("audit1") not in (None, "skip"):
        out["audit_c"] = sum(int(a.get(k) or 0) for k in ("audit1", "audit2", "audit3") if a.get(k) not in (None, "skip"))
    pss_items = [a.get(f"pss{i}") for i in range(1, 5)]
    if all(v is not None for v in pss_items):
        out["pss4"] = int(a["pss1"]) + (4 - int(a["pss2"])) + (4 - int(a["pss3"])) + int(a["pss4"])
    if a.get("phq1") is not None and a.get("phq2") is not None:
        out["phq2"] = int(a["phq1"]) + int(a["phq2"])
    adam = {i: a.get(f"adam{i}") for i in range(1, 11)}
    if any(v is not None for v in adam.values()):
        yes = [i for i, v in adam.items() if v == "yes"]
        out["adam_positive"] = 1 in yes or 7 in yes or len(yes) >= 3
        out["adam_yes"] = len(yes)
    sb = 0
    sb += a.get("snore") == "yes"
    sb += a.get("tired") == "yes"
    sb += a.get("observed") == "yes"
    sb += a.get("bp") == "yes"
    b = bmi(a)
    sb += bool(b and b > 35)
    sb += bool(_num(a, "age", 0) > 50)
    sb += bool(_num(a, "neck_cm", 0) > 40)
    sb += 1  # male sex
    out["stop_bang"] = sb
    out["bmi"] = b
    return out


def build_inputs(a, wearable=None, semen=None, labs=None):
    """Returns (inputs: node -> activation, provenance: node -> [reasons])."""
    wearable = wearable or {}
    inp, why = {}, {}

    def put(node, value, reason, source="questionnaire"):
        if value <= 0:
            return
        if value > inp.get(node, 0):
            inp[node] = round(min(1.0, value), 3)
        why.setdefault(node, []).append({"source": source, "reason": reason})

    ins = instruments(a)
    age = _num(a, "age")

    # substances
    if _is(a, "smoking", "daily"):
        put("smoking", 1.0 if _num(a, "cigs_per_day", 10) >= 10 else 0.7, "Smokes daily")
    elif _is(a, "smoking", "occasional"):
        put("smoking", 0.4, "Smokes occasionally")
    elif _is(a, "smoking", "former"):
        put("smoking", 0.1, "Former smoker")
    put("waterpipe", {"daily": 0.8, "weekly": 0.5, "monthly": 0.2}.get(a.get("waterpipe"), 0), "Shisha / midwakh use")
    if "audit_c" in ins:
        s = ins["audit_c"]
        put("alcohol", 1.0 if s >= 8 else 0.8 if s >= 6 else 0.5 if s >= 4 else 0.2 if s >= 1 else 0, f"AUDIT-C {s}/12", "AUDIT-C")
    if _is(a, "cannabis", "current"):
        put("cannabis", 0.7, "Current recreational substance use")
    put("aas", {"current": 1.0, "past_recent": 0.6, "past_old": 0.2}.get(a.get("aas"), 0), "Testosterone / anabolic steroid use")
    meds = a.get("meds") or []
    if "opioid" in meds:
        put("opioids", 0.8, "Regular opioid painkillers")
    if any(m in meds for m in ("ssri", "finasteride", "other")):
        put("medications", 0.5, "Long-term medicines that can affect hormones or sperm")

    # activity, diet, timing
    sit = _num(a, "sitting_h")
    if sit is not None:
        put("sedentary", 0.8 if sit >= 8 else 0.5 if sit >= 6 else 0, f"Sits about {sit:g} h/day")
    steps = wearable.get("steps_avg")
    if steps is not None and steps < 5000:
        put("sedentary", 0.7, f"Watch: {int(steps)} steps/day on average", "watch")
    if _num(a, "exercise_days", 0) >= 3 and "sedentary" in inp:
        inp["sedentary"] = round(inp["sedentary"] * 0.7, 3)
    put("western_diet", {2: 0.8, 1: 0.4}.get(_int(a.get("fast_food")), 0), "Frequent fast / processed food")
    prudent = (_int(a.get("fruit_veg")) or 0) + (_int(a.get("fish")) or 0)
    put("prudent_diet", 0.8 if prudent >= 4 else 0.4 if prudent >= 2 else 0, "Fruit, vegetables and fish")
    lm = _num(a, "late_meals", 0)
    put("late_eating", 0.8 if lm >= 4 else 0.4 if lm >= 2 else 0, f"Late meals {lm:g} nights/week")
    lc = _num(a, "late_caffeine", 0)
    put("caffeine_late", 0.8 if lc >= 4 else 0.4 if lc >= 2 else 0, f"Caffeine after 4 pm {lc:g} days/week")
    if wearable.get("late_caffeine_days_per_week") is not None:
        d = wearable["late_caffeine_days_per_week"]
        put("caffeine_late", 0.8 if d >= 4 else 0.4 if d >= 2 else 0, f"Health app: caffeine logged after 4 pm on {d:g} days/week", "watch")
    if wearable.get("night_glucose_high_pct") is not None:
        p = wearable["night_glucose_high_pct"]
        cv = wearable.get("glucose_cv") or 0
        v = 0.8 if p >= 10 or cv > 36 else 0.4 if p >= 3 else 0
        put("glycaemic_spikes", v, f"CGM: {p:.0f}% of night readings above 140 mg/dL, CV {cv:.0f}%", "cgm")

    # sleep & screens
    sh = wearable.get("sleep_avg_h")
    src, reason = ("watch", f"Watch: {sh:.1f} h average sleep") if sh else ("questionnaire", None)
    sh = sh or _num(a, "sleep_h")
    if sh is not None:
        put("sleep_loss", 0.8 if sh < 6 else 0.3 if sh < 7 else 0, reason or f"Sleeps about {sh:g} h", src)
    put("shift_work", {"night": 1.0, "rotating": 0.8}.get(a.get("shift"), 0), "Shift / night work")
    if (wearable.get("social_jetlag_h") or 0) >= 2:
        put("circadian", 0.7, f"Watch: weekend sleep shifts by {wearable['social_jetlag_h']:.1f} h", "watch")
    scr = wearable.get("screen_daily_h") or _num(a, "screen_h")
    if scr is not None:
        put("screen_time_high", 0.9 if scr >= 6 else 0.6 if scr >= 4 else 0, f"{scr:g} h/day recreational screen time")
    put("screen_night", {2: 0.8, 1: 0.4}.get(_int(a.get("screen_bed")), 0), "Screens in the hour before sleep")

    # OSA: STOP-Bang (+ wearable SpO2 as supporting signal)
    sb = ins["stop_bang"]
    put("osa", 0.85 if sb >= 5 else 0.5 if sb >= 3 else 0, f"STOP-Bang {sb}/8", "STOP-Bang")
    if (wearable.get("spo2_low_nights") or 0) >= 3:
        put("osa", min(1.0, inp.get("osa", 0) + 0.2), f"Watch: oxygen below 90% on {wearable['spo2_low_nights']} nights", "watch")

    # body
    b = ins["bmi"]
    if b:
        put("obesity", 1.0 if b >= 35 else 0.8 if b >= 30 else 0.4 if b >= 25 else 0, f"BMI {b}")
    w = _num(a, "waist_cm")
    if w and w >= waist_cutoff(a.get("background")):
        put("obesity", 0.6, f"Waist {w:g} cm (cut-off {waist_cutoff(a.get('background'))} cm)")
    put("diabetes", {"yes": 1.0, "pre": 0.5}.get(a.get("diabetes"), 0), "Blood sugar history")

    # heat, clothing, devices, environment
    put("tight_underwear", {"tight": 0.8, "mixed": 0.4}.get(a.get("underwear"), 0), "Tight underwear")
    put("synthetic_textile", {"synthetic": 0.6, "mixed": 0.3}.get(a.get("underwear_fabric"), 0), "Synthetic underwear fabric")
    put("hot_bath", {2: 0.9, 1: 0.6}.get(_int(a.get("hot_bath")), 0), "Sauna / jacuzzi / hot baths")
    lap = _num(a, "laptop_lap", 0)
    put("laptop_lap", 0.7 if lap >= 2 else 0.3 if lap >= 1 else 0, f"Laptop on lap {lap:g} h/day")
    if a.get("phone_pocket") == "yes":
        put("phone_pocket", 0.6, "Phone in front pocket")
    if a.get("heat_work") == "yes":
        put("occupational_heat", 0.7, "Outdoor heat or long daily driving")
    if a.get("near_traffic") == "yes":
        put("air_pollution", 0.6, "Lives or works near heavy traffic / industry")
    occ = a.get("occupation")
    if occ in ("industrial", "agriculture"):
        put("edc", 0.6, "Occupation with chemical exposure")
    if occ in ("outdoor", "driving"):
        put("occupational_heat", 0.6, "Outdoor or driving work")
    if a.get("chemicals_work") == "yes":
        put("edc", 0.8, "Regular work contact with chemicals")
    if a.get("vitd") == "yes":
        put("vitd_def", 1.0, "Known low vitamin D")
    elif a.get("indoors") == "yes":
        put("low_sun", 0.6, "Mostly indoors in daylight")

    # mind
    if "pss4" in ins:
        put("psych_stress", round(ins["pss4"] / 16, 2) if ins["pss4"] >= 6 else 0, f"PSS-4 {ins['pss4']}/16", "PSS-4")
    if ins.get("phq2", 0) >= 3:
        put("low_mood", 0.8, f"PHQ-2 {ins['phq2']}/6", "PHQ-2")
    if ins.get("adam_positive"):
        put("hypogonadism", 0.4, f"ADAM screen positive ({ins['adam_yes']} yes)", "ADAM")

    # history
    if age and age >= 40:
        put("paternal_age", min(1.0, (age - 35) / 15), f"Age {age:g}")
    if a.get("mumps") == "yes":
        put("mumps", 1.0, "Mumps orchitis after puberty")
    if a.get("cryptorchidism") == "yes":
        put("cryptorchidism", 1.0, "Undescended testicle in childhood")
    if a.get("varicocele") == "yes":
        put("varicocele", 1.0, "Known varicocele")
    put("genital_infection", {"untreated": 1.0, "treated": 0.3}.get(a.get("infection"), 0), "Past genital / urinary infection")
    if a.get("chemo") == "yes":
        put("chemo", 1.0, "Past chemotherapy / radiotherapy")
    if a.get("fever") == "yes":
        put("recent_fever", 0.8, "High fever in last 3 months")
    if a.get("parents_related") == "yes":
        put("consanguinity", 0.6, "Parents related by blood")
    if a.get("family_history") == "yes":
        put("genetic", 0.4, "Male relatives needed fertility help")

    # observed test results override inference
    for node, value, reason, source in (semen or {}).get("graph_inputs", []) + (labs or {}).get("graph_inputs", []):
        inp[node] = value
        why.setdefault(node, []).append({"source": source, "reason": reason})

    return inp, why, ins


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
