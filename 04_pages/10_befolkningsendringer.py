"""Befolkningsendringer — reads `befolkning_endringer`, saved by the SSB notebook.

SSB table 06913: befolkning 1. januar and the year's births, deaths and moves,
per fylke and kommune, from 2024 — the first year today's administrative units
existed.
"""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from backend import charts
from backend import regions
from backend import storage

NATURAL = {"levendefodte": "Levendefødte", "dode": "Døde", "fodselsoverskudd": "Fødselsoverskudd"}
MOVES = {"innflyttinger": "Innflyttinger", "utflyttinger": "Utflyttinger", "folketilvekst": "Folketilvekst"}

st.header("🔄 Befolkningsendringer")
st.caption("SSB 06913 — befolkning og endringer, etter region og år.")

df = storage.load("befolkning_endringer")

if df.empty:
    st.info(
        f"No `befolkning_endringer` table yet. Reading from `{storage.describe()}` — "
        "run `make pipeline`, or see Home for setup."
    )
    st.stop()

# ── Slicers ───────────────────────────────────────────────────────────────────
shown, region = regions.pick(df)

first, last = int(df["year"].min()), int(df["year"].max())
if first < last:
    start, end = st.sidebar.slider("År", first, last, (first, last))
    shown = shown[shown["year"].between(start, end)]

shown = shown.sort_values("year")

if shown.empty:
    st.info(f"Ingen tall for {region} i valgt periode.")
    st.stop()

# ── Births and deaths ─────────────────────────────────────────────────────────
natural = shown.rename(columns=NATURAL)

st.plotly_chart(
    charts.style(
        px.line(
            natural,
            x="year",
            y=list(NATURAL.values()),
            color_discrete_sequence=charts.PALETTE,
            markers=True,
            title=f"Levendefødte, døde og fødselsoverskudd — {region}",
            labels={"year": "År", "value": "Personer", "variable": ""},
        )
    ),
    width="stretch",
)

# ── Moves above, population below, one shared year axis ───────────────────────
fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    subplot_titles=("Inn- og utflytting og folketilvekst", "Befolkning 1. januar"),
)
for colour, (column, label) in zip(charts.PALETTE, MOVES.items()):
    fig.add_trace(
        go.Scatter(x=shown["year"], y=shown[column], name=label, mode="lines+markers", line=dict(color=colour)),
        row=1,
        col=1,
    )
fig.add_trace(
    go.Bar(
        x=shown["year"],
        y=shown["befolkning_1_januar"],
        name="Befolkning 1. januar",
        marker_color=charts.PALETTE[len(MOVES)],
    ),
    row=2,
    col=1,
)
fig.update_yaxes(title_text="Personer", row=1, col=1)
fig.update_yaxes(title_text="Personer", row=2, col=1)
fig.update_xaxes(title_text="År", row=2, col=1)
fig.update_layout(title=f"Flytting og befolkning — {region}", height=650)

st.plotly_chart(charts.style(fig), width="stretch")

st.caption(
    "Befolkning 1. januar ligger ett år foran endringene: siste år har "
    "folketall, men ennå ingen fødsler, dødsfall eller flyttinger. For Hele "
    "landet er inn- og utflyttinger inn- og utvandring. Kun år med dagens "
    "fylkes- og kommuneinndeling (fra 2024)."
)

with st.expander("Vis data"):
    st.dataframe(
        shown[["region", "year", "befolkning_1_januar", *NATURAL, *MOVES]],
        width="stretch",
        hide_index=True,
    )
