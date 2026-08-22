"""Smoke test: every page renders without raising, with or without data."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted((ROOT / "04_pages").glob("[0-9]*.py"))


def run(script: Path) -> AppTest:
    app = AppTest.from_file(script, default_timeout=30)
    app.run()
    return app


def check(app: AppTest, name: str) -> None:
    """Fail with the Streamlit error and the line that caused it, not a repr dump."""
    if not app.exception:
        return

    error = app.exception[0]
    frame = (error.stack_trace or [""])[0].strip()
    pytest.fail(f"{name} raised: {error.value}\n{frame}", pytrace=False)


def test_entry_renders():
    check(run(ROOT / "app.py"), "app.py")


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_page_renders(page):
    # app.py owns st.set_page_config, so run it first — a page tested in
    # isolation would otherwise render without it.
    run(ROOT / "app.py")
    check(run(page), page.name)
