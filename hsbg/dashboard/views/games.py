from __future__ import annotations

import streamlit as st

from ..components import GAME_COLUMN_LABELS, translate_columns
from ..data import DashboardContext

COLUMNS = [
    "started_at",
    "hero_name",
    "placement",
    "mmr_before",
    "mmr_delta",
    "final_tier",
    "total_turns",
    "duration_sec",
    "status",
    "game_id",
]


def render(ctx: DashboardContext) -> None:
    st.title("ゲーム一覧")
    g = ctx.filtered.games
    if g.empty:
        st.info("フィルタに一致するゲームがありません。")
        return
    st.caption("行を選ぶとゲーム詳細を開きます。")
    table = g.sort_values("started_at", ascending=False)[COLUMNS].reset_index(drop=True)
    table["duration_min"] = (table["duration_sec"] / 60).round(0)
    event = st.dataframe(
        translate_columns(table.drop(columns=["duration_sec"])),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "started_at": st.column_config.DatetimeColumn("開始", format="YYYY-MM-DD HH:mm"),
            **GAME_COLUMN_LABELS,
            "game_id": None,
        },
    )
    rows = event.selection.rows if event and event.selection else []
    if rows:
        st.session_state["selected_game_id"] = table.iloc[rows[0]]["game_id"]
        st.switch_page(st.session_state["pages"]["detail"])
