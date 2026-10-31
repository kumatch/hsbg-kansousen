"""Parquet cache of the normalized tables for large log folders (docs/architecture.md §6.1).

Below `threshold` logs the JSON files are simply re-read. Above it, the tables are stored under
`<root>/.cache/` together with a signature (file count + newest mtime) and rebuilt when it changes.
The raw logs themselves are always re-read lazily by game id (game detail / summarize).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import cards, loader, normalize
from .normalize import Tables

CACHE_DIR = ".cache"
CACHE_FORMAT = 8  # bump when the table columns change (old caches are then rebuilt)
TABLE_NAMES = (
    "games",
    "turns",
    "combats",
    "board_minions",
    "opponents",
    "discovers",
    "hand",
    "shop_offers",
    "lobby",
    "sells",
)
DEFAULT_THRESHOLD = 200


@dataclass(frozen=True)
class FolderSignature:
    count: int
    newest_mtime_ns: int
    total_bytes: int

    def as_dict(self) -> dict[str, int]:
        return {
            "count": self.count,
            "newest_mtime_ns": self.newest_mtime_ns,
            "total_bytes": self.total_bytes,
        }


def folder_signature(root: Path) -> FolderSignature:
    paths = loader.find_logs(root)
    newest = 0
    total = 0
    for p in paths:
        try:
            st = p.stat()
        except OSError:
            continue
        newest = max(newest, st.st_mtime_ns)
        total += st.st_size
    return FolderSignature(len(paths), newest, total)


@dataclass
class LoadedData:
    tables: Tables
    warnings: list[str]
    from_cache: bool
    signature: FolderSignature


def _cache_dir(root: Path) -> Path:
    return root / CACHE_DIR


def _meta(signature: FolderSignature, names: cards.CardNames) -> dict[str, object]:
    return {**signature.as_dict(), "format": CACHE_FORMAT, "cards": names.signature()}


def _read_cache(root: Path, signature: FolderSignature, names: cards.CardNames) -> Tables | None:
    d = _cache_dir(root)
    meta = d / "signature.json"
    if not meta.exists():
        return None
    try:
        if json.loads(meta.read_text("utf-8")) != _meta(signature, names):
            return None
        frames = {name: pd.read_parquet(d / f"{name}.parquet") for name in TABLE_NAMES}
    except Exception:
        return None
    return Tables(**frames)


def _write_cache(
    root: Path, tables: Tables, signature: FolderSignature, names: cards.CardNames
) -> None:
    d = _cache_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    for name in TABLE_NAMES:
        getattr(tables, name).to_parquet(d / f"{name}.parquet", index=False)
    (d / "signature.json").write_text(json.dumps(_meta(signature, names)), encoding="utf-8")


def load_tables(
    root: Path, *, threshold: int = DEFAULT_THRESHOLD, use_cache: bool | None = None
) -> LoadedData:
    """Normalized tables for the folder, using the parquet cache when the folder is large."""
    signature = folder_signature(root)
    names = cards.default()
    cache_enabled = use_cache if use_cache is not None else signature.count >= threshold
    if cache_enabled:
        cached = _read_cache(root, signature, names)
        if cached is not None:
            return LoadedData(cached, [], True, signature)
    result = loader.load_logs(root)
    tables = normalize.normalize(result.logs, names)
    if cache_enabled:
        try:
            _write_cache(root, tables, signature, names)
        except OSError:
            pass
    return LoadedData(tables, [str(w) for w in result.warnings], False, signature)


def clear_cache(root: Path) -> None:
    d = _cache_dir(root)
    if not d.exists():
        return
    for f in d.iterdir():
        if f.is_file():
            f.unlink()
    try:
        os.rmdir(d)
    except OSError:
        pass
