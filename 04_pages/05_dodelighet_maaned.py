"""Døde per måned — reads `dode_per_maaned`, saved by the SSB notebook.

SSB table 14657, rolled up to ten-year age bands by SSB's own
`agg_TiAarigGruppering` aggregation.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from backend import charts
from backend import storage

st.header("⚰️ Døde per måned")
st.caption("SSB 14657 — foreløpige månedstall, etter kjønn og tiårig aldersgruppe.")

df = storage.load("dode_per_maaned")

if df.empty:
    st.info(
        f"No `dode_per_maaned` table yet. Reading from `{storage.describe()}` — "
        "run `make pipeline`, or see Home for setup."
    )
    st.stop()

# csv gives the month back as text, parquet as a timestamp — normalise either,
# so the chart gets a real time axis instead of 55 categorical labels.
df["date"] = pd.to_datetime(df["date"])

# ── Slicers ───────────────────────────────────────────────────────────────────
# Eleven age bands is more than the palette holds, so the band is a slicer and
# kjønn carries the colour — three series, one hue each, never cycled.
alder_order = list(df["Alder"].drop_duplicates())
band = st.sidebar.selectbox("Aldersgruppe", alder_order, index=len(alder_order) - 4)

months = sorted(df["Tid"].dropna().unique())  # "2022M01" sorts chronologically as text
start, end = st.sidebar.select_slider("Periode", options=months, value=(months[0], months[-1]))

kjonn_order = sorted(df["Kjonn"].dropna().unique())
shown = df[(df["Alder"] == band) & df["Tid"].between(start, end)]

# ── Where the selection landed ────────────────────────────────────────────────
closing = shown[shown["Tid"] == end].sort_values("Kjonn")
if not closing.empty:
    for column, (_, row) in zip(st.columns(len(closing)), closing.iterrows()):
        column.metric(f"{row['Kjonn']} — {end}", f"{row['value']:,.0f}")

st.plotly_chart(
    charts.style(
        px.line(
            shown.sort_values("date"),
            x="date",
            y="value",
            color="Kjonn",
            color_discrete_sequence=charts.PALETTE,
            category_orders={"Kjonn": kjonn_order},
            title=f"Døde per måned, {band} ({start}–{end})",
            labels={"date": "Måned", "value": "Døde", "Kjonn": "Kjønn"},
        )
    ),
    width="stretch",
)

with st.expander("Vis data"):
    st.dataframe(shown[["Kjonn", "Alder", "Tid", "value"]], width="stretch", hide_index=True)
