# Working in this repo

A Streamlit dashboard on a small ETL pipeline. One idea underneath everything:
**a table is a file, addressed by name.** `backend/storage.py` is the only
module that knows where files live; everything else goes through it.

```
01_ingestion/*.py      fetch()         ->  02_data/raw/
backend/transform.py   build_tables()  ->  02_data/tables/
03_notebooks/*.ipynb   storage.save()  ->  02_data/tables/
app.py + 04_pages/     storage.load()  <-  02_data/tables/
```

**`raw/` and `tables/` are not interchangeable.** `storage.load()` reads
`02_data/tables/` only. A file sitting in `02_data/raw/` is invisible to pages
until `make transform` turns it into a table. This is the most common
misunderstanding here.

Run `make ci` before you finish. If you touched the pipeline, run
`make pipeline && make ci`.

---

## Adding a data source

One file in `01_ingestion/`, one function called `fetch()`. **The file is the
registration** — there is no registry, no list, nothing to import.

```python
# 01_ingestion/prices.py
import pandas as pd

from _http import get_html, soup        # helpers live in files starting with _

def fetch() -> pd.DataFrame:
    page = soup(get_html("https://example.com/prices"))
    return pd.DataFrame(...)            # -> 02_data/raw/prices.csv
```

Return **one** DataFrame, or **many** as a dict or `(label, frame)` pairs —
yield them to stream hundreds without holding them in memory:

```python
def fetch():
    for n in range(100):
        yield f"page_{n:03d}", scrape_page(n)   # -> 02_data/raw/prices/page_000.csv
```

Rules:

- **Sources always write to `raw/`.** Never write to `02_data/tables/` from
  ingestion — shaping is `transform.py`'s job, and one path into `tables/` is
  what keeps the CI table-name guard meaningful.
- Files starting with `_` are helpers, not sources. `_http.py` ships
  `get_html()` and `soup()`.
- API keys come from `.env` via `os.getenv(...)`. Never hardcode one.
- **Not writing a scraper is fine.** Dropping CSV/Parquet/Excel files into
  `02_data/raw/` by hand works identically — the pipeline reads whatever is
  there. Suggest this when a user has files already.

---

## Shaping tables

Replace `build_tables()` in `backend/transform.py`. It receives every raw file
stacked into one DataFrame, tagged with a `source` column, and returns
`{name: DataFrame}`. Each key becomes a table a page can load.

```python
def build_tables(raw):
    clean = raw.dropna(subset=["value"])
    return {
        "records": clean,
        "totals": clean.groupby("category", as_index=False)["value"].sum(),
    }
```

**Aggregate here, not in a page.** This runs once per pipeline run; a page runs
on every browser interaction.

---

## Notebooks

`03_notebooks/` is a playground that can also produce tables. Same `storage`
API as everything else — no bridge, no export folder, no wiring:

```python
import sys; sys.path.insert(0, "..")      # required: the notebook runs from 03_notebooks/
from backend import storage

df = storage.load("records")
storage.save("category_totals", totals)   # a page can now load it
storage.save_figure("trend", fig)         # PNG, shown with st.image
```

Keep notebooks **column-name agnostic** where you can. The shipped example
picks the first label column and the first numeric one, so it keeps running
after someone swaps the data out. Copy that habit.

`make notebooks` executes each one in filename order for its `save()` side
effects and throws away the rendered copy, so `.ipynb` files stay clean.

---

## Adding a page

`04_pages/NN_name.py`, ordered by filename. Drop a file in and it appears —
`app.py` finds it. Every page follows **load → guard → draw**:

```python
"""Categories — reads the table transform.py named 'totals'."""

import plotly.express as px
import streamlit as st

from backend import storage

st.header("🏷️ Categories")

df = storage.load("totals")                    # 1. load, by name

if df.empty:                                   # 2. guard — always
    st.info(f"No `totals` table yet. Reading from `{storage.describe()}`.")
    st.stop()

st.plotly_chart(px.bar(df, x="category", y="value"), width="stretch")   # 3. draw
st.dataframe(df, width="stretch", hide_index=True)
```

Keep pages visually consistent with the existing ones:

- `st.header("<emoji> <Title>")` at the top; **never** `st.set_page_config`
  (`app.py` owns it, calling it twice is an error).
- Charts with `plotly.express` + `st.plotly_chart(..., width="stretch")`.
- Tables with `st.dataframe(..., width="stretch", hide_index=True)`.
- Filters in the sidebar (`st.sidebar.multiselect`), and only when the data has
  something to filter on.
- Pages consume; they don't compute. Need a groupby? Put it in `build_tables()`.

**The name in `storage.load("x")` must match a key from `build_tables()`** (or
something a notebook saved). CI fails the build on a mismatch.

### Whenever you add or remove a page

`04_pages/00_home.py` is the landing page and must be reviewed. It currently
shows data-source status and **no page links**, so this is a judgement call, not
a mechanical edit — **ask the developer** whether home should link to or
describe the new page before changing it.

---

## Do not touch

Each of these looks removable and is not.

| Thing | Why it's there |
|---|---|
| `sys.path` line in `01_ingestion/run.py` and the example notebook | Numbered folders can't be imported; these put the repo root on the path. Deleting either breaks imports. |
| `backend/` having no number | It is the only folder imported as a module. `from backend import storage` must stay statically resolvable. |
| `app.py`'s explicit `st.navigation` | Streamlit only auto-discovers a folder literally named `pages/`. Ours is `04_pages/`. |
| `set -eo pipefail` in CI's piped steps | Without it a failing test reports **green** — the pipe returns `tee`'s exit code. |
| `timeout-minutes` on the CI job | A hung notebook kernel would otherwise run to GitHub's 6-hour default. |
| `.PHONY` in the Makefile | Targets share names with directories (`ingestion`); without it make skips them as "up to date". |
| `ttl` **and** `max_entries` on every cache | TTL bounds staleness, `max_entries` bounds memory. Both are needed. |
| `.gitkeep` in `02_data/raw` and `tables` | Keeps the folders in git so the pipeline has somewhere to write. |
| Fixed seeds in `01_ingestion/example_*.py` | Keeps CI deterministic. |

More rules:

- **`02_data/` is generated — never commit it.** `make pipeline` rebuilds it.
- **Reads soft-fail, writes hard-fail.** Don't wrap `storage.save()` in
  try/except, and don't delete a page's `df.empty` guard. A missing table must
  show an empty state; a failed upload must raise.
- **Never put DataFrames in `st.session_state`** — it is per-session and never
  evicted. The cache is shared and bounded.
- **`FILE_FORMAT` controls writes only.** Reads always accept csv, parquet and
  xlsx, mixed freely.
- **New dependency ⇒ run `uv sync`** so `uv.lock` updates. CI installs with
  `--frozen` and fails on a stale lock.
- **`make ci` is the single entry point.** CI calls that same target — don't
  inline commands into the workflow, or the two will drift.
- **Notebook execution**: output is discarded on purpose. Don't switch to
  `--inplace`, and don't set nbconvert to IPC transport — it hangs on WSL and
  leaves stray `kernel-ipc-*` sockets.
- **GCS**: credentials resolve key file → `[connections.gcs]` in Streamlit
  secrets → ADC. Never commit a key file.

---

## What CI enforces

`make ci` runs locally and in GitHub Actions (every push, all three file
formats on pull requests). Two guards define the contract:

- **`05_tests/test_app.py`** — every page must render without raising, *with
  `02_data/` empty*. This is what a fresh clone and a bucket-less deployment
  look like. It's why the `df.empty` guard is mandatory.
- **`05_tests/test_page_tables.py`** — every `storage.load("x")` in a page must
  name a table the pipeline actually produces. Renaming a table without
  updating its page fails the build instead of silently blanking the page.

Run `make ci` with `02_data/` empty to prove your guards work.

`make report` prints what the pipeline currently *is* — every source with its
file and row counts, every table with its columns, and which table each page
reads. CI appends it to the run summary, so each build shows the shape of the
data it built. Use it to check your work after adding a source or a page.

`make doctor` checks the configuration and says what to look at — which
credential sources are present, and a checklist when none of them connect. It
is **deliberately generic about credentials**: it never reads, formats or
echoes a credential value, and never passes through a message from the GCS
library, which was handed the credential and could quote it back. That leaves
no leak to reason about, and its output is safe to paste into an issue or a CI
log. Keep it that way — do not "improve" it by adding the underlying exception.
The home page shows the same thing in an expander when GCS auth fails.

One environment gotcha: `make notebook-kernel` installs the `template-app`
kernel **user-globally**, so running it from a second checkout repoints the
kernel at that checkout's `.venv` and breaks `make notebooks` in the first. If
notebooks start failing with `No such file or directory: .../.venv/bin/python3`,
re-run `make notebook-kernel` from the checkout you are working in.
