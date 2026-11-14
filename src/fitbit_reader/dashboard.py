"""Dashboard Streamlit per esplorare e confrontare i dati per fasi dello studio.

Avvio:  dashboard.bat   (oppure  python -m streamlit run src/fitbit_reader/dashboard.py)
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from fitbit_reader.markers import (
    MARKERS,
    STRESS_INDEX_COMPONENTS,
    build_markers,
    load_points,
    local,
    main_sleep,
)
from fitbit_reader.study import (
    assign_phases,
    load_study,
    phase_list,
    phase_summary,
    save_study,
    stress_index,
    valid_mask,
)

DATA_DIR = Path(os.environ.get("FITBIT_DATA_DIR", "data"))
STRESS = "stress_index"
LABELS = {STRESS: ("Indice di stress composito (sperimentale)", "z", +1)} | MARKERS
STAGE_LEVEL = {"DEEP": 0, "LIGHT": 1, "REM": 2, "AWAKE": 3}
STAGE_NAMES = ["Profondo", "Leggero", "REM", "Sveglio"]
REF_DAY = date(2000, 1, 2)  # asse "ora del giorno" comune per sovrapporre giorni diversi

st.set_page_config(page_title="fitbit_reader", layout="wide")


def label(col: str) -> str:
    name, unit, _ = LABELS[col]
    return f"{name} [{unit}]" if unit else name


@st.cache_data(show_spinner=False)
def get_markers(_stamp: float) -> pd.DataFrame:
    return build_markers(DATA_DIR)


def data_stamp() -> float:
    """Cambia quando arrivano nuovi dati (invalida la cache di Streamlit)."""
    st_file = DATA_DIR / "state.json"
    return st_file.stat().st_mtime if st_file.exists() else 0.0


# ---------------------------------------------------------------------------
# Caricamento
# ---------------------------------------------------------------------------
if not (DATA_DIR / "raw").exists():
    st.error(f"Nessun dato in {DATA_DIR.resolve()}. Esegui prima  fitbit.bat sync")
    st.stop()

with st.spinner("Calcolo dei marcatori (solo i giorni nuovi o modificati)..."):
    markers = get_markers(data_stamp())

study = load_study(DATA_DIR)

st.sidebar.title("fitbit_reader")
st.sidebar.caption(f"Dati: {markers.index.min():%d/%m/%Y} – {markers.index.max():%d/%m/%Y}")
split = st.sidebar.toggle(
    f"Suddividi '{study.get('split_phase')}' in blocchi da {study.get('split_days', 30)} giorni", value=True
)
show_excluded = st.sidebar.toggle("Mostra i giorni esclusi", value=True)

phases = phase_list(study, split)
phase_names = [p["name"] for p in phases]
phase_of = assign_phases(markers.index, phases)
valid = valid_mask(markers, study)

baseline_name = study.get("baseline")
ref_mask = valid & (phase_of == baseline_name)
if ref_mask.sum() < 5:
    ref_mask = valid
    st.sidebar.warning("Baseline non definita o troppo corta: l'indice composito usa tutti i giorni validi come riferimento.")

df = markers.copy()
df[STRESS] = stress_index(df.where(valid), ref_mask)
st.sidebar.caption(
    f"Giorni validi: {int(valid.sum())} su {len(valid)} "
    f"(utilizzo ≥ {study.get('min_wear_hours')} h, esclusioni manuali tolte)"
)
if not phases:
    st.sidebar.info("Nessuna fase definita: impostale nella scheda **Fasi ed esclusioni**.")

tab_trend, tab_cmp, tab_day, tab_ecg, tab_cfg = st.tabs(
    ["📈 Andamento", "⚖️ Confronto fasi", "🕒 Giornata", "❤️ ECG", "⚙️ Fasi ed esclusioni"]
)


def add_phase_bands(fig, rows: int, annotate: bool = True):
    for ph in phases:
        x0 = pd.Timestamp(ph["start"]) - pd.Timedelta(hours=12)
        x1 = pd.Timestamp(ph["end"]) + pd.Timedelta(hours=12)
        for r in range(1, rows + 1):
            fig.add_vrect(x0=x0, x1=x1, fillcolor=ph["color"], opacity=0.10, line_width=0, row=r, col=1)
        if annotate:
            fig.add_annotation(
                x=x0 + (x1 - x0) / 2, y=1.0, yref="paper", text=ph["name"], showarrow=False,
                font=dict(color=ph["color"], size=12), yanchor="bottom",
            )


# ---------------------------------------------------------------------------
# Andamento
# ---------------------------------------------------------------------------
with tab_trend:
    c1, c2, c3 = st.columns([4, 1, 1])
    cols = c1.multiselect(
        "Marcatori",
        list(LABELS),
        default=[STRESS, "hrv_rmssd", "rhr", "hr_sleep_mean", "sleep_efficiency"],
        format_func=lambda c: LABELS[c][0],
    )
    window = c2.slider("Media mobile (giorni)", 1, 28, 7)
    period = c3.selectbox("Periodo", ["Tutto", "Ultimi 90 giorni", "Ultimi 30 giorni"])

    view = df
    if period != "Tutto":
        days = 90 if "90" in period else 30
        view = df[df.index >= df.index.max() - pd.Timedelta(days=days)]
    v_valid = valid.loc[view.index]

    if cols:
        fig = make_subplots(rows=len(cols), cols=1, shared_xaxes=True, vertical_spacing=0.03,
                            subplot_titles=[label(c) for c in cols])
        for i, c in enumerate(cols, start=1):
            y = view[c].where(v_valid)
            fig.add_scatter(x=view.index, y=y, mode="markers", marker=dict(size=5, color="#888"),
                            name=LABELS[c][0], showlegend=False, row=i, col=1,
                            hovertemplate="%{x|%a %d/%m/%Y}: %{y:.2f}<extra></extra>")
            roll = y.rolling(window, min_periods=max(1, window // 2), center=True).mean()
            fig.add_scatter(x=view.index, y=roll, mode="lines", line=dict(width=2.5, color="#1f77b4"),
                            name=f"media {window} gg", showlegend=False, row=i, col=1,
                            hovertemplate=f"media {window} gg: %{{y:.2f}}<extra></extra>")
            if show_excluded and c != STRESS:
                ex = view[c].where(~v_valid)
                fig.add_scatter(x=view.index, y=ex, mode="markers", marker=dict(symbol="x", size=6, color="#d62728"),
                                name="escluso", showlegend=False, row=i, col=1,
                                hovertemplate="escluso %{x|%d/%m}: %{y:.2f}<extra></extra>")
        add_phase_bands(fig, len(cols))
        fig.update_layout(height=230 * len(cols) + 60, margin=dict(t=50, b=20, l=10, r=10), hovermode="x unified")
        st.plotly_chart(fig, width="stretch")

    with st.expander("Come leggere i marcatori"):
        st.markdown(
            f"""
- Ogni punto è una **data di risveglio**: i valori notturni si riferiscono alla notte precedente.
- **Più stress** tende a dare HRV più bassa, battito a riposo e nel sonno più alto, sonno più frammentato.
- **Indice composito (sperimentale)**: media degli z-score di {", ".join(LABELS[c][0] for c in STRESS_INDEX_COMPONENTS)},
  rispetto ai giorni validi della baseline, orientati in modo che **positivo = più stress** del solito.
  Non è validato clinicamente: serve a riassumere, non a sostituire i singoli marcatori.
- Le ✕ rosse sono giorni esclusi (poco utilizzo del braccialetto o esclusi a mano).
"""
        )

# ---------------------------------------------------------------------------
# Confronto fasi
# ---------------------------------------------------------------------------
with tab_cmp:
    if not phases:
        st.info("Definisci almeno una fase nella scheda **Fasi ed esclusioni**.")
    else:
        col = st.selectbox("Marcatore", list(LABELS), format_func=lambda c: LABELS[c][0], key="cmp_col")
        vals = df[col].where(valid)
        present = [p for p in phase_names if (phase_of == p).any()]

        fig = go.Figure()
        for ph in phases:
            if ph["name"] not in present:
                continue
            v = vals[phase_of == ph["name"]].dropna()
            fig.add_box(y=v, name=ph["name"], marker_color=ph["color"], boxpoints="all", jitter=0.4,
                        pointpos=0, boxmean=True, customdata=v.index.strftime("%d/%m/%Y"),
                        hovertemplate="%{customdata}: %{y:.2f}<extra></extra>")
        fig.update_layout(yaxis_title=label(col), height=450, showlegend=False, margin=dict(t=20))
        st.plotly_chart(fig, width="stretch")

        if baseline_name not in present:
            st.warning(f"La fase di riferimento '{baseline_name}' non ha giorni: le differenze non sono calcolabili.")
        tbl = phase_summary(vals, phase_of, present, baseline_name)
        st.dataframe(tbl.style.format(precision=2, na_rep="—"), width="stretch")

        st.subheader("Panoramica: tutti i marcatori rispetto alla baseline")
        st.caption(
            "Hedges g = differenza tra le medie in deviazioni standard (≈0.2 piccola, 0.5 media, 0.8 grande). "
            "🔴 = nella direzione di più stress, 🟢 = di meno stress."
        )
        rows = []
        for c in LABELS:
            direction = LABELS[c][2]
            s = phase_summary(df[c].where(valid), phase_of, present, baseline_name)
            row = {"Marcatore": LABELS[c][0]}
            for p in present:
                if p == baseline_name or "Hedges g" not in s.columns:
                    continue
                g = s.loc[p, "Hedges g"]
                d = s.loc[p, "Δ %"]
                if pd.isna(g):
                    row[p] = "—"
                    continue
                icon = "" if direction == 0 or abs(g) < 0.2 else ("🔴" if g * direction > 0 else "🟢")
                row[p] = f"{icon} g={g:+.2f}  ({d:+.1f}%)"
            rows.append(row)
        st.dataframe(pd.DataFrame(rows).set_index("Marcatore"), width="stretch")
        st.caption(
            "⚠️ I giorni consecutivi non sono indipendenti (stagione, abitudini, malattie): "
            "le dimensioni dell'effetto descrivono il cambiamento ma non sono un test statistico."
        )

# ---------------------------------------------------------------------------
# Giornata
# ---------------------------------------------------------------------------
def day_series(day: date):
    """Battito, fasi del sonno e passi tra le 18:00 del giorno prima e la mezzanotte, ora locale."""
    shift = datetime.combine(REF_DAY, datetime.min.time()) - datetime.combine(day, datetime.min.time())
    lo = datetime.combine(day - timedelta(days=1), datetime.min.time()) + timedelta(hours=18)
    hr = []
    for d in (day - timedelta(days=1), day):
        for p in load_points(DATA_DIR, "heart-rate", d):
            h = p["heartRate"]
            t = local(h["sampleTime"]["physicalTime"], h["sampleTime"].get("utcOffset"))
            if t >= lo:
                hr.append((t + shift, float(h["beatsPerMinute"])))
    hr = pd.DataFrame(hr, columns=["t", "bpm"]).sort_values("t")

    stages = []
    sl = main_sleep(load_points(DATA_DIR, "sleep", day))
    if sl:
        for s in sl.get("stages", []):
            stages.append((local(s["startTime"], s.get("startUtcOffset")) + shift, STAGE_LEVEL.get(s["type"], 3)))
        last = sl["stages"][-1] if sl.get("stages") else None
        if last:
            stages.append((local(last["endTime"], last.get("endUtcOffset")) + shift, stages[-1][1]))
    stages = pd.DataFrame(stages, columns=["t", "level"])

    steps = []
    for p in load_points(DATA_DIR, "steps", day):
        iv = p["steps"]["interval"]
        steps.append((local(iv["startTime"], iv.get("startUtcOffset")) + shift, float(p["steps"]["count"])))
    steps = pd.DataFrame(steps, columns=["t", "count"])
    return hr, stages, steps


with tab_day:
    first, last = markers.index.min().date(), markers.index.max().date()
    c1, c2 = st.columns(2)
    d1 = c1.date_input("Giorno", value=last, min_value=first, max_value=last, format="DD/MM/YYYY")
    d2 = c2.date_input("Confronta con (facoltativo)", value=None, min_value=first, max_value=last,
                       format="DD/MM/YYYY")
    days = [(d1, "#1f77b4")] + ([(d2, "#ff7f0e")] if d2 else [])

    n_hyp = len(days)
    fig = make_subplots(rows=2 + n_hyp, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        row_heights=[0.5] + [0.12] * n_hyp + [0.2],
                        subplot_titles=["Battito [bpm]"] + [f"Sonno {d:%d/%m}" for d, _ in days] + ["Passi / min"])
    for i, (d, color) in enumerate(days):
        hr, stg, stp = day_series(d)
        if not hr.empty:
            fig.add_scatter(x=hr["t"], y=hr["bpm"], mode="lines", line=dict(width=1, color=color),
                            name=f"{d:%a %d/%m}", row=1, col=1)
        if not stg.empty:
            fig.add_scatter(x=stg["t"], y=stg["level"], mode="lines", line=dict(shape="hv", color=color),
                            showlegend=False, row=2 + i, col=1)
        if not stp.empty:
            fig.add_bar(x=stp["t"], y=stp["count"], marker_color=color, opacity=0.7, showlegend=False,
                        row=2 + n_hyp, col=1)
    for i in range(n_hyp):
        fig.update_yaxes(tickvals=[0, 1, 2, 3], ticktext=STAGE_NAMES, range=[-0.5, 3.5], row=2 + i, col=1)
    fig.update_xaxes(tickformat="%H:%M", dtick=3 * 3600 * 1000)
    fig.update_layout(height=750, barmode="overlay", hovermode="x unified", margin=dict(t=40, l=10, r=10),
                      legend=dict(orientation="h", y=1.06))
    st.plotly_chart(fig, width="stretch")
    st.caption("Asse orizzontale: ora locale, dalle 18:00 del giorno prima alla mezzanotte del giorno scelto.")

    sel = [pd.Timestamp(d) for d, _ in days if pd.Timestamp(d) in df.index]
    if sel:
        t = df.loc[sel, list(LABELS)].T
        t.index = [LABELS[c][0] for c in t.index]
        t.columns = [f"{c:%a %d/%m}" for c in t.columns]
        st.dataframe(t.style.format(precision=2, na_rep="—"), width="stretch")

# ---------------------------------------------------------------------------
# ECG
# ---------------------------------------------------------------------------
with tab_ecg:
    files = sorted((DATA_DIR / "ecg").rglob("*.json"), reverse=True)
    if not files:
        st.info("Nessuna registrazione ECG nell'archivio. Avvia l'app ECG sul Charge 5, poi esegui  fitbit.bat sync.")
    else:
        names = {}
        for f in files:
            e = json.loads(f.read_text(encoding="utf-8")).get("electrocardiogram", {})
            iv = e.get("interval", {})
            t = local(iv["startTime"], iv.get("startUtcOffset")) if iv.get("startTime") else None
            names[f] = f"{t:%d/%m/%Y %H:%M}  –  {e.get('resultClassification', '?')}" if t else f.stem
        f = st.selectbox("Registrazione", files, format_func=names.get)
        e = json.loads(f.read_text(encoding="utf-8"))["electrocardiogram"]
        samples = np.array(e.get("waveformSamples") or [], dtype=float)
        fs, scale = e.get("samplingFrequencyHertz"), e.get("millivoltsScalingFactor")
        c1, c2, c3 = st.columns(3)
        c1.metric("Battito medio", f"{e.get('beatsPerMinuteAvg', '—')} bpm")
        c2.metric("Frequenza di campionamento", f"{fs} Hz" if fs else "—")
        c3.metric("Classificazione Fitbit", e.get("resultClassification", "—"))
        if len(samples) and fs and scale:
            t = np.arange(len(samples)) / fs
            fig = go.Figure(go.Scatter(x=t, y=samples / scale, mode="lines", line=dict(width=1, color="#c00")))
            fig.update_xaxes(title="s", dtick=0.2, gridcolor="rgba(200,0,0,0.15)", range=[0, min(10, t[-1])])
            fig.update_yaxes(title="mV", dtick=0.5, gridcolor="rgba(200,0,0,0.15)")
            fig.update_layout(height=380, margin=dict(t=10), plot_bgcolor="#fff8f8")
            st.plotly_chart(fig, width="stretch")
            st.caption("Griglia: 0.2 s × 0.5 mV. Trascina per scorrere i 30 secondi della registrazione.")

# ---------------------------------------------------------------------------
# Configurazione fasi ed esclusioni
# ---------------------------------------------------------------------------
with tab_cfg:
    st.markdown(
        "Definisci le fasi dello studio. Le date sono incluse. La fase di riferimento serve per "
        "le differenze e per l'indice composito. Modifica le tabelle e premi **Salva**."
    )
    ph_df = pd.DataFrame(study["phases"], columns=["name", "start", "end"])
    for c in ("start", "end"):
        ph_df[c] = pd.to_datetime(ph_df[c]).dt.date
    ph_edit = st.data_editor(
        ph_df, num_rows="dynamic", width="stretch", key="ph",
        column_config={
            "name": st.column_config.TextColumn("Fase", required=True),
            "start": st.column_config.DateColumn("Inizio", format="DD/MM/YYYY"),
            "end": st.column_config.DateColumn("Fine", format="DD/MM/YYYY"),
        },
    )
    names_now = [n for n in ph_edit["name"].dropna().tolist() if n]
    c1, c2, c3, c4 = st.columns(4)
    base_sel = c1.selectbox("Fase di riferimento", names_now,
                            index=names_now.index(baseline_name) if baseline_name in names_now else 0)
    split_sel = c2.selectbox("Fase da suddividere", ["(nessuna)"] + names_now,
                             index=(names_now.index(study.get("split_phase")) + 1)
                             if study.get("split_phase") in names_now else 0)
    split_days = c3.number_input("Giorni per blocco", 1, 365, int(study.get("split_days", 30)))
    min_wear = c4.number_input("Ore minime di utilizzo", 0, 24, int(study.get("min_wear_hours", 18)))

    st.markdown("**Giorni da escludere** (malattia, braccialetto non indossato, viaggi, ...)")
    ex_df = pd.DataFrame(study.get("exclusions", []), columns=["date", "reason"])
    ex_df["date"] = pd.to_datetime(ex_df["date"]).dt.date
    ex_edit = st.data_editor(
        ex_df, num_rows="dynamic", width="stretch", key="ex",
        column_config={
            "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
            "reason": st.column_config.TextColumn("Motivo"),
        },
    )

    if st.button("💾 Salva", type="primary"):
        def iso(v):
            return None if pd.isna(v) else pd.Timestamp(v).date().isoformat()

        study["phases"] = [
            {"name": r["name"], "start": iso(r["start"]), "end": iso(r["end"])}
            for _, r in ph_edit.iterrows() if isinstance(r["name"], str) and r["name"]
        ]
        study["baseline"] = base_sel
        study["split_phase"] = None if split_sel == "(nessuna)" else split_sel
        study["split_days"] = int(split_days)
        study["min_wear_hours"] = int(min_wear)
        study["exclusions"] = [
            {"date": iso(r["date"]), "reason": r["reason"] if isinstance(r["reason"], str) else ""}
            for _, r in ex_edit.iterrows() if not pd.isna(r["date"])
        ]
        save_study(DATA_DIR, study)
        st.success("Salvato.")
        st.rerun()

    st.divider()
    st.markdown("**Ore di utilizzo per giorno** (utile per scegliere la soglia)")
    wear = go.Figure(go.Bar(x=markers.index, y=markers["wear_hours"], marker_color="#888"))
    wear.add_hline(y=study.get("min_wear_hours", 18), line_dash="dash", line_color="red")
    wear.update_layout(height=250, margin=dict(t=10), yaxis_title="h")
    st.plotly_chart(wear, width="stretch")
