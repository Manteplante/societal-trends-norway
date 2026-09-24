# CLAUDE.md

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

---

## Working style

- State assumptions before editing.
- If the task is ambiguous, ask one clarifying question.
- Touch only the files the requested change needs. Don't refactor unrelated
  code unless asked.
- Use plan mode for complex issues.
- Before finishing, run `make ci` — the same target GitHub Actions runs. It
  byte-compiles `backend/`, `01_ingestion/`, `app.py` and `04_pages/`, then runs
  `05_tests/` (pages render with `02_data/` empty; every `storage.load()` names
  a real table). There is no lint step: no ruff, no mypy, nothing in CI
  enforces style.
- `make pipeline` (and `make ingestion` / `make notebooks`) is the user's step.
  It fetches live from SSB and runs notebooks, so don't run it to verify a
  change — say which stage the user should re-run instead. Note that `make ci`
  alone only proves pages survive empty data; it doesn't exercise a real
  `build_tables()` run.
- `make help` lists the rest.

## Communication

- Be concise.
- Call out trade-offs when there is more than one reasonable approach.
- Push back if a safer or smaller approach would meet the goal.
- Be critical of what the user suggests, not agreeable.

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

---

## Git

- **Never create a branch.** The user creates the feature branch, always. Not
  `git checkout -b`, `git switch -c`, `git branch <name>`, a worktree, or "a
  quick branch to be safe". Work on whatever branch is checked out. If it looks
  wrong for the task — `main`, or a branch for unrelated work — say so and
  stop. Don't switch branches either; which branch is checked out is the
  user's call.
- **Never push**, to any branch. CI runs on every push to every branch, so a
  push is the user's action.
- Don't run `git commit`, `git push`, `git merge`, `git rebase`,
  `git reset --hard` or `gh pr create`.
- Staging and inspecting is fine: `git add`, `git status`, `git diff`,
  `git log`, `git show`.
- Never stage anything under `02_data/` (generated) or a key file such as
  `cloud-key.json`.
- When work is done, stage it and put the proposed commit message and PR text
  in the reply for the user to run.
- PR text: 1000 words maximum — a hard ceiling; most PRs should land far under
  it. If a change needs more explanation, it belongs in `README.md` or this
  file, and the PR links to it.

## Dependencies

- Use `uv` for every dependency and environment command. Never `pip install`.
- Ask before adding a dependency, runtime or dev.
- Every install is explicit and lands in `pyproject.toml`: `uv add` /
  `uv add --dev`, run by the user, and nothing else. No `uvx`, no
  `uv pip install`, no `--with`, no tool that fetches a package on the fly — an
  implicit install is invisible to `uv.lock`, and CI installs with
  `uv sync --frozen`, so it breaks there even if it works locally.
- Commit `pyproject.toml` and `uv.lock` together. A stale lock fails CI.
- Make targets and scripts must fail with the `uv add` command to run, never
  install the package themselves.

---

## SSB wrapper — `ssb_statistikkbanken`

A git dependency (see `pyproject.toml`), source at
https://github.com/Manteplante/ssb_statistikkbanken. Built on
[pxwebpy](https://pypi.org/project/pxwebpy/), which supplies the HTTP layer,
query batching, threading and response caching; the wrapper adds SSB-specific
defaults, validation and reshaping. Use it from ingestion sources and notebooks.


```python
from ssb_statistikkbanken import SSB, klass

ssb = SSB()
```

---

### The loop

**search → describe → values → fetch → reshape.** Repeat with any table id.

```python
ssb.search("befolkning", limit=10)  # 1. which table?
ssb.describe("05810")  # 2. what's in it?
ssb.values("05810", "Alder")  # 3. what codes can I filter on?
df = ssb.fetch("05810", Kjonn="0", Alder="*", time=range(2020, 2026))  # 4. get it
wide = ssb.dataset("05810", Kjonn="0", Alder="*", time=range(2020, 2026)).to_wide()
```

---

### Discovery

| Call | Returns |
|---|---|
| `ssb.search("ulykke")` | matching tables as a DataFrame |
| `ssb.search("ulykke", limit=25)` | more rows (default 100; warns if truncated) |
| `ssb.search("ulykke", updated_within_days=365)` | only recently updated |
| `ssb.search(include_discontinued=True)` | include retired tables |
| `ssb.paths()` | subject-area tree (downloads full index, ~1.5s, then cached) |
| `ssb.tables("al")` | tables under a subject path |

⚠️ `search` matches **value labels** too, not just titles — `"skred"` returns a
table of surnames. Read the `label` column before trusting a hit.

---

### Inspection

| Call | Returns |
|---|---|
| `ssb.describe("05810")` | `TableInfo` — HTML card in Jupyter |
| `ssb.variables("05810")` | one row per dimension: size, **mandatory**, code lists |
| `ssb.values("05810", "Alder")` | every value code — never truncated |
| `ssb.values("07459", "Region", search="oslo")` | filter codes *and* labels |
| `ssb.values("05810")` | all variables stacked |
| `ssb.code_list("agg_FemAarigGruppering")` | members of a named aggregation |
| `ssb.table("05810")` | handle bound to one table |

Useful `TableInfo` attributes:

```python
info = ssb.describe("05810")
info.label  # '05810: Aldersgrupper og kjønnsfordeling ...'
info.order  # ['Kjonn', 'Alder', 'ContentsCode', 'Tid']
info.mandatory  # ['ContentsCode', 'Tid']  <- omit these and SSB 400s
info.time_unit  # 'annual' | 'monthly' | 'quarterly' | None
info.periods  # ('1845', '2026')
info.decimals  # 0   (a hint, not a promise -- see Gotchas)
info["Alder"].codes  # ['999B', '00-06', ...]  in SSB's own order
info["Alder"].labels  # ['Alle', '0-6 år', ...]
info["Alder"].n_values
```

---

### Fetching

```python
ssb.fetch(table_id, filters=None, *, time=None, latest=1, contents=None,
          code_list=None, labels="both", columns="code", language=None,
          max_cells=None, categorical=False, **filters)
```

#### Filter values — all of these work

```python
ssb.fetch("11342", Region="03")  # single code
ssb.fetch("11342", Region=["03", "11", "15"])  # list (never ",".join!)
ssb.fetch("05810", time=range(2020, 2026))  # range
ssb.fetch("05810", time=[2024, 2025])  # ints are fine
ssb.fetch("07459", Region="03*")  # wildcard prefix
ssb.fetch("11342", Region="*")  # everything
ssb.fetch("05810", Alder="0-6 år")  # labels resolve to codes
ssb.fetch("05810", time="top(5)")  # PxWeb expression (see Gotchas)
ssb.fetch("12292", filters={"KOKkommuneregion0000": "EAK"})  # non-identifier codes
```

#### Key parameters

| Parameter | Default | What it does |
|---|---|---|
| `latest=n` | `1` | last *n* periods when you don't pass `time` |
| `time=` | — | the time variable, by any of the forms above |
| `contents=` | — | alias for `ContentsCode` |
| `code_list={"Alder": "agg_..."}` | — | use an SSB aggregation; auto-selects that variable |
| `labels="both"` | `"both"` | `"label"` or `"code"` for a single column each |
| `columns="code"` | `"code"` | name columns by variable code (stable across languages) or `"label"` |
| `language="en"` | `"no"` | translates values; column names stay put |
| `max_cells=50_000` | `None` | refuse an oversized selection before sending |
| `categorical=True` | `False` | dimension columns as `category` dtype |

Anything mandatory you leave out is filled in automatically (`*`, or `latest`
for time). Eliminable variables you skip are aggregated away by SSB.

---

### Output shapes

```python
ds = ssb.dataset("05810", Kjonn="0", Alder="*", time=range(2020, 2026))

ds.to_pandas()  # tidy long (same as ssb.fetch)
ds.to_wide()  # wide pivot, SSB's value order preserved
ds.to_polars()  # needs polars installed
ds.to_records()  # list[dict] -- bring your own frame
ds.query  # the exact value codes that were sent
len(ds)  # row count
```

#### `to_wide()` — use this instead of `pivot_table`

```python
ds.to_wide()  # time down, widest dimension across
ds.to_wide(columns="Alder_code")  # codes as headers
ds.to_wide(columns="Alder", index="year")
ds.to_wide(aggfunc="mean")
```

Plain `df.pivot_table(...)` sorts columns **alphabetically**, which puts
`7-15 år` between `67-79 år` and `80 år eller eldre` and pushes the `Alle` total
to the end. `to_wide()` restores SSB's published order on both axes.

---

### What comes back

`fetch()` gives one row per observation, already typed:

| Kjonn | Kjonn_code | Alder | Alder_code | Tid | Tid_code | year | value |
|---|---|---|---|---|---|---|---|
| Begge kjønn | 0 | 0-6 år | 00-06 | 2020 | 2020 | 2020 | 412551 |

- every dimension → a label column **and** a `_code` column (join on codes)
- `value` → nullable `Int64`, or `Float64` when the data has decimals
- `year` → `Int16` for annual tables; `date` → `datetime64` for monthly/quarterly

---

### KLASS — classifications and joins

```python
klass.kommuner(2025)  # municipalities at a date
klass.fylker(2025)  # counties
klass.bydeler(2025)  # city districts
klass.kommune_til_fylke(2025)  # {'0301': '03', ...}
klass.codes(klass.Classification.NARING_SN, date=2025)
klass.mapping(104, date=2025)  # {code: name}
klass.correspondence(131, 104, date=2025)  # kommune -> fylke
klass.changes(131, from_=2019, to=2021)  # the 2020 reform
klass.classifications(search="yrke")  # find a classification id
```

#### Attach names / roll up

```python
df = klass.attach_names(df, "Region_code", klass.Classification.KOMMUNE, date=2025)
df = klass.attach_parent(df, "Region_code", date=2025)  # adds fylke_code + fylke
```

`on_missing="warn"` (default) reports codes KLASS doesn't have — SSB tables carry
aggregates like `"0"` (Hele landet) and historic codes. Use `"raise"` in a
pipeline, `"ignore"` to silence.

#### Classification ids

`GRUNNKRETS 1` · `KJONN 2` · `NARING_SN 6` · `YRKE_STYRK 7` · `UTDANNING_NUS 36` ·
`LANDKODER_SSB3 91` · `LANDKODER_ALPHA2 100` · `BYDEL 103` · **`FYLKE 104`** ·
`HELSEREGION 105` · `OKONOMISK_REGION 108` · `TETTSTED 110` · `FYLKESKOMMUNE 127` ·
`SENTRALITET 128` · `KOMMUNEKLASSIFISERING 129` · **`KOMMUNE 131`** · `ALDER 282` ·
`LANDKODER_ALPHA3 552`

---

### Errors

All derive from `SsbError`, so one `except` catches everything:

```python
from ssb_statistikkbanken import SsbError

try:
    ssb.fetch("05810", Kjonne="0")
except SsbError as exc:
    print(exc)
```

| Exception | When |
|---|---|
| `UnknownVariableError` | typo'd variable — includes a did-you-mean |
| `UnknownValueError` | bad value code — includes a did-you-mean |
| `SelectionTooLargeError` | selection exceeds your `max_cells` |
| `TableNotFoundError` | HTTP 404 |
| `BadSelectionError` | HTTP 400 from SSB |
| `RateLimitedError` | HTTP 429 after retries |
| `MissingDependencyError` | `.to_polars()` without polars |
| `KlassError` / `ClassificationNotFoundError` | KLASS problems |

Variable and value names are checked **before** the request goes out, so typos
come back instantly rather than as an HTTP error.

---

### Gotchas

- **`decimals` is a hint.** SSB reports it per table, but units can vary per
  `ContentsCode` (counts + km in one table). The wrapper checks the actual values
  and falls back to `Float64` — don't assume `Int64`.
- **PxWeb expressions defeat batching.** `top(n)`, `from(x)`, `range(x,y)`, `?`
  are resolved by SSB, so the size can't be known up front and the request won't
  be split. For big pulls prefer `latest=n`, an explicit list, or `*`.
- **800,000 cells per request.** Larger selections are split and stitched
  automatically; you get a warning naming the split.
- **Empty KLASS result = wrong date.** A retired classification returns no codes;
  the wrapper warns and names the validity window.
- **Notebook kernels ignore `uv run --with`.** Anything a notebook imports must
  be a real project dependency.
- **Avoid 07:55–08:15**, SSB's publishing peak.

### Notes on the API this wraps

- SSB allows **800,000 cells per request**; pxwebpy splits larger selections
  automatically and fetches the parts concurrently.
- SSB's `/config` reports **no** rate limit, so pxwebpy will not throttle —
  but SSB documents 30 requests/minute per IP, which is why `max_workers`
  defaults to 4 here rather than to automatic sizing.
- `top(n)`, `from(x)`, `range(x,y)` and `?` are resolved by SSB, so a selection
  using them cannot be sized or split up front. `latest=n`, explicit lists and
  `*` all can be — prefer those for large queries.
- Avoid 07:55–08:15, SSB's publishing peak.
