"""Configuration — the only module that reads the environment.

Copy `.env.example` to `.env` to override anything here. Every value has a
working default, so an empty `.env` (or no `.env` at all) is a valid setup.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]  # the repo root, not backend/
load_dotenv(ROOT / ".env")


def _text(name: str, default: str = "") -> str:
    return (os.getenv(name) or "").strip() or default


def _flag(name: str) -> bool:
    return _text(name).lower() in {"1", "true", "yes", "on"}


def _dir(name: str, default: str) -> Path:
    raw = Path(_text(name, default)).expanduser()
    return raw if raw.is_absolute() else (ROOT / raw).resolve()


APP_NAME = _text("APP_NAME", "Streamlit + Google Cloud Storage Template")
APP_ICON = _text("APP_ICON", "📦")

RAW_DIR = _dir("RAW_DIR", "02_data/raw")          # what ingestion writes
TABLES_DIR = _dir("TABLES_DIR", "02_data/tables")  # what the app reads

# What the pipeline *writes*: csv, parquet, or xlsx. Reading always accepts all
# three, whatever you drop in — this only picks the output format.
#   csv      readable anywhere, biggest files
#   parquet  smallest and fastest, keeps dtypes  (recommended once data grows)
#   xlsx     only when a human needs to open it in Excel
FILE_FORMAT = _text("FILE_FORMAT", "csv").strip(".").lower()

# Google Cloud Storage — optional. Leave GCS_BUCKET empty to stay entirely local.
GCS_BUCKET = _text("GCS_BUCKET")
GCS_PREFIX = _text("GCS_PREFIX").strip("/")
GCS_PROJECT = _text("GCS_PROJECT")
GCS_KEY_FILE = _text("GCS_KEY_FILE")
GCS_UPLOAD = _flag("GCS_UPLOAD")  # upload tables after writing them locally
