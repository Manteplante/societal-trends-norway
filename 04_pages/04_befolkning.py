"""Befolkning — reads `befolkning_aldersgrupper`, saved by the SSB notebook.

SSB table 05810: the population by age band and sex, 1845 to today.
"""

import plotly.express as px
import streamlit as st

from backend import charts
from backend import storage

TOTAL = "999B"  # SSB's "Alle" band — the total, not a slice of the stack

st.header("👥 Befolkning")
st.caption("SSB 05810 — aldersgrupper og kjønnsfordeling i hele befolkningen.")

df = storage.load("befolkning_aldersgrupper")

if df.empty:
    st.info(
        f"No `befolkning_aldersgrupper` table yet. Reading from `{storage.describe()}` — "
        "run `make pipeline`, or see Home for setup."
    )
    st.stop()

# The rows arrive in SSB's own value order, so first-seen order is that order —
# which keeps `7-15 år` before `67-79 år` instead of sorting it as text.
alder_order = [a for a in df["Alder"].drop_duplicates() if a != "Alle"]

# ── Slicers ───────────────────────────────────────────────────────────────────
kjonn = sorted(df["Kjonn"].dropna().unique())
chosen = st.sidebar.selectbox("Kjønn", kjonn, index=kjonn.index("Begge kjønn") if "Begge kjønn" in kjonn else 0)

first, last = int(df["year"].min()), int(df["year"].max())
start, end = st.sidebar.slider("År", first, last, (first, last))

bands = charts.cap(st.sidebar.multiselect("Aldersgruppe", alder_order, default=alder_order))

period = df[(df["Kjonn"] == chosen) & df["year"].between(start, end)]
stacked = period[period["Alder"].isin(bands)]
total = period[period["Alder_code"] == TOTAL].sort_values("year")

# ── Where the selection landed ────────────────────────────────────────────────
if not total.empty:
    opened, closed = total.iloc[0], total.iloc[-1]
    growth = closed["value"] - opened["value"]
    left, middle, right = st.columns(3)
    left.metric(f"Personer i {opened['year']}", f"{opened['value']:,.0f}")
    middle.metric(f"Personer i {closed['year']}", f"{closed['value']:,.0f}")
    right.metric(
        "Vekst i perioden",
        f"{growth:+,.0f}",
        f"{growth / opened['value']:+.1%}" if opened["value"] else None,
    )

st.plotly_chart(
    charts.style(
        px.area(
            stacked.sort_values("year"),
            x="year",
            y="value",
            color="Alder",
            color_discrete_sequence=charts.PALETTE,
            # The full band order, not just the selected ones: deselecting a
            # band must not repaint the bands that remain.
            category_orders={"Alder": alder_order},
            title=f"Befolkningen etter aldersgruppe, {chosen.lower()} ({start}–{end})",
            labels={"year": "År", "value": "Personer", "Alder": "Aldersgruppe"},
        ),
        area=True,
    ),
    width="stretch",
)

with st.expander("Vis data"):
    st.dataframe(stacked[["Kjonn", "Alder", "year", "value"]], width="stretch", hide_index=True)
