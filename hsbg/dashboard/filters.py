"""Sidebar filter state -> metrics.LogFilter. Pure functions (testable without Streamlit)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .. import metrics

PRESETS = ("Today", "Last 7 days", "Last 30 days", "All time", "Custom")


@dataclass(frozen=True)
class FilterState:
    preset: str = "All time"
    custom_from: date | None = None
    custom_to: date | None = None
    heroes: tuple[str, ...] = ()
    include_incomplete: bool = False


def date_range(
    state: FilterState, today: date | None = None
) -> tuple[datetime | None, datetime | None]:
    today = today or date.today()
    if state.preset == "Today":
        return datetime.combine(today, time.min), datetime.combine(today, time.max)
    if state.preset == "Last 7 days":
        return datetime.combine(today - timedelta(days=6), time.min), None
    if state.preset == "Last 30 days":
        return datetime.combine(today - timedelta(days=29), time.min), None
    if state.preset == "Custom":
        since = datetime.combine(state.custom_from, time.min) if state.custom_from else None
        until = datetime.combine(state.custom_to, time.max) if state.custom_to else None
        return since, until
    return None, None


def to_log_filter(state: FilterState, today: date | None = None) -> metrics.LogFilter:
    since, until = date_range(state, today)
    return metrics.LogFilter(
        since=since,
        until=until,
        heroes=set(state.heroes),
        include_incomplete=state.include_incomplete,
    )
