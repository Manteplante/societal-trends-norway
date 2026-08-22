"""Every table a page asks for must be one the pipeline actually produces.

Renaming a table in `build_tables()` and forgetting the page that reads it is
the easy mistake: the page hits its `df.empty` guard and renders a blank state,
so nothing crashes and the smoke test stays green. This catches it instead.

Skipped when there is no data yet — on a fresh clone every page is "missing"
its table, which is expected rather than a fault.
"""

import re
from pathlib import Path

import pytest

from backend import storage

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted((ROOT / "04_pages").glob("[0-9]*.py"))

# storage.load("name") / storage.load_figure("name"), literal arguments only.
CALL = re.compile(r"""storage\.(load|load_figure)\(\s*["']([^"']+)["']""")


def requested_names() -> list[tuple[str, str, str]]:
    found = []
    for page in PAGES:
        for kind, name in CALL.findall(page.read_text(encoding="utf-8")):
            found.append((page.name, kind, name))
    return found


def test_every_page_reads_something():
    assert requested_names(), "no storage.load() calls found in 04_pages/"


@pytest.mark.skipif(
    not storage.tables() and not storage.figures(),
    reason="no data yet — run `make pipeline` first",
)
def test_pages_only_read_tables_that_exist():
    tables, figures = set(storage.tables()), set(storage.figures())

    missing = [
        f"{page} reads {kind}({name!r}), which the pipeline does not produce"
        for page, kind, name in requested_names()
        if name not in (figures if kind == "load_figure" else tables)
    ]

    assert not missing, "\n".join(
        missing + [f"available tables: {sorted(tables)}", f"available figures: {sorted(figures)}"]
    )
