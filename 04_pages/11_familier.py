"""Familier — reads `familier_familietype`, saved by the SSB notebook.

SSB table 06083: familier etter familietype, per fylke and kommune, from 2024
— the first year today's administrative units existed. The nine types add up
to all families, so the page shows each type's share.
"""

import plotly.express as px
import streamlit as st

from backend import charts
from backend import regions
from backend import storage

st.header("👨‍👩‍👧 Familier")
st.caption("SSB 06083 — familier, etter region, år og familietype.")

df = storage.load("familier_familietype")

if df.empty:
    st.info(
        f"No `familier_familietype` table yet. Reading from `{storage.describe()}` — "
        "run `make pipeline`, or see Home for setup."
    )
    st.stop()

# Row order is SSB's familietype order, as the notebook saved it.
type_order = list(df["familietype"].drop_duplicates())

# ── Slicers ───────────────────────────────────────────────────────────────────
years = sorted(df["year"].unique(), reverse=True)
year = st.sidebar.selectbox("År", years, index=0)

types = st.sidebar.multiselect("Familietype", type_order, default=type_order)

shown, scope = regions.select(df)
shown = shown[shown["year"] == year]

if shown.empty or not types:
    st.info("Ingen tall for dette utvalget.")
    st.stop()

# ── The selection as a whole ──────────────────────────────────────────────────
# Shares are of *all* families in the selection, so deselecting a type hides
# its bar without inflating the others.
totals = shown.groupby("familietype", sort=False)["familier"].sum()
overall = (
    (100 * totals / totals.sum())
    .rename("andel")
    .to_frame()
    .join(totals)
    .reindex([t for t in type_order if t in types])
    .reset_index()
)

st.metric(f"Familier, {scope} — {year}", f"{totals.sum():,.0f}")

st.plotly_chart(
    charts.style(
        px.bar(
            overall,
            x="andel",
            y="familietype",
            orientation="h",
            color_discrete_sequence=charts.PALETTE,
            category_orders={"familietype": type_order},
            hover_data={"familier": ":,.0f", "andel": ":.1f"},
            title=f"Fordeling av familietyper — {scope} ({year})",
            labels={"andel": "Andel av familiene (%)", "familietype": "", "familier": "Familier"},
        )
    ).update_layout(hovermode="closest"),
    width="stretch",
)

# ── Region by region ──────────────────────────────────────────────────────────
# A heatmap rather than a stacked bar: nine types would outrun the eight-hue
# palette, and a single colour scale reads the same for 15 fylker or 40 kommuner.
grid = shown[shown["familietype"].isin(types)].pivot_table(
    index="region", columns="familietype", values="andel", sort=False
)
grid = grid.reindex(columns=[t for t in type_order if t in types]).sort_index()

st.plotly_chart(
    charts.style(
        px.imshow(
            grid,
            text_auto=".1f",
            aspect="auto",
            color_continuous_scale=[charts.SURFACE, charts.PALETTE[0]],
            title=f"Andel av familiene per region (%) — {scope} ({year})",
            labels={"x": "", "y": "", "color": "%"},
        )
    ).update_layout(hovermode="closest", height=max(400, 28 * len(grid) + 200)),
    width="stretch",
)

st.caption("Kun år med dagens fylkes- og kommuneinndeling (fra 2024).")

with st.expander("Vis data"):
    st.dataframe(
        shown[["region", "fylke", "region_level", "year", "familietype", "familier", "andel"]],
        width="stretch",
        hide_index=True,
    )
