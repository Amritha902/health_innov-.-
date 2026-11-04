"""Arabic wording for every observation the engine records. Exact phrases first, then templates with numbers."""
import re

EXACT = {
    "Smokes daily": "يدخن يومياً",
    "Smokes occasionally": "يدخن أحياناً",
    "Former smoker": "مدخن سابق",
    "Shisha / midwakh use": "يستخدم الشيشة / المدواخ",
    "Current recreational substance use": "يستخدم مواد ترفيهية حالياً",
    "Testosterone / anabolic steroid use": "استخدام التستوستيرون / المنشطات البنائية",
    "Regular opioid painkillers": "مسكنات أفيونية بانتظام",
    "Long-term medicines that can affect hormones or sperm": "أدوية طويلة الأمد قد تؤثر في الهرمونات أو الحيوانات المنوية",
    "Frequent fast / processed food": "وجبات سريعة / مصنعة بكثرة",
    "Fruit, vegetables and fish": "فواكه وخضروات وسمك",
    "Shift / night work": "عمل بنظام المناوبات / ليلي",
    "Screens in the hour before sleep": "شاشات في الساعة الأخيرة قبل النوم",
    "Blood sugar history": "تاريخ مع سكر الدم",
    "Tight underwear": "ملابس داخلية ضيقة",
    "Synthetic underwear fabric": "قماش ملابس داخلية صناعي",
    "Sauna / jacuzzi / hot baths": "ساونا / جاكوزي / حمامات ساخنة",
    "Phone in front pocket": "الهاتف في الجيب الأمامي",
    "Outdoor heat or long daily driving": "حرارة في الخارج أو قيادة يومية طويلة",
    "Outdoor or driving work": "عمل في الخارج أو قيادة",
    "Regular work contact with chemicals": "تعامل منتظم مع مواد كيميائية في العمل",
    "Occupation with chemical exposure": "مهنة فيها تعرض لمواد كيميائية",
    "Lives or works near heavy traffic / industry": "يسكن أو يعمل قرب حركة مرور كثيفة / منطقة صناعية",
    "Known low vitamin D": "نقص معروف في فيتامين د",
    "Mostly indoors in daylight": "معظم ساعات النهار في الداخل",
    "Mumps orchitis after puberty": "التهاب الخصية بالنكاف بعد البلوغ",
    "Undescended testicle in childhood": "خصية معلقة في الطفولة",
    "Known varicocele": "دوالي خصية معروفة",
    "Past genital / urinary infection": "التهاب سابق في الجهاز التناسلي / البولي",
    "Past chemotherapy / radiotherapy": "علاج كيميائي / إشعاعي سابق",
    "High fever in last 3 months": "حمى مرتفعة خلال الأشهر الثلاثة الماضية",
    "Parents related by blood": "الوالدان أقارب",
    "Male relatives needed fertility help": "أقارب ذكور احتاجوا مساعدة في الإنجاب",
    "Lab: no sperm seen": "المختبر: لم تُشاهد حيوانات منوية",
    "Lab: count below WHO reference": "المختبر: العدد أقل من مرجع منظمة الصحة العالمية",
    "Lab: motility below WHO reference": "المختبر: الحركة أقل من مرجع منظمة الصحة العالمية",
    "Lab: morphology below reference": "المختبر: الشكل أقل من المرجع",
    "Lab: low semen volume": "المختبر: حجم منخفض للسائل المنوي",
    "Home device: low motile sperm concentration": "الجهاز المنزلي: تركيز منخفض للحيوانات المتحركة",
    "Home device: count below WHO reference": "الجهاز المنزلي: العدد أقل من مرجع منظمة الصحة العالمية",
    "Home device: motility below WHO reference": "الجهاز المنزلي: الحركة أقل من مرجع منظمة الصحة العالمية",
    "Home device: no sperm seen": "الجهاز المنزلي: لم تُشاهد حيوانات منوية",
}

N = r"([\d.]+)"
TEMPLATES = [
    (rf"^AUDIT-C {N}/12$", r"AUDIT-C \1/12 (استبيان الكحول)"),
    (rf"^Sits about {N} h/day$", r"يجلس نحو \1 ساعة يومياً"),
    (rf"^Watch: {N} steps/day on average$", r"الساعة: \1 خطوة يومياً في المتوسط"),
    (rf"^Late meals {N} nights/week$", r"وجبات متأخرة \1 ليالٍ أسبوعياً"),
    (rf"^Caffeine after 4 pm {N} days/week$", r"كافيين بعد الرابعة عصراً \1 أيام أسبوعياً"),
    (rf"^Health app: caffeine logged after 4 pm on {N} days/week$", r"تطبيق الصحة: كافيين مسجل بعد الرابعة عصراً في \1 أيام أسبوعياً"),
    (rf"^CGM: {N}% of night readings above 140 mg/dL, CV {N}%$", r"جهاز السكر: \1٪ من القراءات الليلية فوق 140 ملغ/دسل، التذبذب \2٪"),
    (rf"^Watch: {N} h average sleep$", r"الساعة: \1 ساعة نوم في المتوسط"),
    (rf"^Sleeps about {N} h$", r"ينام نحو \1 ساعة"),
    (rf"^Watch: weekend sleep shifts by {N} h$", r"الساعة: يتغير النوم في عطلة الأسبوع بمقدار \1 ساعة"),
    (rf"^{N} h/day recreational screen time$", r"\1 ساعة يومياً أمام الشاشات للترفيه"),
    (rf"^STOP-Bang {N}/8$", r"STOP-Bang \1/8 (استبيان انقطاع النفس أثناء النوم)"),
    (rf"^Watch: oxygen below 90% on {N} nights$", r"الساعة: انخفض الأكسجين عن 90٪ في \1 ليالٍ"),
    (rf"^BMI {N}$", r"مؤشر كتلة الجسم \1"),
    (rf"^Waist {N} cm \(cut-off {N} cm\)$", r"الخصر \1 سم (الحد \2 سم)"),
    (rf"^Laptop on lap {N} h/day$", r"الحاسوب على الحضن \1 ساعة يومياً"),
    (rf"^PSS-4 {N}/16$", r"PSS-4 \1/16 (استبيان الضغط)"),
    (rf"^PHQ-2 {N}/6$", r"PHQ-2 \1/6 (استبيان المزاج)"),
    (rf"^ADAM screen positive \({N} yes\)$", r"فحص ADAM إيجابي (\1 إجابات بنعم)"),
    (rf"^Age {N}$", r"العمر \1"),
    (rf"^Lab: concentration {N} M/mL$", r"المختبر: التركيز \1 مليون/مل"),
    (rf"^Home device: concentration {N} M/mL$", r"الجهاز المنزلي: التركيز \1 مليون/مل"),
    (rf"^Lab: testosterone {N} nmol/L$", r"المختبر: التستوستيرون \1 نانومول/لتر"),
    (rf"^Lab: FSH {N} IU/L$", r"المختبر: FSH ‏\1 وحدة/لتر"),
    (rf"^Lab: HbA1c {N}%$", r"المختبر: السكر التراكمي \1٪"),
    (rf"^Lab: vitamin D {N} ng/mL$", r"المختبر: فيتامين د \1 نانوغرام/مل"),
    (r"^Home test \((.+)\) below its cut-off$", r"الفحص المنزلي (\1) أقل من حده"),
]


def to_ar(text):
    """Arabic for a recorded observation; None if no translation is known (callers then keep the original)."""
    if text in EXACT:
        return EXACT[text]
    for pat, rep in TEMPLATES:
        if re.match(pat, text):
            return re.sub(pat, rep, text)
    return None


def translate(text):
    return to_ar(text) or text
