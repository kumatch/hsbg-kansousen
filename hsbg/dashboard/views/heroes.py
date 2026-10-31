from __future__ import annotations

import streamlit as st

from ... import charts, metrics
from ..components import GAME_COLUMN_LABELS, rate_as_percent, translate_columns
from ..data import DashboardContext


def render(ctx: DashboardContext) -> None:
    st.title("ヒーロー")
    t = ctx.filtered
    stats = metrics.hero_stats(t)
    if stats.empty:
        st.info("フィルタに一致するゲームがありません。")
        return
    st.caption(
        "行を選ぶとそのヒーローの内訳を表示します。スキン違いは同じヒーローとして集計しています。"
        "3 ゲーム未満の行は参考程度です。"
    )
    table = rate_as_percent(stats, ["top4_rate", "first_rate"])
    event = st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "hero_base_card_id": None,
            "hero_name": "ヒーロー",
            "games": "ゲーム数",
            "avg_placement": st.column_config.NumberColumn("平均順位", format="%.2f"),
            "top4_rate": st.column_config.NumberColumn("Top 4 率", format="%.0f%%"),
            "first_rate": st.column_config.NumberColumn("1 位率", format="%.0f%%"),
            "mmr_change": "MMR 増減",
        },
    )
    rows = event.selection.rows if event and event.selection else []
    if not rows:
        st.plotly_chart(charts.hero_bar(stats), width="stretch")
        return

    hero_id = stats.iloc[rows[0]]["hero_base_card_id"]
    hero_name = stats.iloc[rows[0]]["hero_name"]
    sub = t.subset(t.games[t.games["hero_base_card_id"] == hero_id]["game_id"])
    st.subheader(f"{hero_name} — {len(sub.games)} ゲーム")
    c1, c2 = st.columns(2)
    c1.plotly_chart(
        charts.placement_histogram(metrics.placement_distribution(sub)), width="stretch"
    )
    c2.plotly_chart(charts.tier_reach_box(metrics.tier_reach_turns(sub)), width="stretch")
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**最終盤面の主な種族**")
        st.dataframe(
            translate_columns(metrics.minion_type_stats(sub)),
            hide_index=True,
            width="stretch",
            column_config={
                "minion_type": "種族",
                "games": "ゲーム数",
                "avg_placement": st.column_config.NumberColumn("平均順位", format="%.2f"),
                "top4_rate": None,
                "first_rate": None,
                "avg_share": None,
                "median_commit_turn": st.column_config.NumberColumn(
                    "主軸を固めたターン", format="%.1f"
                ),
                "avg_pivots": st.column_config.NumberColumn("方針転換", format="%.1f"),
                "mmr_change": None,
            },
        )
    with c4:
        st.markdown("**ゲーム**")
        games = sub.games.sort_values("started_at", ascending=False)[
            [
                "started_at",
                "hero_skin_name",
                "placement",
                "mmr_delta",
                "final_tier",
                "total_turns",
                "hero_rerolled",
            ]
        ]
        st.dataframe(
            games,
            hide_index=True,
            width="stretch",
            column_config={
                "started_at": st.column_config.DatetimeColumn("開始", format="MM-DD HH:mm"),
                "hero_skin_name": "スキン",
                **GAME_COLUMN_LABELS,
            },
        )
