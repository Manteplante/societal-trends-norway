"""Forventet levetid — reads `forventet_gjenstaende_levetid`, saved by the SSB notebook.

SSB table 07902, statistikkvariabel `ForvGjenLevetid`: forventet gjenstående
levetid ved alder x, by sex and year.
"""

import plotly.express as px
import streamlit as st

from backend import charts
from backend import storage

# Alder x = 0 — forventet levealder ved fødsel. Matched on the label, not on
# `AlderX_code`: that column is pure digits, so csv reads it back as an int
# while parquet keeps it a string, and a code comparison silently matches
# nothing in one of the two formats.
VED_FODSEL = "0 år"

st.header("📉 Forventet levetid")
st.caption("SSB 07902 — forventet gjenstående levetid ved alder x, etter kjønn.")

df = storage.load("forventet_gjenstaende_levetid")

if df.empty:
    st.info(
        f"No `forventet_gjenstaende_levetid` table yet. Reading from `{storage.describe()}` — "
        "run `make pipeline`, or see Home for setup."
    )
    st.stop()

alder_order = list(df["AlderX"].drop_duplicates())
kjonn_order = sorted(df["Kjonn"].dropna().unique())  # same hue per sex on both charts

# ── Slicers ───────────────────────────────────────────────────────────────────
first, last = int(df["year"].min()), int(df["year"].max())
start, end = st.sidebar.slider("År", first, last, (first, last))

period = df[df["year"].between(start, end)]
ved_fodsel = period[period["AlderX"] == VED_FODSEL]
kurve = period[period["year"] == end]

# ── Where the selection landed ────────────────────────────────────────────────
closing = ved_fodsel[ved_fodsel["year"] == end].sort_values("Kjonn")
if not closing.empty:
    for column, (_, row) in zip(st.columns(len(closing)), closing.iterrows()):
        column.metric(f"{row['Kjonn']} — {end}", f"{row['value']:,.1f} år")

st.plotly_chart(
    charts.style(
        px.line(
            ved_fodsel.sort_values("year"),
            x="year",
            y="value",
            color="Kjonn",
            color_discrete_sequence=charts.PALETTE,
            category_orders={"Kjonn": kjonn_order},
            title=f"Forventet levealder ved fødsel ({start}–{end})",
            labels={"year": "År", "value": "År", "Kjonn": "Kjønn"},
        )
    ),
    width="stretch",
)

# The whole curve for the year the slicer closes on, so every alder x is still
# reachable now that the age is no longer a control of its own.
st.plotly_chart(
    charts.style(
        px.line(
            kurve,
            x="AlderX",
            y="value",
            color="Kjonn",
            color_discrete_sequence=charts.PALETTE,
            category_orders={"Kjonn": kjonn_order, "AlderX": alder_order},
            title=f"Forventet gjenstående levetid etter alder ({end})",
            labels={"AlderX": "Alder x", "value": "År gjenstående", "Kjonn": "Kjønn"},
        ),
        max_xticks=12,
    ),
    width="stretch",
)

with st.expander("Vis data"):
    st.subheader(f"Ved fødsel, {start}–{end}")
    st.dataframe(ved_fodsel[["Kjonn", "year", "value"]], width="stretch", hide_index=True)
    st.subheader(f"Etter alder, {end}")
    st.dataframe(kurve[["Kjonn", "AlderX", "value"]], width="stretch", hide_index=True)
