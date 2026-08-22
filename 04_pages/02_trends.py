"""Trends — reads a table and a figure saved from a notebook.

Notebooks use the same `storage.save()` / `storage.save_figure()` the pipeline
uses, so anything you save in `03_notebooks/` shows up here with no extra wiring.
"""

import plotly.express as px
import streamlit as st

from backend import storage

st.header("📈 Trends")

df = storage.load("trend_totals")
figure = storage.load_figure("trend_totals")

if df.empty and figure is None:
    st.info(
        "Nothing saved from a notebook yet. Run `make notebooks` to execute "
        "`03_notebooks/00_example.ipynb`, which saves `trend_totals`."
    )
    st.stop()

if not df.empty:
    x, y = df.columns[0], df.columns[1]
    st.plotly_chart(px.bar(df, x=x, y=y, title=f"{y} by {x}"), width="stretch")
    st.dataframe(df, width="stretch", hide_index=True)

if figure is not None:
    st.subheader("Figure saved from the notebook")
    st.image(figure)
