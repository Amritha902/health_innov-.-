/* Voice in and out, on every kind of phone.
   Listening:
     1. the browser's own speech recognition (iPhone Safari, Android Chrome, Samsung Internet, Edge, desktop Chrome/Safari)
     2. otherwise, or when "private mode" is on: Whisper (open-source, OpenAI) running inside the browser with
        transformers.js. Audio never leaves the phone. The model (~40-80 MB) downloads once and is cached.
   Speaking: the device's own voices (SpeechSynthesis). iPhones need one tap before audio can play. */
(function (root) {
  const SR = root.SpeechRecognition || root.webkitSpeechRecognition;
  const canRecord = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && root.MediaRecorder);
  const TRANSFORMERS = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.0.2";
  const MODELS = ["onnx-community/whisper-base", "Xenova/whisper-base", "Xenova/whisper-tiny"];
  let unlocked = false, whisper = null, whisperLoading = null;

  function unlockAudio() {
    if (unlocked || !root.speechSynthesis) return;
    try { const u = new SpeechSynthesisUtterance(" "); u.volume = 0; speechSynthesis.speak(u); } catch {}
    unlocked = true;
  }
  ["pointerdown", "keydown", "touchend"].forEach(ev => document.addEventListener(ev, unlockAudio, { once: true, capture: true }));

  function voicesFor(lang) {
    if (!root.speechSynthesis) return [];
    return speechSynthesis.getVoices().filter(v => v.lang.toLowerCase().replace("_", "-").startsWith(lang));
  }

  function speak(text, { lang, voiceName, onend } = {}) {
    if (!root.speechSynthesis) { onend && onend(); return; }
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text.replace(/\n+/g, ". "));
    u.lang = lang === "ar" ? "ar-AE" : "en-GB";
    const v = voicesFor(lang).find(x => x.name === voiceName) || voicesFor(lang)[0];
    if (v) u.voice = v;
    u.rate = 0.97;
    let done = false;
    const finish = () => { if (!done) { done = true; onend && onend(); } };
    u.onend = finish; u.onerror = finish;
    // some Android builds never fire onend: fall back on an estimate
    setTimeout(finish, Math.min(20000, 1200 + text.length * 70));
    speechSynthesis.speak(u);
  }

  async function loadWhisper(onProgress) {
    if (whisper) return whisper;
    if (whisperLoading) return whisperLoading;
    whisperLoading = (async () => {
      const { pipeline, env } = await import(TRANSFORMERS);
      env.allowLocalModels = false;
      let lastErr;
      for (const id of MODELS) {
        try {
          whisper = await pipeline("automatic-speech-recognition", id, { progress_callback: onProgress });
          return whisper;
        } catch (e) { lastErr = e; }
      }
      throw lastErr;
    })();
    try { return await whisperLoading; } finally { whisperLoading = null; }
  }

  async function toMono16k(blob) {
    const buf = await blob.arrayBuffer();
    const Ctx = root.AudioContext || root.webkitAudioContext;
    const ctx = new Ctx();
    const decoded = await ctx.decodeAudioData(buf);
    const off = new OfflineAudioContext(1, Math.ceil(decoded.duration * 16000), 16000);
    const src = off.createBufferSource(); src.buffer = decoded; src.connect(off.destination); src.start();
    const out = await off.startRendering();
    ctx.close && ctx.close();
    return out.getChannelData(0);
  }

  /* Records until stop() is called or silence/time limit. Returns {stop, promise<Blob>} */
  async function record(maxMs = 15000) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    const type = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm", "audio/ogg"].find(t => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(t)) || "";
    const mr = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
    const chunks = [];
    mr.ondataavailable = e => e.data.size && chunks.push(e.data);
    const promise = new Promise(res => mr.onstop = () => { stream.getTracks().forEach(t => t.stop()); res(new Blob(chunks, { type: mr.mimeType || type || "audio/webm" })); });
    mr.start();
    const timer = setTimeout(() => mr.state !== "inactive" && mr.stop(), maxMs);
    return { stop: () => { clearTimeout(timer); mr.state !== "inactive" && mr.stop(); }, promise };
  }

  /* listen({lang, private, onState}) -> {stop, result: Promise<string[] alternatives>} */
  function listen({ lang, privateMode, onState = () => {} }) {
    if (SR && !privateMode) {
      const rec = new SR();
      rec.lang = lang === "ar" ? "ar-AE" : "en-US";
      rec.interimResults = false; rec.maxAlternatives = 3; rec.continuous = false;
      const result = new Promise((resolve, reject) => {
        rec.onresult = e => resolve([...e.results[0]].map(a => a.transcript));
        rec.onerror = e => reject(new Error(e.error || "speech"));
        rec.onend = () => { onState("idle"); resolve([]); };
      });
      onState("listening");
      rec.start();
      return { stop: () => rec.stop(), result, engine: "browser" };
    }
    if (!canRecord) return { stop() {}, result: Promise.reject(new Error("no-microphone")), engine: "none" };
    let handle;
    const result = (async () => {
      const modelReady = loadWhisper(p => p && p.status === "progress" && onState("loading", Math.round(p.progress || 0)));
      onState("listening");
      handle = await record(12000);
      const blob = await handle.promise;
      onState("thinking");
      const [asr, audio] = await Promise.all([modelReady, toMono16k(blob)]);
      const out = await asr(audio, { language: lang === "ar" ? "arabic" : "english", task: "transcribe", chunk_length_s: 30 });
      onState("idle");
      return [String(out.text || "").trim()].filter(Boolean);
    })();
    return { stop: () => handle && handle.stop(), result, engine: "whisper" };
  }

  root.Voice = { speak, listen, record, voicesFor, hasBrowserASR: !!SR, canRecord, loadWhisper };
})(window);
