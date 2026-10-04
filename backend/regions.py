"""The fylke → kommune slicer the regional SSB pages share.

Expects the columns the SSB notebook writes for every regional table:
`region`, `region_level` (Landet / Fylke / Kommune) and `fylke`, the county a
kommune belongs to (and a fylke's own name).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def select(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Sidebar Fylke and Kommune multiselects → (rows to draw, what they are).

    Nothing picked shows every fylke. Picking fylker shows their kommuner;
    picking kommuner as well narrows to just those.
    """
    level = df["region_level"]
    fylker = sorted(df.loc[level == "Fylke", "region"].dropna().unique())
    chosen_fylker = st.sidebar.multiselect("Fylke", fylker, placeholder="Alle fylker")

    kommuner = df[level == "Kommune"]
    if chosen_fylker:
        kommuner = kommuner[kommuner["fylke"].isin(chosen_fylker)]
    chosen_kommuner = st.sidebar.multiselect(
        "Kommune", sorted(kommuner["region"].dropna().unique()), placeholder="Alle kommuner"
    )

    if chosen_kommuner:
        return kommuner[kommuner["region"].isin(chosen_kommuner)], "utvalgte kommuner"
    if chosen_fylker:
        return kommuner, f"kommuner i {', '.join(chosen_fylker)}"
    return df[level == "Fylke"], "alle fylker"


def national(df: pd.DataFrame) -> pd.DataFrame:
    """The Landet rows, for a headline figure beside the selection."""
    return df[df["region_level"] == "Landet"]
