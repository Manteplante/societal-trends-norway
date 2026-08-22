# Streamlit + Google Cloud Storage Template

[![ci](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)

A starting point for **data engineering, data science and analytics projects**
built entirely on open-source tools — Streamlit, pandas, Plotly and Jupyter.

Most such projects need the same scaffolding before any interesting work starts:
somewhere to put scraped or downloaded data, a place to clean it, a notebook to
explore it, a dashboard to show it, and a way to deploy that dashboard without
committing datasets to git. This template ships all of it, working, so you can
delete two example files and start on the part that is actually yours.

The shape is deliberately small — **fetch → transform → tables → charts** — and
rests on one idea: *a table is a file, addressed by name.* Tables are CSV,
Parquet or Excel files. The app reads them from a local folder, or from a Google
Cloud Storage bucket when you point it at one. The same code runs both ways, so
you build offline and flip one variable to deploy.

## Contents

- [Getting started](#getting-started)
- [Platform support](#platform-support)
- [What you edit](#what-you-edit)
- [Build your own](#build-your-own)
  - [1. Get your data in](#1-get-your-data-in)
  - [2. Shape it into tables](#2-shape-it-into-tables)
  - [3. Draw it](#3-draw-it)
- [How it works](#how-it-works)
- [Notebooks](#notebooks)
- [Google Cloud Storage](#google-cloud-storage)
- [Reference](#reference)

---

## Getting started

You need [`uv`](https://docs.astral.sh/uv/) — which handles Python versions,
virtual environments and packages in one tool — and `make`.

Install uv with the **standalone installer** rather than `pip install uv`. It
puts a single binary on your PATH, independent of any Python you already have,
so uv can manage Python itself and is available in every project on your
machine:

```bash
# Linux / macOS / WSL
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

New to uv? [Python's uv: The Ultimate Guide](https://realpython.com/python-uv/)
on Real Python is a good, thorough introduction to what it does and why it
replaces `pip`, `venv` and `pyenv`.

Then clone and run:

```bash
git clone https://github.com/<you>/<your-repo>.git
cd <your-repo>

make setup      # creates .venv, installs dependencies, registers the notebook kernel
make pipeline   # generates the example data
make app        # opens the dashboard, both pages showing charts
```

`make setup` runs `uv sync`, which reads `uv.lock` and builds an exact,
reproducible environment — no manual `pip install`, and no need to create or
activate a virtualenv yourself. `uv run <command>` uses the project's `.venv`
automatically.

`02_data/` is generated, not committed. The two **example sources** in
`01_ingestion/` invent their data from a fixed seed, so there is no network call
or cloud account involved and every clone produces the same 603 rows.

Then make it yours:

| Change | Where |
|---|---|
| Project name | `name = ` in `pyproject.toml` |
| Dashboard title / icon | `APP_NAME`, `APP_ICON` in `.env` (copy `.env.example`) |
| Colours | `.streamlit/config.toml` |
| Banner image (optional) | drop in `assets/frontpage.png` |
| Your data | delete `01_ingestion/example_*.py`, add your own |

Pushing to GitHub starts CI automatically — it needs no secrets or setup,
because the example sources invent their own data. The badge above is a relative
link, so it tracks your repo without editing.

## Platform support

Developed and tested on **WSL2 / Linux**. macOS should work unchanged (`make`
comes with the Xcode command line tools).

**Windows, without WSL.** Everything Python here is cross-platform; the rough
edge is `make`, which Windows lacks. Two options:

```powershell
# 1a. Install make and use the commands above as-is
choco install make

# 1b. ...or skip make and run the underlying commands directly:
uv sync                                   # = make setup
uv run python -m ipykernel install --user --name template-app   # once, for notebooks

uv run python 01_ingestion/run.py         # = make ingestion
uv run python -m backend.transform        # = make transform
uv run python -m nbconvert --to notebook --execute --stdout --log-level=ERROR `
  --ExecutePreprocessor.kernel_name=template-app 03_notebooks/*.ipynb > $null   # = make notebooks

uv run streamlit run app.py               # = make app
uv run pytest 05_tests -v                 # = make ci
```

Run all three pipeline stages, not just the first two: the Trends page reads a
table the notebook produces, so skipping `nbconvert` leaves one test failing.

Known Windows caveat: `nbconvert` has historically needed different kernel
transport settings on Windows, so the notebooks stage is the most likely to need
adjusting.

**Contributions making this properly cross-platform are very welcome** — a
Windows-friendly task runner, or a Python entry point replacing the Makefile,
would both be good directions.

---

## What you edit

Three places. Everything else is plumbing you can ignore.

| You write | To do what |
|---|---|
| `01_ingestion/*.py` | Get raw data in — scrape, API, file drop, anything |
| `backend/transform.py` | Turn raw data into the tables your charts need |
| `04_pages/*.py` | Draw the charts |

The pipeline runs those in order:

```bash
make pipeline      # all three stages
make ingestion     # or just one:  sources    -> 02_data/raw/
make transform     #               raw        -> 02_data/tables/
make notebooks     #               notebooks  -> 02_data/tables/
```

Two commands help while you work: `make report` prints what your pipeline
currently is (sources, tables with their columns, which table each page reads),
and `make doctor` checks your configuration and credentials.

---

## Build your own

### 1. Get your data in

Delete `01_ingestion/example_*.py` and add your own file. One file per source,
each with a `fetch()`. The file **is** the registration — no registry to update.

```python
# 01_ingestion/prices.py
from _http import get_html, soup          # helpers; files starting with _ aren't sources

def fetch():
    page = soup(get_html("https://example.com/prices"))
    return pd.DataFrame(...)              # -> 02_data/raw/prices.csv
```

Returning one DataFrame writes one file. To write **many** — a file per request,
per month, per page — return a dict or yield `(label, frame)` pairs instead:

```python
def fetch():
    for page in range(100):
        yield f"page_{page:03d}", scrape_page(page)   # -> 02_data/raw/prices/page_000.csv, ...
```

Yielding streams them, so hundreds of frames never sit in memory at once. Both
shapes read back identically downstream.

*No sources at all is fine too* — drop files into `02_data/raw/` by hand and the
rest of the pipeline works unchanged.

**CSV, Parquet and Excel all work**, anywhere in the pipeline. Reading always
accepts all three — mix them in `02_data/raw/` if you like. Writing uses one
format, set once in `.env`:

```bash
FILE_FORMAT=parquet     # csv (default) | parquet | xlsx
```

Parquet is ~3x smaller than CSV and keeps dtypes, so it is worth switching to
once your data grows. Use xlsx only when a human needs to open the output.

### 2. Shape it into tables

`backend/transform.py` has one function to replace. It receives every raw file
stacked into a single DataFrame — with a `source` column naming where each row
came from — and returns the tables you want:

```python
def build_tables(raw):
    clean = raw.dropna(subset=["value"])

    return {
        "records": clean,                                                    # -> records.csv
        "totals": clean.groupby("category", as_index=False)["value"].sum(),  # -> totals.csv
    }
```

Every key becomes a table your pages can load by name. **Do your aggregating
here, not in a page** — it runs once per pipeline run instead of once per
browser refresh.

### 3. Draw it

Every `NN_name.py` in `04_pages/` becomes a page, in filename order. Drop a file
in and it appears — `app.py` finds it. Three steps: load, guard, draw.

```python
# 04_pages/03_categories.py
from backend import storage

st.header("🏷️ Categories")

df = storage.load("totals")               # the table you returned in step 2

if df.empty:                              # always guard: no data yet, or a
    st.info("No data yet.")               # deployed app that lost its bucket
    st.stop()

st.plotly_chart(px.bar(df, x="category", y="value"), width="stretch")
```

Pages don't call `st.set_page_config` — `app.py` does it once.

Run `make ci` to render every page and fail if one raises. Run it with
`02_data/` empty to prove your guards work. It also checks that every name a
page loads is one the pipeline actually produces — so renaming a table without
updating its page fails the build instead of silently blanking the page.

---

## How it works

One idea underneath everything: **a table is a file, addressed by name.**
`backend/storage.py` is the only module that knows where files actually live:

```python
from backend import storage

storage.load("records")            # -> DataFrame, empty if it isn't there
storage.save("records", df)        # -> writes records.csv / .parquet / .xlsx
storage.tables()                   # -> ["records", "totals"]
storage.save_figure("trend", fig)  # load_figure() / figures() for PNGs
```

Set `GCS_BUCKET` and those same calls hit a bucket instead. Nothing else in the
repo changes — no branching, no second code path.

Two rules keep the dashboard hard to break: **reads never raise** (missing file,
bad credentials → empty, so pages show an empty state), and **writes do raise**
(a skipped upload would leave a deployed app serving stale data).

| | |
|---|---|
| `app.py` | entry point — declares the navigation, `make app` runs it |
| `backend/` | config, storage, transform |
| `01_ingestion/` | your sources |
| `02_data/` | `raw/` and `tables/` — generated, not committed |
| `03_notebooks/` | exploration |
| `04_pages/` | your pages — `00_home.py` is the landing page |
| `05_tests/` | renders every page |

> **Why `backend/` has no number.** Python can't import a module whose name
> starts with a digit, and `backend` is the only folder imported as one — so it
> keeps a plain name and `from backend import storage` just works, in your
> editor as well as at runtime. The numbered folders are all found by path
> instead: scripts, `st.Page`, pytest and the data directory never need
> importing.
>
> Two files still put the repo root on `sys.path` because they run from
> elsewhere: `01_ingestion/run.py` (a script) and the example notebook. And
> `app.py` declares its navigation explicitly, because Streamlit only
> auto-discovers a folder literally named `pages/`.

### Memory

Streamlit reruns your script on every interaction, so uncached reads mean
re-reading a file per click. Every read here is cached with both a `ttl` **and**
a `max_entries` cap, so the cache evicts least-recently-used entries instead of
growing until it exhausts RAM. Tune them in `_cache()` in `backend/storage.py`.

Three more levers, in order of impact:

- **Aggregate in `transform.py`, not in a page.** A page that loads a million
  rows to draw ten bars keeps a million rows in RAM per cache entry. Save the
  ten-row table instead.
- **Load only what you need** — `load()` forwards to `pd.read_csv`, so
  `storage.load("records", usecols=["category", "value"])` never materialises
  the rest.
- **Don't put frames in `st.session_state`.** It is per-session and never
  evicted; the cache is shared across sessions and bounded. This template uses
  no session state at all.

The GCS connection is built once per process and reused, so credentials are not
re-negotiated on every rerun.

---

## Notebooks

`03_notebooks/` is for exploration that produces tables. Notebooks call the same
`storage` functions, so anything you save is immediately readable by a page —
no bridge, no export folder, no wiring:

```python
import sys; sys.path.insert(0, "..")
from backend import storage

totals = storage.load("records").groupby("category", as_index=False)["value"].sum()
storage.save("category_totals", totals)      # a page can now load it
storage.save_figure("trend", fig)            # PNG, shown with st.image
```

`make notebooks` runs every notebook in filename order for those `save()` calls,
and throws away the rendered copy so your `.ipynb` files stay clean.

---

## Google Cloud Storage

Optional — skip it and everything stays local. You need it to deploy, since a
hosted app has no `02_data/` folder of its own.

**1. Make a bucket and a key.** In the Google Cloud console: create a bucket,
create a service account, give it **Storage Object Admin** on that bucket, then
create a JSON key and download it. Put it in the repo root — every `*.json` is
gitignored, so it cannot be committed by accident.

**2. Publish from the pipeline** — in `.env`:

```bash
GCS_BUCKET=your-bucket-name
GCS_PROJECT=your-project-id
GCS_KEY_FILE=cloud-key.json     # the JSON you just downloaded
GCS_UPLOAD=true
```

`GCS_BUCKET` and `GCS_UPLOAD` are two separate switches: the bucket makes the
**app read** remotely, upload makes the **pipeline write** remotely. `.env.example`
has the full truth table. `make pipeline` now writes `02_data/tables/` locally
**and** uploads each table; local files are written first, so a failed upload
never loses data.

**3. Deploy the dashboard** — Streamlit Community Cloud, main file `app.py`.
There is no `.env` there, so the same settings go in **Secrets**: copy
`.streamlit/secrets.example.toml` and paste in your bucket name plus the
contents of that JSON key.

```toml
GCS_BUCKET = "your-bucket-name"

[connections.gcs]
type = "service_account"
project_id = "xxx"
private_key = "-----BEGIN PRIVATE KEY-----\nxxx\n-----END PRIVATE KEY-----\n"
client_email = "xxx"
# ... every other field from the JSON, same names
```

The field names under `[connections.gcs]` are exactly the keys in the downloaded
JSON, so it is a straight copy-paste
([Streamlit's GCS guide](https://docs.streamlit.io/develop/tutorials/databases/gcs)).
For a read-only dashboard, use a second service account with **Storage Object
Viewer** instead — then a leaked dashboard key can't modify your data.

Credentials are resolved first-hit-wins: `GCS_KEY_FILE` → `[connections.gcs]` in
secrets → Application Default Credentials. If none of them work, `make doctor`
tells you what to check.

### Refreshing the data on a schedule (optional)

The deployed app reads the bucket, so refreshing the dashboard means re-running
the pipeline — not redeploying. Point a scheduled GitHub Action at it and the
app picks up new tables within its 10-minute cache.

Add three repository secrets under **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `GCS_BUCKET` | your bucket name |
| `GCS_PROJECT` | your GCP project id |
| `GCP_SA_KEY` | the **entire** contents of the writer's JSON key file |

Then add `.github/workflows/refresh.yml`:

```yaml
name: refresh-data

on:
  schedule:
    - cron: "0 5 * * *"     # 05:00 UTC daily
  workflow_dispatch:        # ...and a "Run workflow" button

permissions:
  contents: read

jobs:
  refresh:
    runs-on: ubuntu-latest
    env:
      GCS_BUCKET: ${{ secrets.GCS_BUCKET }}
      GCS_PROJECT: ${{ secrets.GCS_PROJECT }}
      GCS_KEY_FILE: cloud-key.json
      GCS_UPLOAD: "true"

    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - run: uv sync --frozen
      - run: make notebook-kernel

      # Recreate the key file the runner needs. Quoting the secret through an
      # env var (not inline) keeps the JSON intact and out of the command line.
      - name: Write the service-account key
        env:
          GCP_SA_KEY: ${{ secrets.GCP_SA_KEY }}
        run: printf '%s' "$GCP_SA_KEY" > cloud-key.json

      - run: make pipeline      # fetch -> transform -> notebooks -> upload
```

That is the same `make pipeline` you run locally; the only difference is
`GCS_UPLOAD=true`. The runner is thrown away afterwards, so the key file goes
with it.

Two things to know before relying on it. **Your sources must be real** — the
shipped `example_*.py` invent data, so a scheduled run would just regenerate
fake numbers. And **the writer key needs Storage Object Admin**; the read-only
key you gave the dashboard cannot upload.

---

## Reference

| Target | | Variable | Default |
|---|---|---|---|
| `make setup` | dependencies + kernel | `APP_NAME` / `APP_ICON` | template name / 📦 |
| `make app` | run the dashboard | `RAW_DIR` / `TABLES_DIR` | `02_data/raw` / `02_data/tables` |
| `make pipeline` | the whole ETL | `FILE_FORMAT` | `csv` |
| `make ingestion` | fetch raw data | `GCS_BUCKET` | *(empty — stays local)* |
| `make transform` | raw → tables | `GCS_PREFIX` | *(empty)* |
| `make notebooks` | run notebooks | `GCS_PROJECT` | *(empty)* |
| `make report` | show sources/tables/pages | `GCS_KEY_FILE` | *(empty)* |
| `make doctor` | check config + credentials | `GCS_UPLOAD` | `false` |
| `make ci` | compile + render pages | | |

Only `backend/config.py` reads the environment, and every value has a working
default — an empty `.env` is valid. CI runs `make ci`, so local and CI can't
drift.

Working in this repo with a coding agent? `AGENTS.md` documents the conventions
and the handful of things that look removable but are not.

## License

MIT.
