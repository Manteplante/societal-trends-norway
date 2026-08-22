"""Print a markdown snapshot of what this pipeline currently is.

    make report

Sources, tables (with their columns), figures, and which table each page reads
— derived by inspection, so it describes *your* pipeline rather than the
example one. CI appends this to the run summary, so every build shows the shape
of the data it just built.

Read-only and never fails: it is a report, not a check. The assertions live in
`05_tests/`.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import config, storage

ROOT = config.ROOT
INGESTION, PAGES = ROOT / "01_ingestion", ROOT / "04_pages"

# storage.load("name") / storage.load_figure("name"), literal arguments only.
CALL = re.compile(r"""storage\.(load|load_figure)\(\s*["']([^"']+)["']""")

MAX_COLUMNS = 8  # keep the table readable when a frame is very wide


def sources() -> list[tuple[str, int, int]]:
    """(name, files written, rows) for every source module, by inspection."""
    found = []
    for path in sorted(INGESTION.glob("*.py")):
        if path.name.startswith("_") or path.name == "run.py":
            continue

        # A source writes either <name>.<ext> or a <name>/ folder of files.
        folder = config.RAW_DIR / path.stem
        files = (
            sorted(folder.rglob("*"))
            if folder.is_dir()
            else [p for p in config.RAW_DIR.glob(f"{path.stem}.*")]
        )
        files = [f for f in files if f.suffix.lower() in storage.DATA_SUFFIXES]

        rows = 0
        for f in files:
            try:
                rows += len(storage.read_file(f))
            except Exception:
                pass
        found.append((path.stem, len(files), rows))
    return found


def pages() -> list[tuple[str, list[str]]]:
    """(page filename, what it loads) for every page — figures marked as such."""
    found = []
    for path in sorted(PAGES.glob("[0-9]*.py")):
        seen: list[str] = []
        for kind, name in CALL.findall(path.read_text(encoding="utf-8")):
            label = f"`{name}`" + (" _(figure)_" if kind == "load_figure" else "")
            if label not in seen:
                seen.append(label)
        found.append((path.name, seen))
    return found


def main() -> None:
    out: list[str] = []

    out.append("### Sources")
    rows = sources()
    if rows:
        out += ["", "| Source | Files | Rows |", "| --- | --- | --- |"]
        out += [f"| `{n}` | {f} | {r:,} |" for n, f, r in rows]
        if not any(f for _, f, _ in rows):
            out += ["", "_Registered, but nothing fetched yet._"]
    else:
        out += ["", "_None in `01_ingestion/` — the pipeline reads whatever is in `02_data/raw/`._"]

    out += ["", "### Tables"]
    names = storage.tables()
    if names:
        out += ["", "| Table | Rows | Columns |", "| --- | --- | --- |"]
        for name in names:
            df = storage.load(name)
            cols = list(df.columns)
            shown = ", ".join(f"`{c}`" for c in cols[:MAX_COLUMNS])
            if len(cols) > MAX_COLUMNS:
                shown += f" _(+{len(cols) - MAX_COLUMNS} more)_"
            out.append(f"| `{name}` | {len(df):,} | {shown or '—'} |")
    else:
        out += ["", "_No tables yet — run `make pipeline`._"]

    figures = storage.figures()
    out += ["", "### Figures", "", ", ".join(f"`{f}`" for f in figures) or "_None._"]

    out += ["", "### Pages", "", "| Page | Reads |", "| --- | --- |"]
    for name, loads in pages():
        out.append(f"| `{name}` | {', '.join(loads) or '_nothing — status only_'} |")

    out += ["", f"_Reading from `{storage.describe()}`._"]
    print("\n".join(out))


if __name__ == "__main__":
    main()
