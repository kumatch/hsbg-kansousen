from __future__ import annotations

import streamlit as st

from ... import charts, metrics
from ..components import rate_as_percent, translate_columns
from ..data import DashboardContext

_PLACE = st.column_config.NumberColumn("平均順位", format="%.2f")


def render(ctx: DashboardContext) -> None:
    st.title("種族")
    t = ctx.filtered
    if t.games.empty:
        st.info("フィルタに一致するゲームがありません。")
        return
    st.caption(
        "「主軸種族」= そのターンのショップ終了時の盤面で最も数が多い種族（複数種族のミニオンは両方に数え、"
        "全種族ミニオンは多い方に加算。同数なら合計スタッツが大きい方）。"
        "盤面が記録されていないゲーム（プラグイン v0.2 以前）は集計に入りません。3 ゲーム未満の行は参考程度です。"
    )

    # 1. offered vs played ------------------------------------------------------------------
    st.subheader("出現した種族と成績")
    st.caption(
        "各種族が「出現したゲーム」の成績と、その種族を最終盤面の主軸にした「使ったゲーム」の成績。"
        "使わなかったときより使ったときの方が順位が良い種族は、次に出たら狙う候補です。"
        "毎回出現する種族（今シーズンの異形など）は比較の意味が薄いので出現率で判断してください。"
    )
    avail = metrics.type_availability_stats(t)
    st.dataframe(
        translate_columns(rate_as_percent(avail, ["offered_top4_rate", "pick_rate"])),
        hide_index=True,
        width="stretch",
        column_config={
            "minion_type": "種族",
            "offered_games": "出現したゲーム",
            "offered_avg_placement": st.column_config.NumberColumn(
                "出現時の平均順位", format="%.2f"
            ),
            "offered_top4_rate": st.column_config.NumberColumn(
                "出現時の Top 4 率", format="%.0f%%"
            ),
            "played_games": "主軸にしたゲーム",
            "pick_rate": st.column_config.NumberColumn("採用率", format="%.0f%%"),
            "played_avg_placement": st.column_config.NumberColumn(
                "使ったときの平均順位", format="%.2f"
            ),
            "not_played_avg_placement": st.column_config.NumberColumn(
                "使わなかったときの平均順位", format="%.2f"
            ),
        },
    )
    st.plotly_chart(charts.type_offered_vs_played_bar(avail), width="stretch")

    # 2. final main type vs placement -------------------------------------------------------
    st.subheader("最終盤面の主軸種族と順位")
    st.caption(
        "主軸を固めたターン = その種族が最後まで主軸であり続けた最初のターン。"
        "方針転換 = ターン 4 以降に主軸種族が入れ替わった回数。"
    )
    final = metrics.minion_type_stats(t)
    st.dataframe(
        translate_columns(rate_as_percent(final, ["top4_rate", "first_rate", "avg_share"])),
        hide_index=True,
        width="stretch",
        column_config={
            "minion_type": "種族",
            "games": "ゲーム数",
            "avg_placement": _PLACE,
            "top4_rate": st.column_config.NumberColumn("Top 4 率", format="%.0f%%"),
            "first_rate": st.column_config.NumberColumn("1 位率", format="%.0f%%"),
            "avg_share": st.column_config.NumberColumn("盤面に占める割合", format="%.0f%%"),
            "median_commit_turn": st.column_config.NumberColumn(
                "主軸を固めたターン（中央値）", format="%.1f"
            ),
            "avg_pivots": st.column_config.NumberColumn("方針転換（平均）", format="%.1f"),
            "mmr_change": "MMR 増減",
        },
    )
    st.plotly_chart(charts.type_placement_bar(final), width="stretch")

    # 3. progression inside games ------------------------------------------------------------
    st.subheader("ゲーム内の主軸種族の推移")
    st.plotly_chart(charts.type_timeline_chart(metrics.type_timeline(t)), width="stretch")
    phases = metrics.type_phases(t).sort_values("started_at", ascending=False)
    st.markdown("**ゲームごとの序盤・中盤・終盤の主軸**")
    st.caption(
        "序盤 = T1〜5、中盤 = T6〜10、終盤 = T11 以降。それぞれの最後のターンの主軸種族。"
        "序盤の主軸が最後まで残ったか、途中で乗り換えたかと順位の関係を見ます。"
    )
    st.dataframe(
        translate_columns(
            phases[
                [
                    "started_at",
                    "hero_name",
                    "placement",
                    "early_type",
                    "mid_type",
                    "late_type",
                    "final_type",
                    "commit_turn",
                    "pivots",
                    "total_turns",
                ]
            ]
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "started_at": st.column_config.DatetimeColumn("開始", format="MM-DD HH:mm"),
            "hero_name": "ヒーロー",
            "placement": "順位",
            "early_type": "序盤",
            "mid_type": "中盤",
            "late_type": "終盤",
            "final_type": "最終",
            "commit_turn": "主軸を固めたターン",
            "pivots": "方針転換",
            "total_turns": "ターン数",
        },
    )
    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.type_phase_scatter(phases, "commit_turn"), width="stretch")
    c2.plotly_chart(charts.type_phase_scatter(phases, "pivots"), width="stretch")
    st.markdown("**序盤の主軸 → 最終の主軸**")
    st.dataframe(
        translate_columns(metrics.type_transitions(t, "early")),
        hide_index=True,
        width="stretch",
        column_config={
            "from_type": "序盤の主軸",
            "final_type": "最終の主軸",
            "games": "ゲーム数",
            "avg_placement": _PLACE,
            "changed": "乗り換え",
        },
    )

    # 4. matchups ----------------------------------------------------------------------------
    st.subheader("種族の相性（戦闘）")
    st.caption("自分の主軸種族 × 相手の主軸種族ごとの戦闘勝率。セルの数字は 勝ち/戦闘数。")
    st.plotly_chart(charts.type_matchup_heatmap(metrics.type_matchups(t)), width="stretch")
    st.markdown("**相手の主軸種族別の戦闘成績**")
    opp = metrics.opponent_type_stats(t)
    st.dataframe(
        translate_columns(rate_as_percent(opp, ["win_rate"])),
        hide_index=True,
        width="stretch",
        column_config={
            "opp_type": "相手の主軸種族",
            "combats": "戦闘数",
            "wins": "勝ち",
            "losses": "負け",
            "ties": "引き分け",
            "win_rate": st.column_config.NumberColumn("勝率", format="%.0f%%"),
            "avg_damage_taken": st.column_config.NumberColumn("平均被ダメージ", format="%.1f"),
        },
    )
