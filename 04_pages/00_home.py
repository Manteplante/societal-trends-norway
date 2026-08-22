"""Landing page — what the dashboard opens on."""

import streamlit as st

from backend import config
from backend import storage

st.title(f"{config.APP_ICON} {config.APP_NAME}")
st.caption("A Streamlit app backed by a small pipeline, reading tables from a local folder or a GCS bucket.")

frontpage = config.ROOT / "assets" / "frontpage.png"
if frontpage.exists():
    st.image(str(frontpage))

st.divider()

# ── Where is the data coming from, and is it there? ───────────────────────────
available = storage.tables()

if available:
    st.success(f"Reading from `{storage.describe()}` — tables: {', '.join(available)}")
elif not storage.remote():
    st.warning(f"No tables yet in `{storage.describe()}`.")
    st.caption("Put a CSV in `02_data/raw/` and run `make pipeline`, or set GCS_BUCKET to read from a bucket.")
elif not storage.ready():
    st.error(f"`{storage.describe()}` is configured, but GCS authentication failed.")
    with st.expander("What went wrong?"):
        # Reports which credential source was used and what was wrong with it.
        # Field names only — never a secret value. Same output as `make doctor`.
        st.code("\n".join(storage.diagnose()), language="text")
else:
    st.warning(f"No tables found in `{storage.describe()}`.")

st.divider()
st.caption(
    "Make it yours: your sources in `01_ingestion/`, your logic in "
    "`backend/transform.py`, your charts in `04_pages/`."
)
