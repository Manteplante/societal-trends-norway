"""Overview — reads a table written by transform.py."""

import plotly.express as px
import streamlit as st

from backend import storage

st.header("📊 Overview")

df = storage.load("records")

if df.empty:
    st.info(f"No `records` table yet. Reading from `{storage.describe()}` — see Home for setup.")
    st.stop()

# Optional filter, shown only when the data has something to filter on.
if "source" in df.columns:
    chosen = st.sidebar.multiselect("Source", sorted(df["source"].unique()))
    if chosen:
        df = df[df["source"].isin(chosen)]

st.metric("Rows", f"{len(df):,}")

if {"category", "value"} <= set(df.columns):
    totals = df.groupby("category", as_index=False)["value"].sum()
    st.plotly_chart(px.bar(totals, x="category", y="value", title="Value by category"), width="stretch")

st.dataframe(df, width="stretch", hide_index=True)
