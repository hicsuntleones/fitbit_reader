"""Incremental synchronization logic."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from .api import ApiError, HealthApi
from .datatypes import DATA_TYPES, DataType
from .store import Store

log = logging.getLogger("fitbit_reader")

# The Charge 5 may sync with the phone late: every run also re-downloads the last
# days already marked "complete", to pick up data that arrived late.
OVERLAP_DAYS = 3
ECG_OVERLAP_DAYS = 7
DEFAULT_FIRST_RUN_DAYS = 30


def sync(
    api: HealthApi,
    store: Store,
    types: list[str] | None = None,
    since: date | None = None,
    until: date | None = None,
) -> bool:
    """Download missing data. Return True if every type succeeded."""
    today = date.today()
    until = until or today
    state = store.load_state()
    ok = True

    for name in types or list(DATA_TYPES):
        dt = DATA_TYPES[name]
        try:
            if dt.kind == "ecg":
                _sync_ecg(api, store, state, since)
            else:
                _sync_daily(api, store, state, dt, since, until, today)
        except ApiError as e:
            ok = False
            log.error("%s: errore API, salto questo tipo.\n%s", name, e)
        except Exception:
            # an unexpected error on one type must not block the others
            ok = False
            log.exception("%s: errore imprevisto, salto questo tipo.", name)
        store.save_state(state)
    return ok


def _sync_daily(api, store, state, dt: DataType, since, until, today) -> None:
    last = state.get(dt.name)
    if since:
        start = since
    elif last:
        start = date.fromisoformat(last) - timedelta(days=OVERLAP_DAYS - 1)
    else:
        start = today - timedelta(days=DEFAULT_FIRST_RUN_DAYS)

    day = start
    total = 0
    while day <= until:
        points = list(api.list_data_points(dt.name, dt.day_filter(day), dt.page_size))
        store.write_day(dt.name, day, points)
        total += len(points)
        # today is partial: don't mark it as complete
        if day < today and (last is None or day.isoformat() > last):
            last = day.isoformat()
            state[dt.name] = last
        day += timedelta(days=1)
    log.info("%-36s %s -> %s  %7d punti", dt.name, start, until, total)


def _sync_ecg(api, store, state, since) -> None:
    # For ECG the API only accepts "start_time >=": download everything after the
    # last recording already saved.
    last = state.get("electrocardiogram")
    if since:
        start = f"{since.isoformat()}T00:00:00Z"
    elif last:
        # also re-check the last days: an ECG taken offline may arrive late
        back = datetime.fromisoformat(last.replace("Z", "+00:00")) - timedelta(days=ECG_OVERLAP_DAYS)
        start = back.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        start = f"{(date.today() - timedelta(days=DEFAULT_FIRST_RUN_DAYS)).isoformat()}T00:00:00Z"

    flt = f'electrocardiogram.interval.start_time >= "{start}"'
    count = new = 0
    for p in api.list_data_points("electrocardiogram", flt, 100):
        if store.write_ecg(p):
            new += 1
        count += 1
        t = p.get("electrocardiogram", {}).get("interval", {}).get("startTime")
        if t and (last is None or t > last):
            last = t
    if last:
        state["electrocardiogram"] = last
    total = len(list((store.root / "ecg").rglob("*.json")))
    log.info("%-36s da %s  %d trovate, %d nuove (in archivio: %d)",
             "electrocardiogram", start, count, new, total)
