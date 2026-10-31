from __future__ import annotations

import streamlit as st

from ... import charts, metrics
from ..components import GAME_COLUMN_LABELS, kpi_row
from ..data import DashboardContext


def render(ctx: DashboardContext) -> None:
    st.title("概要")
    t = ctx.filtered
    if t.games.empty:
        st.info("フィルタに一致するゲームがありません。")
        return
    kpi_row(metrics.kpis(t))
    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.mmr_line(metrics.mmr_progression(t)), width="stretch")
    c2.plotly_chart(
        charts.rolling_placement_line(metrics.rolling_avg_placement(t)), width="stretch"
    )
    c3, c4 = st.columns(2)
    c3.plotly_chart(charts.placement_histogram(metrics.placement_distribution(t)), width="stretch")
    with c4:
        st.subheader("直近のゲーム")
        recent = metrics.recent_games(t, 10)[
            ["started_at", "hero_name", "placement", "mmr_delta", "final_tier", "total_turns"]
        ]
        st.dataframe(
            recent,
            hide_index=True,
            width="stretch",
            column_config={
                "started_at": st.column_config.DatetimeColumn("開始", format="MM-DD HH:mm"),
                **GAME_COLUMN_LABELS,
            },
        )
