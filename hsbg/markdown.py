"""Markdown rendering of metrics tables for `hsbg stats` (AI input). Presentation only."""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import metrics
from .lenses import Lens, TableResult
from .normalize import Tables


def table(df: pd.DataFrame, columns: dict[str, str] | None = None, floatfmt: str = ".2f") -> str:
    """DataFrame -> GitHub Markdown table without extra dependencies."""
    if df.empty:
        return "_no data_"
    cols = columns or {c: c for c in df.columns}

    def cell(v: Any) -> str:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "-"
        if isinstance(v, pd.Timestamp):
            return v.strftime("%Y-%m-%d %H:%M")
        if isinstance(v, bool):
            return "yes" if v else "no"
        if isinstance(v, float):
            return format(v, floatfmt).rstrip("0").rstrip(".") if v != int(v) else str(int(v))
        return str(v).replace("|", "\\|")

    head = "| " + " | ".join(cols.values()) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    rows = ["| " + " | ".join(cell(r[c]) for c in cols) + " |" for _, r in df.iterrows()]
    return "\n".join([head, sep, *rows])


def _pct(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out:
            out[c] = (out[c] * 100).round(0)
    return out


def stats_markdown(tables: Tables, title: str = "HSBG stats") -> str:
    k = metrics.kpis(tables)
    if k["games"] == 0:
        return f"# {title}\n\n_no games in the selected range_\n"
    lines = [
        f"# {title}",
        "",
        f"Period: {k['period_start']:%Y-%m-%d} – {k['period_end']:%Y-%m-%d} · Games: {k['games']} · "
        f"Avg placement: {k['avg_placement']} · Top 4: {k['top4_rate']:.0%} · 1st: {k['first_rate']:.0%} · "
        f"MMR change: {k['mmr_change']:+d}"
        if k["mmr_change"] is not None
        else f"Period: {k['period_start']:%Y-%m-%d} – {k['period_end']:%Y-%m-%d} · Games: {k['games']} · "
        f"Avg placement: {k['avg_placement']} · Top 4: {k['top4_rate']:.0%} · 1st: {k['first_rate']:.0%}",
        "",
        "## Placement distribution",
        table(metrics.placement_distribution(tables), {"placement": "Place", "count": "Games"}),
        "",
        "## Heroes",
        table(
            _pct(metrics.hero_stats(tables), ["top4_rate", "first_rate"]),
            {
                "hero_name": "Hero",
                "games": "n",
                "avg_placement": "Avg place",
                "top4_rate": "Top4 %",
                "first_rate": "1st %",
                "mmr_change": "MMR",
            },
        ),
        "",
        "## Median turn each tier was reached",
        table(
            pd.DataFrame(
                [
                    {"tier": t, "median_turn": m}
                    for t, m in sorted(metrics.tier_reach_median(tables).items())
                ]
            ),
            {"tier": "Tier", "median_turn": "Median turn"},
        ),
        "",
        "## Combat win rate by turn",
        table(
            _pct(metrics.combat_winrate_by_turn(tables), ["win_rate"]),
            {
                "turn": "Turn",
                "combats": "Combats",
                "wins": "W",
                "ties": "T",
                "losses": "L",
                "win_rate": "Win %",
            },
        ),
        "",
        "## Health (HP + armor) at shop start, median by turn",
        table(
            metrics.health_by_turn(tables)
            .pivot(index="turn", columns="group", values="median")
            .reset_index(),
        ),
        "",
        "## Opponent heroes",
        table(
            _pct(metrics.opponent_hero_stats(tables), ["win_rate"]),
            {
                "opponent_hero_name": "Opponent hero",
                "combats": "Combats",
                "wins": "W",
                "losses": "L",
                "ties": "T",
                "win_rate": "Win %",
                "avg_damage_taken": "Avg dmg taken",
            },
        ),
        "",
        "## Rerolls per game vs placement",
        table(
            metrics.reroll_vs_placement(tables).sort_values("placement"),
            {
                "hero_name": "Hero",
                "placement": "Place",
                "rerolls": "Rerolls",
                "rerolls_per_turn": "Per turn",
                "total_turns": "Turns",
            },
        ),
        "",
        "## Minion types offered vs played (played = main type of my final board)",
        table(
            _pct(metrics.type_availability_stats(tables), ["offered_top4_rate", "pick_rate"]),
            {
                "minion_type": "Type",
                "offered_games": "Offered",
                "offered_avg_placement": "Avg place (offered)",
                "offered_top4_rate": "Top4 % (offered)",
                "played_games": "Played",
                "pick_rate": "Pick %",
                "played_avg_placement": "Avg place (played)",
                "not_played_avg_placement": "Avg place (not played)",
            },
        ),
        "",
        "## Final board main type vs placement",
        table(
            _pct(metrics.minion_type_stats(tables), ["top4_rate", "first_rate", "avg_share"]),
            {
                "minion_type": "Type",
                "games": "Games",
                "avg_placement": "Avg place",
                "top4_rate": "Top4 %",
                "first_rate": "1st %",
                "avg_share": "Board share %",
                "median_commit_turn": "Commit turn (median)",
                "avg_pivots": "Pivots (avg)",
                "mmr_change": "MMR",
            },
        ),
        "",
        "## Main type by phase, per game (early T1-5 / mid T6-10 / late T11+; commit = first turn the final type stayed main; pivots = main-type changes from T4)",
        table(
            metrics.type_phases(tables).sort_values("started_at", ascending=False),
            {
                "started_at": "Started",
                "hero_name": "Hero",
                "placement": "Place",
                "early_type": "Early",
                "mid_type": "Mid",
                "late_type": "Late",
                "final_type": "Final",
                "commit_turn": "Commit turn",
                "pivots": "Pivots",
                "total_turns": "Turns",
            },
        ),
        "",
        "## Type matchups (my main type vs opponent main type)",
        table(
            _pct(metrics.type_matchups(tables), ["win_rate"]),
            {
                "my_type": "Mine",
                "opp_type": "Opponent",
                "combats": "Combats",
                "wins": "W",
                "losses": "L",
                "ties": "T",
                "win_rate": "Win %",
            },
        ),
        "",
        "## Opponent main types",
        table(
            _pct(metrics.opponent_type_stats(tables), ["win_rate"]),
            {
                "opp_type": "Opponent type",
                "combats": "Combats",
                "wins": "W",
                "losses": "L",
                "ties": "T",
                "win_rate": "Win %",
                "avg_damage_taken": "Avg dmg taken",
            },
        ),
        "",
        "## Deity (神祇) by game (final = after the last combat; T8 = size at the T8 shop end; awakened = combats it awakened in)",
        table(
            metrics.deity_game_stats(tables).drop(columns=["game_id"]),
            {
                "started_at": "Started",
                "hero_name": "Hero",
                "placement": "Place",
                "deity_name": "Deity",
                "first_awaken_turn": "First awaken T",
                "awakened_combats": "Awakened",
                "golden_awakenings": "Golden",
                "combats": "Combats",
                "deity_stats_t8": "T8 atk+hp",
                "final_deity_attack": "Final atk",
                "final_deity_health": "Final hp",
            },
        ),
        "",
        "## Recent games",
        table(
            metrics.recent_games(tables, 20).drop(columns=["path", "game_id"]),
            {
                "started_at": "Started",
                "hero_name": "Hero",
                "placement": "Place",
                "mmr_before": "MMR",
                "mmr_after": "After",
                "mmr_delta": "Δ",
                "final_tier": "Tier",
                "total_turns": "Turns",
                "duration_sec": "Sec",
                "status": "Status",
            },
        ),
        "",
    ]
    return "\n".join(lines)


def lenses_markdown(items: list[tuple[Lens, list[TableResult]]]) -> str:
    """`## Lens: ...` sections for `hsbg stats` from (Lens, its table results) pairs.
    The AI reads them next to the core tables; the lens's lens.md says what to do with them."""
    out: list[str] = []
    for lens, results in items:
        out += [f"## Lens: {lens.label} (`{lens.name}`)", ""]
        if lens.description:
            out += [lens.description, ""]
        out += [f"Guide for the analysis: `{lens.guide}`", ""]
        for w in lens.warnings:
            out += [f"_warning: {w}_", ""]
        for r in results:
            out += [f"### {r.spec.label}", ""]
            if r.spec.description:
                out += [r.spec.description, ""]
            out += [f"_error: {r.error}_" if r.error else table(r.df), ""]
    return "\n".join(out)
