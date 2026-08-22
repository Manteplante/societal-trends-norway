"""Fetch every source in this folder into 02_data/raw/.

Drop a module in here with a `fetch()` function and it is picked up
automatically: no registry to keep in sync, the filename is the source name.

`fetch()` returns either **one** DataFrame:

    01_ingestion/prices.py  ->  DataFrame  ->  02_data/raw/prices.csv  (or .parquet / .xlsx — see FILE_FORMAT)

or **many**, as a dict or as `(label, DataFrame)` pairs — one file each, in a
folder named after the source:

    prices.py  ->  {"jan": df, "feb": df}  ->  02_data/raw/prices/jan.csv
                                                02_data/raw/prices/feb.csv

Yielding pairs instead of returning a dict lets a source stream hundreds of
frames without holding them all in memory:

    def fetch():
        for page in range(100):
            yield f"page_{page:03d}", scrape_page(page)

Either way `backend/transform.py` reads them all back and tags every row
with the source name, so the two shapes are interchangeable downstream.

Scrape it, call an API, read a shared drive — the rest of the pipeline neither
knows nor cares which. Files starting with `_` are helpers, not sources;
`_http.py` ships with `get_html()` and `soup()`.

A scraped source, 01_ingestion/prices.py:

    import pandas as pd
    from _http import get_html, soup

    def fetch() -> pd.DataFrame:
        page = soup(get_html("https://example.com/prices"))
        return pd.DataFrame(
            {"category": row.th.text, "value": row.td.text}
            for row in page.select("table tr")
        )
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # run as a script, so put the repo root on the path

import pandas as pd

from backend import config, storage


def source_files() -> list[Path]:
    """Every source module in this folder, in filename order."""
    return sorted(
        path
        for path in HERE.glob("*.py")
        if not path.name.startswith("_") and path.name != "run.py"
    )


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def run() -> None:
    found = source_files()
    if not found:
        print("[ingest] No sources in 01_ingestion/ — using whatever is in 02_data/raw/ already.")
        return

    for path in found:
        fetch = getattr(_load(path), "fetch", None)
        if fetch is None:
            print(f"[ingest] {path.name}: no fetch() function — skipped")
            continue
        _collect(path.stem, fetch())


def _collect(name: str, result) -> None:
    """Write whatever fetch() returned — one frame, or many."""
    if isinstance(result, pd.DataFrame):
        _write(config.RAW_DIR / f"{name}{storage.data_suffix()}", result)
        return

    # A dict, or any iterable of (label, DataFrame) pairs — generators included.
    pairs = result.items() if isinstance(result, dict) else result
    written = 0
    for label, df in pairs:
        _write(config.RAW_DIR / name / f"{label}{storage.data_suffix()}", df)
        written += 1

    if not written:
        print(f"[ingest] {name}: returned nothing")


def _write(path: Path, df: pd.DataFrame) -> None:
    storage.write_frame(path, df)
    print(f"[ingest] {path.relative_to(config.RAW_DIR)}: {len(df):,} rows")


if __name__ == "__main__":
    run()
