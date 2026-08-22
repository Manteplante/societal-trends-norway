"""EXAMPLE SOURCE — delete this file once you have a real one.

Stands in for a paginated API: **yields** one DataFrame per month instead of
returning a single one. Each lands in its own file under
02_data/raw/example_web_traffic/.

This is the shape to use when a source produces many frames — yielding streams
them one at a time, so hundreds of pages never sit in memory at once.
"""

from __future__ import annotations

import random

import pandas as pd

CHANNELS = ["Organic", "Paid", "Referral", "Direct"]


def fetch():
    rng = random.Random(21)

    for month in pd.period_range("2025-01", periods=6, freq="M"):
        days = pd.date_range(month.start_time, month.end_time, freq="D")

        yield str(month), pd.DataFrame(
            {
                "date": [day.date().isoformat() for day in days],
                "category": [rng.choice(CHANNELS) for _ in days],
                "value": [rng.randint(50, 500) for _ in days],
            }
        )
