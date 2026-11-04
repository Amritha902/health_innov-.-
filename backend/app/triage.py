"""Deterministic triage. Rules are explicit, ordered and each one cites its basis.
The model never decides a referral on its own: anything above primary care is queued for a clinician."""

LEVELS = ["self_care", "primary_care", "fertility_services", "andrology", "same_day_primary", "urgent_specialist", "emergency"]

LEVEL_TEXT = {
    "emergency": {"en": "Go to an emergency department now, or call 998.",
                  "ar": "توجّه إلى قسم الطوارئ الآن أو اتصل بالرقم ٩٩٨."},
    "urgent_specialist": {"en": "See a urologist within the next few days. Early checks give the best outcomes.",
                          "ar": "راجع طبيب المسالك البولية خلال الأيام القليلة القادمة. الفحص المبكر يعطي أفضل النتائج."},
    "same_day_primary": {"en": "See a doctor today. This is usually quick to treat when caught early.",
                         "ar": "راجع طبيباً اليوم. غالباً ما يكون العلاج سريعاً عند الاكتشاف المبكر."},
    "andrology": {"en": "Book a men's health (andrology / urology) appointment in the next few weeks.",
                  "ar": "احجز موعداً في عيادة صحة الرجل (أمراض الذكورة / المسالك البولية) خلال الأسابيع القادمة."},
    "fertility_services": {"en": "A joint visit to a fertility clinic is the right next step. You can be checked at the same time as your wife, not after.",
                           "ar": "الخطوة المناسبة هي زيارة مشتركة لعيادة الخصوبة. يمكن فحصك في نفس الوقت مع زوجتك، وليس بعدها."},
    "primary_care": {"en": "A routine check with your family doctor (or your IFHAS screening visit) is a smart next step.",
                     "ar": "فحص روتيني لدى طبيب الأسرة (أو زيارة فحص «إفحص») خطوة ذكية تالية."},
    "self_care": {"en": "No need for a visit now. Here is your personal plan; check in again in 3 months.",
                  "ar": "لا حاجة لزيارة الآن. هذه خطتك الشخصية؛ عُد للمتابعة بعد ٣ أشهر."},
}

RED_FLAG_LEVEL = {
    "emergency": "emergency", "emergency_mental": "emergency", "urgent_urology": "urgent_specialist",
    "same_day_primary": "same_day_primary", "andrology": "andrology",
}

TIERS = [(0.55, "high"), (0.30, "moderate"), (0.0, "low")]


def tier_of(index):
    return next(t for cut, t in TIERS if index >= cut)


def decide(answers, ins, scores, semen, graph, wearable=None):
    wearable = wearable or {}
    level, reasons, tests, parallel = "self_care", [], [], []

    def raise_to(new, reason, basis):
        nonlocal level
        if LEVELS.index(new) > LEVELS.index(level):
            level = new
        reasons.append({"level": new, "reason": reason, "basis": basis})

    flags = {f["id"]: f for f in graph.red_flags}
    for fid in answers.get("red_flags") or []:
        f = flags.get(fid)
        if f:
            raise_to(RED_FLAG_LEVEL[f["action"]], f["text"] + " — " + f["why"], f["refs"])
            if fid == "rf_mood":
                parallel.append("mental_health_urgent")

    # semen results
    sem = semen or {}
    codes = {c for c, _, _ in sem.get("findings", [])}
    if codes & {"azoospermia", "severe_oligo"}:
        raise_to("andrology", "Semen result well below reference — needs specialist assessment (hormones, genetics, examination).",
                 ["schlegel2021", "eau2024"])
        tests += ["Repeat semen analysis", "FSH, LH, total testosterone (morning)", "Scrotal examination ± ultrasound"]
        if "azoospermia" in codes:
            tests += ["Karyotype and Y-chromosome microdeletion testing (if indicated)"]
    elif codes & {"oligo", "astheno", "low_volume", "home_below"}:
        raise_to("primary_care", "A result below reference. One test is not enough — repeat in ~3 months while working on your plan.",
                 ["who2021manual", "schlegel2021"])
        tests.append("Repeat semen analysis after 2–7 days abstinence")
        if len(codes & {"oligo", "astheno", "low_volume"}) >= 2:
            raise_to("andrology", "More than one semen measure below reference.", ["schlegel2021"])

    # time trying (ASRM: 12 months, or 6 months if female partner >= 35)
    months = _f(answers.get("months_trying"))
    p_age = _f(answers.get("partner_age"))
    if months is not None and (months >= 12 or (p_age and p_age >= 35 and months >= 6)):
        raise_to("fertility_services", f"Trying for {months:g} months — the point at which both partners should be assessed together.",
                 ["asrm2020", "schlegel2021"])
        tests.append("Semen analysis (should happen at the first visit, alongside your wife's assessment)")

    # clinical history needing a specialist
    if answers.get("aas") in ("current", "past_recent"):
        raise_to("andrology", "Testosterone / steroid use switches off natural sperm production; recovery is usually possible with supervision.",
                 ["who1990", "christou2017"])
        tests += ["FSH, LH, total testosterone", "Semen analysis"]
    for key, text in (("varicocele", "Known varicocele — treatable"), ("cryptorchidism", "Undescended testicle history"),
                      ("mumps", "Mumps orchitis after puberty"), ("chemo", "Past chemotherapy / radiotherapy")):
        if answers.get(key) == "yes":
            raise_to("andrology", text + ".", ["eau2024"])
    if answers.get("infection") == "untreated":
        raise_to("primary_care", "Past infection that may not have been fully treated — a simple test can check.", ["eau2024"])
        tests.append("Urine / swab test for common infections")
    if ins.get("adam_positive"):
        raise_to("primary_care", "Symptoms that can go with low testosterone. A morning blood test can check.", ["morley2000"])
        tests.append("Total testosterone (7–11 am)")

    # sleep apnoea
    sb = ins.get("stop_bang", 0)
    if sb >= 5 or (sb >= 3 and (wearable.get("spo2_low_nights") or 0) >= 3):
        raise_to("primary_care", f"Sleep breathing signals (STOP-Bang {sb}/8). A sleep study can confirm; treatment helps hormones and energy.",
                 ["chung2016", "u_osa2026"])
        parallel.append("sleep_study")

    # metabolic
    if ins.get("bmi") and ins["bmi"] >= 30 or answers.get("diabetes") in ("yes", "pre"):
        raise_to("primary_care", "Weight / blood sugar — the most modifiable signals in your profile.", ["sermondade2013", "ding2015"])
        tests += ["HbA1c", "Lipid profile"]

    if ins.get("phq2", 0) >= 3:
        parallel.append("mental_health")
    if answers.get("parents_related") == "yes" and (codes & {"azoospermia", "severe_oligo"} or answers.get("family_history") == "yes"):
        parallel.append("genetic_counselling")

    # overall signal load
    index = scores.get("subfertility", 0)
    tier = tier_of(index)
    if tier == "high":
        raise_to("primary_care", "Several signals add up. A baseline check gives you a clear picture.", ["who2021manual"])
        tests.append("Baseline semen analysis")
    elif tier == "moderate" and level == "self_care":
        reasons.append({"level": "self_care", "reason": "Some modifiable signals. A focused 3-month plan is the best first move.", "basis": []})

    requires_review = LEVELS.index(level) >= LEVELS.index("fertility_services") or tier == "high" or bool(answers.get("red_flags"))
    return {
        "level": level,
        "tier": tier,
        "index": round(index, 3),
        "message": LEVEL_TEXT[level],
        "reasons": reasons,
        "tests": list(dict.fromkeys(tests)),
        "parallel": list(dict.fromkeys(parallel)),
        "requires_review": requires_review,
        "immediate": level in ("emergency", "urgent_specialist", "same_day_primary"),
    }


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
