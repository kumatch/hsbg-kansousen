from __future__ import annotations

import streamlit as st

from ... import metrics
from ..components import translate_columns
from ..data import DashboardContext


def render(ctx: DashboardContext) -> None:
    st.title("対戦相手")
    t = ctx.filtered
    stats = metrics.opponent_hero_stats(t)
    if stats.empty:
        st.info("フィルタに一致する戦闘がありません。")
        return
    st.subheader("相手ヒーロー別の戦闘成績")
    st.dataframe(
        stats,
        hide_index=True,
        width="stretch",
        column_config={
            "opponent_hero_base_card_id": None,
            "opponent_hero_name": "相手ヒーロー",
            "combats": "戦闘数",
            "wins": "勝ち",
            "losses": "負け",
            "ties": "引き分け",
            "win_rate": st.column_config.NumberColumn("勝率", format="%.2f"),
            "avg_damage_taken": st.column_config.NumberColumn("平均被ダメージ", format="%.1f"),
        },
    )
    st.subheader("負けた戦闘の相手盤面の種族")
    st.caption("負けた戦闘で、相手の盤面に最も多かった種族の分布。")
    st.dataframe(
        translate_columns(metrics.losing_opponent_board_types(t)),
        hide_index=True,
        width="stretch",
        column_config={
            "minion_type": "種族",
            "combats_lost": "負けた戦闘数",
            "share": st.column_config.NumberColumn("割合", format="%.2f"),
        },
    )
