/* Understands short spoken or typed answers in Gulf Arabic, MSA and English.
   Deterministic and on-device: no answer text leaves the phone for interpretation. */
(function (root) {
  const AR_DIGITS = { "٠": 0, "١": 1, "٢": 2, "٣": 3, "٤": 4, "٥": 5, "٦": 6, "٧": 7, "٨": 8, "٩": 9 };
  const NUM_WORDS = {
    zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
    thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19, twenty: 20, thirty: 30,
    forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90, hundred: 100, half: 0.5,
    "صفر": 0, "واحد": 1, "وحدة": 1, "اثنين": 2, "اثنان": 2, "ثنين": 2, "ثلاث": 3, "ثلاثة": 3, "ثلاثه": 3, "اربع": 4, "أربع": 4, "اربعة": 4, "أربعة": 4,
    "خمس": 5, "خمسة": 5, "خمسه": 5, "ست": 6, "ستة": 6, "سته": 6, "سبع": 7, "سبعة": 7, "سبعه": 7, "ثمان": 8, "ثمانية": 8, "ثمانيه": 8, "ثمن": 8,
    "تسع": 9, "تسعة": 9, "تسعه": 9, "عشر": 10, "عشرة": 10, "عشره": 10, "احدعش": 11, "احدى عشر": 11, "اثنعش": 12, "اثنا عشر": 12,
    "ثلطعش": 13, "ثلاثطعش": 13, "اربعطعش": 14, "خمسطعش": 15, "ستطعش": 16, "سبعطعش": 17, "ثمنطعش": 18, "تسعطعش": 19,
    "عشرين": 20, "عشرون": 20, "ثمانين": 80, "تسعين": 90, "مية": 100, "مئة": 100, "مائة": 100, "ثلاثين": 30, "ثلاثون": 30, "اربعين": 40, "أربعين": 40, "خمسين": 50, "ستين": 60, "سبعين": 70,
    "نص": 0.5, "نصف": 0.5,
  };

  const norm = s => String(s || "").toLowerCase()
    .replace(/[٠-٩]/g, d => AR_DIGITS[d])
    .replace(/[إأآ]/g, "ا").replace(/ى/g, "ي").replace(/[ًٌٍَُِّْـ]/g, "")
    .replace(/[^\p{L}\p{N}.\s]/gu, " ").replace(/\s+/g, " ").trim();

  function number(text) {
    const t = norm(text);
    const m = t.match(/\d+(?:\.\d+)?/);
    if (m) return parseFloat(m[0]);
    // word numbers: "thirty two", "اثنين وثلاثين", "ست ونص"
    let total = 0, found = false;
    for (const raw of t.split(/\s+|و(?=\S)/)) {
      const w = raw.replace(/^و/, "");
      if (w in NUM_WORDS) { total += NUM_WORDS[w]; found = true; }
      else if (w === "hundred" && found) total *= 100;
    }
    return found ? total : null;
  }

  const YES = ["yes", "yeah", "yep", "sure", "correct", "right", "true", "i do", "نعم", "اي", "ايه", "ايوه", "ايوا", "اكيد", "صح", "بلى", "اجل", "طبعا", "يب", "اوكي", "ok", "okay"];
  const NO = ["no", "nope", "not", "never", "dont", "don t", "nah", "لا", "لاء", "مب", "مو", "ابدا", "ما", "مافي", "ماشي", "كلا", "none"];
  const UNSURE = ["not sure", "dont know", "don t know", "maybe", "unsure", "مادري", "ما ادري", "لا اعرف", "مش متاكد", "مب متاكد", "يمكن", "ربما"];
  const SKIP = ["skip", "prefer not", "pass", "next", "تخطي", "تخطى", "افضل عدم", "ما ابي اجاوب", "بعدين", "التالي"];

  const has = (t, words) => words.some(w => new RegExp(`(^|\\s)${norm(w)}(\\s|$)`).test(t));

  function yesNo(text, allowUnsure = true) {
    const t = norm(text);
    if (has(t, SKIP)) return "skip";
    if (allowUnsure && has(t, UNSURE)) return "unsure";
    if (has(t, NO)) return "no";
    if (has(t, YES)) return "yes";
    return null;
  }

  /* options: [{value, keys: ["word", ...]}] — returns the option whose key appears; earliest/longest match wins */
  function choice(text, options) {
    const t = norm(text);
    if (has(t, SKIP)) return "skip";
    let best = null, bestLen = 0;
    for (const o of options) for (const k of o.keys) {
      const nk = norm(k);
      if (nk && t.includes(nk) && nk.length > bestLen) { best = o.value; bestLen = nk.length; }
    }
    return best;
  }

  root.NLU = { norm, number, yesNo, choice };
  if (typeof module !== "undefined") module.exports = root.NLU;
})(typeof window !== "undefined" ? window : globalThis);
