"""Omsorgstjenester — reads `omsorg_bistandsbehov`, saved by the SSB notebook.

SSB table 12292: hjemmetjenestebrukere med omfattende bistandsbehov, in four
age bands, for the kommuner and fylker that exist under today's boundaries.
"""

import plotly.express as px
import streamlit as st

from backend import charts
from backend import storage

REGION = "KOKkommuneregion0000"
LEVELS = ("Landet", "Fylke", "Kommune")

st.header("🏥 Omsorgstjenester")
st.caption("SSB 12292 — hjemmetjenestebrukere med omfattende bistandsbehov, etter aldersgruppe.")

df = storage.load("omsorg_bistandsbehov")

if df.empty:
    st.info(
        f"No `omsorg_bistandsbehov` table yet. Reading from `{storage.describe()}` — "
        "run `make pipeline`, or see Home for setup."
    )
    st.stop()

# Row order is the band order the notebook saved, so the bands stay in SSB's
# own sequence rather than sorting `80 år og over` in front of `67-79 år`.
band_order = list(df["aldersgruppe"].drop_duplicates())

# ── Slicers ───────────────────────────────────────────────────────────────────
available = [level for level in LEVELS if level in set(df["region_level"])]
level = st.sidebar.selectbox("Regionnivå", available, index=0)

scope = df[df["region_level"] == level]

if level == "Kommune":
    counties = ["Alle fylker"] + sorted(scope["fylke"].dropna().unique())
    county = st.sidebar.selectbox("Fylke", counties, index=0)
    if county != "Alle fylker":
        scope = scope[scope["fylke"] == county]

regions = sorted(scope[REGION].dropna().unique())
region = st.sidebar.selectbox("Region", regions, index=0)

# Four bands, four hues — the colour channel carries the measure, so the region
# above is a single pick rather than a multiselect.
bands = st.sidebar.multiselect("Aldersgruppe", band_order, default=band_order)

first, last = int(df["year"].min()), int(df["year"].max())
start, end = st.sidebar.slider("År", first, last, (first, last))

shown = scope[
    (scope[REGION] == region)
    & scope["aldersgruppe"].isin(bands)
    & scope["year"].between(start, end)
]

if shown.empty:
    st.info(
        f"`{region}` reports nothing for {start}–{end} in the selected bands. "
        "A region only has figures from the year its current boundaries took "
        "effect — the 2020 and 2024 reforms are why the early years are thin."
    )
    st.stop()

# ── Where the selection landed ────────────────────────────────────────────────
closing_year = int(shown["year"].max())
closing = shown[shown["year"] == closing_year].set_index("aldersgruppe")

for column, band in zip(st.columns(len(bands)), [b for b in band_order if b in bands]):
    value = closing["value"].get(band)
    column.metric(f"{band} — {closing_year}", f"{value:,.0f}" if value is not None else "—")

st.plotly_chart(
    charts.style(
        px.line(
            shown.sort_values("year"),
            x="year",
            y="value",
            color="aldersgruppe",
            color_discrete_sequence=charts.PALETTE,
            # The full band order, so deselecting a band leaves the rest their hue.
            category_orders={"aldersgruppe": band_order},
            markers=True,
            title=f"Hjemmetjenestebrukere med omfattende bistandsbehov — {region} ({start}–{end})",
            labels={"year": "År", "value": "Brukere", "aldersgruppe": "Aldersgruppe"},
        )
    ),
    width="stretch",
)

st.caption(
    "Bandene overlapper: «67 år og over» er «67-79 år» og «80 år og over» lagt "
    "sammen. Kommuner og fylker er de som gjelder i dag (KLASS 2025)."
)

with st.expander("Vis data"):
    st.dataframe(
        shown[[REGION, "fylke", "aldersgruppe", "year", "value"]],
        width="stretch",
        hide_index=True,
    )
