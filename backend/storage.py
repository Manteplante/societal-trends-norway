"""Tables in, tables out — from a local folder or a GCS bucket, same calls.

    load("sales")        -> DataFrame, empty if it isn't there (any of the 3 formats)
    save("sales", df)    -> writes 02_data/tables/sales.<csv|parquet|xlsx>
    tables()             -> ["sales", ...]

    save_figure("trend", fig) / load_figure("trend") / figures()

The pipeline, the notebooks, and the app all use these same six functions. A
table is a file; you read it by name.

Reads never raise: a missing file, an unset bucket, or bad credentials all come
back empty, so the app shows an empty state instead of a stack trace. Writes do
raise — a silently skipped upload would leave a deployed app showing stale data.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from . import config

try:
    import gcsfs
except Exception:
    gcsfs = None


# ── Streamlit niceties, optional ──────────────────────────────────────────────
# These modules are imported from notebooks and plain scripts too, where
# `st.cache_data` warns and there is no `st.secrets` to read.

def _cache(ttl: int, max_entries: int):
    """`st.cache_data` when a Streamlit runtime is live, otherwise a no-op.

    `max_entries` is the memory guard: caches evict least-recently-used entries
    past that count instead of growing until the TTL expires. Raise it if you
    have many small tables; lower it if you have a few very large ones.
    """
    try:
        import streamlit as st
        import streamlit.runtime

        if streamlit.runtime.exists():
            return st.cache_data(ttl=ttl, max_entries=max_entries)
    except Exception:
        pass
    return lambda func: func


# ── File formats ──────────────────────────────────────────────────────────────
# Reading accepts any of these, whatever a user drops in. Writing uses the one
# FILE_FORMAT names, so a pipeline produces one consistent format.

DATA_SUFFIXES = (".csv", ".parquet", ".xlsx", ".xls")


def data_suffix() -> str:
    """The extension the pipeline writes, e.g. ".csv"."""
    suffix = f".{config.FILE_FORMAT}"
    if suffix not in DATA_SUFFIXES:
        raise ValueError(
            f"FILE_FORMAT={config.FILE_FORMAT!r} is not supported. "
            f"Use one of: {', '.join(s.lstrip('.') for s in DATA_SUFFIXES)}."
        )
    return suffix


def _read_frame(handle, suffix: str, **kwargs) -> pd.DataFrame:
    if suffix == ".parquet":
        return pd.read_parquet(handle, **kwargs)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(handle, **kwargs)
    return pd.read_csv(handle, **kwargs)


def _frame_bytes(df: pd.DataFrame, suffix: str) -> bytes:
    buffer = io.BytesIO()
    if suffix == ".parquet":
        df.to_parquet(buffer, index=False)
    elif suffix in (".xlsx", ".xls"):
        df.to_excel(buffer, index=False)
    else:
        buffer.write(df.to_csv(index=False).encode("utf-8"))
    return buffer.getvalue()


def read_file(path: Path, **kwargs) -> pd.DataFrame:
    """Read one local file, format taken from its extension."""
    with path.open("rb") as handle:
        return _read_frame(handle, path.suffix.lower(), **kwargs)


def write_frame(path: Path, df: pd.DataFrame) -> Path:
    """Write a DataFrame to an explicit path, format taken from its extension."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_frame_bytes(df, path.suffix.lower()))
    return path


def _secret(key: str) -> str:
    try:
        import streamlit as st

        value = st.secrets.get(key)
        return value.strip() if isinstance(value, str) else ""
    except Exception:
        return ""


# ── Where the tables live ─────────────────────────────────────────────────────

def _bucket() -> str:
    return config.GCS_BUCKET or _secret("GCS_BUCKET")


def _prefix() -> str:
    return (config.GCS_PREFIX or _secret("GCS_PREFIX")).strip("/")


def remote() -> bool:
    """True when a bucket is configured, i.e. the app reads from GCS."""
    return bool(_bucket())


def describe() -> str:
    """Where tables are being read from, for status messages."""
    return _uri("").rstrip("/") if remote() else str(config.TABLES_DIR)


def _uri(filename: str) -> str:
    parts = [p for p in (_prefix(), filename.strip("/")) if p]
    return f"gs://{_bucket()}/{'/'.join(parts)}"


_FS: Optional[Any] = None
_FS_RESOLVED = False

# Where the credentials came from, and why they failed — recorded for
# `diagnose()`. Only ever holds descriptions, never a credential value.
_CRED_SOURCE = "not resolved yet"
_AUTH_ERROR = ""


def _fs() -> Optional[Any]:
    """The GCS filesystem, or None if unavailable. Built once, then reused."""
    global _FS, _FS_RESOLVED, _CRED_SOURCE, _AUTH_ERROR
    if _FS_RESOLVED:
        return _FS

    _FS_RESOLVED = True
    if gcsfs is None:
        _CRED_SOURCE, _AUTH_ERROR = "none", "the gcsfs package is not installed"
        return None
    if not remote():
        _CRED_SOURCE, _AUTH_ERROR = "none", "no bucket configured — staying local"
        return None

    # Credentials, in order: the downloaded JSON key file, a [connections.gcs]
    # secrets section (Streamlit's documented layout — the same fields as that
    # JSON), then whatever ambient credentials the platform provides.
    # The key file is only used when it is actually there, so leaving
    # GCS_KEY_FILE set in .env never blocks the secrets path.
    token: Any = None
    if (path := key_file_path()) is not None and path.exists():
        token, _CRED_SOURCE = str(path), f"key file {path}"

    if token is None:
        try:
            import streamlit as st

            token = dict(st.secrets["connections"]["gcs"]) or None
            if token:
                _CRED_SOURCE = "[connections.gcs] in Streamlit secrets"
        except Exception:
            token = None
    if token is None:
        token = "google_default"
        _CRED_SOURCE = "Application Default Credentials"

    if isinstance(token, dict) and isinstance(token.get("private_key"), str):
        token["private_key"] = token["private_key"].replace("\\n", "\n")

    try:
        _FS = gcsfs.GCSFileSystem(token=token, project=config.GCS_PROJECT or None)
        _AUTH_ERROR = ""
    except Exception:
        # The library's message is deliberately NOT passed through: it was
        # handed the credential and could quote it back. `make doctor` says
        # what to check instead.
        _AUTH_ERROR = "could not authenticate"
        print("[storage] GCS authentication failed; reads return empty. Run `make doctor`.")
        _FS = None
    return _FS


def key_file_path() -> Optional[Path]:
    """Absolute path GCS_KEY_FILE resolves to, or None when it is unset."""
    if not config.GCS_KEY_FILE:
        return None
    path = Path(config.GCS_KEY_FILE).expanduser()
    return path if path.is_absolute() else config.ROOT / path


def ready() -> bool:
    """True when a bucket is configured *and* its credentials actually worked."""
    return _fs() is not None


# ── Diagnostics ───────────────────────────────────────────────────────────────
# Deliberately generic about credentials. Nothing here reads, formats or echoes
# a credential value, and no message from the GCS library is passed through —
# that way there is no leak to reason about. The output says what to check, not
# what your key contains, and is safe to paste into an issue or a CI log.

def _credential_sources() -> list[str]:
    """Which credential sources are present — presence only, never content."""
    lines = []

    path = key_file_path()
    if path is None:
        lines.append("      key file:              GCS_KEY_FILE is unset")
    elif path.exists():
        lines.append(f"      key file:              found at {path}")
    else:
        lines.append(f"      key file:              NOT FOUND at {path}")

    try:
        import streamlit as st

        present = bool(dict(st.secrets["connections"]["gcs"]))
    except Exception:
        present = False
    lines.append(f"      Streamlit secrets:     [connections.gcs] {'present' if present else 'not present'}")
    lines.append("      default credentials:   used only if neither of the above works")
    return lines


def diagnose() -> list[str]:
    """Human-readable config check. Reports settings and presence, never values."""
    lines: list[str] = ["Configuration", ""]

    try:
        lines.append(f"  \u2713 FILE_FORMAT={config.FILE_FORMAT} (writes {data_suffix()})")
    except ValueError as exc:
        lines.append(f"  \u2717 {exc}")

    for label, folder in (("RAW_DIR", config.RAW_DIR), ("TABLES_DIR", config.TABLES_DIR)):
        mark = "\u2713" if folder.is_dir() else "\u2717"
        note = "" if folder.is_dir() else "  (missing \u2014 created on first write)"
        lines.append(f"  {mark} {label}={folder}{note}")

    lines += ["", "Google Cloud Storage", ""]

    if not remote():
        lines += ["  \u2014 GCS_BUCKET is empty, so everything stays local.",
                  f"    The app reads {config.TABLES_DIR}."]
        if config.GCS_UPLOAD:
            lines.append("  \u2717 GCS_UPLOAD=true with no bucket \u2014 the pipeline will raise on write.")
        return lines

    source = "env/.env" if config.GCS_BUCKET else "Streamlit secrets"
    lines += [f"  \u2713 bucket: {_bucket()}   (from {source})",
              f"    prefix:  {_prefix() or '(none \u2014 objects at bucket root)'}",
              f"    upload:  GCS_UPLOAD={config.GCS_UPLOAD}"]
    if not config.GCS_PROJECT:
        lines.append("    note:    GCS_PROJECT is unset; gcsfs warns but object access still works.")

    lines += ["", "  Credentials are tried in order:"] + _credential_sources()

    if ready():
        lines += ["", "  \u2713 connection working.",
                  f"    tables visible remotely: {', '.join(tables()) or 'none'}"]
        return lines

    lines += ["", "  \u2717 could not connect with any of them.", "",
              "    Things to check, commonest first:",
              "      \u2022 the key file is the complete JSON you downloaded, not a truncated copy",
              "      \u2022 the service account has access to this bucket (Storage Object Viewer",
              "        to read, Storage Object Admin to upload)",
              "      \u2022 the bucket name and prefix are spelled correctly",
              "      \u2022 in a deployed app, secrets are saved under [connections.gcs]",
              "",
              "    Reads soft-fail, so the dashboard looks empty rather than erroring."]
    return lines


# ── Reading ───────────────────────────────────────────────────────────────────

@_cache(ttl=600, max_entries=8)
def load(name: str, **read_kwargs) -> pd.DataFrame:
    """Read one table by name, in whatever format it was saved.

    Extra keyword arguments go to the underlying pandas reader, so
    `load("records", columns=[...])` (parquet) or `usecols=[...]` (csv) avoids
    materialising columns you do not need.
    """
    filename = _find(name, DATA_SUFFIXES)
    if not filename:
        return pd.DataFrame()

    suffix = Path(filename).suffix.lower()
    return _read(filename, lambda h: _read_frame(h, suffix, **read_kwargs), pd.DataFrame())


@_cache(ttl=600, max_entries=8)
def load_figure(name: str) -> Optional[bytes]:
    """Read a saved PNG by name, for `st.image`. None if it isn't there."""
    filename = _find(name, (".png",))
    if not filename:
        return None
    return _read(filename, lambda h: h.read(), None)


def _find(name: str, suffixes: tuple[str, ...]) -> str:
    """Resolve a bare name to a real filename, whatever extension it carries.

    The configured FILE_FORMAT is tried first, so switching formats picks up the
    freshly written file rather than an older one left behind in another format.
    """
    available = set(_entries())
    preferred = data_suffix() if data_suffix() in suffixes else None
    ordered = ([preferred] if preferred else []) + [s for s in suffixes if s != preferred]

    for suffix in ordered:
        candidate = f"{name}{suffix}"
        if candidate in available:
            return candidate
    return ""


def _read(filename: str, parse, default):
    try:
        if remote():
            fs = _fs()
            if fs is None:
                return default
            with fs.open(_uri(filename), "rb") as handle:
                return parse(handle)

        path = config.TABLES_DIR / filename
        if not path.exists():
            return default
        with path.open("rb") as handle:
            return parse(handle)
    except Exception:
        return default


def tables() -> list[str]:
    """Names of every available table, without the extension."""
    return _stems(DATA_SUFFIXES)


def figures() -> list[str]:
    """Names of every available figure, without the extension."""
    return _stems((".png",))


def _stems(suffixes: tuple[str, ...]) -> list[str]:
    return sorted(
        {Path(name).stem for name in _entries() if Path(name).suffix.lower() in suffixes}
    )


@_cache(ttl=60, max_entries=1)
def _entries() -> list[str]:
    """Every filename where the tables live, local folder or bucket."""
    try:
        if remote():
            fs = _fs()
            if fs is None:
                return []
            found = fs.ls(_uri(""), detail=False)
        else:
            if not config.TABLES_DIR.is_dir():
                return []
            found = [str(path) for path in config.TABLES_DIR.iterdir()]
    except Exception:
        return []

    return sorted(Path(str(item)).name for item in found)


# ── Writing ───────────────────────────────────────────────────────────────────

def save(name: str, df: pd.DataFrame) -> Path:
    """Write a table locally in FILE_FORMAT, and upload it when GCS_UPLOAD is on."""
    suffix = data_suffix()
    path = _write(f"{name}{suffix}", _frame_bytes(df, suffix))
    print(f"[storage] {path.name}: {len(df):,} rows")
    return path


def save_figure(name: str, fig, dpi: int = 150) -> Path:
    """Write a Matplotlib figure as PNG, and upload it when GCS_UPLOAD is on."""
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight")
    path = _write(f"{name}.png", buffer.getvalue())
    print(f"[storage] {path.name}")
    return path


def _write(filename: str, payload: bytes) -> Path:
    config.TABLES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.TABLES_DIR / filename
    path.write_bytes(payload)

    if config.GCS_UPLOAD:
        if not _bucket():
            raise RuntimeError("GCS_UPLOAD is on but GCS_BUCKET is empty.")
        fs = _fs()
        if fs is None:
            raise RuntimeError(f"GCS_UPLOAD is on but GCS is unreachable for {filename}.")
        destination = _uri(filename)
        fs.put(str(path), destination)
        print(f"[storage] uploaded {destination}")

    return path
