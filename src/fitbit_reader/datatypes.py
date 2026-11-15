"""Catalogue of the Google Health API data types downloaded by fitbit_reader.

Each type has a "kind" that determines how the time filter is built
(see https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/list):

- sample   -> {field}.sample_time.civil_time
- interval -> {field}.interval.civil_start_time
- session  -> {field}.interval.civil_start_time   (e.g. exercise)
- daily    -> {field}.date
- sleep    -> sleep.interval.civil_end_time        (a night belongs to the wake-up day)
- ecg      -> electrocardiogram.interval.start_time (only >= supported, handled separately)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


def kebab_to_camel(name: str) -> str:
    head, *rest = name.split("-")
    return head + "".join(p.capitalize() for p in rest)


@dataclass(frozen=True)
class DataType:
    name: str  # kebab-case form used in the URL path, e.g. "heart-rate"
    kind: str
    page_size: int = 10000

    @property
    def field(self) -> str:
        """snake_case name used in filters (the API rejects the camelCase form)."""
        return self.name.replace("-", "_")

    @property
    def json_key(self) -> str:
        """camelCase key under which the type appears in the returned DataPoint."""
        return kebab_to_camel(self.name)

    def day_filter(self, day: date) -> str:
        d0, d1 = day.isoformat(), (day + timedelta(days=1)).isoformat()
        f = self.field
        if self.kind == "sample":
            key = f"{f}.sample_time.civil_time"
        elif self.kind in ("interval", "session"):
            key = f"{f}.interval.civil_start_time"
        elif self.kind == "daily":
            key = f"{f}.date"
        elif self.kind == "sleep":
            key = "sleep.interval.civil_end_time"
        else:
            raise ValueError(f"Il tipo {self.name} ({self.kind}) non usa filtri giornalieri")
        return f'{key} >= "{d0}" AND {key} < "{d1}"'


DATA_TYPES: dict[str, DataType] = {
    t.name: t
    for t in [
        # Physiological metrics (scope health_metrics_and_measurements)
        DataType("heart-rate", "sample"),
        DataType("heart-rate-variability", "sample"),
        DataType("oxygen-saturation", "sample"),
        DataType("daily-heart-rate-variability", "daily"),
        DataType("daily-oxygen-saturation", "daily"),
        DataType("daily-resting-heart-rate", "daily"),
        DataType("daily-sleep-temperature-derivations", "daily"),
        # Activity (scope activity_and_fitness)
        DataType("steps", "interval"),
        DataType("active-minutes", "interval"),
        DataType("active-zone-minutes", "interval"),
        # total-calories and floors don't support "list" (only rollUp/dailyRollUp):
        # excluded for now. The Charge 5 has no altimeter, so floors has no data anyway.
        DataType("distance", "interval"),
        DataType("sedentary-period", "interval"),
        DataType("exercise", "session", page_size=25),
        # Sleep (scope sleep)
        DataType("sleep", "sleep", page_size=25),
        # ECG (scope ecg)
        DataType("electrocardiogram", "ecg"),
    ]
}
