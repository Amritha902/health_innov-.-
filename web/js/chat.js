/* "Talk it through": the quick check as a conversation. Same answer schema and backend as the detailed form. */
const C = {
  en: { voice: "Voice", send: "Send", typeHere: "Type or tap the mic…", listening: "Listening…", notUnderstood: "Sorry, I didn't catch that. You can also tap an option.",
        micNote: "Your browser's speech service turns speech into text; only the text answer is saved.", noMic: "Voice input isn't available in this browser — type or tap instead.",
        working: "Preparing your summary…", full: "See my full summary", more: "Add more detail (devices, tests)", voices: { auto: "Default voice" },
        start: "Start with voice", startText: "Start without voice", handsFree: "Hands-free", private: "Private mode (speech stays on this phone)",
        loading: p => `Preparing on-phone speech model ${p}%…`, thinking: "Understanding…", micDenied: "Microphone access was blocked. Allow it in your browser settings, or type instead.",
        noVoiceLang: "This phone has no Arabic voice installed, so questions are shown as text." },
  ar: { voice: "الصوت", send: "إرسال", typeHere: "اكتب أو اضغط على الميكروفون…", listening: "أستمع إليك…", notUnderstood: "عذراً، لم أفهم. يمكنك أيضاً اختيار أحد الخيارات.",
        micNote: "تحوّل خدمة المتصفح الكلام إلى نص؛ ويُحفظ نص الإجابة فقط.", noMic: "الإدخال الصوتي غير متاح في هذا المتصفح — اكتب أو اختر بدلاً من ذلك.",
        working: "جارٍ إعداد ملخصك…", full: "اعرض ملخصي الكامل", more: "أضف تفاصيل أكثر (الأجهزة، الفحوصات)", voices: { auto: "الصوت الافتراضي" },
        start: "ابدأ بالصوت", startText: "ابدأ بدون صوت", handsFree: "بدون استخدام اليدين", private: "الوضع الخاص (يبقى الكلام على هذا الهاتف)",
        loading: p => `جارٍ تجهيز نموذج الكلام على الهاتف ${p}٪…`, thinking: "جارٍ الفهم…", micDenied: "تم حظر الميكروفون. اسمح به من إعدادات المتصفح، أو اكتب بدلاً من ذلك.",
        noVoiceLang: "لا يوجد صوت عربي مثبت على هذا الهاتف، لذا تظهر الأسئلة كنص." },
};
const o = (value, en, ar, keys = []) => ({ value, en, ar, keys: [en, ar, ...keys] });
const YN = [o("yes", "Yes", "نعم"), o("no", "No", "لا")];
const YNU = [...YN, o("unsure", "Not sure", "لست متأكداً")];
const SKIPO = o("skip", "Prefer not to say", "أفضّل عدم الإجابة");

const STEPS = [
  { id: "consent_core", type: "yesno", en: "Hi, I'm Riaya. I'll ask about 14 quick questions about everyday habits that affect energy, hormones and your future family.\nNo name or phone number, and nothing is shared unless you choose.\nShall we start?",
    ar: "مرحباً، أنا رعاية. سأطرح عليك نحو ١٤ سؤالاً سريعاً عن عادات يومية تؤثر في طاقتك وهرموناتك ومستقبل عائلتك.\nبلا اسم ولا رقم هاتف، ولا يُشارك شيء إلا باختيارك.\nهل نبدأ؟", opts: YN },
  { id: "consent_review", type: "yesno", en: "If something needs a doctor, may a licensed doctor review your summary? You can say no and still get it.",
    ar: "إذا احتاج الأمر إلى طبيب، هل تسمح لطبيب مرخّص بمراجعة ملخصك؟ يمكنك الرفض وستحصل على ملخصك أيضاً.", opts: YN },
  { id: "age", type: "number", min: 18, max: 80, en: "How old are you?", ar: "كم عمرك؟" },
  { id: "height_cm", type: "number", min: 130, max: 220, skippable: true, en: "Your height in centimetres? (say skip if you don't know)", ar: "طولك بالسنتيمتر؟ (قل تخطي إن كنت لا تعرف)" },
  { id: "weight_kg", type: "number", min: 40, max: 250, skippable: true, en: "And your weight in kilograms?", ar: "ووزنك بالكيلوغرام؟" },
  { id: "reason", type: "choice", en: "What brings you here?", ar: "ما الذي جاء بك؟", multi: true,
    opts: [o("general", "General check", "فحص عام", ["health", "صحة", "عام"]), o("future", "Planning ahead", "تخطيط للمستقبل", ["future", "later", "مستقبل", "زواج", "marriage"]),
           o("trying", "Trying for a child now", "نحاول الإنجاب الآن", ["trying", "baby", "child", "pregnan", "نحاول", "حمل", "طفل", "انجاب"]),
           o("fitness", "Energy / fitness", "الطاقة / اللياقة", ["gym", "energy", "fitness", "نادي", "طاقة", "رياضة"])] },
  { id: "months_trying", type: "number", min: 0, max: 240, when: a => (a.reason || []).includes("trying"),
    en: "How many months have you been trying?", ar: "منذ كم شهراً وأنتم تحاولون؟" },
  { id: "smoking", type: "choice", en: "Do you smoke cigarettes or vape?", ar: "هل تدخن السجائر أو السجائر الإلكترونية؟",
    opts: [o("never", "Never", "لا", ["no", "never", "ابدا", "ما ادخن", "لا ادخن"]), o("former", "I stopped", "أقلعت", ["quit", "stopped", "used to", "تركت", "اقلعت", "كنت"]),
           o("occasional", "Sometimes", "أحياناً", ["sometimes", "occasionally", "social", "احيانا", "مرات"]), o("daily", "Daily", "يومياً", ["daily", "every day", "yes", "يوميا", "كل يوم", "نعم", "اي"])] },
  { id: "waterpipe", type: "choice", en: "Shisha, midwakh or dokha?", ar: "الشيشة أو المدواخ أو الدوخة؟",
    opts: [o("never", "Never", "أبداً", ["no", "never", "لا", "ابدا"]), o("monthly", "Now and then", "أحياناً", ["sometimes", "month", "احيانا", "شهر"]),
           o("weekly", "Weekly", "أسبوعياً", ["week", "weekend", "اسبوع", "ويكند"]), o("daily", "Daily", "يومياً", ["daily", "every day", "يوميا", "كل يوم"])] },
  { id: "aas", type: "choice", sensitive: true,
    en: "Gym question, no judgement: have you used testosterone, steroids or SARMs? It's one of the most common, and most reversible, reasons for low sperm production.",
    ar: "سؤال عن النادي بلا أحكام: هل استخدمت التستوستيرون أو المنشطات أو SARMs؟ هذا من أكثر الأسباب شيوعاً لانخفاض إنتاج الحيوانات المنوية، وغالباً ما يكون قابلاً للعكس.",
    opts: [o("never", "Never", "أبداً", ["no", "never", "لا", "ابدا"]), o("past_old", "Over a year ago", "قبل أكثر من سنة", ["years ago", "long ago", "سنين", "زمان"]),
           o("past_recent", "In the last year", "خلال السنة الماضية", ["last year", "recently", "months ago", "مؤخرا", "السنة"]),
           o("current", "Currently", "حالياً", ["now", "currently", "cycle", "on a", "الحين", "حاليا", "الان", "كورس"]), SKIPO] },
  { id: "sitting_h", type: "number", min: 0, max: 20, en: "On a normal day, how many hours do you sit — desk, car and sofa together?", ar: "في يوم عادي، كم ساعة تجلس — المكتب والسيارة والأريكة معاً؟" },
  { id: "sleep_h", type: "number", min: 2, max: 14, en: "How many hours do you actually sleep on a typical night?", ar: "كم ساعة تنام فعلياً في ليلة عادية؟" },
  { id: "snore", type: "yesno", en: "Do you snore loudly, or has anyone noticed you stop breathing in your sleep?", ar: "هل تشخر بصوت عالٍ، أو لاحظ أحد أنك تتوقف عن التنفس أثناء النوم؟", opts: YNU,
    set: (a, v) => { a.snore = v; if (v === "yes") a.observed = "unsure"; } },
  { id: "tired", type: "yesno", en: "Do you often feel sleepy during the day?", ar: "هل تشعر غالباً بالنعاس خلال النهار؟", opts: YN },
  { id: "underwear", type: "choice", en: "Usual underwear: loose like boxers or sirwal, or tight like briefs?", ar: "ملابسك الداخلية عادةً: فضفاضة مثل البوكسر أو السروال، أم ضيقة؟",
    opts: [o("loose", "Loose", "فضفاضة", ["boxer", "sirwal", "wizar", "بوكسر", "سروال", "وزار", "واسع"]), o("mixed", "Mix", "مختلطة", ["both", "mix", "الاثنين", "مختلف"]),
           o("tight", "Tight", "ضيقة", ["brief", "tight", "compression", "سليب", "ضيق"])] },
  { id: "hot_bath", type: "choice", en: "Sauna, jacuzzi or very hot baths?", ar: "الساونا أو الجاكوزي أو الحمامات الساخنة جداً؟",
    opts: [o(0, "Rarely", "نادراً", ["no", "never", "rarely", "لا", "نادرا", "ابدا"]), o(1, "About weekly", "أسبوعياً", ["week", "اسبوع"]),
           o(2, "Several times a week", "عدة مرات أسبوعياً", ["often", "several", "daily", "every day", "كثير", "يوميا"])] },
  { id: "phq1", type: "choice", en: "In the last two weeks, how often have you had little interest or pleasure in things?", ar: "خلال الأسبوعين الماضيين، كم مرة شعرت بقلة الاهتمام أو المتعة؟",
    opts: [o(0, "Not at all", "إطلاقاً", ["no", "never", "لا", "ابدا"]), o(1, "Some days", "بعض الأيام", ["some", "sometimes", "احيانا"]),
           o(2, "More than half the days", "أكثر من نصف الأيام", ["often", "most", "كثير", "اغلب"]), o(3, "Nearly every day", "تقريباً كل يوم", ["every day", "always", "يوميا", "دايم", "دائما"])] },
  { id: "phq2", type: "choice", en: "And feeling down or hopeless?", ar: "والشعور بالإحباط أو اليأس؟",
    opts: [o(0, "Not at all", "إطلاقاً", ["no", "never", "لا", "ابدا"]), o(1, "Some days", "بعض الأيام", ["some", "sometimes", "احيانا"]),
           o(2, "More than half the days", "أكثر من نصف الأيام", ["often", "most", "كثير", "اغلب"]), o(3, "Nearly every day", "تقريباً كل يوم", ["every day", "always", "يوميا", "دايم", "دائما"])] },
  { id: "rf_any", type: "yesno", en: "Last one. Right now, do you have sudden testicle pain or swelling, a new lump, blood in your semen, or thoughts of harming yourself?",
    ar: "آخر سؤال. هل لديك الآن ألم أو تورم مفاجئ في الخصية، أو كتلة جديدة، أو دم في السائل المنوي، أو أفكار لإيذاء نفسك؟", opts: YN },
  { id: "red_flags", type: "choice", multi: true, when: a => a.rf_any === "yes", en: "Which one? Tap all that apply.", ar: "أيّها؟ اختر كل ما ينطبق.",
    opts: [o("rf_torsion", "Sudden pain or swelling", "ألم أو تورم مفاجئ", ["pain", "swelling", "الم", "ورم"]), o("rf_lump", "A new lump", "كتلة جديدة", ["lump", "كتلة", "حبة"]),
           o("rf_hematospermia", "Blood in semen", "دم في السائل المنوي", ["blood", "دم"]), o("rf_mood", "Thoughts of self-harm", "أفكار لإيذاء النفس", ["harm", "hopeless", "ايذاء", "انتحار"])] },
];

let L = LANG, S = { answers: {}, step: 0, aid: null, multi: [] }, voices = [], rec = null;
const log = () => $("#log");
const CT = k => C[L][k];

function speak(text, then) {
  if (!$("#voiceOn").checked) { then && then(); return; }
  Voice.speak(text, { lang: L, voiceName: $("#voice").value, onend: then });
}

function loadVoices() {
  voices = Voice.voicesFor(L);
  const saved = store.get("voice_" + L);
  $("#voice").innerHTML = `<option value="">${CT("voices").auto}</option>` +
    voices.map(v => `<option ${v.name === saved ? "selected" : ""}>${esc(v.name)}</option>`).join("");
  $("#voiceNote").textContent = window.speechSynthesis && speechSynthesis.getVoices().length && !voices.length && L === "ar" ? CT("noVoiceLang") : "";
}

function bubble(text, who) {
  const d = document.createElement("div");
  d.className = "bubble " + who;
  d.textContent = text;
  log().appendChild(d);
  d.scrollIntoView({ behavior: "smooth", block: "end" });
}

function current() {
  while (S.step < STEPS.length && STEPS[S.step].when && !STEPS[S.step].when(S.answers)) S.step++;
  return STEPS[S.step];
}

function ask() {
  const q = current();
  if (!q) return finish();
  bubble(q[L], "bot");
  speak(q[L], () => { if (handsFree() && !S.finished) startListening(); });
  S.multi = [];
  const opts = q.opts || (q.skippable ? [SKIPO] : []);
  $("#chips").innerHTML = opts.map((x, i) => `<span class="opt" data-i="${i}">${esc(x[L])}</span>`).join("") +
    (q.multi ? `<span class="opt" id="done" style="border-color:var(--brand)">✓</span>` : "");
  $$("#chips .opt[data-i]").forEach(el => el.onclick = () => {
    const x = opts[+el.dataset.i];
    if (q.multi && x.value !== "skip") { el.classList.toggle("on"); S.multi = $$("#chips .opt.on").map(e => opts[+e.dataset.i].value); return; }
    answer(x.value, x[L]);
  });
  if ($("#done")) $("#done").onclick = () => S.multi.length && answer(S.multi, S.multi.map(v => opts.find(x => x.value === v)[L]).join("، "));
  $("#text").focus();
}

function interpret(q, text) {
  if (q.type === "number") {
    if (NLU.yesNo(text, false) === "skip") return "skip";
    const n = NLU.number(text);
    return n != null && n >= q.min && n <= q.max ? n : null;
  }
  if (q.type === "yesno") return NLU.yesNo(text, (q.opts || []).some(x => x.value === "unsure"));
  if (q.multi) {
    const hits = q.opts.filter(x => NLU.choice(text, [x]) != null).map(x => x.value);
    return hits.length ? hits : null;
  }
  return NLU.choice(text, q.opts);
}

function onText(text, spoken) {
  const q = current();
  if (!q || !text.trim()) return;
  const v = interpret(q, text);
  if (v == null) { bubble(text, "me"); bubble(CT("notUnderstood"), "bot"); speak(CT("notUnderstood"), () => handsFree() && startListening()); return; }
  answer(v, text);
}

async function answer(v, shown) {
  const q = current();
  bubble(shown, "me");
  $("#chips").innerHTML = "";
  if (q.id === "consent_core") {
    if (v !== "yes") { bubble(L === "ar" ? "لا بأس. يمكنك العودة في أي وقت." : "No problem. You can come back any time.", "bot"); return; }
  } else if (q.id === "consent_review") {
    if (!API.token) { API.token = (await API.post("/api/session", { lang: L })).token; store.set("token", API.token); }
    const carried = store.get("passive_aid");
    await API.post("/api/consent", { core: true, clinician_review: v === "yes", wearables: !!carried, research: false });
    if (carried) { S.aid = carried; store.del("passive_aid"); }
    else S.aid = (await API.post("/api/assessments?channel=chat")).id;
    store.set("aid", S.aid); store.del("done");
  } else if (q.set) q.set(S.answers, v);
  else if (q.id === "rf_any") S.answers.rf_any = v;
  else if (v !== "skip") S.answers[q.id] = v;
  if (S.aid && !q.id.startsWith("consent")) {
    const clean = { ...S.answers }; delete clean.rf_any;
    store.set("draft", JSON.stringify(clean));
    API.put(`/api/assessments/${S.aid}/answers`, { answers: clean }).catch(() => {});
  }
  S.step++;
  setTimeout(ask, 350);
}

async function finish() {
  S.finished = true;
  $("#chips").innerHTML = "";
  bubble(CT("working"), "bot");
  const clean = { ...S.answers }; delete clean.rf_any;
  await API.put(`/api/assessments/${S.aid}/answers`, { answers: clean });
  await API.post(`/api/assessments/${S.aid}/submit?lang=${L}`);
  const r = await API.get(`/api/assessments/${S.aid}/result?lang=${L}`);
  store.set("done", "1");
  const lines = [r.disclaimer, "", r.summary, r.next_step];
  if (r.plan.length) lines.push("", (L === "ar" ? "أهم فرصك:" : "Your top opportunities:"), ...r.plan.map((p, i) => `${i + 1}. ${p.action}`));
  bubble(lines.join("\n"), "bot");
  speak([r.summary, r.next_step, ...r.plan.map(p => p.action)].join(". "));
  $("#chips").innerHTML = `<a class="btn" href="index.html">${CT("full")}</a> <a class="btn ghost" href="index.html#more">${CT("more")}</a>`;
}

const handsFree = () => $("#handsFree").checked;
let listening = null;

function micState(st, pct) {
  $("#mic").classList.toggle("live", st === "listening");
  $("#text").placeholder = st === "listening" ? CT("listening") : st === "thinking" ? CT("thinking") : st === "loading" ? CT("loading")(pct || 0) : CT("typeHere");
}

async function startListening() {
  if (listening || !(Voice.hasBrowserASR || Voice.canRecord)) return;
  if (window.speechSynthesis) speechSynthesis.cancel();
  const h = Voice.listen({ lang: L, privateMode: $("#private").checked, onState: micState });
  listening = h;
  try {
    const alts = await h.result;
    const q = current();
    if (alts.length && q) onText(alts.find(a => interpret(q, a) != null) || alts[0], true);
  } catch (e) {
    const m = String(e.message || e);
    if (/not-allowed|denied|permission/i.test(m)) { $("#micNote").textContent = CT("micDenied"); $("#handsFree").checked = false; }
    else if (!/no-speech|aborted/i.test(m)) $("#micNote").textContent = m;
  } finally { listening = null; micState("idle"); }
}

function setupMic() {
  const ok = Voice.hasBrowserASR || Voice.canRecord;
  $("#micNote").textContent = ok ? CT("micNote") : CT("noMic");
  $("#mic").disabled = !ok; $("#mic").style.opacity = ok ? 1 : .4;
  $("#private").disabled = !Voice.canRecord;
  $("#mic").onclick = () => listening ? listening.stop() : startListening();
}

function chrome() {
  applyLang();
  $("#brand").textContent = t("app"); $("#langBtn").textContent = t("lang");
  $("#lblVoice").textContent = CT("voice"); $("#send").textContent = CT("send"); $("#text").placeholder = CT("typeHere");
  $("#lblHands").textContent = CT("handsFree"); $("#lblPrivate").textContent = CT("private");
  loadVoices(); setupMic();
}

$("#langBtn").onclick = () => { L = LANG = L === "ar" ? "en" : "ar"; store.set("lang", L); chrome(); log().innerHTML = ""; S = { answers: {}, step: 0, aid: null, multi: [] }; ask(); };
$("#voice").onchange = e => store.set("voice_" + L, e.target.value);
$("#send").onclick = () => { onText($("#text").value); $("#text").value = ""; };
$("#text").onkeydown = e => { if (e.key === "Enter") { onText(e.target.value); e.target.value = ""; } };
if (window.speechSynthesis) speechSynthesis.onvoiceschanged = loadVoices;
API.token = store.get("token");
$("#private").checked = store.get("private_voice") === "1";
$("#private").onchange = e => store.set("private_voice", e.target.checked ? "1" : "0");
chrome();
// one tap is needed before phones allow audio; it also decides voice on/off
$("#log").innerHTML = `<div class="startpad"><button class="btn" id="startVoice">${CT("start")}</button><button class="btn ghost" id="startText">${CT("startText")}</button></div>`;
$("#startVoice").onclick = () => { $("#voiceOn").checked = true; $("#handsFree").checked = Voice.hasBrowserASR || Voice.canRecord; $("#log").innerHTML = ""; ask(); };
$("#startText").onclick = () => { $("#voiceOn").checked = false; $("#handsFree").checked = false; $("#log").innerHTML = ""; ask(); };
