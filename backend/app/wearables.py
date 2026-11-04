"""Wearable / phone / CGM importers.

Raw files are parsed in memory and discarded; only the derived weekly summary is stored
(data minimisation). Supported:
  - Apple Health export (export.zip or export.xml): sleep, steps, HRV, resting HR, SpO2,
    blood glucose (e.g. synced from a CGM), dietary caffeine, alcoholic beverages
  - CGM CSV exports (Dexcom Clarity, Abbott LibreView, generic timestamp/glucose)
  - Generic daily CSV (Health Connect / Fitbit / Garmin exports reshaped, or manual):
    date, sleep_hours, steps, resting_hr, hrv_ms, spo2_min, screen_min, screen_bed_min
"""
import csv
import io
import statistics
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta
from xml.etree.ElementTree import iterparse

WINDOW_DAYS = 30
NIGHT_START, NIGHT_END = 21, 6
GLUCOSE_HIGH = 140  # mg/dL


def _dt(s):
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%d-%m-%Y %H:%M", "%m-%d-%Y %I:%M %p", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            d = datetime.strptime(s, fmt)
            return d.replace(tzinfo=None)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _is_night(d):
    return d.hour >= NIGHT_START or d.hour < NIGHT_END


# ---------------------------------------------------------------- Apple Health
APPLE_TYPES = {
    "HKCategoryTypeIdentifierSleepAnalysis": "sleep",
    "HKQuantityTypeIdentifierStepCount": "steps",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv",
    "HKQuantityTypeIdentifierRestingHeartRate": "rhr",
    "HKQuantityTypeIdentifierOxygenSaturation": "spo2",
    "HKQuantityTypeIdentifierBloodGlucose": "glucose",
    "HKQuantityTypeIdentifierDietaryCaffeine": "caffeine",
    "HKQuantityTypeIdentifierNumberOfAlcoholicBeverages": "alcohol",
}
ASLEEP = ("HKCategoryValueSleepAnalysisAsleep",)  # prefix covers Core/Deep/REM/Unspecified


def parse_apple_health(fileobj, filename=""):
    if filename.endswith(".zip") or zipfile.is_zipfile(fileobj):
        fileobj.seek(0)
        z = zipfile.ZipFile(fileobj)
        name = next(n for n in z.namelist() if n.endswith("export.xml") and "cda" not in n)
        stream = z.open(name)
    else:
        fileobj.seek(0)
        stream = fileobj
    recs = defaultdict(list)
    for _, el in iterparse(stream, events=("end",)):
        if el.tag != "Record":
            continue
        kind = APPLE_TYPES.get(el.get("type"))
        if kind:
            start, end = _dt(el.get("startDate", "")), _dt(el.get("endDate", ""))
            if start:
                recs[kind].append((start, end, el.get("value"), el.get("unit")))
        el.clear()
    return summarise_apple(recs)


def summarise_apple(recs):
    latest = max((r[0] for v in recs.values() for r in v), default=None)
    if not latest:
        return {"source": "apple_health", "days": 0}
    since = latest - timedelta(days=WINDOW_DAYS)
    recent = {k: [r for r in v if r[0] >= since] for k, v in recs.items()}
    out = {"source": "apple_health", "window_days": WINDOW_DAYS, "period_end": latest.date().isoformat()}

    # sleep: sum asleep intervals per "sleep date" (night assigned to the date it ends)
    per_night = defaultdict(float)
    mids = {}
    for s, e, v, _ in recent.get("sleep", []):
        if e and v and v.startswith(ASLEEP):
            key = (e - timedelta(hours=12)).date()
            per_night[key] += (e - s).total_seconds() / 3600
            mids.setdefault(key, []).append(s + (e - s) / 2)
    nights = {k: v for k, v in per_night.items() if 2 <= v <= 16}
    if nights:
        out["sleep_avg_h"] = round(statistics.mean(nights.values()), 2)
        out["sleep_nights"] = len(nights)
        out["sleep_short_nights_pct"] = round(100 * sum(v < 6 for v in nights.values()) / len(nights))
        out.update(_social_jetlag({k: min(m) + (max(m) - min(m)) / 2 for k, m in mids.items() if k in nights}))

    steps = defaultdict(float)
    for s, _, v, _ in recent.get("steps", []):
        steps[s.date()] += float(v)
    if steps:
        out["steps_avg"] = round(statistics.mean(steps.values()))
    base = {}
    for key, daily in (("sleep_h", nights), ("steps", dict(steps))):
        b = _baseline(daily)
        if b:
            base[key] = b
    for kind, key in (("hrv", "hrv_sdnn"), ("rhr", "resting_hr")):
        daily = defaultdict(list)
        for s, _, v, _ in recent.get(kind, []):
            daily[s.date()].append(float(v))
        b = _baseline({d: statistics.mean(v) for d, v in daily.items()})
        if b:
            base[key] = b
    if base:
        out["personal_baseline"] = base

    for kind, key in (("hrv", "hrv_sdnn_avg"), ("rhr", "resting_hr_avg")):
        vals = [float(v) for _, _, v, _ in recent.get(kind, [])]
        if vals:
            out[key] = round(statistics.mean(vals), 1)

    low_nights = set()
    for s, _, v, _ in recent.get("spo2", []):
        val = float(v) * (100 if float(v) <= 1 else 1)
        if _is_night(s) and val < 90:
            low_nights.add((s - timedelta(hours=12)).date())
    if recent.get("spo2"):
        out["spo2_low_nights"] = len(low_nights)

    glucose = [(s, float(v) * (18 if (u or "").lower().startswith("mmol") else 1)) for s, _, v, u in recent.get("glucose", [])]
    if glucose:
        out.update(glucose_summary(glucose))

    caf_days = {s.date() for s, _, v, _ in recent.get("caffeine", []) if s.hour >= 16 and float(v) > 0}
    if recent.get("caffeine"):
        weeks = max(1, WINDOW_DAYS / 7)
        out["late_caffeine_days_per_week"] = round(len(caf_days) / weeks, 1)
    alc = [float(v) for _, _, v, _ in recent.get("alcohol", [])]
    if alc:
        out["alcohol_drinks_per_week"] = round(sum(alc) / (WINDOW_DAYS / 7), 1)
    return out


def _baseline(daily, recent_days=7):
    """Compares his last week with his own earlier weeks, so changes are judged against him, not a population cut-off."""
    if len(daily) < recent_days + 5:
        return None
    days = sorted(daily)
    recent, base = [daily[d] for d in days[-recent_days:]], [daily[d] for d in days[:-recent_days]]
    r, b = statistics.mean(recent), statistics.mean(base)
    sd = statistics.pstdev(base) or 1e-9
    return {"recent": round(r, 2), "baseline": round(b, 2), "change_pct": round(100 * (r - b) / b, 1) if b else None,
            "unusual": abs(r - b) > 1.5 * sd}


def _social_jetlag(midpoints):
    wk, we = [], []
    for day, m in midpoints.items():
        hour = m.hour + m.minute / 60
        hour = hour + 24 if hour < 12 else hour  # keep post-midnight midpoints continuous
        # Abu Dhabi weekend is Saturday-Sunday (since 2022); nights ending Sat/Sun are "free" nights
        (we if day.weekday() in (5, 6) else wk).append(hour)
    if wk and we:
        return {"social_jetlag_h": round(abs(statistics.mean(we) - statistics.mean(wk)), 2)}
    return {}


# ---------------------------------------------------------------- CGM
def glucose_summary(points):
    vals = [g for _, g in points]
    night = [g for d, g in points if _is_night(d)]
    out = {"glucose_readings": len(vals), "glucose_mean": round(statistics.mean(vals), 1)}
    if len(vals) > 1:
        out["glucose_cv"] = round(100 * statistics.pstdev(vals) / statistics.mean(vals), 1)
    if night:
        out["night_glucose_high_pct"] = round(100 * sum(g > GLUCOSE_HIGH for g in night) / len(night), 1)
        out["night_glucose_peak"] = round(max(night))
    return out


def parse_cgm_csv(text):
    lines = text.splitlines()
    # LibreView puts a title line above the header
    start = next((i for i, l in enumerate(lines[:5]) if "glucose" in l.lower() and ("time" in l.lower() or "date" in l.lower())), 0)
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    cols = reader.fieldnames or []
    tcol = next((c for c in cols if "timestamp" in c.lower()), None) or next((c for c in cols if "time" in c.lower() or "date" in c.lower()), None)
    gcols = [c for c in cols if "glucose" in c.lower() and "type" not in c.lower() and "unit" not in c.lower()]
    if not tcol or not gcols:
        raise ValueError("Could not find timestamp and glucose columns")
    pts = []
    for row in reader:
        d = _dt(row.get(tcol) or "")
        g = next((row[c] for c in gcols if (row.get(c) or "").strip()), None)
        if not d or g is None:
            continue
        try:
            v = float(g.replace(",", "."))
        except ValueError:
            continue
        mmol = "mmol" in " ".join(gcols).lower() or v < 35
        pts.append((d, v * 18 if mmol else v))
    if not pts:
        raise ValueError("No glucose readings found")
    latest = max(d for d, _ in pts)
    pts = [p for p in pts if p[0] >= latest - timedelta(days=WINDOW_DAYS)]
    out = {"source": "cgm", "window_days": WINDOW_DAYS, "period_end": latest.date().isoformat()}
    out.update(glucose_summary(pts))
    return out


# ---------------------------------------------------------------- generic daily CSV
DAILY_COLS = ["date", "sleep_hours", "steps", "resting_hr", "hrv_ms", "spo2_min", "screen_min", "screen_bed_min"]


def parse_daily_csv(text):
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError("Empty file")

    def col(name):
        vals = []
        for r in rows:
            try:
                vals.append(float(r.get(name, "")))
            except ValueError:
                pass
        return vals

    out = {"source": "daily_csv", "days": len(rows)}
    if s := col("sleep_hours"):
        out["sleep_avg_h"] = round(statistics.mean(s), 2)
        out["sleep_short_nights_pct"] = round(100 * sum(v < 6 for v in s) / len(s))
    if s := col("steps"):
        out["steps_avg"] = round(statistics.mean(s))
    if s := col("resting_hr"):
        out["resting_hr_avg"] = round(statistics.mean(s), 1)
    if s := col("hrv_ms"):
        out["hrv_sdnn_avg"] = round(statistics.mean(s), 1)
    if s := col("spo2_min"):
        out["spo2_low_nights"] = sum(v < 90 for v in s)
    if s := col("screen_min"):
        out["screen_daily_h"] = round(statistics.mean(s) / 60, 1)
    if s := col("screen_bed_min"):
        out["screen_bed_nights_pct"] = round(100 * sum(v >= 30 for v in s) / len(s))
    return out


def detect_and_parse(filename, raw: bytes):
    name = filename.lower()
    if name.endswith(".zip") or name.endswith(".xml"):
        return parse_apple_health(io.BytesIO(raw), name)
    text = raw.decode("utf-8-sig", errors="replace")
    head = text[:2000].lower()
    if "glucose" in head:
        return parse_cgm_csv(text)
    if "sleep_hours" in head or "steps" in head:
        return parse_daily_csv(text)
    raise ValueError("Unrecognised file. Use an Apple Health export, a CGM CSV, or the daily CSV template.")


def merge(existing, new):
    out = dict(existing or {})
    out.update({k: v for k, v in new.items() if v is not None})
    out.setdefault("sources", [])
    if new.get("source") and new["source"] not in out["sources"]:
        out["sources"] = out["sources"] + [new["source"]]
    return out
