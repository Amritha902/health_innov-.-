/* Graph reasoning engine: traces cause → effect pathways through the knowledge graph. */
(function (root) {
  const GRADE_RANK = { A: 4, B: 3, C: 2, D: 1 };

  function index(KG) {
    const byId = Object.fromEntries(KG.nodes.map(n => [n.id, n]));
    const out = {}, inc = {};
    KG.edges.forEach(e => {
      (out[e.source] ||= []).push(e);
      (inc[e.target] ||= []).push(e);
    });
    return { byId, out, inc };
  }

  /* All simple paths from `start` to terminal outcomes (default: subfertility), max depth, min grade. */
  function pathsFrom(KG, start, { target = null, maxDepth = 6, minGrade = "D" } = {}) {
    const { byId, out } = index(KG);
    const min = GRADE_RANK[minGrade];
    const results = [];
    (function dfs(node, path, seen) {
      const n = byId[node];
      if (path.length && (target ? node === target : n.terminal)) {
        results.push(path.slice());
        if (target) return;
      }
      if (path.length >= maxDepth) return;
      for (const e of out[node] || []) {
        if (GRADE_RANK[e.grade] < min || seen.has(e.target)) continue;
        if (e.sign === "-" && path.length) continue; // protective edges only meaningful as first hop
        seen.add(e.target); path.push(e);
        dfs(e.target, path, seen);
        path.pop(); seen.delete(e.target);
      }
    })(start, [], new Set([start]));
    return results
      .map(p => ({ edges: p, grade: weakest(p), length: p.length }))
      .sort((a, b) => GRADE_RANK[b.grade] - GRADE_RANK[a.grade] || a.length - b.length);
  }

  const weakest = p => p.reduce((g, e) => (GRADE_RANK[e.grade] < GRADE_RANK[g] ? e.grade : g), "A");

  /* Everything that feeds into `node` (upstream causes), with depth. */
  function upstream(KG, node, maxDepth = 6) {
    const { inc } = index(KG);
    const found = new Map(); const q = [[node, 0]];
    while (q.length) {
      const [cur, d] = q.shift();
      if (d >= maxDepth) continue;
      for (const e of inc[cur] || []) if (!found.has(e.source) && e.source !== node) {
        found.set(e.source, d + 1); q.push([e.source, d + 1]);
      }
    }
    return found;
  }

  function downstream(KG, node, maxDepth = 8) {
    const { out } = index(KG);
    const found = new Map(); const q = [[node, 0]];
    while (q.length) {
      const [cur, d] = q.shift();
      if (d >= maxDepth) continue;
      for (const e of out[cur] || []) if (!found.has(e.target) && e.target !== node) {
        found.set(e.target, d + 1); q.push([e.target, d + 1]);
      }
    }
    return found;
  }

  /* Human-readable sentence for a path. */
  function explain(KG, path) {
    const { byId } = index(KG);
    const parts = [byId[path.edges[0].source].label];
    path.edges.forEach(e => parts.push((e.sign === "-" ? " ⟞ " : " → ") + byId[e.target].label));
    return parts.join("");
  }

  root.Engine = { pathsFrom, upstream, downstream, explain, weakest, GRADE_RANK, index };
  if (typeof module !== "undefined") module.exports = root.Engine;
})(typeof window !== "undefined" ? window : globalThis);
