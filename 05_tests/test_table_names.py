"""Every table a page reads must be named by something that produces one.

`test_page_tables.py` checks the same contract against tables that actually
exist, so it only runs once `make pipeline` has been through. This checks it
statically — against the dict keys `build_tables()` returns and the
`storage.save()` calls in `03_notebooks/` — so a rename or a typo fails on a
fresh clone, with `02_data/` empty and before anything has been fetched.

That matters now that a notebook fetches from SSB's live API: without this, a
misspelled table name would only surface after a two-minute round trip.
"""

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted((ROOT / "04_pages").glob("[0-9]*.py"))
NOTEBOOKS = sorted((ROOT / "03_notebooks").glob("*.ipynb"))

# storage.load("name") / storage.load_figure("name"), literal arguments only.
LOAD = re.compile(r"""storage\.(load|load_figure)\(\s*["']([^"']+)["']""")
SAVE = re.compile(r"""storage\.(save|save_figure)\(\s*["']([^"']+)["']""")


def notebook_code(path: Path) -> str:
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    return "\n".join(
        "".join(cell["source"]) for cell in cells if cell["cell_type"] == "code"
    )


def produced() -> tuple[set[str], set[str]]:
    """Table and figure names anything in the repo writes."""
    tables, figures = transform_keys(), set()

    for notebook in NOTEBOOKS:
        for kind, name in SAVE.findall(notebook_code(notebook)):
            (figures if kind == "save_figure" else tables).add(name)

    return tables, figures


def transform_keys() -> set[str]:
    """The string keys of every dict literal inside `build_tables()`."""
    tree = ast.parse((ROOT / "backend" / "transform.py").read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "build_tables"
    )
    return {
        key.value
        for mapping in ast.walk(function)
        if isinstance(mapping, ast.Dict)
        for key in mapping.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def test_every_page_table_has_a_producer():
    tables, figures = produced()

    missing = [
        f"{page.name} reads {kind}({name!r}), which nothing in the repo writes"
        for page in PAGES
        for kind, name in LOAD.findall(page.read_text(encoding="utf-8"))
        if name not in (figures if kind == "load_figure" else tables)
    ]

    assert not missing, "\n".join(
        missing
        + [
            f"build_tables() returns: {sorted(transform_keys())}",
            f"notebooks save tables:  {sorted(tables - transform_keys())}",
            f"notebooks save figures: {sorted(figures)}",
            "(names built at runtime rather than written as literals are invisible here)",
        ]
    )
