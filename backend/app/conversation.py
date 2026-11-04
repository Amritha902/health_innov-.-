"""Channel-agnostic quick check, used by WhatsApp (Twilio) and the in-app WhatsApp-style demo.
Same questions and answer schema as the web chat; numbered options suit WhatsApp."""
import re

AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "half": 0.5,
    "واحد": 1, "اثنين": 2, "ثنين": 2, "ثلاث": 3, "ثلاثه": 3, "اربع": 4, "اربعه": 4, "خمس": 5, "خمسه": 5, "ست": 6, "سته": 6,
    "سبع": 7, "سبعه": 7, "ثمان": 8, "ثمانيه": 8, "تسع": 9, "تسعه": 9, "عشر": 10, "عشره": 10, "عشرين": 20, "ثلاثين": 30,
    "اربعين": 40, "خمسين": 50, "ستين": 60, "نص": 0.5, "نصف": 0.5,
}
YES = {"yes", "y", "yeah", "sure", "ok", "okay", "نعم", "اي", "ايه", "ايوه", "ايوا", "اكيد", "صح", "اوكي"}
NO = {"no", "n", "nope", "never", "لا", "مب", "مو", "ابدا", "كلا"}
UNSURE = {"maybe", "unsure", "مادري", "يمكن", "ربما"}
SKIP = {"skip", "pass", "تخطي", "تخطى"}


def norm(s):
    s = (s or "").lower().translate(AR_DIGITS)
    s = re.sub("[إأآ]", "ا", s).replace("ى", "ي").replace("ة", "ه")
    s = re.sub("[ً-ْـ]", "", s)
    return re.sub(r"[^\w\s.]", " ", s).strip()


def number(text):
    t = norm(text)
    m = re.search(r"\d+(?:\.\d+)?", t)
    if m:
        return float(m.group())
    total, found = 0.0, False
    for w in re.split(r"\s+", t):
        w = w[1:] if w.startswith("و") and w[1:] in NUM_WORDS else w
        if w in NUM_WORDS:
            total += NUM_WORDS[w]
            found = True
    return total if found else None


def words(text):
    return set(norm(text).split())


def o(value, en, ar, *keys):
    return {"value": value, "en": en, "ar": ar, "keys": [en, ar, *keys]}


YN = [o("yes", "Yes", "نعم"), o("no", "No", "لا")]
YNU = YN + [o("unsure", "Not sure", "لست متأكداً")]

STEPS = [
    {"id": "consent_review", "type": "choice", "opts": YN,
     "en": "If something needs a doctor, may a licensed doctor review your summary? You still get it if you say no.",
     "ar": "إذا احتاج الأمر إلى طبيب، هل تسمح لطبيب مرخّص بمراجعة ملخصك؟ ستحصل عليه حتى لو رفضت."},
    {"id": "age", "type": "number", "min": 18, "max": 80, "en": "How old are you?", "ar": "كم عمرك؟"},
    {"id": "height_cm", "type": "number", "min": 130, "max": 220, "skip": True, "en": "Height in cm? (or 'skip')", "ar": "طولك بالسنتيمتر؟ (أو «تخطي»)"},
    {"id": "weight_kg", "type": "number", "min": 40, "max": 250, "skip": True, "en": "Weight in kg? (or 'skip')", "ar": "وزنك بالكيلوغرام؟ (أو «تخطي»)"},
    {"id": "reason", "type": "choice", "multi": True, "en": "What brings you here?", "ar": "ما الذي جاء بك؟",
     "opts": [o("general", "General check", "فحص عام"), o("future", "Planning ahead", "تخطيط للمستقبل"),
              o("trying", "Trying for a child now", "نحاول الإنجاب الآن", "trying", "نحاول"), o("fitness", "Energy / fitness", "الطاقة / اللياقة")]},
    {"id": "months_trying", "type": "number", "min": 0, "max": 240, "when": lambda a: "trying" in (a.get("reason") or []),
     "en": "How many months have you been trying?", "ar": "منذ كم شهراً تحاولون؟"},
    {"id": "smoking", "type": "choice", "en": "Cigarettes or vaping?", "ar": "السجائر أو السجائر الإلكترونية؟",
     "opts": [o("never", "Never", "أبداً"), o("former", "I stopped", "أقلعت"), o("occasional", "Sometimes", "أحياناً"), o("daily", "Daily", "يومياً", "كل يوم")]},
    {"id": "waterpipe", "type": "choice", "en": "Shisha, midwakh or dokha?", "ar": "الشيشة أو المدواخ أو الدوخة؟",
     "opts": [o("never", "Never", "أبداً"), o("monthly", "Now and then", "أحياناً"), o("weekly", "Weekly", "أسبوعياً"), o("daily", "Daily", "يومياً")]},
    {"id": "aas", "type": "choice", "en": "No judgement: testosterone, steroids or SARMs for the gym or any reason?",
     "ar": "بلا أحكام: هل استخدمت التستوستيرون أو المنشطات أو SARMs للنادي أو لأي سبب؟",
     "opts": [o("never", "Never", "أبداً"), o("past_old", "Over a year ago", "قبل أكثر من سنة"), o("past_recent", "In the last year", "خلال السنة الماضية"),
              o("current", "Currently", "حالياً"), o("skip", "Prefer not to say", "أفضّل عدم الإجابة")]},
    {"id": "sitting_h", "type": "number", "min": 0, "max": 20, "en": "Hours sitting on a normal day (desk + car + sofa)?", "ar": "كم ساعة تجلس في يوم عادي (مكتب + سيارة + أريكة)؟"},
    {"id": "sleep_h", "type": "number", "min": 2, "max": 14, "en": "Hours you actually sleep on a typical night?", "ar": "كم ساعة تنام فعلياً في ليلة عادية؟"},
    {"id": "snore", "type": "choice", "opts": YNU, "en": "Loud snoring, or has anyone seen you stop breathing in sleep?", "ar": "هل تشخر بصوت عالٍ أو لاحظ أحد توقف تنفسك أثناء النوم؟"},
    {"id": "tired", "type": "choice", "opts": YN, "en": "Often sleepy during the day?", "ar": "هل تشعر غالباً بالنعاس نهاراً؟"},
    {"id": "underwear", "type": "choice", "en": "Usual underwear?", "ar": "ملابسك الداخلية عادةً؟",
     "opts": [o("loose", "Loose (boxers, sirwal)", "فضفاضة (بوكسر، سروال)"), o("mixed", "Mix", "مختلطة"), o("tight", "Tight (briefs)", "ضيقة")]},
    {"id": "phq1", "type": "choice", "en": "Last 2 weeks, how often have you had little interest or pleasure in things?", "ar": "خلال الأسبوعين الماضيين، كم مرة شعرت بقلة الاهتمام أو المتعة؟",
     "opts": [o(0, "Not at all", "إطلاقاً"), o(1, "Some days", "بعض الأيام"), o(2, "More than half the days", "أكثر من نصف الأيام"), o(3, "Nearly every day", "تقريباً كل يوم")]},
    {"id": "phq2", "type": "choice", "en": "And how often have you felt down or hopeless?", "ar": "خلال الأسبوعين الماضيين، كم مرة شعرت بالإحباط أو اليأس؟",
     "opts": [o(0, "Not at all", "إطلاقاً"), o(1, "Some days", "بعض الأيام"), o(2, "More than half the days", "أكثر من نصف الأيام"), o(3, "Nearly every day", "تقريباً كل يوم")]},
    {"id": "red_flags", "type": "choice", "multi": True, "en": "Right now, any of these? (or 'none')", "ar": "هل لديك الآن أيٌّ مما يلي؟ (أو «لا شيء»)",
     "opts": [o("none", "None", "لا شيء", "no", "لا"), o("rf_torsion", "Sudden testicle pain or swelling", "ألم أو تورم مفاجئ في الخصية"),
              o("rf_lump", "A new lump", "كتلة جديدة"), o("rf_hematospermia", "Blood in semen", "دم في السائل المنوي"),
              o("rf_mood", "Thoughts of harming myself", "أفكار لإيذاء نفسي")]},
]

INTRO = {
    "en": "Welcome to Riaya, a private men's health check. No app, no name, about 3 minutes.\nReply *delete* at any time to erase everything, or *restart* to begin again.",
    "ar": "أهلاً بك في رعاية، فحص خاص لصحة الرجل. بلا تطبيق ولا اسم، نحو ٣ دقائق.\nأرسل *حذف* في أي وقت لمسح كل شيء، أو *إعادة* للبدء من جديد.",
}
NOT_UNDERSTOOD = {"en": "Sorry, I didn't catch that. Reply with a number from the list.", "ar": "عذراً، لم أفهم. أرسل رقماً من القائمة."}
VOICE_NOTE = {"en": "Voice messages can't be read in this chat yet. Please type, or reply with a number.",
              "ar": "لا يمكن قراءة الرسائل الصوتية هنا بعد. اكتب أو أرسل رقماً من فضلك."}


def _visible(step, answers):
    return "when" not in step or step["when"](answers)


def current(state):
    while state["step"] < len(STEPS) and not _visible(STEPS[state["step"]], state["answers"]):
        state["step"] += 1
    return STEPS[state["step"]] if state["step"] < len(STEPS) else None


def render(step, lang):
    text = step[lang]
    if step["type"] == "choice":
        text += "\n" + "\n".join(f"{i + 1}. {x[lang]}" for i, x in enumerate(step["opts"]))
        if step.get("multi"):
            text += "\n" + ("(you can send several, e.g. 1 3)" if lang == "en" else "(يمكنك إرسال أكثر من رقم، مثل 1 3)")
    return text


def interpret(step, text):
    t = norm(text)
    ws = words(text)
    if ws & SKIP and (step.get("skip") or step["type"] == "choice"):
        return "skip"
    if step["type"] == "number":
        n = number(text)
        return n if n is not None and step["min"] <= n <= step["max"] else None
    opts = step["opts"]
    picks = [int(x) - 1 for x in re.findall(r"\b\d+\b", t) if 0 < int(x) <= len(opts)]
    if not picks:
        for i, x in enumerate(opts):
            keys = [norm(k) for k in x["keys"]]
            if any(k and (k in ws or (" " in k and k in t)) for k in keys):
                picks.append(i)
        if not picks and (opts is YN or opts is YNU):
            if ws & YES:
                picks = [0]
            elif ws & NO:
                picks = [1]
            elif ws & UNSURE and opts is YNU:
                picks = [2]
    if not picks:
        return None
    if step.get("multi"):
        vals = [opts[i]["value"] for i in dict.fromkeys(picks)]
        return [] if vals == ["none"] else [v for v in vals if v != "none"]
    return opts[picks[0]]["value"]


def new_state():
    return {"lang": None, "step": 0, "answers": {}, "review": False, "done": False}


def handle(state, text, has_media=False):
    """Returns (replies: list[str], event) where event is None, 'start', 'answers', 'finish', 'delete' or 'restart'."""
    t = norm(text)
    if t in ("delete", "حذف", "امسح"):
        return [], "delete"
    if t in ("restart", "اعاده") or (state.get("done") and t in ("start", "hi", "hello", "مرحبا", "السلام عليكم")):
        return [], "restart"
    if state["lang"] is None:
        if t in ("1", "عربي", "العربيه", "arabic"):
            state["lang"] = "ar"
        elif t in ("2", "english", "انجليزي", "en"):
            state["lang"] = "en"
        else:
            return ["Riaya | رعاية\n1. العربية\n2. English"], None
        return [INTRO[state["lang"]], render(current(state), state["lang"])], "start"
    lang = state["lang"]
    if state["done"]:
        return [("Your summary is above. Reply *restart* for a new check or *delete* to erase everything."
                 if lang == "en" else "ملخصك أعلاه. أرسل *إعادة* لفحص جديد أو *حذف* لمسح كل شيء.")], None
    if has_media and not t:
        return [VOICE_NOTE[lang]], None
    step = current(state)
    value = interpret(step, text)
    if value is None:
        return [NOT_UNDERSTOOD[lang] if step["type"] == "choice" else
                ("Please send a number." if lang == "en" else "أرسل رقماً من فضلك."), render(step, lang)], None
    if step["id"] == "consent_review":
        state["review"] = value == "yes"
    elif step["id"] == "snore" and value == "yes":
        state["answers"]["snore"] = "yes"
        state["answers"]["observed"] = "unsure"
    elif value != "skip":
        state["answers"][step["id"]] = value
    state["step"] += 1
    nxt = current(state)
    if nxt is None:
        state["done"] = True
        return [], "finish"
    return [render(nxt, lang)], "answers"
