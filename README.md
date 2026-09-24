# Societal Trends Norway

[![ci](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)

A Streamlit dashboard on Norwegian public statistics — elderly care, population,
mortality and life expectancy — fed straight from
[Statistikkbanken](https://www.ssb.no/statbank), Statistics Norway's open
statistics API.

It is two things at once, and worth being clear about which is which:

- a **testbed for [`ssb_statistikkbanken`](https://github.com/Manteplante/ssb_statistikkbanken)**,
  a Python wrapper around Statistikkbanken and KLASS, exercised here against
  real tables rather than a test suite;
- a **small ETL + dashboard**, built on a Streamlit + Google Cloud Storage
  template, so the wrapper's output has somewhere real to land.

The shape is **fetch → tables → charts**, resting on one idea: *a table is a
file, addressed by name.* Tables are CSV, Parquet or Excel files. The app reads
them from a local folder, or from a Google Cloud Storage bucket when you point
it at one. The same code runs both ways, so you build offline and flip one
variable to deploy.

## Contents

- [Getting started](#getting-started)
- [The SSB wrapper](#the-ssb-wrapper)
  - [Where it comes from](#where-it-comes-from)
  - [The loop: search → describe → values → fetch → plot](#the-loop-search--describe--values--fetch--plot)
  - [KLASS: which regions actually exist](#klass-which-regions-actually-exist)
  - [What this repo ingests](#what-this-repo-ingests)
- [Platform support](#platform-support)
- [What you edit](#what-you-edit)
- [Build your own](#build-your-own)
- [Charts](#charts)
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
git clone https://github.com/<you>/societal-trends-norway.git
cd societal-trends-norway

make setup      # creates .venv, installs dependencies, registers the notebook kernel
make pipeline   # fetches from SSB and builds 02_data/tables/
make app        # opens the dashboard
```

`make setup` runs `uv sync`, which reads `uv.lock` and builds an exact,
reproducible environment — no manual `pip install`, and no need to create or
activate a virtualenv yourself. `uv run <command>` uses the project's `.venv`
automatically.

`02_data/` is generated, not committed. **`make pipeline` calls the live SSB
API**, so this step needs network — see
[What this repo ingests](#what-this-repo-ingests) for what it pulls and how long
it takes.

---

## The SSB wrapper

Statistikkbanken is a PxWeb API: powerful, and awkward by hand. Every table has
its own dimensions with their own code lists, the mandatory ones must all be
named or the request 400s, values come back as a flat matrix with codes rather
than labels, and the useful selections are large enough to need splitting.

`ssb_statistikkbanken` closes that gap. The point of this repo is that **the
notebook below contains no cleanup code at all** — no renaming, no splitting a
combined `"code - label"` column, no retyping, no manual binning. What comes out
of `fetch()` is what gets saved.

### Where it comes from

It is a private package, not on PyPI, installed straight from its git repo. In
`pyproject.toml`:

```toml
dependencies = [
    "ssb-statistikkbanken",
    # ...
]

[tool.uv.sources]
ssb-statistikkbanken = { git = "https://github.com/Manteplante/ssb_statistikkbanken", branch = "main" }
```

`uv sync` resolves it like any other dependency and pins the exact commit in
`uv.lock`, so a clone gets the same version. Import it anywhere in the repo:

```python
from ssb_statistikkbanken import SSB, klass

ssb = SSB()
```

> **Notebook kernels ignore `uv run --with`.** Anything a notebook imports has to
> be a real project dependency, which is why the wrapper is listed in
> `pyproject.toml` rather than added ad hoc.

### The loop: search → describe → values → fetch → plot

Five steps, the same for any table id. `03_notebooks/01_ssb_ingest_tables.ipynb`
runs them four times over, once per SSB table.

```python
ssb.search("dødelighetstabeller", limit=5)   # 1. which table?
ssb.describe("07902")                        # 2. what's in it — renders as a card
ssb.values("07902", "ContentsCode")          # 3. what codes can I filter on?

df = ssb.fetch("07902", Kjonn="*", AlderX="*",
               contents="ForvGjenLevetid", time="*")   # 4. get it
```

`fetch()` returns tidy, typed data — one row per observation:

| Kjonn | Kjonn_code | AlderX | AlderX_code | Tid | year | value |
|---|---|---|---|---|---|---|
| Begge kjønn | 0 | 0 år | 000 | 1966 | 1966 | 73.96 |

Every dimension arrives as a **label column and a `_code` sibling**, `year` is
already an `Int16`, and `value` is a nullable numeric. Three defaults do most of
the work:

- **Mandatory variables you leave out are selected in full** (`*`), and
  eliminable ones you skip are aggregated away by SSB — so a short call still
  produces a valid request.
- **Values check before the request goes out.** A typo comes back as
  `UnknownVariableError: did you mean Kjonn?` instantly, not as an HTTP 400.
- **Selections over 800,000 cells are split and stitched automatically.**

Two things it does that are easy to get wrong by hand, both used here:

```python
# Server-side aggregation: 106 single ages arrive as 11 ten-year bands.
ssb.fetch("14657", Kjonn="*", code_list={"Alder": "agg_TiAarigGruppering"}, time="*")

# SSB's own value order, not alphabetical.
info["Alder"].labels     # ['Alle', '0-6 år', '7-15 år', '16-44 år', ...]
```

That second one matters more than it looks. `df.pivot_table(...)` sorts
categories as text, which files `7-15 år` between `67-79 år` and `80 år eller
eldre` and pushes the `Alle` total to the end. SSB publishes the intended order
and the wrapper hands it back, so charts read correctly.

> **`decimals` is a hint, not a promise.** SSB reports it per table, but a table
> can mix units across `ContentsCode`. Table 07902 declares `decimals = 0` while
> life expectancy is plainly fractional — the wrapper checks the actual values
> and falls back to `Float64`. That is one more thing that would otherwise be
> manual cleanup.

### KLASS: which regions actually exist

KOSTRA table 12292 puts 891 values in one region dimension: today's
municipalities, every municipality and county merged or split away since 2015
(`Halden (-2019)`, `Viken (2020-2023)`), and KOSTRA's municipality groups.
Filtering that to "the ones operational today" by hand means a list that rots at
the next reform.

The wrapper ships KLASS — Statistics Norway's classification service — so it is
a join instead:

```python
kommuner = klass.kommuner(2025)                                # 358 municipalities
fylker = klass.fylker(2025)                                    # 16 counties
kommune_til_fylke = klass.correspondence(131, 104, date=2025)  # kommune -> fylke
```

That drops 518 of the 891 values and leaves 15 current counties, 357 current
municipalities, and Landet. Each municipality also carries its county, which is
what lets the page narrow a 278-entry dropdown to one county's worth. Next
year's reform is a date change, not a list edit.

The one adjustment needed: **SSB prefixes county codes with `EKA`** (`EKA32`)
where KLASS uses the bare digits (`32`).

> **The reform gap is real, and the dashboard says so.** Statistics Norway does
> not backcast KOSTRA figures onto new boundaries, so a region has no figures
> before its current borders took effect. Filtering to current regions therefore
> empties the early years: 4 of 15 counties report in 2015, 8 in 2020, all 15
> from 2024. Only Oslo, Rogaland, Møre og Romsdal and Nordland survived both
> reforms unchanged. Landet is unaffected.

### What this repo ingests

One notebook, `03_notebooks/01_ssb_ingest_tables.ipynb`, four SSB tables, four
saved tables, four pages:

| SSB table | Saved as | Rows | Page |
|---|---|---|---|
| **12292** Omsorgstjenester — supplerende grunnlagstall | `omsorg_bistandsbehov` | 5,808 | `03_omsorgstjenester.py` |
| **05810** Aldersgrupper og kjønnsfordeling | `befolkning_aldersgrupper` | 1,050 | `04_befolkning.py` |
| **14657** Døde per måned | `dode_per_maaned` | 1,815 | `05_dodelighet_maaned.py` |
| **07902** Dødelighetstabeller | `forventet_gjenstaende_levetid` | 19,260 | `06_forventet_levetid.py` |

`make pipeline` runs the notebook for its `storage.save()` side effects. It
takes about ten seconds — the selections are small and the wrapper fetches them
concurrently — and fails loudly if SSB is unreachable, rather than leaving the
pages on stale tables.

> **Avoid 07:55–08:15**, Statistics Norway's publishing peak.

---

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

**Do not skip the notebooks stage.** Every SSB page reads a table the notebook
produces, so without it the dashboard has nothing to draw.

Known Windows caveat: `nbconvert` has historically needed different kernel
transport settings on Windows, so the notebooks stage is the most likely to need
adjusting.

**Contributions making this properly cross-platform are very welcome** — a
Windows-friendly task runner, or a Python entry point replacing the Makefile,
would both be good directions.

---

## What you edit

| You write | To do what |
|---|---|
| `03_notebooks/*.ipynb` | Fetch from SSB and save tables — **where this repo's data comes from** |
| `01_ingestion/*.py` | Get raw data in some other way — scrape, API, file drop |
| `backend/transform.py` | Turn `02_data/raw/` files into tables |
| `04_pages/*.py` | Draw the charts |
| `backend/charts.py` | The palette and layout every chart shares |

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

> **Two routes into `02_data/tables/`.** A notebook writes tables directly with
> `storage.save()`. `01_ingestion/` writes *raw files*, which `transform.py`
> then shapes. The SSB work uses the notebook route, because the wrapper already
> returns analysis-ready frames and there is nothing for `transform.py` to do.
>
> The template's example sources are still in `01_ingestion/` and still produce
> a `records` table from a fixed seed. **No page reads it any more** — delete
> them whenever you like; the pipeline notices on its own.

---

## Build your own

### Adding another SSB table

Open the notebook, copy a section, change the id. The five steps are the same
every time, and `storage.save("<name>", df)` is the only line a page depends on.

Then add `04_pages/NN_name.py` reading that name. Nothing registers a page —
`app.py` finds any `NN_name.py` in `04_pages/`, in filename order.

### Adding a non-SSB source

One file in `01_ingestion/`, one function called `fetch()`. The file **is** the
registration — no registry to update.

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

Yielding streams them, so hundreds of frames never sit in memory at once.

*No sources at all is fine too* — drop files into `02_data/raw/` by hand and the
rest of the pipeline works unchanged.

**CSV, Parquet and Excel all work**, anywhere in the pipeline. Reading always
accepts all three. Writing uses one format, set once in `.env`:

```bash
FILE_FORMAT=parquet     # csv (default) | parquet | xlsx
```

> **Watch the `_code` columns if you use CSV.** An SSB code column that happens
> to be all digits (`AlderX_code` holding `000`–`106`) is read back from CSV as
> an integer, while Parquet keeps it a string — so `df["AlderX_code"] == "000"`
> silently matches nothing in one of the two formats. Compare on the label
> column, which is text everywhere.
>
> CI does build all three formats on pull requests, but **this failure is
> silent** — nothing raises, the chart or metric just renders empty — so no test
> catches it for you. Check by eye when you switch format.

### Drawing a page

Three steps: load, guard, draw.

```python
# 04_pages/07_something.py
from backend import charts, storage

st.header("🏷️ Something")

df = storage.load("my_table")             # the name the notebook saved

if df.empty:                              # always guard: no data yet, or a
    st.info("No data yet.")               # deployed app that lost its bucket
    st.stop()

st.plotly_chart(charts.style(px.bar(df, x="category", y="value")), width="stretch")
```

Pages don't call `st.set_page_config` — `app.py` does it once. **Pages consume;
they don't compute** — put a groupby in the notebook, which runs once per
pipeline run rather than once per browser interaction.

Run `make ci` to render every page and fail if one raises. Run it with
`02_data/` empty to prove your guards work. Three tests define the contract:

| Test | Catches |
|---|---|
| `test_app.py` | a page that raises, **with `02_data/` empty** — a fresh clone or a bucket-less deploy |
| `test_page_tables.py` | a page loading a table the pipeline doesn't produce |
| `test_table_names.py` | the same, but statically — against notebook `save()` calls and `build_tables()` keys, so a typo fails before a two-minute SSB round trip |

---

## Charts

Every chart goes through `charts.style()`, so the dashboard reads as one thing
and a change lands everywhere at once:

```python
from backend import charts

st.plotly_chart(charts.style(px.line(df, x="year", y="value", color="Kjonn",
                                     color_discrete_sequence=charts.PALETTE)),
                width="stretch")
```

`PALETTE` is a fixed eight-hue categorical order, validated against the app's
white surface for colour-vision separation, lightness and chroma. Three rules
come with it:

- **Hues are assigned in order and never cycled.** A ninth series would repeat
  the first hue, so pages cap at `charts.SERIES_LIMIT` (or make the dimension a
  slicer instead — that is why the eleven age bands on the mortality page are a
  dropdown and sex carries the colour).
- **Pass `category_orders` as well as the sequence.** Plotly maps colour by
  position in that list, so a longer list silently wraps — and a stable list is
  what stops a filter from repainting the series that survive it.
- **Three of the eight hues sit below 3:1 contrast on white.** That is legal
  only if the numbers are reachable without colour, which is why every page
  keeps its table in a "Vis data" expander. Don't remove it.

`style()` also forces whole-number axis ticks, leaving date and category axes
alone, and pins `dtick=1` on a narrow range so integer formatting can't print
the same label twice.

---

## How it works

One idea underneath everything: **a table is a file, addressed by name.**
`backend/storage.py` is the only module that knows where files actually live:

```python
from backend import storage

storage.load("befolkning_aldersgrupper")   # -> DataFrame, empty if it isn't there
storage.save("befolkning_aldersgrupper", df)
storage.tables()                           # -> ["befolkning_aldersgrupper", ...]
storage.save_figure("trend", fig)          # load_figure() / figures() for PNGs
```

Set `GCS_BUCKET` and those same calls hit a bucket instead. Nothing else in the
repo changes — no branching, no second code path.

Two rules keep the dashboard hard to break: **reads never raise** (missing file,
bad credentials → empty, so pages show an empty state), and **writes do raise**
(a skipped upload would leave a deployed app serving stale data).

| | |
|---|---|
| `app.py` | entry point — declares the navigation, `make app` runs it |
| `backend/` | config, storage, transform, charts |
| `01_ingestion/` | non-SSB sources |
| `02_data/` | `raw/` and `tables/` — generated, not committed |
| `03_notebooks/` | the SSB ingest notebook |
| `04_pages/` | the dashboard — `00_home.py` is the landing page |
| `05_tests/` | renders every page, checks every table name |

> **Why `backend/` has no number.** Python can't import a module whose name
> starts with a digit, and `backend` is the only folder imported as one — so it
> keeps a plain name and `from backend import storage` just works, in your
> editor as well as at runtime. The numbered folders are all found by path
> instead: scripts, `st.Page`, pytest and the data directory never need
> importing.
>
> Two files still put the repo root on `sys.path` because they run from
> elsewhere: `01_ingestion/run.py` (a script) and the notebooks. And `app.py`
> declares its navigation explicitly, because Streamlit only auto-discovers a
> folder literally named `pages/`.

### Memory

Streamlit reruns your script on every interaction, so uncached reads mean
re-reading a file per click. Every read here is cached with both a `ttl` **and**
a `max_entries` cap, so the cache evicts least-recently-used entries instead of
growing until it exhausts RAM. Tune them in `_cache()` in `backend/storage.py`.

Three more levers, in order of impact:

- **Aggregate in the notebook, not in a page.** A page that loads a million rows
  to draw ten bars keeps a million rows in RAM per cache entry.
- **Load only what you need** — `load()` forwards to `pd.read_csv`, so
  `storage.load("records", usecols=["category", "value"])` never materialises
  the rest.
- **Don't put frames in `st.session_state`.** It is per-session and never
  evicted; the cache is shared across sessions and bounded. This repo uses no
  session state at all.

The GCS connection is built once per process and reused, so credentials are not
re-negotiated on every rerun.

---

## Notebooks

`03_notebooks/` is where this repo's data comes from. Notebooks call the same
`storage` functions as everything else, so anything saved there is immediately
readable by a page — no bridge, no export folder, no wiring:

```python
import sys; sys.path.insert(0, "..")      # required: the notebook runs from 03_notebooks/

from backend import storage
from ssb_statistikkbanken import SSB

storage.save("befolkning_aldersgrupper", SSB().fetch("05810", Kjonn="*", Alder="*", time="*"))
```

`make notebooks` runs every notebook in filename order for those `save()` calls,
and throws away the rendered copy so your `.ipynb` files stay clean — they are
committed without output.

One environment gotcha: `make notebook-kernel` installs the `template-app`
kernel **user-globally**, so running it from a second checkout repoints the
kernel at that checkout's `.venv`. If notebooks start failing with
`No such file or directory: .../.venv/bin/python3`, re-run it from the checkout
you are working in.

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

### Refreshing the data on a schedule

This is where a deployed version earns its keep: SSB republishes, and the
dashboard should follow without a redeploy. The deployed app reads the bucket,
so refreshing means re-running the pipeline. Point a scheduled GitHub Action at
it and the app picks up new tables within its 10-minute cache.

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
    - cron: "0 5 * * *"     # 05:00 UTC daily — clear of SSB's 07:55–08:15 peak
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

      - run: make pipeline      # SSB -> tables -> upload
```

That is the same `make pipeline` you run locally; the only difference is
`GCS_UPLOAD=true`. The runner is thrown away afterwards, so the key file goes
with it. Note that **the writer key needs Storage Object Admin** — the read-only
key you gave the dashboard cannot upload.

---

## Reference

| Target | | Variable | Default |
|---|---|---|---|
| `make setup` | dependencies + kernel | `APP_NAME` | *Testing ssb wrapper and streamlit deployment* |
| `make app` | run the dashboard | `APP_ICON` | 📦 |
| `make pipeline` | the whole ETL | `RAW_DIR` / `TABLES_DIR` | `02_data/raw` / `02_data/tables` |
| `make ingestion` | fetch raw data | `FILE_FORMAT` | `csv` |
| `make transform` | raw → tables | `GCS_BUCKET` | *(empty — stays local)* |
| `make notebooks` | run notebooks (SSB) | `GCS_PREFIX` | *(empty)* |
| `make report` | show sources/tables/pages | `GCS_PROJECT` | *(empty)* |
| `make doctor` | check config + credentials | `GCS_KEY_FILE` | *(empty)* |
| `make ci` | compile + render pages | `GCS_UPLOAD` | `false` |

Only `backend/config.py` reads the environment, and every value has a working
default — an empty `.env` is valid, which is why there isn't one in the repo.
CI runs `make ci`, so local and CI can't drift.

Working in this repo with a coding agent? `CLAUDE.md` documents the conventions,
the wrapper's API in full, and the handful of things that look removable but are
not.

## Credits

- Data: [Statistisk sentralbyrå](https://www.ssb.no) (Statistics Norway), via
  Statistikkbanken and KLASS.
- Wrapper: [`ssb_statistikkbanken`](https://github.com/Manteplante/ssb_statistikkbanken),
  built on [pxwebpy](https://pypi.org/project/pxwebpy/).
- Frontpage image generated with OpenAI; the prompt is credited on the home page.

## License

MIT.
