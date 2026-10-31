"""Small reusable Streamlit widgets (KPI row, board cards, tables). Labels are Japanese."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from .. import labels
from ..normalize import divine_shields


def kpi_row(k: dict[str, Any]) -> None:
    cols = st.columns(6)
    cols[0].metric("ゲーム数", k["games"])
    cols[1].metric("平均順位", k["avg_placement"] if k["avg_placement"] is not None else "-")
    cols[2].metric("Top 4 率", f"{k['top4_rate']:.0%}" if k["top4_rate"] is not None else "-")
    cols[3].metric("1 位率", f"{k['first_rate']:.0%}" if k["first_rate"] is not None else "-")
    cols[4].metric("MMR 増減", f"{k['mmr_change']:+d}" if k["mmr_change"] is not None else "-")
    cols[5].metric(
        "平均ゲーム時間", f"{k['avg_duration_min']} 分" if k["avg_duration_min"] else "-"
    )


def board_cards(minions: list[dict[str, Any]] | None, empty_text: str = "（盤面なし）") -> None:
    """Seven columns of bordered cards, left to right."""
    if not minions:
        st.caption(empty_text)
        return
    cols = st.columns(7)
    for i, m in enumerate(minions[:7]):
        with cols[i].container(border=True):
            name = m.get("name") or m.get("card_id") or "?"
            star = " ★" if m.get("golden") else ""
            st.markdown(f"**{name}{star}**")
            st.markdown(f"### {m.get('attack')} / {m.get('health')}")
            tier = f"ティア {m['tier']}" if m.get("tier") else ""
            types = labels.minion_types(m.get("minion_types"))
            st.caption(" · ".join(x for x in (tier, types) if x))
            shields = divine_shields(m)
            kws = [
                labels.keyword(k) + (f"×{shields}" if k == "divine_shield" and shields > 1 else "")
                for k in m.get("keywords") or []
            ]
            if kws:
                st.caption(" ".join(f"`{k}`" for k in kws))


def percent_columns(df: pd.DataFrame, columns: list[str]) -> dict[str, Any]:
    """column_config for st.dataframe: rates as percentages."""
    return {c: st.column_config.NumberColumn(format="%.0f%%") for c in columns}


def rate_as_percent(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in columns:
        if c in out:
            out[c] = (out[c] * 100).round(0)
    return out


def translate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Enum-like columns (result / status / minion_type) -> Japanese words for display."""
    out = df.copy()
    if "result" in out:
        out["result"] = out["result"].map(labels.result)
    if "status" in out:
        out["status"] = out["status"].map(labels.status)
    for c in TYPE_COLUMNS:
        if c in out:
            out[c] = out[c].map(lambda v: labels.minion_type(v) if isinstance(v, str) else "-")
    return out


# DataFrame columns that hold a minion-type token (metrics.py naming).
TYPE_COLUMNS = (
    "minion_type",
    "early_type",
    "mid_type",
    "late_type",
    "final_type",
    "from_type",
    "my_type",
    "opp_type",
)


# Column headers shared by several pages (DataFrame column -> Japanese label).
GAME_COLUMN_LABELS: dict[str, Any] = {
    "hero_name": "ヒーロー",
    "placement": "順位",
    "mmr_before": "MMR",
    "mmr_after": "MMR 後",
    "mmr_delta": "MMR 増減",
    "final_tier": "最終ティア",
    "total_turns": "ターン数",
    "duration_min": "時間（分）",
    "status": "状態",
    "hero_rerolled": "ヒーロー再抽選",
}
