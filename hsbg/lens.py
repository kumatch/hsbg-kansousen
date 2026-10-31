"""Public API for lens code (docs/lenses.md). A lens's `metrics.py` imports only from here; the rest
of hsbg may change without notice. Changes that break lenses raise `LENS_API`.

A lens table is a function that takes the normalized tables (the games of the current filter) and
returns a DataFrame. Mark it with `@lens_table`; `hsbg stats` prints it under `## Lens: ...` and the
dashboard's マイ分析 page shows it, with a chart when `chart` is "bar" or "line":

    from hsbg.lens import Tables, lens_table, early_game_features, compare_groups

    @lens_table("tier4_by_group", "Tier 4 turn: top 4 vs bottom 4", chart="bar",
                x="feature", y="diff")
    def tier4(t: Tables) -> pd.DataFrame:
        return compare_groups(early_game_features(t), {"tier4_turn": "Tier 4 turn"})

Charts are drawn by hsbg (charts.py); a lens never calls plotly itself. `x` is the category / turn
column, `y` the numeric column, `color` an optional column that splits the bars / lines.
The dashboard (マイ分析) can show a table in the player's language while `hsbg stats` (the AI's
input) keeps the DataFrame as returned: `title` / `note` replace `label` / `description` there,
`display` turns the result into what is shown (e.g. map "yes" to "はい", format times, translate
minion types with `minion_type_name`) and `columns` renames columns last. Chart columns (`x`, `y`,
`color`) name the returned columns; the chart is drawn from the shown table, so `display` should
keep numbers as numbers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from . import labels, metrics
from .normalize import Tables

LENS_API = 1
CHART_KINDS = ("table", "bar", "barh", "line")

TableFn = Callable[[Tables], pd.DataFrame]
DisplayFn = Callable[[pd.DataFrame], pd.DataFrame]
_ATTR = "__hsbg_lens_table__"


@dataclass(frozen=True)
class TableSpec:
    name: str
    label: str
    chart: str = "table"
    x: str | None = None
    y: str | None = None
    color: str | None = None
    description: str = ""
    columns: dict[str, str] = field(default_factory=dict)
    title: str = ""  # dashboard heading (default: label)
    note: str = ""  # dashboard caption (default: description)
    display: DisplayFn | None = None


def lens_table(
    name: str,
    label: str,
    *,
    chart: str = "table",
    x: str | None = None,
    y: str | None = None,
    color: str | None = None,
    description: str = "",
    columns: dict[str, str] | None = None,
    title: str = "",
    note: str = "",
    display: DisplayFn | None = None,
) -> Callable[[TableFn], TableFn]:
    """Register a function as a lens table. Raises ValueError for an unknown chart or a chart
    without x / y (the lens then fails to load and `hsbg lens check` reports it)."""
    if chart not in CHART_KINDS:
        raise ValueError(f"chart must be one of {', '.join(CHART_KINDS)}: {chart!r}")
    if chart != "table" and (not x or not y):
        raise ValueError(f"chart={chart!r} needs x and y columns")
    spec = TableSpec(
        name, label, chart, x, y, color, description, dict(columns or {}), title, note, display
    )

    def mark(fn: TableFn) -> TableFn:
        setattr(fn, _ATTR, spec)
        return fn

    return mark


def table_spec(obj: object) -> TableSpec | None:
    """The spec `@lens_table` attached, or None."""
    spec = getattr(obj, _ATTR, None)
    return spec if isinstance(spec, TableSpec) else None


# ---------------------------------------------------------------- helpers for lens code

placement_group = metrics.placement_group
""""top4" for 1st-4th, "bottom4" otherwise."""

early_game_features = metrics.early_game_features
"""One row per game: placement, `group`, tier turns, early boards, HP, rerolls / buys / sells ..."""

compare_groups = metrics.compare_groups
"""Median of each listed column in bottom-4 vs top-4 games (columns: key, feature, bottom4, top4,
diff, games_bottom4, games_top4)."""

card_tiers = metrics.card_tiers
"""Tavern tier per base card id (golden `_G` folded in), from every board in the tables."""

minion_type_name = labels.minion_type
"""Minion-type token (e.g. "MECHANICAL") -> the display name in Japanese (for `display`)."""

result_name = labels.result
""""win" / "loss" / "tie" -> 勝ち / 負け / 引き分け (for `display`)."""

apply_filter = metrics.apply_filter
LogFilter = metrics.LogFilter

__all__ = [
    "CHART_KINDS",
    "LENS_API",
    "LogFilter",
    "TableSpec",
    "Tables",
    "apply_filter",
    "card_tiers",
    "compare_groups",
    "early_game_features",
    "lens_table",
    "minion_type_name",
    "placement_group",
    "result_name",
    "table_spec",
]
