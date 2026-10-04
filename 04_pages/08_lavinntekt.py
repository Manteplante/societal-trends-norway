"""Lavinntekt — reads `lavinntekt_eu60`, saved by the SSB notebook.

SSB table 06947: personer i privathusholdninger med inntekt etter skatt per
forbruksenhet under 60 % av medianen (EU-skala), per fylke and kommune, from
2024 — the first year today's administrative units existed.
"""

import plotly.express as px
import streamlit as st

from backend import charts
from backend import regions
from backend import storage

MEASURES = {
    "Andel (%)": ("andel_eu60", "Andel under 60 % av median"),
    "Antall personer (ca.)": ("antall_eu60", "Personer under 60 % av median"),
}

st.header("💰 Lavinntekt")
st.caption(
    "SSB 06947 — personer i privathusholdninger med inntekt under 60 % av "
    "medianinntekten (EU-skala), etter region og år."
)

df = storage.load("lavinntekt_eu60")

if df.empty:
    st.info(
        f"No `lavinntekt_eu60` table yet. Reading from `{storage.describe()}` — "
        "run `make pipeline`, or see Home for setup."
    )
    st.stop()

years = charts.cap(str(y) for y in sorted(df["year"].unique()))

# ── Slicers ───────────────────────────────────────────────────────────────────
measure = st.sidebar.radio("Mål", list(MEASURES))
column, label = MEASURES[measure]

shown, scope = regions.select(df)
shown = shown.assign(år=shown["year"].astype(str))

if shown.empty:
    st.info("Ingen tall for dette utvalget.")
    st.stop()

# ── Where the selection landed ────────────────────────────────────────────────
last = int(df["year"].max())
landet = regions.national(df)
landet_last = landet[landet["year"] == last]

if not landet_last.empty:
    left, right = st.columns(2)
    left.metric(f"Landet, andel — {last}", f"{landet_last['andel_eu60'].iloc[0]:.1f} %")
    right.metric(f"Landet, personer (ca.) — {last}", f"{landet_last['antall_eu60'].iloc[0]:,.0f}")

order = (
    shown[shown["year"] == shown["year"].max()]
    .sort_values(column, ascending=False)["region"]
    .tolist()
)

st.plotly_chart(
    charts.style(
        px.bar(
            shown,
            x="region",
            y=column,
            color="år",
            barmode="group",
            color_discrete_sequence=charts.PALETTE,
            category_orders={"år": years, "region": order},
            title=f"{label} — {scope}",
            labels={"region": "", column: measure, "år": "År"},
        )
    ),
    width="stretch",
)

st.caption(
    "SSB publiserer andelen. Antallet er beregnet som personer × andel og er "
    "omtrentlig, fordi andelen er avrundet til én desimal. Kun år med dagens "
    "fylkes- og kommuneinndeling (fra 2024)."
)

with st.expander("Vis data"):
    st.dataframe(
        shown[["region", "fylke", "region_level", "year", "personer", "andel_eu60", "antall_eu60"]],
        width="stretch",
        hide_index=True,
    )
