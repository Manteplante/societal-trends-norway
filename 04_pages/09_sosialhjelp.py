"""Sosialhjelp — reads `sosialhjelp_mottakere`, saved by the SSB notebook.

SSB table 13995: sosialhjelpstilfeller per fylke and kommune, from 2024 — the
first year today's administrative units existed. The notebook splits "alle
mottakere" into two parts that add up to it, so the bars can be stacked:
mottakere som forsørger barn under 18 år, and øvrige mottakere.
"""

import plotly.express as px
import streamlit as st

from backend import charts
from backend import regions
from backend import storage

st.header("🤝 Sosialhjelp")
st.caption("SSB 13995 — sosialhjelpstilfeller (antall), etter region og år.")

df = storage.load("sosialhjelp_mottakere")

if df.empty:
    st.info(
        f"No `sosialhjelp_mottakere` table yet. Reading from `{storage.describe()}` — "
        "run `make pipeline`, or see Home for setup."
    )
    st.stop()

# Row order is the group order the notebook saved: barn first, øvrige on top.
group_order = list(df["gruppe"].drop_duplicates())

# ── Slicers ───────────────────────────────────────────────────────────────────
years = sorted(df["year"].unique(), reverse=True)
year = st.sidebar.selectbox("År", years, index=0)

groups = st.sidebar.multiselect("Mottakergruppe", group_order, default=group_order)

shown, scope = regions.select(df)
shown = shown[(shown["year"] == year) & shown["gruppe"].isin(groups)]

if shown.empty:
    st.info("Ingen tall for dette utvalget.")
    st.stop()

# ── Where the selection landed ────────────────────────────────────────────────
landet = regions.national(df)
landet = landet[landet["year"] == year].set_index("gruppe")["value"]

if not landet.empty:
    columns = st.columns(len(group_order) + 1)
    columns[0].metric(f"Landet, alle mottakere — {year}", f"{landet.sum():,.0f}")
    for column, group in zip(columns[1:], group_order):
        if group in landet:
            column.metric(group, f"{landet[group]:,.0f}")

# Tallest stack first.
order = shown.groupby("region")["value"].sum().sort_values(ascending=False).index.tolist()

st.plotly_chart(
    charts.style(
        px.bar(
            shown,
            x="region",
            y="value",
            color="gruppe",
            barmode="stack",
            color_discrete_sequence=charts.PALETTE,
            # The full group order, so deselecting one keeps the other its hue.
            category_orders={"gruppe": group_order, "region": order},
            title=f"Sosialhjelpsmottakere — {scope} ({year})",
            labels={"region": "", "value": "Mottakere", "gruppe": "Gruppe"},
        )
    ),
    width="stretch",
)

st.caption(
    "Begge delene til sammen er alle sosialhjelpsmottakere. Kommuner der SSB "
    "har skjult tallet for mottakere som forsørger barn, kan ikke deles opp og "
    "vises ikke. Kun år med dagens fylkes- og kommuneinndeling (fra 2024)."
)

with st.expander("Vis data"):
    st.dataframe(
        shown[["region", "fylke", "region_level", "year", "gruppe", "value"]],
        width="stretch",
        hide_index=True,
    )
