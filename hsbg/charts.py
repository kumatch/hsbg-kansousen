"""Every plotly figure lives here. report.py and the dashboard only call these.

Labels are Japanese (the user's language); the DataFrame columns stay English.

Each function takes the DataFrame produced by the matching metrics.py function.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from . import labels

TOP4_COLOR = "#2a9d8f"
BOTTOM4_COLOR = "#e76f51"
NEUTRAL = "#457b9d"


def _empty(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=title, annotations=[{"text": "データなし", "showarrow": False}])
    return fig


def placement_histogram(dist: pd.DataFrame) -> go.Figure:
    if dist.empty or dist["count"].sum() == 0:
        return _empty("順位分布")
    colors = [TOP4_COLOR if p <= 4 else BOTTOM4_COLOR for p in dist["placement"]]
    fig = go.Figure(
        go.Bar(x=dist["placement"], y=dist["count"], marker_color=colors, text=dist["count"])
    )
    fig.update_layout(
        title="順位分布",
        xaxis_title="順位",
        yaxis_title="ゲーム数",
        xaxis={"dtick": 1},
    )
    return fig


def mmr_line(prog: pd.DataFrame) -> go.Figure:
    if prog.empty:
        return _empty("MMR")
    hover = [
        f"{r.started_at:%Y-%m-%d %H:%M}<br>{r.hero_name}<br>#{r.placement}"
        for r in prog.itertuples()
    ]
    fig = go.Figure(
        go.Scatter(
            x=prog["game_no"],
            y=prog["mmr_after"],
            mode="lines+markers",
            text=hover,
            hoverinfo="text+y",
            line={"color": NEUTRAL},
        )
    )
    fig.update_layout(title="ゲームごとの MMR", xaxis_title="ゲーム番号", yaxis_title="MMR")
    return fig


def rolling_placement_line(df: pd.DataFrame, window: int = 20) -> go.Figure:
    if df.empty:
        return _empty("順位の移動平均")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["game_no"],
            y=df["placement"],
            mode="markers",
            name="順位",
            marker={"color": "#adb5bd"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["game_no"],
            y=df["rolling_avg"],
            mode="lines",
            name=f"移動平均（直近 {window} ゲーム）",
            line={"color": NEUTRAL, "width": 3},
        )
    )
    fig.update_layout(
        title="ゲームごとの順位と移動平均",
        xaxis_title="ゲーム番号",
        yaxis={"title": "順位", "autorange": "reversed", "dtick": 1},
    )
    return fig


def hero_bar(stats: pd.DataFrame, min_games_solid: int = 3) -> go.Figure:
    if stats.empty:
        return _empty("ヒーロー別 平均順位")
    df = stats.sort_values("avg_placement", ascending=False)
    opacity = [1.0 if n >= min_games_solid else 0.4 for n in df["games"]]
    fig = go.Figure(
        go.Bar(
            x=df["avg_placement"],
            y=df["hero_name"],
            orientation="h",
            text=[f"{a} (n={n})" for a, n in zip(df["avg_placement"], df["games"], strict=True)],
            marker={"color": NEUTRAL, "opacity": opacity},
        )
    )
    fig.update_layout(
        title=f"ヒーロー別 平均順位（薄い色: {min_games_solid} ゲーム未満）",
        xaxis={"title": "平均順位", "range": [0, 8.5], "dtick": 1},
        height=max(300, 28 * len(df) + 120),
    )
    return fig


def tier_reach_box(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty("ティア到達ターン")
    fig = go.Figure()
    for flag, name, color in ((True, "Top 4", TOP4_COLOR), (False, "5〜8 位", BOTTOM4_COLOR)):
        part = df[df["top4"] == flag]
        if part.empty:
            continue
        fig.add_trace(go.Box(x=part["tier"], y=part["turn"], name=name, marker_color=color))
    fig.update_layout(
        title="各酒場ティアに到達したターン",
        boxmode="group",
        xaxis={"title": "酒場ティア", "dtick": 1},
        yaxis_title="ターン",
    )
    return fig


def combat_winrate_line(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty("ターン別 戦闘勝率")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["turn"],
            y=df["win_rate"],
            mode="lines+markers",
            name="勝率",
            text=[f"{w}/{n}" for w, n in zip(df["wins"], df["combats"], strict=True)],
            line={"color": TOP4_COLOR},
        )
    )
    fig.update_layout(
        title="ターン別 戦闘勝率",
        xaxis={"title": "ターン", "dtick": 1},
        yaxis={"title": "勝率", "range": [0, 1], "tickformat": ".0%"},
    )
    return fig


def health_band(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty("ターン別 体力（HP + アーマー）")
    fig = go.Figure()
    for group, color in (("top4", TOP4_COLOR), ("bottom4", BOTTOM4_COLOR)):
        part = df[df["group"] == group].sort_values("turn")
        if part.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=part["turn"],
                y=part["q3"],
                mode="lines",
                line={"width": 0},
                showlegend=False,
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=part["turn"],
                y=part["q1"],
                mode="lines",
                line={"width": 0},
                fill="tonexty",
                fillcolor=color + "33",
                showlegend=False,
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=part["turn"],
                y=part["median"],
                mode="lines+markers",
                name=("Top 4" if group == "top4" else "5〜8 位") + " の中央値",
                line={"color": color},
            )
        )
    fig.update_layout(
        title="ショップ開始時の体力（HP + アーマー）",
        xaxis={"title": "ターン", "dtick": 1},
        yaxis_title="HP + アーマー",
    )
    return fig


def reroll_scatter(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty("リロール数と順位")
    fig = go.Figure(
        go.Scatter(
            x=df["rerolls"],
            y=df["placement"],
            mode="markers",
            text=df["hero_name"],
            marker={"color": NEUTRAL, "size": 10},
        )
    )
    fig.update_layout(
        title="1 ゲームのリロール合計と順位",
        xaxis_title="リロール回数",
        yaxis={"title": "順位", "autorange": "reversed", "dtick": 1},
    )
    return fig


def game_hp_tier_line(turns: pd.DataFrame) -> go.Figure:
    """Single game: HP+armor and tavern tier per turn (dashboard game detail)."""
    if turns.empty:
        return _empty("ゲーム")
    t = turns.sort_values("turn")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=t["turn"],
            y=t["health"].fillna(0) + t["armor"].fillna(0),
            mode="lines+markers",
            name="HP + アーマー",
            line={"color": BOTTOM4_COLOR},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t["turn"],
            y=t["tavern_tier"],
            mode="lines+markers",
            name="ティア",
            yaxis="y2",
            line={"color": NEUTRAL, "dash": "dot"},
        )
    )
    fig.update_layout(
        title="HP と酒場ティアの推移",
        xaxis={"title": "ターン", "dtick": 1},
        yaxis={"title": "HP + アーマー"},
        yaxis2={"title": "ティア", "overlaying": "y", "side": "right", "range": [0, 7], "dtick": 1},
    )
    return fig


# ---------------------------------------------------------------- minion types (tribes)
#
# Fixed categorical palette (dataviz skill's validated 8-slot order, then three extras) so a type
# keeps its colour whatever the filter shows. Marker symbols are the secondary encoding.
TYPE_ORDER = [
    "aberration",
    "undead",
    "mechanical",
    "beast",
    "dragon",
    "demon",
    "elemental",
    "murloc",
    "pirate",
    "quilboar",
    "naga",
]
_TYPE_HEX = [
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#4a3aa7",
    "#e34948",
    "#7a5c3a",
    "#6c757d",
    "#0d366b",
]
_TYPE_SYMBOLS = [
    "square",
    "circle",
    "diamond",
    "triangle-up",
    "cross",
    "x",
    "star",
    "hexagon",
    "pentagon",
    "triangle-down",
    "diamond-wide",
]
TYPE_COLORS = dict(zip(TYPE_ORDER, _TYPE_HEX, strict=True))
TYPE_SYMBOLS = dict(zip(TYPE_ORDER, _TYPE_SYMBOLS, strict=True))
OTHER_COLOR = "#adb5bd"
_BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def type_color(token: str) -> str:
    return TYPE_COLORS.get(token, OTHER_COLOR)


def _type_label(token: object) -> str:
    return labels.minion_type(token) if isinstance(token, str) else "-"


def type_placement_bar(stats: pd.DataFrame, min_games_solid: int = 3) -> go.Figure:
    """Average placement by final main type (metrics.minion_type_stats)."""
    if stats.empty:
        return _empty("最終盤面の主軸種族別 平均順位")
    df = stats.sort_values("avg_placement", ascending=False)
    fig = go.Figure(
        go.Bar(
            x=df["avg_placement"],
            y=[_type_label(t) for t in df["minion_type"]],
            orientation="h",
            text=[f"{a} (n={n})" for a, n in zip(df["avg_placement"], df["games"], strict=True)],
            marker={
                "color": [type_color(t) for t in df["minion_type"]],
                "opacity": [1.0 if n >= min_games_solid else 0.4 for n in df["games"]],
            },
            hovertemplate="%{y}<br>平均順位 %{x}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"最終盤面の主軸種族別 平均順位（薄い色: {min_games_solid} ゲーム未満）",
        xaxis={"title": "平均順位", "range": [0, 8.5], "dtick": 1},
        height=max(300, 28 * len(df) + 120),
    )
    return fig


def type_offered_vs_played_bar(df: pd.DataFrame) -> go.Figure:
    """Placement when a type was offered vs when it was my final main type
    (metrics.type_availability_stats)."""
    if df.empty:
        return _empty("種族の出現時と使用時の平均順位")
    d = df.sort_values("offered_games", ascending=False)
    names = [_type_label(t) for t in d["minion_type"]]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=names,
            y=d["offered_avg_placement"],
            name="出現したゲーム",
            marker_color=OTHER_COLOR,
            customdata=d["offered_games"],
            hovertemplate="%{x}<br>出現 %{customdata} ゲーム · 平均順位 %{y}<extra></extra>",
        )
    )
    played = d.dropna(subset=["played_avg_placement"])
    fig.add_trace(
        go.Bar(
            x=[_type_label(t) for t in played["minion_type"]],
            y=played["played_avg_placement"],
            name="主軸にしたゲーム",
            marker_color=NEUTRAL,
            customdata=played["played_games"],
            hovertemplate="%{x}<br>主軸 %{customdata} ゲーム · 平均順位 %{y}<extra></extra>",
        )
    )
    fig.update_layout(
        title="種族ごとの平均順位: 出現したとき vs 主軸にしたとき",
        barmode="group",
        bargap=0.3,
        yaxis={"title": "平均順位（低いほど良い）", "range": [0, 8.5], "dtick": 1},
        legend={"orientation": "h", "y": 1.12},
    )
    return fig


def type_timeline_chart(df: pd.DataFrame) -> go.Figure:
    """Main type per turn for every game (metrics.type_timeline): one row per game."""
    d = df.dropna(subset=["minion_type"])
    if d.empty:
        return _empty("ゲーム内の主軸種族の推移")
    games = (
        d[["game_id", "started_at", "hero_name", "placement"]]
        .drop_duplicates("game_id")
        .sort_values("started_at")
    )
    label_by_id = {
        r.game_id: f"{r.started_at:%m-%d %H:%M} {r.hero_name} #{int(r.placement)}"
        if r.placement == r.placement
        else f"{r.started_at:%m-%d %H:%M} {r.hero_name}"
        for r in games.itertuples()
    }
    fig = go.Figure()
    present = [t for t in TYPE_ORDER if t in set(d["minion_type"])] + sorted(
        set(d["minion_type"]) - set(TYPE_ORDER)
    )
    for token in present:
        part = d[d["minion_type"] == token]
        fig.add_trace(
            go.Scatter(
                x=part["turn"],
                y=[label_by_id[g] for g in part["game_id"]],
                mode="markers",
                name=_type_label(token),
                marker={
                    "symbol": TYPE_SYMBOLS.get(token, "circle"),
                    "size": 14,
                    "color": type_color(token),
                    "line": {"width": 1, "color": "#ffffff"},
                },
                customdata=list(zip(part["n"], part["share"], strict=True)),
                hovertemplate=(
                    "%{y}<br>T%{x}: " + _type_label(token) + " %{customdata[0]} 体"
                    "（%{customdata[1]:.0%}）<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        title="ゲーム内の主軸種族の推移（各ターンのショップ終了時の盤面）",
        xaxis={"title": "ターン", "dtick": 1},
        yaxis={"categoryorder": "array", "categoryarray": list(label_by_id.values())},
        height=max(320, 26 * len(label_by_id) + 160),
        legend={"orientation": "h", "y": -0.15},
    )
    return fig


def type_phase_scatter(df: pd.DataFrame, x: str = "commit_turn") -> go.Figure:
    """Placement against commit turn or pivots, one point per game (metrics.type_phases)."""
    titles = {
        "commit_turn": ("主軸を固めたターンと順位", "主軸を固めたターン"),
        "pivots": ("方針転換の回数と順位", "方針転換（T4 以降の主軸の入れ替わり）"),
    }
    title, xlabel = titles.get(x, (x, x))
    d = df.dropna(subset=[x, "placement", "final_type"])
    if d.empty:
        return _empty(title)
    fig = go.Figure()
    present = [t for t in TYPE_ORDER if t in set(d["final_type"])] + sorted(
        set(d["final_type"]) - set(TYPE_ORDER)
    )
    for token in present:
        part = d[d["final_type"] == token]
        fig.add_trace(
            go.Scatter(
                x=part[x],
                y=part["placement"],
                mode="markers",
                name=_type_label(token),
                text=[
                    f"{h} ({s:%m-%d})"
                    for h, s in zip(part["hero_name"], part["started_at"], strict=True)
                ],
                marker={
                    "symbol": TYPE_SYMBOLS.get(token, "circle"),
                    "size": 12,
                    "color": type_color(token),
                    "line": {"width": 1, "color": "#ffffff"},
                },
                hovertemplate="%{text}<br>" + xlabel + " %{x} · 順位 %{y}<extra></extra>",
            )
        )
    fig.update_layout(
        title=title,
        xaxis={"title": xlabel, "dtick": 1},
        yaxis={"title": "順位", "autorange": "reversed", "dtick": 1},
        legend={"title": "最終の主軸"},
    )
    return fig


def type_matchup_heatmap(df: pd.DataFrame) -> go.Figure:
    """Win rate of my main type (rows) vs the opponent's main type (columns)
    (metrics.type_matchups)."""
    if df.empty:
        return _empty("種族の相性（戦闘勝率）")
    rows = [t for t in TYPE_ORDER if t in set(df["my_type"])] + sorted(
        set(df["my_type"]) - set(TYPE_ORDER)
    )
    cols = [t for t in TYPE_ORDER if t in set(df["opp_type"])] + sorted(
        set(df["opp_type"]) - set(TYPE_ORDER)
    )
    rate = df.pivot(index="my_type", columns="opp_type", values="win_rate").reindex(
        index=rows, columns=cols
    )
    wins = df.pivot(index="my_type", columns="opp_type", values="wins").reindex(
        index=rows, columns=cols
    )
    n = df.pivot(index="my_type", columns="opp_type", values="combats").reindex(
        index=rows, columns=cols
    )
    text = [
        [
            "" if n.iat[i, j] != n.iat[i, j] else f"{int(wins.iat[i, j])}/{int(n.iat[i, j])}"
            for j in range(len(cols))
        ]
        for i in range(len(rows))
    ]
    fig = go.Figure(
        go.Heatmap(
            z=rate.values,
            x=[_type_label(c) for c in cols],
            y=[_type_label(r) for r in rows],
            text=text,
            texttemplate="%{text}",
            colorscale=[[i / (len(_BLUES) - 1), c] for i, c in enumerate(_BLUES)],
            zmin=0,
            zmax=1,
            xgap=2,
            ygap=2,
            colorbar={"title": "勝率", "tickformat": ".0%"},
            hovertemplate="自分 %{y} vs 相手 %{x}<br>勝率 %{z:.0%}（%{text}）<extra></extra>",
        )
    )
    fig.update_layout(
        title="種族の相性: 自分の主軸 × 相手の主軸 の戦闘勝率（セル: 勝ち/戦闘数）",
        xaxis={"title": "相手の主軸種族", "side": "bottom"},
        yaxis={"title": "自分の主軸種族", "autorange": "reversed"},
        height=max(320, 40 * len(rows) + 160),
    )
    return fig


# ---------------------------------------------------------------- deity (神祇)
#
# Me vs the combat opponent keep fixed hues (first two slots of the validated type palette); the
# line style is the secondary encoding (solid = Deity, dotted = board total). One y-axis: all four
# series are the same measure (attack + health).
DEITY_ME_COLOR = _TYPE_HEX[0]
DEITY_OPP_COLOR = _TYPE_HEX[1]


def deity_growth_line(df: pd.DataFrame, log_y: bool = False) -> go.Figure:
    """Single game: my Deity vs my board total, and the combat opponent's (metrics.deity_by_turn).

    Board totals are solid (always present); Deities are dotted (absent in many games).
    Filled circle = the Deity awakened in that combat, star = awakened golden, hollow = it did not.
    Without Deity data (no aberration in the lobby) only the two board totals are drawn.
    """
    has_deity = not df.empty and df["deity_stats"].notna().any()
    title = (
        "盤面・神祇ステータス（攻撃力 + 体力）" if has_deity else "盤面ステータス（攻撃力 + 体力）"
    )
    if df.empty:
        return _empty(title)
    fig = go.Figure()

    def awakened_symbols(col: str) -> list[str]:
        golden = df[col.replace("_awakened", "_golden")]
        return [
            ("star" if g is True else "circle") if v is True else "circle-open"
            for v, g in zip(df[col], golden, strict=True)
        ]

    def hover(prefix: str, a: str, h: str, aa: str, ha: str, aw: str) -> list[str]:
        out = []
        for r in df.itertuples():
            if pd.isna(getattr(r, a)):
                out.append("")
                continue
            after = (
                f" → 戦闘後 {int(getattr(r, aa))}/{int(getattr(r, ha))}"
                if not pd.isna(getattr(r, aa))
                else ""
            )
            woke = {True: "目覚めた", False: "目覚めず"}.get(getattr(r, aw), "不明")
            if getattr(r, aw.replace("_awakened", "_golden")) is True:
                woke += "・金色"
            out.append(f"{prefix} {int(getattr(r, a))}/{int(getattr(r, h))}{after}（{woke}）")
        return out

    if has_deity:
        fig.add_trace(
            go.Scatter(
                x=df["turn"],
                y=df["deity_stats"],
                mode="lines+markers",
                name="自分の神祇（戦闘開始時）",
                line={"color": DEITY_ME_COLOR, "width": 2, "dash": "dot"},
                marker={
                    "size": 9,
                    "symbol": awakened_symbols("deity_awakened"),
                    "line": {"width": 2},
                },
                text=hover(
                    "自分の神祇",
                    "deity_attack",
                    "deity_health",
                    "deity_attack_after",
                    "deity_health_after",
                    "deity_awakened",
                ),
                hovertemplate="%{text}<extra></extra>",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=df["turn"],
            y=df["board_stats"],
            mode="lines",
            name="自分の盤面合計",
            line={"color": DEITY_ME_COLOR, "width": 2},
            hovertemplate="自分の盤面合計 %{y:,}<extra></extra>",
        )
    )
    if df["opponent_deity_stats"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=df["turn"],
                y=df["opponent_deity_stats"],
                mode="lines+markers",
                name="相手の神祇（戦闘開始時）",
                line={"color": DEITY_OPP_COLOR, "width": 2, "dash": "dot"},
                marker={
                    "size": 9,
                    "symbol": awakened_symbols("opponent_deity_awakened"),
                    "line": {"width": 2},
                },
                text=hover(
                    "相手の神祇",
                    "opponent_deity_attack",
                    "opponent_deity_health",
                    "opponent_deity_attack_after",
                    "opponent_deity_health_after",
                    "opponent_deity_awakened",
                ),
                hovertemplate="%{text}<extra></extra>",
                connectgaps=False,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=df["turn"],
            y=df["opponent_board_stats"],
            mode="lines",
            name="相手の盤面合計",
            line={"color": DEITY_OPP_COLOR, "width": 2},
            hovertemplate="相手の盤面合計 %{y:,}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis={"title": "ターン", "dtick": 1},
        yaxis={
            "title": "攻撃力 + 体力" + ("（対数目盛）" if log_y else ""),
            "type": "log" if log_y else "linear",
            "tickformat": ",",
        },
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.2},
    )
    return fig


# ---------------------------------------------------------------- lenses (workspace lenses/)


def lens_figure(
    df: pd.DataFrame,
    kind: str,
    x: str | None,
    y: str | None,
    color: str | None = None,
    title: str = "",
) -> go.Figure | None:
    """Generic chart for a lens table (hsbg.lens `chart=`): "bar" (x = category, y = value),
    "barh" (the same, horizontal, for long category names) or "line" (x = turn / game number,
    y = value), one series per value of `color` when given.
    "table" -> None (the table alone). Missing columns -> an empty figure that says so."""
    if kind not in ("bar", "barh", "line") or not x or not y:
        return None
    if df.empty:
        return _empty(title)
    missing = [c for c in (x, y, color) if c and c not in df.columns]
    if missing:
        fig = _empty(title)
        fig.update_layout(
            annotations=[{"text": f"列がありません: {', '.join(missing)}", "showarrow": False}]
        )
        return fig
    groups = list(df.groupby(color, sort=False)) if color else [(None, df)]
    fig = go.Figure()
    for i, (name, part) in enumerate(groups):
        series = str(name) if name is not None else y
        hue = _TYPE_HEX[i % len(_TYPE_HEX)] if color else NEUTRAL
        if kind == "bar":
            fig.add_trace(go.Bar(x=part[x], y=part[y], name=series, marker_color=hue))
        elif kind == "barh":
            fig.add_trace(
                go.Bar(x=part[y], y=part[x], name=series, marker_color=hue, orientation="h")
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=part[x], y=part[y], name=series, mode="lines+markers", line={"color": hue}
                )
            )
    fig.update_layout(
        title=title,
        xaxis_title=x,
        yaxis_title=y,
        barmode="group",
        showlegend=bool(color),
        legend={"orientation": "h", "y": -0.2},
    )
    if kind == "bar":
        fig.update_xaxes(type="category")
    elif kind == "barh":
        categories = df[x].nunique()
        fig.update_layout(
            xaxis_title=y,
            yaxis_title=None,
            yaxis={"type": "category", "autorange": "reversed"},
            height=max(320, 60 * categories + 140),
        )
    return fig
