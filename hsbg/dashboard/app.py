"""Streamlit entry point. Run via `hsbg serve` (or `streamlit run hsbg/dashboard/app.py`)."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import streamlit as st

from hsbg import cards, config, loader
from hsbg.dashboard import data
from hsbg.dashboard.filters import PRESETS, FilterState
from hsbg.dashboard.views import (
    game_detail,
    games,
    heroes,
    my_lenses,
    opponents,
    overview,
    trends,
    tribes,
)

PRESET_LABELS = {
    "Today": "今日",
    "Last 7 days": "直近 7 日",
    "Last 30 days": "直近 30 日",
    "All time": "全期間",
    "Custom": "日付を指定",
}


def _root() -> Path:
    return Path(os.environ.get("HSBG_LOGS") or loader.default_log_dir())


def _sidebar(root: Path, hero_options: dict[str, str]) -> FilterState:
    with st.sidebar:
        st.markdown("### フィルタ")
        preset = st.selectbox(
            "期間",
            PRESETS,
            index=PRESETS.index("All time"),
            format_func=lambda p: PRESET_LABELS.get(p, p),
            key="f_preset",
        )
        custom_from = custom_to = None
        if preset == "Custom":
            c1, c2 = st.columns(2)
            custom_from = c1.date_input("開始日", value=date.today().replace(day=1), key="f_from")
            custom_to = c2.date_input("終了日", value=date.today(), key="f_to")
        heroes = st.multiselect(
            "ヒーロー",
            options=list(hero_options),
            format_func=lambda k: hero_options[k],
            placeholder="すべて",
            key="f_heroes",
        )
        include_incomplete = st.checkbox("未完了のゲームを含める", value=False, key="f_incomplete")
        st.divider()
        if st.button("ログを再読み込み", width="stretch"):
            data.refresh()
            data.load_game.clear()
            st.rerun()
        # st.caption(f"フォルダ: {root}")
    return FilterState(preset, custom_from, custom_to, tuple(heroes), include_incomplete)


def main() -> None:
    st.set_page_config(page_title="HSBG ダッシュボード", page_icon="🃏", layout="wide")
    root = _root()

    # first pass with an empty filter just to know the hero list, then the real one
    base = data.load_context(root, FilterState())
    all_games = base.tables.games
    hero_options = (
        all_games.dropna(subset=["hero_base_card_id"])
        .groupby("hero_base_card_id")["hero_name"]
        .first()
        .sort_values()
        .to_dict()
    )
    state = _sidebar(root, hero_options)
    ctx = data.load_context(root, state)
    st.session_state["ctx"] = ctx

    with st.sidebar:
        st.caption(
            f"{len(ctx.filtered.games)} / {len(ctx.tables.games)} ゲームを表示"
            + ("（parquet キャッシュ）" if ctx.from_cache else "")
        )
        if ctx.warnings:
            with st.expander(f"読めなかったログ: {len(ctx.warnings)} 件"):
                for w in ctx.warnings:
                    st.caption(w)
        names = cards.default()
        if not names.available:
            st.caption("カード名: 英語（HDT の CardDefs が見つかりません）")

    pages = {
        "overview": st.Page(
            lambda: overview.render(ctx), title="概要", url_path="overview", default=True
        ),
        "heroes": st.Page(lambda: heroes.render(ctx), title="ヒーロー", url_path="heroes"),
        "tribes": st.Page(lambda: tribes.render(ctx), title="種族", url_path="tribes"),
        "trends": st.Page(lambda: trends.render(ctx), title="プレイ傾向", url_path="trends"),
        "lenses": st.Page(
            lambda: my_lenses.render(ctx, config.load().lenses_dir),
            title="マイ分析",
            url_path="lenses",
        ),
        "opponents": st.Page(lambda: opponents.render(ctx), title="対戦相手", url_path="opponents"),
        "games": st.Page(lambda: games.render(ctx), title="ゲーム一覧", url_path="games"),
        "detail": st.Page(lambda: game_detail.render(ctx), title="ゲーム詳細", url_path="game"),
    }
    st.session_state["pages"] = pages
    nav = st.navigation(list(pages.values()))
    nav.run()


main()
