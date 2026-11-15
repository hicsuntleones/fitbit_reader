"""Daily stress / recovery markers derived from the local archive.

Convention: each row is a date D = wake-up day. Nightly markers therefore refer
to the night ending on the morning of D.

Results are cached in data/derived/markers.json and recomputed only for the
dates whose source files have changed.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, median

import pandas as pd

# Marker description: column name -> (label, unit, stress direction)
# direction +1: higher values = more stress; -1: lower values = more stress; 0: neutral
MARKERS: dict[str, tuple[str, str, int]] = {
    "hrv_rmssd": ("HRV notturna (RMSSD)", "ms", -1),
    "hrv_deep_rmssd": ("HRV sonno profondo (RMSSD)", "ms", -1),
    "rhr": ("Battito a riposo", "bpm", +1),
    "hr_sleep_mean": ("Battito medio nel sonno", "bpm", +1),
    "hr_sleep_min": ("Battito minimo nel sonno", "bpm", +1),
    "hr_nonrem": ("Battito sonno non-REM", "bpm", +1),
    "lf_hf_sleep": ("LF/HF nel sonno", "", +1),
    "hrv_entropy": ("Entropia HRV", "", -1),
    "sleep_asleep_min": ("Sonno totale", "min", -1),
    "sleep_efficiency": ("Efficienza del sonno", "%", -1),
    "sleep_deep_min": ("Sonno profondo", "min", -1),
    "sleep_rem_min": ("Sonno REM", "min", -1),
    "sleep_awake_min": ("Veglia nel periodo di sonno", "min", +1),
    "sleep_awakenings": ("Risvegli", "n", +1),
    "sleep_onset_h": ("Ora di addormentamento", "h", 0),
    "temp_dev": ("Temperatura notturna vs baseline", "°C", 0),
    "spo2_avg": ("SpO2 media notturna", "%", 0),
    "steps": ("Passi", "n", 0),
    "wear_hours": ("Ore di utilizzo", "h", 0),
}

# Markers included in the (experimental) composite index
STRESS_INDEX_COMPONENTS = ["hrv_rmssd", "rhr", "hr_sleep_mean"]

CACHE_VERSION = 1
_DAILY_SOURCES = [
    "daily-resting-heart-rate",
    "daily-heart-rate-variability",
    "daily-sleep-temperature-derivations",
    "daily-oxygen-saturation",
    "sleep",
    "heart-rate",
    "heart-rate-variability",
    "steps",
]


# ---------------------------------------------------------------------------
# Archive reading
# ---------------------------------------------------------------------------
def raw_path(data_dir: Path, data_type: str, day: date) -> Path:
    return data_dir / "raw" / data_type / str(day.year) / f"{day.isoformat()}.json"


def load_points(data_dir: Path, data_type: str, day: date) -> list[dict]:
    p = raw_path(data_dir, data_type, day)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("dataPoints", [])


def available_days(data_dir: Path, data_type: str = "heart-rate") -> list[date]:
    root = data_dir / "raw" / data_type
    if not root.exists():
        return []
    return sorted(date.fromisoformat(p.stem) for p in root.rglob("*.json"))


def utc(ts: str) -> datetime:
    """'2026-11-13T02:06:00Z' (optionally with fractions) -> naive UTC datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)


def offset(s: str | None) -> timedelta:
    return timedelta(seconds=float(s.rstrip("s"))) if s else timedelta(0)


def local(ts: str, off: str | None) -> datetime:
    return utc(ts) + offset(off)


def main_sleep(points: list[dict]) -> dict | None:
    """Main sleep session (not a nap, the longest one)."""
    sessions = [p["sleep"] for p in points if "sleep" in p]
    main = [s for s in sessions if s.get("metadata", {}).get("mainSleep")]
    if not main:
        main = [s for s in sessions if not s.get("metadata", {}).get("nap")]
    if not main:
        return None
    return max(main, key=lambda s: int(s.get("summary", {}).get("minutesInSleepPeriod", 0)))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Markers for a single day
# ---------------------------------------------------------------------------
def day_markers(data_dir: Path, day: date) -> dict:
    m: dict = {"date": day.isoformat()}

    for p in load_points(data_dir, "daily-resting-heart-rate", day):
        m["rhr"] = _num(p["dailyRestingHeartRate"].get("beatsPerMinute"))

    for p in load_points(data_dir, "daily-heart-rate-variability", day):
        h = p["dailyHeartRateVariability"]
        m["hrv_rmssd"] = _num(h.get("averageHeartRateVariabilityMilliseconds"))
        deep = _num(h.get("deepSleepRootMeanSquareOfSuccessiveDifferencesMilliseconds"))
        m["hrv_deep_rmssd"] = deep if deep else None  # 0 = not computed
        m["hr_nonrem"] = _num(h.get("nonRemHeartRateBeatsPerMinute"))
        m["hrv_entropy"] = _num(h.get("entropy"))

    for p in load_points(data_dir, "daily-sleep-temperature-derivations", day):
        t = p["dailySleepTemperatureDerivations"]
        n, b = _num(t.get("nightlyTemperatureCelsius")), _num(t.get("baselineTemperatureCelsius"))
        if n is not None and b is not None:
            m["temp_dev"] = n - b

    for p in load_points(data_dir, "daily-oxygen-saturation", day):
        m["spo2_avg"] = _num(p["dailyOxygenSaturation"].get("averagePercentage"))

    # --- main sleep ---
    sleep = main_sleep(load_points(data_dir, "sleep", day))
    start = end = None
    if sleep:
        s = sleep.get("summary", {})
        in_period = _num(s.get("minutesInSleepPeriod")) or 0
        asleep = _num(s.get("minutesAsleep"))
        m["sleep_asleep_min"] = asleep
        m["sleep_awake_min"] = _num(s.get("minutesAwake"))
        if in_period and asleep is not None:
            m["sleep_efficiency"] = 100 * asleep / in_period
        stages = {x["type"]: x for x in s.get("stagesSummary", [])}
        m["sleep_deep_min"] = _num(stages.get("DEEP", {}).get("minutes"))
        m["sleep_rem_min"] = _num(stages.get("REM", {}).get("minutes"))
        awake_count = _num(stages.get("AWAKE", {}).get("count")) or 0
        m["sleep_awakenings"] = awake_count + len(sleep.get("shortAwakenings", []))
        iv = sleep["interval"]
        start, end = utc(iv["startTime"]), utc(iv["endTime"])
        onset = local(iv["startTime"], iv.get("startUtcOffset"))
        h = onset.hour + onset.minute / 60
        m["sleep_onset_h"] = h if h >= 12 else h + 24  # 23:30 -> 23.5, 01:00 -> 25.0

    # --- heart rate: daily wear time and values during sleep ---
    hr_today = load_points(data_dir, "heart-rate", day)
    minutes = {p["heartRate"]["sampleTime"]["physicalTime"][:16] for p in hr_today}
    m["wear_hours"] = len(minutes) / 60 if hr_today else 0.0

    if start and end:
        hr_night = load_points(data_dir, "heart-rate", day - timedelta(days=1)) + hr_today
        bpm = [
            float(p["heartRate"]["beatsPerMinute"])
            for p in hr_night
            if start <= utc(p["heartRate"]["sampleTime"]["physicalTime"]) <= end
        ]
        if bpm:
            m["hr_sleep_mean"] = mean(bpm)
            # robust minimum: median of the lowest 5%
            low = sorted(bpm)[: max(1, len(bpm) // 20)]
            m["hr_sleep_min"] = median(low)

        hrv_night = load_points(data_dir, "heart-rate-variability", day - timedelta(days=1))
        hrv_night += load_points(data_dir, "heart-rate-variability", day)
        ratios = []
        for p in hrv_night:
            h = p["heartRateVariability"]
            t = utc(h["sampleTime"]["physicalTime"])
            md = h.get("metadata", {})
            lf, hf = _num(md.get("lowFrequencyPower")), _num(md.get("highFrequencyPower"))
            if start <= t <= end and lf and hf:
                ratios.append(lf / hf)
        if ratios:
            m["lf_hf_sleep"] = median(ratios)

    steps = load_points(data_dir, "steps", day)
    m["steps"] = sum(float(p["steps"].get("count", 0)) for p in steps)
    return m


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
def _sources_mtime(data_dir: Path, day: date) -> float:
    paths = [raw_path(data_dir, t, day) for t in _DAILY_SOURCES]
    paths += [raw_path(data_dir, t, day - timedelta(days=1)) for t in ("heart-rate", "heart-rate-variability")]
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


def build_markers(data_dir: Path, progress=None) -> pd.DataFrame:
    """Return the markers DataFrame (index: date), updating the cache."""
    cache_path = data_dir / "derived" / "markers.json"
    cache: dict = {}
    if cache_path.exists():
        c = json.loads(cache_path.read_text(encoding="utf-8"))
        if c.get("version") == CACHE_VERSION:
            cache = c["days"]

    days = available_days(data_dir)
    changed = False
    for i, d in enumerate(days):
        key = d.isoformat()
        mt = _sources_mtime(data_dir, d)
        if key not in cache or cache[key].get("_mtime", 0) < mt:
            cache[key] = day_markers(data_dir, d) | {"_mtime": mt}
            changed = True
        if progress:
            progress(i + 1, len(days))

    if changed:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"version": CACHE_VERSION, "days": cache}), encoding="utf-8")

    if not cache:
        return pd.DataFrame(columns=list(MARKERS))
    df = pd.DataFrame(cache.values()).drop(columns="_mtime")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df.reindex(columns=list(MARKERS)).astype(float)
    # days without any data (band never worn, or before the archive starts)
    empty = (df["wear_hours"].fillna(0) == 0) & df.drop(columns=["wear_hours", "steps"]).isna().all(axis=1)
    return df[~empty]
