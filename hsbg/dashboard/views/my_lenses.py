from __future__ import annotations

from pathlib import Path

import streamlit as st

from ... import charts, lenses
from ..data import DashboardContext


def render(ctx: DashboardContext, lenses_dir: Path | None) -> None:
    st.title("マイ分析")
    st.caption(
        "ワークスペースの lenses/ にある、あなた自身の分析の筋（レンズ）の表です。"
        "レンズは `hsbg lens new <名前>` で作り、`hsbg lens check` で確かめます。"
    )
    if lenses_dir is None:
        st.info(
            "ワークスペースがありません。`hsbg init <フォルダ>` で作り、そのフォルダから "
            "`hsbg serve` を起動すると、ここにレンズの表が出ます。"
        )
        return
    found = lenses.discover(lenses_dir)
    active = [ln for ln in found if ln.active]
    if not active:
        st.info(f"有効なレンズがありません（{lenses_dir}）。`hsbg lens new <名前>` で作れます。")
        return
    t = ctx.filtered
    if t.games.empty:
        st.info("フィルタに一致するゲームがありません。")
        return
    for ln in active:
        st.header(ln.label)
        if ln.description:
            st.caption(ln.description)
        for w in ln.warnings:
            st.warning(w)
        for r in lenses.run(ln, t):
            st.subheader(r.spec.title or r.spec.label)
            note = r.spec.note or r.spec.description
            if note:
                st.caption(note)
            shown = lenses.shown_table(r)
            if shown.error or shown.df is None:
                st.error(f"{r.spec.name}: {shown.error or r.error}")
                continue
            fig = charts.lens_figure(shown.df, r.spec.chart, shown.x, shown.y, shown.color)
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
            st.dataframe(shown.df, hide_index=True, width="stretch")
    retired = [ln.label for ln in found if not ln.active]
    if retired:
        st.caption("引退したレンズ（表示しない）: " + "、".join(retired))
