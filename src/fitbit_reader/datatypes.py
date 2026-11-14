"""Catalogo dei tipi di dato Google Health API scaricati da fitbit_reader.

Ogni tipo ha un "kind" che decide come costruire il filtro temporale
(vedi https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/list):

- sample   -> {campo}.sample_time.civil_time
- interval -> {campo}.interval.civil_start_time
- session  -> {campo}.interval.civil_start_time   (es. exercise)
- daily    -> {campo}.date
- sleep    -> sleep.interval.civil_end_time        (la notte appartiene al giorno del risveglio)
- ecg      -> electrocardiogram.interval.start_time (supporta solo >=, gestito a parte)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


def kebab_to_camel(name: str) -> str:
    head, *rest = name.split("-")
    return head + "".join(p.capitalize() for p in rest)


@dataclass(frozen=True)
class DataType:
    name: str  # forma kebab-case usata nel percorso URL, es. "heart-rate"
    kind: str
    page_size: int = 10000

    @property
    def field(self) -> str:
        """Nome snake_case usato nei filtri (l'API rifiuta la forma camelCase)."""
        return self.name.replace("-", "_")

    @property
    def json_key(self) -> str:
        """Chiave camelCase con cui il tipo compare nel DataPoint restituito."""
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
        # Metriche fisiologiche (scope health_metrics_and_measurements)
        DataType("heart-rate", "sample"),
        DataType("heart-rate-variability", "sample"),
        DataType("oxygen-saturation", "sample"),
        DataType("daily-heart-rate-variability", "daily"),
        DataType("daily-oxygen-saturation", "daily"),
        DataType("daily-resting-heart-rate", "daily"),
        DataType("daily-sleep-temperature-derivations", "daily"),
        # Attività (scope activity_and_fitness)
        DataType("steps", "interval"),
        DataType("active-minutes", "interval"),
        DataType("active-zone-minutes", "interval"),
        # total-calories e floors non supportano "list" (solo rollUp/dailyRollUp):
        # esclusi per ora. Il Charge 5 non ha altimetro, quindi floors non ha dati.
        DataType("distance", "interval"),
        DataType("sedentary-period", "interval"),
        DataType("exercise", "session", page_size=25),
        # Sonno (scope sleep)
        DataType("sleep", "sleep", page_size=25),
        # ECG (scope ecg)
        DataType("electrocardiogram", "ecg"),
    ]
}
