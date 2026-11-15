"""Study design (phases, exclusions) and statistics to compare phases.

Configuration in data/study.json (outside git, editable from the dashboard):

{
  "phases": [{"name": "Baseline", "start": "2026-09-01", "end": "2026-11-30"}, ...],
  "baseline": "Baseline",
  "split_phase": "Terapia",      # phase to split into 30-day blocks
  "min_wear_hours": 18,          # days with fewer wear hours are excluded
  "exclusions": [{"date": "2026-10-03", "reason": "febbre"}]
}
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .markers import MARKERS, STRESS_INDEX_COMPONENTS

DEFAULT_STUDY = {
    "phases": [
        {"name": "Baseline", "start": None, "end": None},
        {"name": "Terapia", "start": None, "end": None},
        {"name": "Follow-up", "start": None, "end": None},
    ],
    "baseline": "Baseline",
    "split_phase": "Terapia",
    "split_days": 30,
    "min_wear_hours": 18,
    "exclusions": [],
}

PHASE_COLORS = ["#4C78A8", "#F58518", "#54A24B", "#B279A2", "#E45756", "#72B7B2", "#EECA3B"]


def study_path(data_dir: Path) -> Path:
    return data_dir / "study.json"


def load_study(data_dir: Path) -> dict:
    p = study_path(data_dir)
    if p.exists():
        return DEFAULT_STUDY | json.loads(p.read_text(encoding="utf-8"))
    return json.loads(json.dumps(DEFAULT_STUDY))


def save_study(data_dir: Path, study: dict) -> None:
    p = study_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(study, indent=2, ensure_ascii=False), encoding="utf-8")


def _d(v) -> date | None:
    if v is None or (isinstance(v, float) and math.isnan(v)) or v == "":
        return None
    if isinstance(v, date):
        return v
    return pd.Timestamp(v).date()


def defined_phases(study: dict) -> list[dict]:
    """Phases with valid dates."""
    out = []
    for ph in study["phases"]:
        s, e = _d(ph.get("start")), _d(ph.get("end"))
        if not ph.get("name") or not s or not e or e < s:
            continue
        out.append({"name": ph["name"], "start": s, "end": e})
    return out


def split_blocks(phase: dict, days: int) -> list[dict]:
    blocks, s, i = [], phase["start"], 1
    while s <= phase["end"]:
        e = min(s + pd.Timedelta(days=days - 1).to_pytimedelta(), phase["end"])
        blocks.append({"name": f"{phase['name']} M{i}", "start": s, "end": e})
        s, i = e + pd.Timedelta(days=1).to_pytimedelta(), i + 1
    return blocks


def phase_list(study: dict, split: bool) -> list[dict]:
    out = []
    for ph in defined_phases(study):
        if split and ph["name"] == study.get("split_phase"):
            out += split_blocks(ph, int(study.get("split_days", 30)))
        else:
            out.append(ph)
    for i, ph in enumerate(out):
        ph["color"] = PHASE_COLORS[i % len(PHASE_COLORS)]
    return out


def assign_phases(index: pd.DatetimeIndex, phases: list[dict]) -> pd.Series:
    s = pd.Series(pd.NA, index=index, dtype="object")
    for ph in phases:
        mask = (index.date >= ph["start"]) & (index.date <= ph["end"])
        s[mask] = ph["name"]
    return s


def valid_mask(df: pd.DataFrame, study: dict) -> pd.Series:
    """True for usable days (enough wear time and not manually excluded)."""
    ok = df["wear_hours"].fillna(0) >= float(study.get("min_wear_hours", 0))
    excluded = {_d(x.get("date")) for x in study.get("exclusions", [])}
    ok &= ~pd.Series(df.index.date, index=df.index).isin(excluded)
    return ok


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def stress_index(df: pd.DataFrame, reference: pd.Series) -> pd.Series:
    """EXPERIMENTAL composite index: mean of the components' z-scores (relative to the
    reference days), oriented so that positive = more stress."""
    zs = []
    for col in STRESS_INDEX_COMPONENTS:
        ref = df.loc[reference, col].dropna()
        if len(ref) < 5 or ref.std() == 0:
            continue
        direction = MARKERS[col][2]
        zs.append(direction * (df[col] - ref.mean()) / ref.std())
    if not zs:
        return pd.Series(np.nan, index=df.index)
    z = pd.concat(zs, axis=1)
    return z.mean(axis=1).where(z.notna().sum(axis=1) >= 2)


def hedges_g(a: pd.Series, b: pd.Series) -> float:
    a, b = a.dropna(), b.dropna()
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    sp = math.sqrt(((na - 1) * a.var() + (nb - 1) * b.var()) / (na + nb - 2))
    if sp == 0:
        return float("nan")
    j = 1 - 3 / (4 * (na + nb) - 9)
    return j * (a.mean() - b.mean()) / sp


def phase_summary(values: pd.Series, phases: pd.Series, order: list[str], baseline: str) -> pd.DataFrame:
    rows = []
    base = values[phases == baseline]
    for name in order:
        v = values[phases == name].dropna()
        row = {
            "Fase": name,
            "Giorni": len(v),
            "Media": v.mean(),
            "Dev. std": v.std(),
            "Mediana": v.median(),
            "IQR": v.quantile(0.75) - v.quantile(0.25) if len(v) else np.nan,
        }
        if name != baseline and len(base.dropna()):
            row["Δ vs baseline"] = v.mean() - base.mean()
            row["Δ %"] = 100 * (v.mean() - base.mean()) / abs(base.mean()) if base.mean() else np.nan
            row["Hedges g"] = hedges_g(v, base)
        rows.append(row)
    return pd.DataFrame(rows).set_index("Fase")
