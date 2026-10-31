"""One module per page. Each exposes `render(ctx: DashboardContext) -> None`."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from ... import charts, labels, metrics, summarize
from ..components import board_cards, translate_columns
from ..data import DashboardContext, game_path, load_game, raw_json


def _label(row: pd.Series) -> str:
    return f"{row['started_at']:%Y-%m-%d %H:%M}  {row['hero_name']}  {row['placement']} 位"


def _name(ref: dict | None) -> str:
    if not ref:
        return "-"
    return ref.get("name") or ref.get("card_id") or "-"


def _deity_text(d: dict | None) -> str:
    """'3703/3983 → 戦闘後 6187/6467（目覚めた）'. d = turns[].deity or combat.opponent_deity."""
    if not d:
        return "-"
    text = f"{d.get('attack')}/{d.get('health')}"
    if d.get("attack_after_combat") is not None:
        text += f" → 戦闘後 {d['attack_after_combat']}/{d['health_after_combat']}"
    woke = {True: "目覚めた", False: "目覚めず"}.get(d.get("awakened"))
    if woke and d.get("golden"):
        woke += "・金色"
    return text + (f"（{woke}）" if woke else "")


_SELECT_KEY = "game_detail_select"


def _on_select() -> None:
    st.session_state["selected_game_id"] = st.session_state[_SELECT_KEY]


def render(ctx: DashboardContext) -> None:
    st.title("ゲーム詳細")
    games = ctx.tables.games.sort_values("started_at", ascending=False).reset_index(drop=True)
    if games.empty:
        st.info("ゲームが読み込まれていません。")
        return
    ids = games["game_id"].tolist()
    labels_by_id = {gid: _label(games.iloc[i]) for i, gid in enumerate(ids)}
    # "selected_game_id" is the page-independent selection (also set by the games page).
    # The selectbox has a fixed key so it keeps its identity across reruns; passing a changing
    # `index` instead makes Streamlit recreate the widget and drop every other user choice.
    # Widget state is discarded while the page is not shown, so seed it from the persistent
    # value on each run and copy it back in on_change (callbacks run before the script).
    if st.session_state.get("selected_game_id") not in ids:
        st.session_state["selected_game_id"] = ids[0]
    st.session_state[_SELECT_KEY] = st.session_state["selected_game_id"]
    game_id = st.selectbox(
        "ゲーム",
        ids,
        key=_SELECT_KEY,
        format_func=lambda g: labels_by_id[g],
        on_change=_on_select,
    )

    path = game_path(ctx, game_id)
    raw, log = load_game(path) if path else (None, None)
    if log is None or raw is None:
        st.error(f"ログを読めませんでした: {path}")
        return
    g, p, r = log["game"], log["player"], log["result"]
    game_row = games[games["game_id"] == game_id].iloc[0]

    # header
    mmr = f"{r.get('mmr_before')} → {r.get('mmr_after')}"
    if r.get("mmr_delta") is not None:
        mmr += f" ({r['mmr_delta']:+d})"
    cols = st.columns(5)
    cols[0].metric("順位", f"{r.get('placement') or '-'} 位")
    cols[1].metric("MMR", mmr)
    cols[2].metric("ターン数", r.get("total_turns") or "-")
    cols[3].metric("最終ティア", r.get("final_tavern_tier") or "-")
    cols[4].metric("時間", f"{round((g.get('duration_sec') or 0) / 60)} 分")
    hero_line = f"**{game_row['hero_name']}**"
    skin = p["hero"].get("name")
    if skin and skin != game_row["hero_name"]:
        hero_line += f"（スキン: {skin}）"
    parts = [
        hero_line,
        f"ヒーローパワー: {_name(p.get('hero_power'))}",
        f"開始 HP {p.get('starting_health')} + アーマー {p.get('starting_armor')}",
        f"種族: {labels.minion_types(g.get('minion_types'), '、') or '-'}",
    ]
    # Optional per-game modifiers: shown only when the log has one (anomaly = the retired
    # "Anomaly" season mechanic, still recorded by HDT but 0 in current games).
    for label, ref in (("神祇", g.get("global_old_god")), ("異常", g.get("anomaly"))):
        if _name(ref) != "-":
            parts.append(f"{label}: {_name(ref)}")
    st.markdown(" · ".join(parts))
    if p.get("trinkets"):
        st.caption(
            "トリンケット: " + "、".join(f"{_name(t)}（T{t.get('turn')}）" for t in p["trinkets"])
        )
    if log.get("notes"):
        st.warning("プラグインの注記: " + "; ".join(log["notes"]))

    turns_df = ctx.tables.turns[ctx.tables.turns["game_id"] == game_id]
    st.plotly_chart(charts.game_hp_tier_line(turns_df), width="stretch")
    deity_df = metrics.deity_by_turn(ctx.tables, game_id)
    if not deity_df.empty:
        log_y = st.checkbox(
            "グラフを対数目盛にする",
            value=False,
            help="盤面や神祇は終盤に桁違いに伸びるので、序盤の伸び方を見るときは対数目盛が読みやすい",
        )
        st.plotly_chart(charts.deity_growth_line(deity_df, log_y=log_y), width="stretch")
        deity_card = next(
            (t["deity"].get("card_id") for t in log.get("turns") or [] if t.get("deity")), None
        )
        if deity_card:
            st.caption(
                "神祇は盤面にいないが、各戦闘で味方の異形が 4 体（36.6.3 より前の 2026-10-02 以前は 3 体）死ぬと目覚めて参戦する。"
                f"{labels.deity_ability(deity_card)}。"
                "●＝その戦闘で目覚めた、★＝金色で目覚めた（古なる者の仮面。効果が 2 倍）、○＝目覚めなかった。実線は盤面のミニオンの合計。"
            )
        else:
            st.caption(
                "自分の盤面（ショップ終了時）と、その戦闘の相手の盤面のミニオンの合計。"
                "神祇の記録が無いゲーム（ロビーに異形がいない、または 2026-09-25 19:26 より前のログ）なので、神祇の線は出ません。"
            )
    runs = metrics.type_runs(log)
    if runs:
        st.caption(
            "主軸種族の推移: "
            + " → ".join(
                (f"T{a}" if a == b else f"T{a}〜{b}") + f" {labels.minion_type(mt) or '種族なし'}"
                for a, b, mt in runs
            )
        )

    # turn picker
    turns = log.get("turns") or []
    if turns:
        turn_no = st.select_slider(
            "ターン", options=[t["turn"] for t in turns], value=turns[-1]["turn"]
        )
        t = next(x for x in turns if x["turn"] == turn_no)
        c = t.get("combat") or {}
        a = t.get("actions") or {}
        info = st.columns(6)
        info[0].metric("ティア", t.get("tavern_tier") or "-")
        info[1].metric("HP", f"{t.get('health')}" + (f" +{t['armor']}" if t.get("armor") else ""))
        info[2].metric(
            "使ったゴールド / 所持",
            f"{a.get('gold_spent') if a.get('gold_spent') is not None else '-'} / {t.get('gold_available') or '-'}",
        )
        info[3].metric("購入 / 売却", f"{a.get('buys', '-')} / {a.get('sells', '-')}")
        info[4].metric("リロール", a.get("rerolls") if a.get("rerolls") is not None else "-")
        info[5].metric(
            "ティアアップ / HP / 呪文 / 悪夢の発見",
            f"{a.get('tier_ups', '-')} / {a.get('hero_power_uses', '-')} / {a.get('spells_played', '-')}"
            f" / {a.get('dark_gifts') if a.get('dark_gifts') is not None else '-'}",
        )

        st.markdown(f"**自分の盤面（ターン {turn_no} のショップ終了時）**")
        board_cards(t.get("board_end_of_shop"))
        if t.get("deity"):
            d = t["deity"]
            st.markdown(f"**自分の{_name(d)}**: {_deity_text(d)}")
        if c:
            oh = _name(c.get("opponent_hero")) if c.get("opponent_hero") else "?"
            res = labels.result(c.get("result"))
            dmg = ""
            if c.get("damage_dealt"):
                dmg = f"、与ダメージ {c['damage_dealt']}"
            elif c.get("damage_taken"):
                dmg = f"、被ダメージ {c['damage_taken']}"
            bb = c.get("bobs_buddy") or {}
            bbs = (
                f" · Bob's Buddy 勝 {bb['win']:.0%} / 分 {bb['tie']:.0%} / 負 {bb['loss']:.0%}"
                f"（平均ダメージ {bb['avg_damage']:+.1f}）"
                if bb
                else ""
            )
            st.markdown(
                f"**vs {oh}**（HP {c.get('opponent_health')} + アーマー {c.get('opponent_armor') or 0}）"
                f" — **{res}**{dmg}{bbs}"
            )
            board_cards(c.get("opponent_board"), "（相手の盤面は記録されていません）")
            if c.get("opponent_deity"):
                od = c["opponent_deity"]
                st.markdown(f"**相手の{_name(od)}**: {_deity_text(od)}")
        if t.get("hand_end_of_shop"):
            st.caption("手札: " + "、".join(_name(h) for h in t["hand_end_of_shop"]))

    # per-turn table
    st.markdown("**全ターン**")
    table = turns_df[
        [
            "turn",
            "tavern_tier",
            "health",
            "armor",
            "gold_available",
            "gold_spent",
            "buys",
            "sells",
            "rerolls",
            "tier_ups",
            "hero_power_uses",
            "spells_played",
            "dark_gifts",
            "board_size",
            "deity_attack",
            "deity_health",
            "deity_awakened",
            "deity_golden",
        ]
    ]
    if table["deity_attack"].isna().all():  # 神祇の無いシーズン / schema 1.2.0 より前のログ
        table = table.drop(
            columns=["deity_attack", "deity_health", "deity_awakened", "deity_golden"]
        )
    combats = ctx.tables.combats[ctx.tables.combats["game_id"] == game_id][
        ["turn", "opponent_hero_name", "result", "damage_dealt", "damage_taken", "bb_win"]
    ]
    st.dataframe(
        translate_columns(table.merge(combats, on="turn", how="left")),
        hide_index=True,
        width="stretch",
        column_config={
            "turn": "T",
            "tavern_tier": "ティア",
            "health": "HP",
            "armor": "アーマー",
            "gold_available": "所持ゴールド",
            "gold_spent": "使用ゴールド",
            "buys": "購入",
            "sells": "売却",
            "rerolls": "リロール",
            "tier_ups": "ティアアップ",
            "hero_power_uses": "ヒロパ",
            "spells_played": "呪文",
            "dark_gifts": "悪夢の発見",
            "board_size": "盤面数",
            "deity_attack": "神祇 攻撃",
            "deity_health": "神祇 体力",
            "deity_awakened": st.column_config.CheckboxColumn("神祇 覚醒"),
            "deity_golden": st.column_config.CheckboxColumn("神祇 金色"),
            "opponent_hero_name": "相手",
            "result": "結果",
            "damage_dealt": "与ダメ",
            "damage_taken": "被ダメ",
            "bb_win": st.column_config.NumberColumn("BB 勝率", format="%.0f%%"),
        },
    )

    # lobby
    st.markdown("**ロビー**")
    opp = ctx.tables.opponents[ctx.tables.opponents["game_id"] == game_id].sort_values(
        "estimated_placement"
    )[
        [
            "estimated_placement",
            "placement",
            "hero_name",
            "eliminated_turn",
            "final_tavern_tier",
            "final_health",
        ]
    ]
    st.dataframe(
        opp,
        hide_index=True,
        width="stretch",
        column_config={
            "estimated_placement": "推定順位",
            "placement": "順位",
            "hero_name": "ヒーロー",
            "eliminated_turn": "敗退ターン",
            "final_tavern_tier": "最終ティア",
            "final_health": "最終 HP",
        },
    )

    # key moments + summary for AI
    history = metrics.apply_filter(ctx.tables, metrics.LogFilter())
    st.markdown("**注目ポイント**")
    for m in metrics.key_moments(log, history, lang="ja") or ["（なし）"]:
        st.markdown(f"- {m}")

    st.subheader("AI 分析用の要約")
    md = summarize.summarize(log, history)
    c1, c2, c3 = st.columns(3)
    c1.download_button(
        "要約をダウンロード (.md)",
        md,
        file_name=f"{Path(path or 'game').stem}.md",
        mime="text/markdown",
    )
    c2.download_button(
        "元のログをダウンロード (.json)",
        raw_json(raw),
        file_name=Path(path or "game.json").name,
        mime="application/json",
    )
    c3.caption("コピー: 下のブロック右上のコピーアイコンを使ってください。")
    st.code(md, language="markdown")
