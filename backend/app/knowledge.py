import itertools
import json
import random
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = ROOT / "knowledge" / "graph.json"

GRADE_WEIGHT = {"A": 1.0, "B": 0.7, "C": 0.4, "D": 0.0}
EDGE_GAIN = 1.0           # global scale on edge weights (tuned on vignettes, see validation/)
ITERATIONS = 8            # fixed-point passes (graph has feedback loops)
REDUNDANCY_DAMP = 0.3
SCORED_OUTCOMES = ["low_count", "low_motility", "abn_morph", "dna_frag", "azoospermia",
                   "hypogonadism", "subfertility"]


def combine(contrib):
    """Strongest parent counts fully; the rest add with damping. Many mechanisms share upstream
    causes (e.g. smoking -> ROS -> DNA damage and smoking -> DNA damage), so a plain noisy-OR
    double-counts them and saturates."""
    if not contrib:
        return 0.0
    contrib = sorted(contrib, reverse=True)
    rest = 1.0
    for c in contrib[1:]:
        rest *= 1 - c
    return contrib[0] + (1 - contrib[0]) * REDUNDANCY_DAMP * (1 - rest)


class Graph:
    def __init__(self, data):
        self.data = data
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.edges = data["edges"]
        self.refs = data["references"]
        self.signals = data.get("signals", [])
        self.red_flags = data["redFlags"]
        self.parents = {nid: [] for nid in self.nodes}
        self.children = {nid: [] for nid in self.nodes}
        for e in self.edges:
            self.parents[e["target"]].append(e)
            self.children[e["source"]].append(e)

    def validate(self):
        problems = []
        for i, e in enumerate(self.edges):
            for end in ("source", "target"):
                if e[end] not in self.nodes:
                    problems.append(f"edge {i}: unknown {end} {e[end]}")
            if e["grade"] not in GRADE_WEIGHT:
                problems.append(f"edge {i}: bad grade")
            if not e["refs"]:
                problems.append(f"edge {i}: no reference")
            for r in e["refs"]:
                if r not in self.refs:
                    problems.append(f"edge {i}: unknown ref {r}")
        for s in self.signals:
            if s["node"] not in self.nodes:
                problems.append(f"signal {s['id']}: unknown node")
            problems += [f"signal {s['id']}: unknown ref {r}" for r in s["refs"] if r not in self.refs]
        for f in self.red_flags:
            problems += [f"red flag {f['id']}: unknown ref {r}" for r in f["refs"] if r not in self.refs]
        linked = {e["source"] for e in self.edges} | {e["target"] for e in self.edges}
        problems += [f"orphan node {n}" for n in self.nodes if n not in linked]
        return problems

    # ---- propagation ---------------------------------------------------------------
    def propagate(self, inputs):
        """Noisy-OR propagation. `inputs` maps node id -> activation in [0, 1].
        Input nodes are clamped (observed); every other node is inferred from its parents.
        Edges leaving terminal outcomes (feedback, e.g. infertility -> stress) are ignored for scoring."""
        act = {n: 0.0 for n in self.nodes}
        act.update(inputs)
        for _ in range(ITERATIONS):
            new = dict(act)
            for nid in self.nodes:
                if nid in inputs:
                    continue
                contrib, protect = [], 1.0
                for e in self.parents[nid]:
                    if self.nodes[e["source"]].get("terminal"):
                        continue
                    w = min(1.0, GRADE_WEIGHT[e["grade"]] * e.get("strength", 0.4) * EDGE_GAIN * act[e["source"]])
                    if e["sign"] == "+":
                        contrib.append(w)
                    else:
                        protect *= 1 - 0.5 * w
                new[nid] = combine(contrib) * protect
            act = new
        return act

    def score(self, inputs):
        a = self.propagate(inputs)
        return {k: round(a[k], 4) for k in SCORED_OUTCOMES}

    # ---- attribution (Shapley values over the active inputs) ----------------------
    def shapley(self, inputs, target="subfertility", samples=300, seed=7):
        players = [k for k, v in inputs.items() if v > 0]
        if not players:
            return {}
        value = lambda subset: self.propagate({k: inputs[k] for k in subset})[target]
        phi = {p: 0.0 for p in players}
        if len(players) <= 8:
            n = len(players)
            from math import factorial
            for p in players:
                others = [q for q in players if q != p]
                for r in range(len(others) + 1):
                    wt = factorial(r) * factorial(n - r - 1) / factorial(n)
                    for s in itertools.combinations(others, r):
                        phi[p] += wt * (value(s + (p,)) - value(s))
        else:
            rng = random.Random(seed)
            for _ in range(samples):
                order = players[:]
                rng.shuffle(order)
                prev, chosen = value(()), []
                for p in order:
                    chosen.append(p)
                    cur = value(tuple(chosen))
                    phi[p] += (cur - prev) / samples
                    prev = cur
        return {k: round(v, 4) for k, v in sorted(phi.items(), key=lambda kv: -kv[1])}

    # ---- explanation --------------------------------------------------------------
    def paths(self, start, target="subfertility", max_depth=6, min_grade="C"):
        rank = {"A": 4, "B": 3, "C": 2, "D": 1}
        out = []

        def dfs(node, path, seen):
            if path and node == target:
                out.append(list(path))
                return
            if len(path) >= max_depth:
                return
            for e in self.children[node]:
                if rank[e["grade"]] < rank[min_grade] or e["target"] in seen or e["sign"] == "-":
                    continue
                if self.nodes[e["source"]].get("terminal"):
                    continue
                seen.add(e["target"]); path.append(e)
                dfs(e["target"], path, seen)
                path.pop(); seen.discard(e["target"])

        dfs(start, [], {start})
        weakest = lambda p: min(rank[e["grade"]] for e in p)
        out.sort(key=lambda p: (-weakest(p), len(p)))
        return [{
            "grade": "DCBA"[weakest(p) - 1],
            "nodes": [start] + [e["target"] for e in p],
            "labels": [self.nodes[start]["label"]] + [self.nodes[e["target"]]["label"] for e in p],
            "refs": sorted({r for e in p for r in e["refs"]}),
        } for p in out]


@lru_cache(maxsize=1)
def graph():
    return Graph(json.loads(GRAPH_PATH.read_text(encoding="utf-8")))
