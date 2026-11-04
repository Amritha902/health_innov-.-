"""Programme dashboard for the health authority (ADPHC / DoH). Aggregates only: no row-level data leaves this
module, and any subgroup smaller than K is suppressed so no individual can be singled out."""
import statistics
import time
from collections import Counter, defaultdict

from . import db, security
from .knowledge import graph

K = 5
SIGNALS = ["sleep_loss", "obesity", "sedentary", "smoking", "waterpipe", "osa", "psych_stress", "tight_underwear",
           "aas", "glycaemic_spikes", "alcohol", "diabetes", "varicocele", "screen_night"]
USUAL_PATHWAY_DAYS = 365  # reference: men are typically assessed only after >= 12 months trying and the wife's work-up (ASRM 2020)


def _median(v):
    return round(statistics.median(v), 1) if v else None


def build(include_simulated=True):
    g = graph()
    where = "" if include_simulated else " AND a.simulated=0"
    with db.tx() as c:
        rows = c.execute(f"SELECT a.* FROM assessments a WHERE 1=1{where}").fetchall()
        refs = {r["assessment_id"]: r for r in c.execute("SELECT * FROM referrals").fetchall()}
    done = [r for r in rows if r["completed_at"]]
    started, completed = len(rows), len(done)
    referred = [r for r in done if r["level"] and r["level"] != "self_care"]
    ref_rows = [refs[r["id"]] for r in referred if r["id"] in refs]
    reviewed = [x for x in ref_rows if x["reviewed_at"]]
    booked = [x for x in ref_rows if x["booked_at"] or x["attended_at"]]
    attended = [x for x in ref_rows if x["attended_at"]]

    days_to_eval = []
    by_id = {r["id"]: r for r in done}
    for x in attended:
        a = by_id.get(x["assessment_id"])
        if a:
            days_to_eval.append((x["attended_at"] - a["completed_at"]) / 86400)
    rapid = [x for x in ref_rows if x["rapid"]]
    rapid_reviewed = [x for x in rapid if x["reviewed_at"]]
    rapid_on_time = [x for x in rapid_reviewed if x["due_at"] and x["reviewed_at"] <= x["due_at"]]
    now = time.time()
    overdue = [x for x in rapid if not x["reviewed_at"] and x["due_at"] and x["due_at"] < now]

    # signal prevalence and population drivers (decrypted in memory, aggregated, discarded)
    prevalence, drivers = Counter(), defaultdict(float)
    weeks = Counter()
    for r in done:
        res = security.unseal(r["result"]) or {}
        inputs = res.get("inputs", {})
        for n in SIGNALS:
            if inputs.get(n, 0) >= 0.5:
                prevalence[n] += 1
        attr = {k: v for k, v in (res.get("attribution") or {}).items() if v > 0 and g.nodes.get(k, {}).get("modifiable")}
        total = sum(attr.values())
        for k, v in attr.items():
            drivers[k] += v / total
        weeks[time.strftime("%Y-%W", time.gmtime(r["completed_at"]))] += 1

    def group(key):
        out = []
        groups = defaultdict(list)
        for r in done:
            groups[key(r)].append(r)
        for name, rs in sorted(groups.items()):
            if len(rs) < K:
                out.append({"group": name, "n": f"<{K}", "suppressed": True})
                continue
            ref = [x for x in rs if x["level"] != "self_care"]
            att = [refs[x["id"]] for x in ref if x["id"] in refs and refs[x["id"]]["attended_at"]]
            out.append({"group": name, "n": len(rs), "referred_pct": round(100 * len(ref) / len(rs), 1),
                        "high_pct": round(100 * sum(x["tier"] == "high" for x in rs) / len(rs), 1),
                        "attended_pct": round(100 * len(att) / len(ref), 1) if ref else None})
        return out

    pct = lambda a, b: round(100 * a / b, 1) if b else None
    return {
        "generated_at": now, "includes_simulated": include_simulated,
        "simulated": sum(r["simulated"] for r in rows), "k_anonymity": K,
        "tiles": {"completed": completed, "completion_rate": pct(completed, started), "median_minutes": _median(
            [(r["completed_at"] - r["started_at"]) / 60 for r in done]),
            "median_days_to_evaluation": _median(days_to_eval), "usual_pathway_days": USUAL_PATHWAY_DAYS,
            "referral_completion": pct(len(attended), len(ref_rows)), "rapid_on_time": pct(len(rapid_on_time), len(rapid_reviewed)),
            "rapid_overdue": len(overdue), "median_hours_to_review": _median([(x["reviewed_at"] - x["created_at"]) / 3600 for x in reviewed])},
        "funnel": [{"step": "Started", "n": started}, {"step": "Completed", "n": completed}, {"step": "Referred beyond self-care", "n": len(referred)},
                   {"step": "Appointment booked", "n": len(booked)}, {"step": "Seen by a clinician", "n": len(attended)},
                   {"step": "Tests completed", "n": sum(1 for x in ref_rows if x["tests_done_at"])}, {"step": "Followed up", "n": sum(1 for x in ref_rows if x["followup_at"])}],
        "barriers": dict(Counter(x["barrier"] for x in ref_rows if x["status"] == "declined" and x["barrier"])),
        "self_reported_pct": pct(sum(1 for x in ref_rows if x["self_reported"]), len(ref_rows)),
        "reviewed": {"specialist_referrals": sum(1 for x in ref_rows if x["rapid"] or x["status"] in ("approved", "pending_review") or x["reviewed_at"]),
                     "reviewed_by_doctor": len(reviewed)},
        "levels": dict(Counter(r["level"] for r in done)),
        "channels": dict(Counter(r["channel"] or "web" for r in rows)),
        "prevalence": sorted(({"node": n, "label": g.nodes[n]["label"], "pct": pct(prevalence[n], completed)} for n in SIGNALS),
                             key=lambda d: -(d["pct"] or 0)),
        "drivers": sorted(({"node": k, "label": g.nodes[k]["label"], "share": round(100 * v / completed, 1)} for k, v in drivers.items()),
                          key=lambda d: -d["share"])[:8] if completed else [],
        "weekly": [{"week": w, "n": n} for w, n in sorted(weeks.items())][-10:],
        "by_age": group(lambda r: (r["cohort"] or "unknown|").split("|")[0]),
        "by_background": group(lambda r: (r["cohort"] or "|unknown").split("|")[1]),
    }
