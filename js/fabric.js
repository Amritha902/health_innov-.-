/*
 * Fabric / garment check. Parses a care-label composition and scores GROIN HEAT & BREATHABILITY risk.
 * Evidence hierarchy is deliberate:
 *   1. Fit + heat (grade B, Mínguez-Alarcón 2018; Durairajanayagam 2015)  → drives the score
 *   2. Fibre breathability (grade D/C)                                     → modifies the score
 *   3. Microplastic / BPA concerns (grade D)                               → shown as precautionary note only
 */
(function (root) {
  // breathability 0..1 (higher = cooler / better moisture handling next to skin)
  const FIBRES = {
    linen:     { b: 1.0,  names: ["linen", "flax"], kind: "natural" },
    hemp:      { b: 0.95, names: ["hemp"], kind: "natural" },
    cotton:    { b: 0.9,  names: ["cotton", "organic cotton", "pima", "supima", "coton", "algodón", "algodon"], kind: "natural" },
    lyocell:   { b: 0.85, names: ["lyocell", "tencel"], kind: "cellulosic" },
    modal:     { b: 0.85, names: ["modal"], kind: "cellulosic" },
    viscose:   { b: 0.8,  names: ["viscose", "rayon", "bamboo", "cupro"], kind: "cellulosic" },
    silk:      { b: 0.7,  names: ["silk"], kind: "natural" },
    wool:      { b: 0.7,  names: ["wool", "merino", "cashmere"], kind: "natural" },
    polypropylene: { b: 0.4, names: ["polypropylene"], kind: "synthetic" },
    polyester: { b: 0.3,  names: ["polyester", "poly", "pes", "pet", "microfiber", "microfibre"], kind: "synthetic" },
    nylon:     { b: 0.3,  names: ["nylon", "polyamide", "pa"], kind: "synthetic" },
    acrylic:   { b: 0.3,  names: ["acrylic"], kind: "synthetic" },
    elastane:  { b: 0.2,  names: ["elastane", "spandex", "lycra", "ea", "el"], kind: "synthetic" },
    pu:        { b: 0.05, names: ["polyurethane", "pu", "pvc", "vinyl", "faux leather"], kind: "synthetic" }
  };

  // how close / how much of the day the garment sits on the scrotum
  const GARMENTS = {
    underwear: { label: "Underwear", proximity: 1.0 },
    trousers:  { label: "Trousers / jeans", proximity: 0.7 },
    shorts:    { label: "Shorts / gym wear", proximity: 0.8 },
    wizar:     { label: "Wizar / sirwal (under kandura)", proximity: 0.9 },
    kandura:   { label: "Kandura / thobe", proximity: 0.25 },
    top:       { label: "Shirt / top", proximity: 0.05 }
  };
  const FIT = { tight: 1.0, regular: 0.6, loose: 0.3 };

  function parse(text) {
    const t = text.toLowerCase();
    const found = {};
    // tokens: percentages and words, in order. Each % binds to the fibre word right after it,
    // or (label style "Cotton 95%") right before it.
    const toks = [...t.matchAll(/(\d{1,3}(?:\.\d+)?)\s*%|[a-zà-ÿ]+/g)]
      .map(m => (m[1] ? { pct: parseFloat(m[1]) } : { w: m[0] }));
    const used = new Set();
    // style: does the first fibre word come before the first percentage ("Cotton 95%")?
    const firstPct = toks.findIndex(x => x.pct !== undefined);
    const firstFibre = toks.findIndex(x => x.w && match(x.w));
    const nameFirst = firstFibre !== -1 && firstFibre < firstPct;
    toks.forEach((tok, i) => {
      if (tok.pct === undefined) return;
      const seek = (from, step) => {
        for (let j = from; j >= 0 && j < toks.length && toks[j].pct === undefined; j += step) {
          const k = match(toks[j].w); if (k && !used.has(j)) return [j, k];
        }
      };
      const hit = nameFirst ? (seek(i - 1, -1) || seek(i + 1, 1)) : (seek(i + 1, 1) || seek(i - 1, -1));
      if (hit) { used.add(hit[0]); found[hit[1]] = (found[hit[1]] || 0) + tok.pct; }
    });
    if (!Object.keys(found).length) { // no percentages: e.g. "100 cotton" or "linen"
      const key = match(t.trim());
      if (key) found[key] = 100;
    }
    return found;
  }

  function match(name) {
    const words = name.split(/\s+/).filter(Boolean);
    for (const [key, f] of Object.entries(FIBRES))
      for (const n of f.names)
        if (n.length <= 3 ? words.includes(n) : name.includes(n)) return key;
    return null;
  }

  function assess(text, garment = "underwear", fit = "regular", { hotDay = true } = {}) {
    const comp = parse(text);
    const total = Object.values(comp).reduce((a, b) => a + b, 0);
    if (!total) return { ok: false, message: "Couldn't read a fibre composition. Try e.g. '95% cotton 5% elastane'." };
    let breath = 0, synthetic = 0;
    for (const [k, p] of Object.entries(comp)) {
      breath += FIBRES[k].b * p / total;
      if (FIBRES[k].kind === "synthetic") synthetic += p / total;
    }
    const g = GARMENTS[garment], f = FIT[fit];
    // Fit dominates (better evidence), fibre modifies.
    const heat = g.proximity * (0.65 * f + 0.35 * (1 - breath)) * (hotDay ? 1.1 : 1.0);
    const score = Math.round(Math.min(1, heat) * 100);
    const verdict = score < 30 ? "good" : score < 55 ? "okay" : "caution";

    const notes = [];
    if (fit === "tight" && g.proximity >= 0.7)
      notes.push({ grade: "B", text: "Tight fit holds the testes against the body and raises scrotal temperature. Men wearing boxers had ~25% higher sperm concentration than men in tight underwear.", refs: ["minguez2018", "durairajanayagam2015"] });
    if (synthetic >= 0.5 && g.proximity >= 0.7)
      notes.push({ grade: "D", text: `${Math.round(synthetic * 100)}% synthetic. Synthetic fibres usually let less air through and hold more moisture than cotton or linen, so the area can stay warmer, especially in UAE heat. On its own this is a small effect; fit matters more.`, refs: ["durairajanayagam2015"] });
    if (comp.polyester && g.proximity >= 0.7)
      notes.push({ grade: "C", text: "Two small 1990s studies (Shafik) reported lower sperm counts in men wearing polyester underwear, possibly due to static charge. They were never replicated, so treat this as a weak signal.", refs: ["shafik1992", "shafik1993"] });
    if (synthetic >= 0.5 && g.proximity >= 0.7)
      notes.push({ grade: "D", text: "Precautionary: BPA has been detected in some polyester-spandex sportswear, and microplastics have been found in human testes. There is currently no evidence that wearing synthetic clothes puts plastic into your blood. Most microplastic exposure comes from food, water and air.", refs: ["ceh2022", "hu2024", "defalco2019"] });
    if (breath >= 0.8 && (fit !== "tight" || g.proximity < 0.7))
      notes.push({ grade: "B", text: "Breathable fibre with a comfortable fit — a good everyday choice.", refs: ["minguez2018"] });
    if (garment === "kandura")
      notes.push({ grade: "B", text: "A kandura hangs loosely, so its fabric matters little for heat. What you wear under it (wizar/sirwal) matters more.", refs: ["durairajanayagam2015"] });

    const swaps = [];
    if (verdict !== "good") {
      if (fit === "tight") swaps.push("Choose a looser cut (boxers, relaxed-fit trousers).");
      if (synthetic >= 0.5) swaps.push("Look for ≥ 90% cotton, linen, lyocell/Tencel or modal for garments in direct contact.");
      if (garment === "shorts") swaps.push("Fine for workouts — change out of sweaty gym wear soon after.");
    }
    return { ok: true, composition: comp, breathability: +breath.toFixed(2), synthetic: +synthetic.toFixed(2), score, verdict, notes, swaps, graphNodes: ["tight_underwear", "synthetic_textile", "scrotal_heat"] };
  }

  root.Fabric = { assess, parse, FIBRES, GARMENTS, FIT };
  if (typeof module !== "undefined") module.exports = root.Fabric;
})(typeof window !== "undefined" ? window : globalThis);
