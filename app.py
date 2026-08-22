"""Dashboard entry point.  Run with:  make app

Every `NN_name.py` in `04_pages/` becomes a page, in filename order — dropping
a file in is all it takes. The first one (`00_home.py`) is what the app opens
on.

Navigation is declared here rather than left to Streamlit's auto-discovery,
which only looks at a folder literally named `pages/`.
"""

from pathlib import Path

import streamlit as st

from backend import config

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title=config.APP_NAME,
    page_icon=config.APP_ICON,
    layout="wide",
)


def title_of(path: Path) -> str:
    """01_overview.py -> "Overview"."""
    return path.stem.split("_", 1)[-1].replace("_", " ").title()


pages = [
    st.Page(str(path), title=title_of(path))
    for path in sorted((ROOT / "04_pages").glob("[0-9]*.py"))
]

if not pages:
    st.error("No pages found in `04_pages/`.")
    st.stop()

st.navigation(pages).run()
