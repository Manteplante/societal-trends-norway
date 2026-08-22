"""Raw files -> app tables.

Replace `build_tables()` with your own logic. Everything around it — reading
02_data/raw/, writing 02_data/tables/, uploading when GCS_UPLOAD is on — stays
same whatever your domain is.
"""

from __future__ import annotations

import pandas as pd

from . import config
from . import storage


def read_raw() -> pd.DataFrame:
    """Every raw file, stacked, tagged with where it came from.

    Reads CSV, Parquet and Excel alike, so you can drop in whatever you have.
    """
    frames = []
    for path in sorted(config.RAW_DIR.rglob("*")):
        if path.suffix.lower() not in storage.DATA_SUFFIXES:
            continue
        try:
            df = storage.read_file(path)
        except Exception as exc:
            print(f"  [skip] {path.name}: {exc}")
            continue
        if df.empty:
            continue
        # raw/prices.csv -> "prices";  raw/prices/jan.parquet -> "prices"
        df["source"] = path.stem if path.parent == config.RAW_DIR else path.parent.name
        frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_tables(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """TODO: your transformation. Return {table name: DataFrame}.

    The example passes the raw rows straight through as one `records` table.
    Real projects clean, join, and aggregate here, and usually return several
    tables — one per thing a page needs to draw.
    """
    return {"records": raw}


def run() -> None:
    raw = read_raw()
    if raw.empty:
        print(f"[transform] No data files under {config.RAW_DIR} — nothing to do.")
        return

    print(f"[transform] Read {len(raw):,} raw rows")
    for name, df in build_tables(raw).items():
        storage.save(name, df)


if __name__ == "__main__":
    run()
