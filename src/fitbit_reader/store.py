"""Archivio locale.

Struttura:
    data/
      state.json                              ultimo giorno completo per ogni tipo
      raw/<tipo>/<anno>/<YYYY-MM-DD>.json     risposta API integrale (fonte di verità)
      csv/<tipo>/<anno>/<YYYY-MM-DD>.csv      stessa cosa appiattita, per l'analisi
      ecg/<anno>/<timestamp>_<id>.json        registrazione ECG integrale
      ecg/<anno>/<timestamp>_<id>.csv         forma d'onda: t_s, mV
"""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.state_path = root / "state.json"

    # ---- stato ----------------------------------------------------------
    def load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {}

    def save_state(self, state: dict) -> None:
        _atomic_write(self.state_path, json.dumps(state, indent=2, sort_keys=True))

    # ---- dati giornalieri -----------------------------------------------
    def write_day(self, data_type: str, day: date, points: list[dict]) -> None:
        year = str(day.year)
        payload = {
            "dataType": data_type,
            "date": day.isoformat(),
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "count": len(points),
            "dataPoints": points,
        }
        _atomic_write(
            self.root / "raw" / data_type / year / f"{day.isoformat()}.json",
            json.dumps(payload, ensure_ascii=False),
        )
        write_csv(self.root / "csv" / data_type / year / f"{day.isoformat()}.csv", points)

    # ---- ECG ------------------------------------------------------------
    def write_ecg(self, point: dict) -> bool:
        """Salva una registrazione ECG. Restituisce True se non era già in archivio."""
        ecg = point.get("electrocardiogram", {})
        start = ecg.get("interval", {}).get("startTime", "unknown")
        point_id = point.get("name", "").rsplit("/", 1)[-1] or "noid"
        # gli ID possono contenere ':' (es. '2026-11-15T00:26:07.125'), vietati su Windows
        stem = _safe_name(f"{start.replace(':', '').replace('-', '')}_{point_id}")
        folder = self.root / "ecg" / (start[:4] if start[:4].isdigit() else "unknown")
        is_new = not (folder / f"{stem}.json").exists()
        _atomic_write(folder / f"{stem}.json", json.dumps(point, ensure_ascii=False, indent=2))

        samples = ecg.get("waveformSamples") or []
        fs = ecg.get("samplingFrequencyHertz")
        scale = ecg.get("millivoltsScalingFactor")
        if samples and fs and scale:
            tmp = folder / f"{stem}.csv.tmp"
            with tmp.open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["t_s", "mV", "raw"])
                for i, s in enumerate(samples):
                    w.writerow([f"{i / fs:.6f}", f"{s / scale:.6f}", s])
            os.replace(tmp, folder / f"{stem}.csv")
        return is_new


def flatten(obj, prefix: str = "") -> dict:
    """Appiattisce un DataPoint: dizionari annidati -> chiavi col punto, liste -> JSON."""
    out: dict = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}{k}."))
    elif isinstance(obj, list):
        out[prefix[:-1]] = json.dumps(obj, ensure_ascii=False)
    else:
        out[prefix[:-1]] = obj
    return out


def write_csv(path: Path, points: list[dict]) -> None:
    rows = [flatten(p) for p in points]
    columns: list[str] = []
    for r in rows:
        columns.extend(k for k in r if k not in columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def _safe_name(name: str) -> str:
    """Sostituisce i caratteri non ammessi nei nomi di file Windows."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", name).rstrip(". ")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
