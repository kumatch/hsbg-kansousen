"""Data loading for the dashboard: cached on the log folder's signature, refreshable by button."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

from .. import cache, cards, loader, metrics
from ..normalize import Tables
from .filters import FilterState, to_log_filter


@dataclass
class DashboardContext:
    root: Path
    tables: Tables  # everything loaded
    filtered: Tables  # after sidebar filters
    state: FilterState
    warnings: list[str]
    from_cache: bool
    signature: cache.FolderSignature


@st.cache_data(show_spinner="ログを読み込んでいます...")
def _load(root_str: str, signature_key: tuple[int, int, int]) -> tuple[Tables, list[str], bool]:
    data = cache.load_tables(Path(root_str))
    return data.tables, data.warnings, data.from_cache


def load_context(root: Path, state: FilterState) -> DashboardContext:
    signature = cache.folder_signature(root)
    key = (signature.count, signature.newest_mtime_ns, signature.total_bytes)
    tables, warnings, from_cache = _load(str(root), key)
    filtered = metrics.apply_filter(tables, to_log_filter(state))
    return DashboardContext(root, tables, filtered, state, warnings, from_cache, signature)


def refresh() -> None:
    _load.clear()


@st.cache_data(show_spinner=False)
def load_game(path_str: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """(raw JSON, localized copy) of one game. Raw = for download, localized = for display."""
    log, _ = loader.load_log(Path(path_str))
    if log is None:
        return None, None
    return log, cards.default().localize(log)


def game_path(ctx: DashboardContext, game_id: str) -> str | None:
    row = ctx.tables.games[ctx.tables.games["game_id"] == game_id]
    if row.empty:
        return None
    return str(row["path"].iloc[0])


def raw_json(log: dict[str, Any]) -> str:
    return json.dumps({k: v for k, v in log.items() if k != "_path"}, ensure_ascii=False, indent=2)
