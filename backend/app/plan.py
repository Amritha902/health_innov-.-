"""Personal action plan: one concrete, positive step per modifiable driver.
Sperm take about 74 days to develop, so changes show in roughly 3 months."""

ACTIONS = {
    "smoking": ("Stopping smoking improves count, movement and shape. Free support is available through your doctor.",
                "الإقلاع عن التدخين يحسّن العدد والحركة والشكل. الدعم المجاني متاح عبر طبيبك."),
    "waterpipe": ("One shisha session can equal many cigarettes of smoke. Cutting down counts.",
                  "جلسة شيشة واحدة قد تعادل دخان عدد كبير من السجائر. التقليل يُحدث فرقاً."),
    "alcohol": ("Keeping alcohol low or none supports hormones and sperm quality.",
                "تقليل الكحول أو الامتناع عنه يدعم الهرمونات وجودة الحيوانات المنوية."),
    "cannabis": ("Stopping cannabis is linked to better sperm count.", "التوقف عن القنب مرتبط بعدد أفضل للحيوانات المنوية."),
    "aas": ("Talk to a men's health doctor before stopping a cycle — supervised recovery restores natural production in most men.",
            "تحدّث مع طبيب صحة الرجل قبل إيقاف الكورس — التعافي تحت الإشراف يعيد الإنتاج الطبيعي لدى معظم الرجال."),
    "opioids": ("Ask your doctor about alternatives to long-term strong painkillers.", "اسأل طبيبك عن بدائل للمسكنات القوية طويلة الأمد."),
    "medications": ("Don't stop any medicine — but ask your doctor whether a fertility-friendly alternative exists.",
                    "لا توقف أي دواء — لكن اسأل طبيبك عن بديل مناسب للخصوبة."),
    "sedentary": ("Stand or walk for 5 minutes every hour; aim for 7,000+ steps a day.", "قف أو امشِ ٥ دقائق كل ساعة؛ واهدف إلى أكثر من ٧٠٠٠ خطوة يومياً."),
    "western_diet": ("Swap processed meat and sugary snacks for fish, nuts, vegetables and whole grains.",
                     "استبدل اللحوم المصنعة والوجبات السكرية بالسمك والمكسرات والخضروات والحبوب الكاملة."),
    "late_eating": ("Finish your last meal 2–3 hours before sleep.", "أنهِ وجبتك الأخيرة قبل النوم بساعتين إلى ثلاث."),
    "caffeine_late": ("Move coffee, karak and energy drinks to before 2 pm.", "انقل القهوة والكرك ومشروبات الطاقة إلى ما قبل الثانية ظهراً."),
    "glycaemic_spikes": ("Night-time glucose spikes: pair carbs with protein and avoid sweet drinks after 9 pm.",
                         "ارتفاعات السكر الليلية: اجمع النشويات مع البروتين وتجنب المشروبات المحلاة بعد التاسعة مساءً."),
    "sleep_loss": ("Protect 7+ hours: a fixed wake-up time is the strongest lever.", "احمِ ٧ ساعات نوم أو أكثر: ثبات وقت الاستيقاظ هو الأقوى أثراً."),
    "shift_work": ("On night shifts, keep the same sleep block each day and use blackout curtains.",
                   "في المناوبات الليلية، حافظ على نفس فترة النوم يومياً واستخدم ستائر معتمة."),
    "circadian": ("Keep weekend sleep within an hour of weekdays.", "اجعل نوم عطلة الأسبوع قريباً من أيام العمل (بفارق ساعة)."),
    "screen_night": ("Put the phone away 60 minutes before sleep, or use night mode at minimum.",
                     "ضع الهاتف جانباً قبل النوم بستين دقيقة، أو استخدم الوضع الليلي على الأقل."),
    "screen_time_high": ("Set a daily screen-time limit and replace one hour with a walk.", "حدّد وقتاً يومياً للشاشة واستبدل ساعة منه بالمشي."),
    "osa": ("Snoring and daytime tiredness can be checked with a simple home sleep test.", "يمكن فحص الشخير والتعب النهاري باختبار نوم منزلي بسيط."),
    "obesity": ("Losing 5–10% of body weight improves hormones. Small steady changes win.", "خسارة ٥–١٠٪ من الوزن تحسّن الهرمونات. التغييرات الصغيرة الثابتة هي الأنجح."),
    "diabetes": ("Good blood-sugar control protects sperm DNA. Keep up with your HbA1c checks.", "ضبط السكر يحمي الحمض النووي للحيوانات المنوية. تابع فحص HbA1c."),
    "tight_underwear": ("Switch to loose cotton boxers or sirwal.", "استبدلها بملابس داخلية قطنية فضفاضة أو سروال."),
    "synthetic_textile": ("Choose cotton or linen for underwear — cooler in UAE heat.", "اختر القطن أو الكتان للملابس الداخلية — أبرد في حرارة الإمارات."),
    "hot_bath": ("Pause sauna and jacuzzi for 3 months.", "أوقف الساونا والجاكوزي لمدة ٣ أشهر."),
    "laptop_lap": ("Use a desk or lap tray for your laptop.", "استخدم مكتباً أو حاملاً للحاسوب المحمول."),
    "phone_pocket": ("Keep the phone in a jacket pocket or bag.", "ضع الهاتف في جيب السترة أو في حقيبة."),
    "occupational_heat": ("Take cool breaks out of the heat and wear loose, breathable clothing.", "خذ استراحات باردة بعيداً عن الحرارة وارتدِ ملابس فضفاضة جيدة التهوية."),
    "edc": ("Use gloves and ventilation at work; wash before eating.", "استخدم القفازات والتهوية في العمل؛ واغسل يديك قبل الأكل."),
    "low_sun": ("Get 15 minutes of morning sun or ask about a vitamin D test.", "تعرّض لشمس الصباح ١٥ دقيقة أو اسأل عن فحص فيتامين د."),
    "vitd_def": ("Take vitamin D as advised by your doctor.", "تناول فيتامين د حسب إرشاد طبيبك."),
    "psych_stress": ("Ten minutes a day of something that resets you — a walk, prayer, breathing — measurably lowers stress hormones.",
                     "عشر دقائق يومياً لما يعيد توازنك — مشي، صلاة، تنفس عميق — تخفض هرمونات التوتر بشكل ملموس."),
    "low_mood": ("Talking to someone helps. A confidential conversation with a professional is a sign of strength.",
                 "الحديث مع أحد يساعد. محادثة سرية مع مختص علامة قوة."),
    "genital_infection": ("A quick test makes sure any past infection is fully cleared.", "فحص سريع يتأكد من زوال أي التهاب سابق تماماً."),
    "hypogonadism": ("A morning testosterone test gives a clear answer.", "فحص التستوستيرون الصباحي يعطي إجابة واضحة."),
    "varicocele": ("Varicocele is treatable — a specialist can advise whether treatment would help.", "دوالي الخصية قابلة للعلاج — يمكن للمختص تحديد ما إذا كان العلاج مفيداً."),
}


def build(shapley, graph, inputs, limit=3):
    items = []
    for node, contribution in shapley.items():
        n = graph.nodes[node]
        if contribution <= 0 or not n.get("modifiable") or node not in ACTIONS:
            continue
        en, ar = ACTIONS[node]
        path = graph.paths(node)
        items.append({
            "node": node, "label": n["label"], "contribution": contribution,
            "action_en": en, "action_ar": ar,
            "why": path[0] if path else None,
        })
    return items[:limit], items[limit:]
