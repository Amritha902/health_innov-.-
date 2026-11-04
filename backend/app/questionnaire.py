"""Intake questionnaire (Arabic / English).

Wording rules (from the cultural research):
- never "infertility", "problem", "at risk", "suffering"
- no assumption of marriage, children or family plans
- every sensitive item can be skipped ("prefer not to say") and is marked as such
- validated instruments are used verbatim where licensing allows: STOP-Bang, AUDIT-C, PHQ-2, PSS-4, ADAM
"""

SKIP = {"value": "skip", "en": "Prefer not to say", "ar": "أفضّل عدم الإجابة"}


def opt(value, en, ar):
    return {"value": value, "en": en, "ar": ar}


YES_NO = [opt("yes", "Yes", "نعم"), opt("no", "No", "لا")]
YES_NO_UNSURE = YES_NO + [opt("unsure", "Not sure", "لست متأكداً")]
FREQ_0_4 = [opt(0, "Never", "أبداً"), opt(1, "Almost never", "نادراً جداً"), opt(2, "Sometimes", "أحياناً"),
            opt(3, "Fairly often", "غالباً"), opt(4, "Very often", "كثيراً جداً")]
FREQ_0_4_REV = [dict(o, score=4 - o["value"]) for o in FREQ_0_4]
PHQ = [opt(0, "Not at all", "إطلاقاً"), opt(1, "Several days", "عدة أيام"),
       opt(2, "More than half the days", "أكثر من نصف الأيام"), opt(3, "Nearly every day", "تقريباً كل يوم")]


def q(id, section, type, en, ar, options=None, sensitive=False, optional=False, show_if=None, unit=None,
      min=None, max=None, instrument=None, help_en=None, help_ar=None):
    d = {k: v for k, v in dict(id=id, section=section, type=type, en=en, ar=ar, options=options,
                                sensitive=sensitive, optional=optional or sensitive, show_if=show_if, unit=unit,
                                min=min, max=max, instrument=instrument, help_en=help_en, help_ar=help_ar).items()
         if v is not None}
    if sensitive and options is not None:
        d["options"] = options + [SKIP]
    return d


SECTIONS = [
    {"id": "about", "en": "About you", "ar": "عنك"},
    {"id": "goals", "en": "Your goals", "ar": "أهدافك"},
    {"id": "daily", "en": "Daily habits", "ar": "عاداتك اليومية"},
    {"id": "sleep", "en": "Sleep & screens", "ar": "النوم والشاشات"},
    {"id": "heat", "en": "Heat, clothing & devices", "ar": "الحرارة والملابس والأجهزة"},
    {"id": "mind", "en": "Energy, mood & stress", "ar": "الطاقة والمزاج والضغط"},
    {"id": "history", "en": "Health history", "ar": "التاريخ الصحي"},
    {"id": "now", "en": "Anything right now?", "ar": "هل هناك شيء الآن؟"},
]

QUESTIONS = [
    # about
    q("age", "about", "number", "Your age", "عمرك", unit="years", min=18, max=80),
    q("height_cm", "about", "number", "Height", "الطول", unit="cm", min=130, max=220),
    q("weight_kg", "about", "number", "Weight", "الوزن", unit="kg", min=40, max=250),
    q("waist_cm", "about", "number", "Waist (at the navel), if you know it", "محيط الخصر (عند السرة) إن كنت تعرفه",
      unit="cm", min=50, max=200, optional=True),
    q("neck_cm", "about", "number", "Collar / neck size, if you know it", "مقاس الرقبة إن كنت تعرفه",
      unit="cm", min=25, max=60, optional=True),
    q("background", "about", "choice", "Which best describes your background? (used only to pick the right waist cut-off)",
      "ما الذي يصف خلفيتك؟ (يُستخدم فقط لاختيار مقياس الخصر المناسب)", [
          opt("arab", "Arab / Middle Eastern", "عربي / شرق أوسطي"), opt("south_asian", "South Asian", "جنوب آسيوي"),
          opt("east_asian", "East / South-East Asian", "شرق / جنوب شرق آسيوي"), opt("european", "European", "أوروبي"),
          opt("african", "African", "أفريقي"), opt("other", "Other", "أخرى")], sensitive=True),
    # goals: no assumptions about marriage or children
    q("reason", "goals", "multi", "What brings you here? Choose any.", "ما الذي جاء بك؟ اختر ما ينطبق.", [
        opt("general", "A general health check", "فحص صحي عام"),
        opt("future", "Planning ahead for a future family", "التخطيط المسبق لعائلة في المستقبل"),
        opt("trying", "We are trying for a child now", "نحاول الإنجاب حالياً"),
        opt("concern", "A specific concern", "استفسار محدد"),
        opt("fitness", "Fitness / energy / performance", "اللياقة / الطاقة / الأداء")], optional=True),
    q("months_trying", "goals", "number", "For how many months?", "منذ كم شهراً؟", unit="months", min=0, max=240,
      show_if={"reason": "trying"}, optional=True),
    q("partner_age", "goals", "number", "Partner's age (optional, it changes the recommended timing)",
      "عمر الزوجة (اختياري، يؤثر على التوقيت المقترح)", unit="years", min=16, max=60,
      show_if={"reason": "trying"}, optional=True),
    # daily habits
    q("smoking", "daily", "choice", "Cigarettes or vaping", "السجائر أو السجائر الإلكترونية", [
        opt("never", "Never", "لا أدخن"), opt("former", "Stopped", "أقلعت"),
        opt("occasional", "Occasionally", "أحياناً"), opt("daily", "Daily", "يومياً")]),
    q("cigs_per_day", "daily", "number", "About how many per day?", "كم سيجارة تقريباً في اليوم؟", min=0, max=80,
      show_if={"smoking": "daily"}, optional=True),
    q("waterpipe", "daily", "choice", "Shisha, midwakh or dokha", "الشيشة أو المدواخ أو الدوخة", [
        opt("never", "Never", "أبداً"), opt("monthly", "A few times a month", "عدة مرات في الشهر"),
        opt("weekly", "Weekly", "أسبوعياً"), opt("daily", "Daily", "يومياً")]),
    q("audit1", "daily", "choice", "How often do you have a drink containing alcohol? Many people never do — choose 'Never' if so.",
      "كم مرة تتناول مشروباً يحتوي على الكحول؟ كثيرون لا يتناولونه أبداً — اختر «أبداً» إن كان كذلك.", [
          opt(0, "Never", "أبداً"), opt(1, "Monthly or less", "مرة شهرياً أو أقل"), opt(2, "2–4 times a month", "٢–٤ مرات شهرياً"),
          opt(3, "2–3 times a week", "٢–٣ مرات أسبوعياً"), opt(4, "4+ times a week", "٤ مرات أو أكثر أسبوعياً")],
      sensitive=True, instrument="AUDIT-C"),
    q("audit2", "daily", "choice", "Drinks on a typical day when drinking", "عدد المشروبات في يوم الشرب المعتاد", [
        opt(0, "1–2", "١–٢"), opt(1, "3–4", "٣–٤"), opt(2, "5–6", "٥–٦"), opt(3, "7–9", "٧–٩"), opt(4, "10+", "١٠ أو أكثر")],
      sensitive=True, show_if={"audit1": [1, 2, 3, 4]}, instrument="AUDIT-C"),
    q("audit3", "daily", "choice", "How often 6 or more drinks on one occasion?", "كم مرة تتناول ٦ مشروبات أو أكثر في المرة الواحدة؟", [
        opt(0, "Never", "أبداً"), opt(1, "Less than monthly", "أقل من مرة شهرياً"), opt(2, "Monthly", "شهرياً"),
        opt(3, "Weekly", "أسبوعياً"), opt(4, "Daily or almost", "يومياً تقريباً")],
      sensitive=True, show_if={"audit1": [1, 2, 3, 4]}, instrument="AUDIT-C"),
    q("cannabis", "daily", "choice", "Cannabis or other recreational substances", "القنب أو مواد ترفيهية أخرى", [
        opt("never", "Never", "أبداً"), opt("past", "In the past", "في الماضي"), opt("current", "Currently", "حالياً")],
      sensitive=True),
    q("aas", "daily", "choice", "Testosterone, anabolic steroids, SARMs or 'cycles' — for gym or any reason",
      "التستوستيرون أو المنشطات البنائية أو SARMs أو «الكورسات» — للنادي أو لأي سبب", [
          opt("never", "Never", "أبداً"), opt("past_old", "More than a year ago", "قبل أكثر من سنة"),
          opt("past_recent", "Within the last year", "خلال السنة الماضية"), opt("current", "Currently", "حالياً")],
      sensitive=True, help_en="This is one of the most common and most reversible reasons for low sperm production. Your answer stays private.",
      help_ar="هذا من أكثر الأسباب شيوعاً لانخفاض إنتاج الحيوانات المنوية، وغالباً ما يكون قابلاً للعكس. إجابتك تبقى خاصة."),
    q("sitting_h", "daily", "number", "Hours sitting on a typical day (desk, car, sofa)", "ساعات الجلوس في يوم معتاد (مكتب، سيارة، أريكة)",
      unit="h", min=0, max=20),
    q("exercise_days", "daily", "number", "Days per week with 30+ minutes of exercise", "عدد أيام الأسبوع التي تمارس فيها الرياضة ٣٠ دقيقة أو أكثر",
      min=0, max=7),
    q("fast_food", "daily", "choice", "Fast food, processed meat or sugary snacks", "الوجبات السريعة أو اللحوم المصنعة أو الوجبات السكرية", [
        opt(0, "Rarely", "نادراً"), opt(1, "1–3 times a week", "١–٣ مرات أسبوعياً"), opt(2, "4+ times a week", "٤ مرات أو أكثر أسبوعياً")]),
    q("fruit_veg", "daily", "choice", "Fruit and vegetable servings per day", "حصص الفواكه والخضروات يومياً", [
        opt(0, "0–1", "٠–١"), opt(1, "2–4", "٢–٤"), opt(2, "5 or more", "٥ أو أكثر")]),
    q("fish", "daily", "choice", "Fish per week", "السمك أسبوعياً", [
        opt(0, "Rarely", "نادراً"), opt(1, "Once", "مرة"), opt(2, "Twice or more", "مرتين أو أكثر")]),
    q("late_meals", "daily", "number", "Nights per week you eat a meal or sugary drink after 9 pm", "عدد الليالي أسبوعياً التي تتناول فيها وجبة أو مشروباً سكرياً بعد التاسعة مساءً",
      min=0, max=7),
    q("late_caffeine", "daily", "number", "Days per week with coffee, tea or energy drinks after 4 pm", "عدد الأيام أسبوعياً التي تشرب فيها القهوة أو الشاي أو مشروبات الطاقة بعد الرابعة عصراً",
      min=0, max=7),
    # sleep & screens
    q("sleep_h", "sleep", "number", "Hours of actual sleep on a typical night", "ساعات النوم الفعلية في ليلة معتادة", unit="h", min=2, max=14),
    q("shift", "sleep", "choice", "Work schedule", "جدول العمل", [
        opt("day", "Regular daytime", "نهاري منتظم"), opt("rotating", "Rotating shifts", "مناوبات متغيرة"), opt("night", "Mostly nights", "ليلي غالباً")]),
    q("snore", "sleep", "yesno", "Do you snore loudly (heard through a closed door or others complain)?", "هل تشخر بصوت عالٍ (يُسمع من خلف باب مغلق أو يشتكي الآخرون)؟",
      YES_NO_UNSURE, instrument="STOP-Bang"),
    q("tired", "sleep", "yesno", "Do you often feel tired or sleepy during the day?", "هل تشعر غالباً بالتعب أو النعاس خلال النهار؟", YES_NO, instrument="STOP-Bang"),
    q("observed", "sleep", "yesno", "Has anyone seen you stop breathing or choke during sleep?", "هل رآك أحد تتوقف عن التنفس أو تختنق أثناء النوم؟",
      YES_NO_UNSURE, instrument="STOP-Bang"),
    q("bp", "sleep", "yesno", "Have you been told you have high blood pressure?", "هل قيل لك إن لديك ارتفاعاً في ضغط الدم؟", YES_NO_UNSURE, instrument="STOP-Bang"),
    q("screen_h", "sleep", "number", "Hours per day on phone/TV/gaming outside work", "ساعات استخدام الهاتف/التلفاز/الألعاب يومياً خارج العمل",
      unit="h", min=0, max=18),
    q("screen_bed", "sleep", "choice", "Screens in the last hour before sleep", "استخدام الشاشات في الساعة الأخيرة قبل النوم", [
        opt(0, "Rarely", "نادراً"), opt(1, "Some nights", "بعض الليالي"), opt(2, "Most nights", "معظم الليالي")]),
    # heat, clothing, devices
    q("underwear", "heat", "choice", "Usual underwear", "الملابس الداخلية المعتادة", [
        opt("loose", "Loose (boxers, sirwal)", "فضفاضة (بوكسر، سروال)"), opt("mixed", "Mix", "مختلطة"),
        opt("tight", "Tight (briefs, compression)", "ضيقة (سليب، ضاغطة)")]),
    q("underwear_fabric", "heat", "choice", "Usual underwear fabric", "قماش الملابس الداخلية المعتاد", [
        opt("natural", "Mostly cotton / linen", "قطن / كتان غالباً"), opt("mixed", "Mixed", "مختلط"),
        opt("synthetic", "Mostly synthetic (polyester, nylon)", "صناعي غالباً (بوليستر، نايلون)"), opt("unsure", "Not sure", "لست متأكداً")]),
    q("hot_bath", "heat", "choice", "Sauna, jacuzzi or very hot baths", "الساونا أو الجاكوزي أو الحمامات الساخنة جداً", [
        opt(0, "Rarely", "نادراً"), opt(1, "About weekly", "أسبوعياً تقريباً"), opt(2, "Several times a week", "عدة مرات أسبوعياً")]),
    q("laptop_lap", "heat", "number", "Hours per day with a laptop on your lap", "ساعات وضع الحاسوب المحمول على الحضن يومياً", unit="h", min=0, max=16),
    q("phone_pocket", "heat", "yesno", "Phone in a front trouser pocket most of the day?", "هل تضع الهاتف في الجيب الأمامي للبنطال معظم اليوم؟", YES_NO),
    q("heat_work", "heat", "yesno", "Work outdoors in the heat, or drive more than 2 hours a day?", "هل تعمل في الخارج تحت الحرارة أو تقود أكثر من ساعتين يومياً؟", YES_NO),
    q("chemicals_work", "heat", "yesno", "Regular work contact with pesticides, solvents, paints, fuels or metals?", "هل تتعامل في العمل بانتظام مع المبيدات أو المذيبات أو الدهانات أو الوقود أو المعادن؟", YES_NO),
    q("indoors", "heat", "yesno", "Do you spend almost all daylight hours indoors?", "هل تقضي معظم ساعات النهار في الأماكن المغلقة؟", YES_NO),
    # mind: PSS-4 + PHQ-2 + ADAM
    q("pss1", "mind", "choice", "In the last month, how often have you felt unable to control the important things in your life?",
      "خلال الشهر الماضي، كم مرة شعرت أنك غير قادر على التحكم في الأمور المهمة في حياتك؟", FREQ_0_4, instrument="PSS-4"),
    q("pss2", "mind", "choice", "...felt confident about your ability to handle personal problems?",
      "...شعرت بالثقة في قدرتك على التعامل مع مشكلاتك الشخصية؟", FREQ_0_4_REV, instrument="PSS-4"),
    q("pss3", "mind", "choice", "...felt that things were going your way?", "...شعرت أن الأمور تسير كما تريد؟", FREQ_0_4_REV, instrument="PSS-4"),
    q("pss4", "mind", "choice", "...felt difficulties were piling up so high you could not overcome them?",
      "...شعرت أن الصعوبات تتراكم لدرجة أنك لا تستطيع التغلب عليها؟", FREQ_0_4, instrument="PSS-4"),
    q("phq1", "mind", "choice", "Last 2 weeks: little interest or pleasure in doing things", "خلال الأسبوعين الماضيين: قلة الاهتمام أو المتعة في القيام بالأشياء",
      PHQ, instrument="PHQ-2"),
    q("phq2", "mind", "choice", "Last 2 weeks: feeling down, depressed or hopeless", "خلال الأسبوعين الماضيين: الشعور بالإحباط أو الاكتئاب أو اليأس",
      PHQ, instrument="PHQ-2"),
    q("adam1", "mind", "yesno", "Decrease in sex drive?", "هل انخفضت الرغبة الجنسية؟", YES_NO, sensitive=True, instrument="ADAM"),
    q("adam2", "mind", "yesno", "Lack of energy?", "هل تشعر بنقص في الطاقة؟", YES_NO, instrument="ADAM"),
    q("adam3", "mind", "yesno", "Decrease in strength or endurance?", "هل انخفضت القوة أو القدرة على التحمل؟", YES_NO, instrument="ADAM"),
    q("adam4", "mind", "yesno", "Lost height?", "هل نقص طولك؟", YES_NO, instrument="ADAM"),
    q("adam5", "mind", "yesno", "Decreased enjoyment of life?", "هل قلّ استمتاعك بالحياة؟", YES_NO, instrument="ADAM"),
    q("adam6", "mind", "yesno", "Sad and/or grumpy?", "هل تشعر بالحزن أو العصبية؟", YES_NO, instrument="ADAM"),
    q("adam7", "mind", "yesno", "Erections less strong?", "هل أصبح الانتصاب أضعف؟", YES_NO, sensitive=True, instrument="ADAM"),
    q("adam8", "mind", "yesno", "Recent decline in ability to play sports?", "هل تراجعت قدرتك على ممارسة الرياضة مؤخراً؟", YES_NO, instrument="ADAM"),
    q("adam9", "mind", "yesno", "Falling asleep after dinner?", "هل تغفو بعد العشاء؟", YES_NO, instrument="ADAM"),
    q("adam10", "mind", "yesno", "Recent deterioration in work performance?", "هل تراجع أداؤك في العمل مؤخراً؟", YES_NO, instrument="ADAM"),
    # history
    q("diabetes", "history", "choice", "Blood sugar", "سكر الدم", [
        opt("no", "Normal / never checked", "طبيعي / لم أفحصه"), opt("pre", "Told it is borderline (pre-diabetes)", "قيل لي إنه على الحد (ما قبل السكري)"),
        opt("yes", "Diabetes", "سكري")]),
    q("mumps", "history", "yesno_unsure", "Mumps with swollen testicles after puberty?", "النكاف مع تورم الخصيتين بعد البلوغ؟", YES_NO_UNSURE),
    q("cryptorchidism", "history", "yesno_unsure", "An undescended testicle as a child (incl. surgery for it)?", "خصية معلقة في الطفولة (بما في ذلك جراحة لها)؟", YES_NO_UNSURE),
    q("testis_injury", "history", "yesno", "Injury or surgery to the testicles or groin (incl. hernia repair)?", "إصابة أو جراحة في الخصيتين أو أعلى الفخذ (بما في ذلك إصلاح الفتق)؟", YES_NO),
    q("varicocele", "history", "yesno_unsure", "Told you have a varicocele (enlarged veins above the testicle)?", "هل قيل لك إن لديك دوالي الخصية؟", YES_NO_UNSURE),
    q("infection", "history", "choice", "Ever had a genital or urinary infection with pain, burning or discharge?", "هل أصبت بالتهاب في الجهاز التناسلي أو البولي مع ألم أو حرقة أو إفرازات؟", [
        opt("never", "No", "لا"), opt("treated", "Yes, treated", "نعم، وتمت معالجته"), opt("untreated", "Yes, not sure it was treated / recurrent", "نعم، لست متأكداً من علاجه / متكرر")],
      sensitive=True, help_en="These are common and treatable. Early treatment protects the tubes that carry sperm.",
      help_ar="هذه الالتهابات شائعة وقابلة للعلاج. العلاج المبكر يحمي القنوات الناقلة."),
    q("chemo", "history", "yesno", "Chemotherapy or radiotherapy in the past?", "علاج كيميائي أو إشعاعي في الماضي؟", YES_NO),
    q("meds", "history", "multi", "Regular medicines (choose any)", "أدوية منتظمة (اختر ما ينطبق)", [
        opt("ssri", "Antidepressants", "مضادات الاكتئاب"), opt("finasteride", "Hair-loss / prostate tablets (finasteride, dutasteride)", "أقراص تساقط الشعر / البروستاتا (فيناسترايد، دوتاسترايد)"),
        opt("opioid", "Strong painkillers (opioids, tramadol)", "مسكنات قوية (أفيونات، ترامادول)"), opt("other", "Other long-term medicine", "دواء آخر طويل الأمد")], optional=True),
    q("fever", "history", "yesno", "High fever (above 38.5 °C) in the last 3 months?", "حمى مرتفعة (أعلى من ٣٨٫٥ درجة) خلال الأشهر الثلاثة الماضية؟", YES_NO),
    q("vitd", "history", "yesno_unsure", "Told you have low vitamin D?", "هل قيل لك إن لديك نقصاً في فيتامين د؟", YES_NO_UNSURE),
    q("family_history", "history", "yesno_unsure", "Any male relatives who needed help to have children?", "هل احتاج أحد أقاربك الذكور إلى مساعدة طبية للإنجاب؟", YES_NO_UNSURE, sensitive=True),
    q("parents_related", "history", "yesno_unsure", "Are your parents related by blood (e.g. cousins)?", "هل والداك أقارب (مثل أبناء العمومة)؟", YES_NO_UNSURE, sensitive=True,
      help_en="Common in many families and nothing to worry about on its own. It helps us suggest genetic counselling only when useful.",
      help_ar="أمر شائع في كثير من العائلات ولا يدعو للقلق بحد ذاته. يساعدنا فقط في اقتراح الاستشارة الوراثية عند الحاجة."),
    # right now
    q("red_flags", "now", "multi", "Do any of these apply right now?", "هل ينطبق عليك أيٌّ مما يلي الآن؟", None, optional=True),
]


def red_flag_options(graph):
    ar = {
        "rf_torsion": "ألم أو تورم مفاجئ وشديد في الخصية",
        "rf_lump": "كتلة أو تصلب جديد في الخصية",
        "rf_hematospermia": "دم في السائل المنوي مستمر، أو أي دم بعد سن الأربعين",
        "rf_fever_pain": "ألم وتورم في كيس الصفن مع حمى أو إفرازات",
        "rf_no_ejac": "عدم خروج سائل عند القذف",
        "rf_breast": "تضخم جديد في الثدي مع ضعف الرغبة أو صغر الخصيتين",
        "rf_steroid_stop": "توقفت عن المنشطات/التستوستيرون وأشعر بانهيار (تعب، مزاج منخفض، لا رغبة)",
        "rf_mood": "أفكار لإيذاء النفس أو شعور باليأس",
    }
    return [opt(f["id"], f["text"], ar[f["id"]]) for f in graph.red_flags]


def schema(graph):
    qs = []
    for item in QUESTIONS:
        item = dict(item)
        if item["id"] == "red_flags":
            item["options"] = red_flag_options(graph)
        qs.append(item)
    return {"sections": SECTIONS, "questions": qs}
