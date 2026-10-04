"""Sykehjemsbeboere — reads `sykehjemsbeboere`, saved by the SSB notebook.

SSB table 12292: beboere i sykehjem, per fylke and kommune, from 2024 — the
first year today's administrative units existed.
"""

import plotly.express as px
import streamlit as st

from backend import charts
from backend import regions
from backend import storage

st.header("🛏️ Sykehjemsbeboere")
st.caption("SSB 12292 — Institusjon: sykehjemsbeboere (antall), etter region og år.")

df = storage.load("sykehjemsbeboere")

if df.empty:
    st.info(
        f"No `sykehjemsbeboere` table yet. Reading from `{storage.describe()}` — "
        "run `make pipeline`, or see Home for setup."
    )
    st.stop()

years = charts.cap(str(y) for y in sorted(df["year"].unique()))

# ── Slicers ───────────────────────────────────────────────────────────────────
shown, scope = regions.select(df)
shown = shown.assign(år=shown["year"].astype(str))

if shown.empty:
    st.info("Ingen tall for dette utvalget.")
    st.stop()

# ── Where the selection landed ────────────────────────────────────────────────
last = int(df["year"].max())
landet = regions.national(df)
landet_last = landet.loc[landet["year"] == last, "value"]

left, right = st.columns(2)
if not landet_last.empty:
    left.metric(f"Landet — {last}", f"{landet_last.iloc[0]:,.0f}")
latest_values = shown.loc[shown["year"] == last, "value"]
right.metric(
    f"Sum, {scope} — {last}",
    f"{latest_values.sum():,.0f}" if not latest_values.empty else "—",
)

# Largest first, by the latest year, so the ranking reads left to right.
order = (
    shown[shown["year"] == shown["year"].max()]
    .sort_values("value", ascending=False)["region"]
    .tolist()
)

st.plotly_chart(
    charts.style(
        px.bar(
            shown,
            x="region",
            y="value",
            color="år",
            barmode="group",
            color_discrete_sequence=charts.PALETTE,
            category_orders={"år": years, "region": order},
            title=f"Sykehjemsbeboere — {scope}",
            labels={"region": "", "value": "Beboere", "år": "År"},
        )
    ),
    width="stretch",
)

st.caption("Kun år med dagens fylkes- og kommuneinndeling (fra 2024).")

with st.expander("Vis data"):
    st.dataframe(
        shown[["region", "fylke", "region_level", "year", "value"]],
        width="stretch",
        hide_index=True,
    )
