"""Shared HTTP/HTML helpers for scraped sources.

Leading underscore means this file is not itself a source.
"""

from __future__ import annotations

import time

import requests
from bs4 import BeautifulSoup


def get_html(url: str, delay_seconds: float = 1.0) -> str:
    """GET a page, pausing first to be considerate to the server."""
    time.sleep(delay_seconds)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")
