"""EXAMPLE SOURCE — delete this file once you have a real one.

Stands in for a scraped or API-backed source: returns **one** DataFrame, which
lands in 02_data/raw/example_store_sales.csv.

Generates deterministic fake rows (fixed seed) so a fresh clone has something
to look at without any network access or credentials.
"""

from __future__ import annotations

import random

import pandas as pd

CATEGORIES = ["Espresso", "Pastry", "Sandwich", "Tea", "Smoothie"]


def fetch() -> pd.DataFrame:
    rng = random.Random(7)

    rows = [
        {
            "date": day.date().isoformat(),
            "category": rng.choice(CATEGORIES),
            "value": round(rng.uniform(5, 90), 2),
        }
        for day in pd.date_range("2025-01-01", periods=180, freq="D")
        for _ in range(rng.randint(1, 4))
    ]

    return pd.DataFrame(rows)
