// Integrity checks for the knowledge graph + smoke tests for engine and fabric checker.
// Run: node scripts/validate.js
const KG = require("../knowledge/graph.js");
const Engine = require("../js/engine.js");
const Fabric = require("../js/fabric.js");

let errors = 0;
const fail = m => { errors++; console.error("✗", m); };
const ids = new Set(KG.nodes.map(n => n.id));
if (ids.size !== KG.nodes.length) fail("duplicate node ids");

KG.edges.forEach((e, i) => {
  if (!ids.has(e.source)) fail(`edge ${i} unknown source ${e.source}`);
  if (!ids.has(e.target)) fail(`edge ${i} unknown target ${e.target}`);
  if (!"ABCD".includes(e.grade)) fail(`edge ${i} bad grade`);
  if (!e.refs.length) fail(`edge ${i} ${e.source}->${e.target} has no reference`);
  e.refs.forEach(r => KG.references[r] || fail(`edge ${i} unknown ref ${r}`));
});
KG.redFlags.forEach(f => f.refs.forEach(r => KG.references[r] || fail(`redflag ${f.id} unknown ref ${r}`)));

// every exposure must reach a terminal outcome; every node must be connected
const connected = new Set(KG.edges.flatMap(e => [e.source, e.target]));
KG.nodes.forEach(n => connected.has(n.id) || fail(`orphan node ${n.id}`));
KG.nodes.filter(n => n.type === "exposure" && !n.protective).forEach(n => {
  if (!Engine.pathsFrom(KG, n.id).length) fail(`exposure ${n.id} reaches no terminal outcome`);
});

const used = new Set(KG.edges.flatMap(e => e.refs).concat(KG.redFlags.flatMap(f => f.refs)));
const unused = Object.keys(KG.references).filter(r => !used.has(r));

// smoke tests
const t1 = Fabric.assess("65% polyester 30% cotton 5% elastane", "underwear", "tight");
if (t1.verdict !== "caution") fail("tight polyester underwear should be 'caution', got " + t1.verdict);
const t2 = Fabric.assess("100% linen", "trousers", "loose");
if (t2.verdict !== "good") fail("loose linen trousers should be 'good', got " + t2.verdict);
const t3 = Fabric.parse("Shell: Cotton 95%, Elastane 5%");
if (t3.cotton !== 95 || t3.elastane !== 5) fail("label parse failed " + JSON.stringify(t3));

const g = KG.edges.reduce((a, e) => (a[e.grade] = (a[e.grade] || 0) + 1, a), {});
console.log(`nodes ${KG.nodes.length} | edges ${KG.edges.length} | refs ${Object.keys(KG.references).length} | red flags ${KG.redFlags.length}`);
console.log("edges by grade", g);
if (unused.length) console.log("unused refs (fine, background):", unused.join(", "));
console.log("sample path:", Engine.explain(KG, Engine.pathsFrom(KG, "osa")[0]));
process.exit(errors ? 1 : 0);
