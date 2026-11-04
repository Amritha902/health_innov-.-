"""Clinical vignettes with the expected next step written from guidelines (WHO 2021, AUA/ASRM 2021, EAU 2024,
ASRM 2020 definitions), independently of the code. 'min_level' is the lowest acceptable level: landing
lower is under-triage (a safety failure); landing higher is over-triage (a cost / burden failure)."""

HEALTHY = {"age": 28, "height_cm": 178, "weight_kg": 72, "smoking": "never", "waterpipe": "never", "audit1": 0,
           "aas": "never", "sitting_h": 5, "exercise_days": 4, "fast_food": 0, "fruit_veg": 2, "fish": 2,
           "late_meals": 0, "late_caffeine": 0, "sleep_h": 7.5, "shift": "day", "snore": "no", "tired": "no",
           "observed": "no", "bp": "no", "screen_h": 2, "screen_bed": 0, "underwear": "loose", "hot_bath": 0,
           "pss1": 1, "pss2": 3, "pss3": 3, "pss4": 1, "phq1": 0, "phq2": 0, "diabetes": "no"}


def v(**kw):
    return {**HEALTHY, **kw}


VIGNETTES = [
    ("Healthy 28-year-old, general check", v(), None, "self_care", "self_care"),
    ("Sudden severe testicular pain", v(red_flags=["rf_torsion"]), None, "emergency", "emergency"),
    ("New testicular lump", v(red_flags=["rf_lump"]), None, "urgent_specialist", "urgent_specialist"),
    ("Painful swollen scrotum with fever", v(red_flags=["rf_fever_pain"]), None, "same_day_primary", "same_day_primary"),
    ("Thoughts of self-harm", v(red_flags=["rf_mood"]), None, "emergency", "emergency"),
    ("Dry orgasm", v(red_flags=["rf_no_ejac"]), None, "andrology", "andrology"),
    ("Lab: no sperm seen", v(), {"source": "lab", "volume_ml": 2.5, "concentration_m_per_ml": 0}, "andrology", "andrology"),
    ("Lab: concentration 3 M/mL", v(), {"source": "lab", "volume_ml": 3, "concentration_m_per_ml": 3, "progressive_motility_pct": 35}, "andrology", "andrology"),
    ("Lab: mild single low value", v(), {"source": "lab", "volume_ml": 3, "concentration_m_per_ml": 14, "progressive_motility_pct": 38, "normal_forms_pct": 5}, "primary_care", "primary_care"),
    ("Lab: two parameters low", v(), {"source": "lab", "volume_ml": 3, "concentration_m_per_ml": 10, "progressive_motility_pct": 20}, "andrology", "andrology"),
    ("Lab: normal", v(), {"source": "lab", "volume_ml": 3, "concentration_m_per_ml": 60, "progressive_motility_pct": 50, "normal_forms_pct": 6}, "self_care", "self_care"),
    ("Home device below cut-off", v(), {"source": "home_quant", "kit": "yo", "concentration_m_per_ml": 9, "motile_conc_m_per_ml": 4}, "primary_care", "primary_care"),
    ("Trying 14 months", v(reason=["trying"], months_trying=14), None, "fertility_services", "fertility_services"),
    ("Trying 7 months, wife 37", v(reason=["trying"], months_trying=7, partner_age=37), None, "fertility_services", "fertility_services"),
    ("Trying 5 months, wife 29", v(reason=["trying"], months_trying=5, partner_age=29), None, "self_care", "self_care"),
    ("Current anabolic steroid cycle", v(aas="current"), None, "andrology", "andrology"),
    ("Steroids more than a year ago, otherwise well", v(aas="past_old"), None, "self_care", "primary_care"),
    ("Known varicocele", v(varicocele="yes"), None, "andrology", "andrology"),
    ("Undescended testis as a child", v(cryptorchidism="yes"), None, "andrology", "andrology"),
    ("Past chemotherapy", v(chemo="yes"), None, "andrology", "andrology"),
    ("Loud snoring, apnoeas, BMI 36, age 52", v(age=52, weight_kg=112, height_cm=176, snore="yes", tired="yes", observed="yes", bp="yes"), None, "primary_care", "primary_care"),
    ("Obese with pre-diabetes", v(weight_kg=100, height_cm=175, diabetes="pre"), None, "primary_care", "primary_care"),
    ("Low libido + weaker erections (ADAM+)", v(adam1="yes", adam7="yes"), None, "primary_care", "primary_care"),
    ("Smoker, shisha, short sleep, tight underwear", v(smoking="daily", cigs_per_day=15, waterpipe="weekly", sleep_h=5, underwear="tight", sitting_h=10), None, "self_care", "primary_care"),
    ("Possibly untreated past infection", v(infection="untreated"), None, "primary_care", "primary_care"),
    ("Low mood (PHQ-2 = 4), otherwise well", v(phq1=2, phq2=2), None, "self_care", "primary_care"),
]
