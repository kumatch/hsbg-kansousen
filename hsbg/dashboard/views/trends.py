from __future__ import annotations

import streamlit as st

from ... import charts, metrics
from ..data import DashboardContext


def render(ctx: DashboardContext) -> None:
    st.title("プレイ傾向")
    t = ctx.filtered
    if t.games.empty:
        st.info("フィルタに一致するゲームがありません。")
        return
    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.tier_reach_box(metrics.tier_reach_turns(t)), width="stretch")
    c2.plotly_chart(charts.combat_winrate_line(metrics.combat_winrate_by_turn(t)), width="stretch")
    c3, c4 = st.columns(2)
    c3.plotly_chart(charts.health_band(metrics.health_by_turn(t)), width="stretch")
    c4.plotly_chart(charts.reroll_scatter(metrics.reroll_vs_placement(t)), width="stretch")
    med = metrics.tier_reach_median(t)
    if med:
        st.caption(
            "各ティアへの到達ターンの中央値: "
            + "、".join(f"ティア {tier} → T{turn:g}" for tier, turn in sorted(med.items()))
        )
