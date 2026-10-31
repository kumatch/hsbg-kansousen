"""Every aggregation lives here. report.py / dashboard / summarize.py only call these functions.

All functions take a `Tables` (already filtered with `apply_filter`) and return DataFrames or dicts.
They must not import plotly or anything from the presentation layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from .normalize import Tables, base_hero_id

TIERS = [2, 3, 4, 5, 6]


@dataclass
class LogFilter:
    since: datetime | None = None
    until: datetime | None = None
    heroes: set[str] = field(default_factory=set)  # base hero card ids
    include_incomplete: bool = False
    last: int | None = None  # keep the N most recent games after other filters
    # MMR at the start of the game (inclusive). Games without an MMR are dropped when either is set.
    # Added 2026-10-10: in 36.6.3 the starting-MMR band moved results more than patches did.
    min_mmr: int | None = None
    max_mmr: int | None = None


def _ts_like(series: pd.Series, value: datetime) -> pd.Timestamp:
    """Make a naive filter date comparable with the tz-aware started_at column."""
    ts = pd.Timestamp(value)
    tz = getattr(series.dt, "tz", None) if len(series) else None
    if ts.tzinfo is None and tz is not None:
        return ts.tz_localize(tz)
    if ts.tzinfo is not None and tz is None:
        return ts.tz_localize(None)
    return ts


def apply_filter(tables: Tables, flt: LogFilter | None) -> Tables:
    flt = flt or LogFilter()
    g = tables.games
    mask = pd.Series(True, index=g.index)
    if not flt.include_incomplete:
        mask &= g["status"] == "complete"
    if flt.since is not None:
        mask &= g["started_at"] >= _ts_like(g["started_at"], flt.since)
    if flt.until is not None:
        mask &= g["started_at"] <= _ts_like(g["started_at"], flt.until)
    if flt.heroes:
        mask &= g["hero_base_card_id"].isin(flt.heroes)
    mmr = pd.to_numeric(g["mmr_before"], errors="coerce")
    if flt.min_mmr is not None:
        mask &= mmr >= flt.min_mmr
    if flt.max_mmr is not None:
        mask &= mmr <= flt.max_mmr
    selected = g[mask].sort_values("started_at", kind="stable")
    if flt.last is not None and flt.last > 0:
        selected = selected.tail(flt.last)
    return tables.subset(selected["game_id"])


# ---------------------------------------------------------------- overview


def kpis(tables: Tables) -> dict[str, Any]:
    g = tables.games
    n = len(g)
    if n == 0:
        return {
            "games": 0,
            "avg_placement": None,
            "top4_rate": None,
            "first_rate": None,
            "mmr_change": None,
            "avg_duration_min": None,
            "period_start": None,
            "period_end": None,
        }
    placement = g["placement"].dropna()
    mmr = g.dropna(subset=["mmr_delta"])
    return {
        "games": n,
        "avg_placement": round(float(placement.mean()), 2) if len(placement) else None,
        "top4_rate": round(float((placement <= 4).mean()), 3) if len(placement) else None,
        "first_rate": round(float((placement == 1).mean()), 3) if len(placement) else None,
        "mmr_change": int(mmr["mmr_delta"].sum()) if len(mmr) else None,
        "avg_duration_min": round(float(g["duration_sec"].dropna().mean()) / 60, 1)
        if g["duration_sec"].notna().any()
        else None,
        "period_start": g["started_at"].min(),
        "period_end": g["started_at"].max(),
    }


def placement_distribution(tables: Tables) -> pd.DataFrame:
    """placement 1..8 -> count (always 8 rows)."""
    counts = tables.games["placement"].dropna().astype(int).value_counts()
    return pd.DataFrame(
        {"placement": list(range(1, 9)), "count": [int(counts.get(p, 0)) for p in range(1, 9)]}
    )


def mmr_progression(tables: Tables) -> pd.DataFrame:
    """One row per game with a known mmr_after, in time order (no interpolation)."""
    g = tables.games.sort_values("started_at")
    out = g[["game_id", "started_at", "hero_name", "placement", "mmr_before", "mmr_after"]].copy()
    out["game_no"] = range(1, len(out) + 1)
    return out[out["mmr_after"].notna()].reset_index(drop=True)


def rolling_avg_placement(tables: Tables, window: int = 20) -> pd.DataFrame:
    g = tables.games.sort_values("started_at")
    out = g[["game_id", "started_at", "placement"]].copy()
    out["game_no"] = range(1, len(out) + 1)
    out["rolling_avg"] = out["placement"].rolling(window, min_periods=1).mean().round(2)
    return out.reset_index(drop=True)


# ---------------------------------------------------------------- heroes


def hero_stats(tables: Tables, min_games: int = 1) -> pd.DataFrame:
    g = tables.games.dropna(subset=["placement"])
    if g.empty:
        return pd.DataFrame(
            columns=[
                "hero_base_card_id",
                "hero_name",
                "games",
                "avg_placement",
                "top4_rate",
                "first_rate",
                "mmr_change",
            ]
        )
    grp = g.groupby("hero_base_card_id")
    out = pd.DataFrame(
        {
            "hero_name": grp["hero_name"].first(),
            "games": grp.size(),
            "avg_placement": grp["placement"].mean().round(2),
            "top4_rate": grp["placement"].apply(lambda s: float((s <= 4).mean())).round(3),
            "first_rate": grp["placement"].apply(lambda s: float((s == 1).mean())).round(3),
            "mmr_change": grp["mmr_delta"].sum(min_count=1),
        }
    ).reset_index()
    out = out[out["games"] >= min_games]
    return out.sort_values(["games", "avg_placement"], ascending=[False, True]).reset_index(
        drop=True
    )


# ---------------------------------------------------------------- tiers


def tier_reach_turns(tables: Tables) -> pd.DataFrame:
    """First turn each tier (2..6) was reached, per game, with the game's top4 flag."""
    t = tables.turns.dropna(subset=["tavern_tier"])
    rows: list[dict] = []
    placements = tables.games.set_index("game_id")["placement"]
    for game_id, grp in t.groupby("game_id"):
        grp = grp.sort_values("turn")
        for tier in TIERS:
            reached = grp[grp["tavern_tier"] >= tier]
            if reached.empty:
                continue
            place = placements.get(game_id)
            rows.append(
                {
                    "game_id": game_id,
                    "tier": tier,
                    "turn": int(reached["turn"].iloc[0]),
                    "top4": bool(place is not None and not pd.isna(place) and place <= 4),
                }
            )
    return pd.DataFrame(rows, columns=["game_id", "tier", "turn", "top4"])


def tier_reach_median(tables: Tables) -> dict[int, float]:
    df = tier_reach_turns(tables)
    if df.empty:
        return {}
    return {int(k): float(v) for k, v in df.groupby("tier")["turn"].median().items()}


# ---------------------------------------------------------------- combat


def combat_winrate_by_turn(tables: Tables) -> pd.DataFrame:
    c = tables.combats.dropna(subset=["result"])
    if c.empty:
        return pd.DataFrame(columns=["turn", "combats", "wins", "ties", "losses", "win_rate"])
    grp = c.groupby("turn")["result"]
    out = pd.DataFrame(
        {
            "combats": grp.size(),
            "wins": grp.apply(lambda s: int((s == "win").sum())),
            "ties": grp.apply(lambda s: int((s == "tie").sum())),
            "losses": grp.apply(lambda s: int((s == "loss").sum())),
        }
    )
    out["win_rate"] = (out["wins"] / out["combats"]).round(3)
    return out.reset_index()


def health_by_turn(tables: Tables) -> pd.DataFrame:
    """Median / quartiles of (health + armor) at shop start, split by top4 vs bottom4."""
    t = tables.turns.dropna(subset=["health"]).copy()
    if t.empty:
        return pd.DataFrame(columns=["group", "turn", "median", "q1", "q3", "games"])
    t["hp"] = t["health"] + t["armor"].fillna(0)
    places = tables.games.set_index("game_id")["placement"]
    t["group"] = t["game_id"].map(lambda gid: "top4" if (places.get(gid) or 9) <= 4 else "bottom4")
    grp = t.groupby(["group", "turn"])["hp"]
    out = pd.DataFrame(
        {
            "median": grp.median(),
            "q1": grp.quantile(0.25),
            "q3": grp.quantile(0.75),
            "games": grp.size(),
        }
    ).reset_index()
    return out


def opponent_hero_stats(tables: Tables, min_combats: int = 1) -> pd.DataFrame:
    c = tables.combats.dropna(subset=["result", "opponent_hero_base_card_id"])
    if c.empty:
        return pd.DataFrame(
            columns=[
                "opponent_hero_base_card_id",
                "opponent_hero_name",
                "combats",
                "wins",
                "losses",
                "ties",
                "win_rate",
                "avg_damage_taken",
            ]
        )
    grp = c.groupby("opponent_hero_base_card_id")
    out = pd.DataFrame(
        {
            "opponent_hero_name": grp["opponent_hero_name"].first(),
            "combats": grp.size(),
            "wins": grp["result"].apply(lambda s: int((s == "win").sum())),
            "losses": grp["result"].apply(lambda s: int((s == "loss").sum())),
            "ties": grp["result"].apply(lambda s: int((s == "tie").sum())),
            "avg_damage_taken": grp["damage_taken"].mean().round(1),
        }
    ).reset_index()
    out["win_rate"] = (out["wins"] / out["combats"]).round(3)
    out = out[out["combats"] >= min_combats]
    return out.sort_values(["combats", "win_rate"], ascending=[False, True]).reset_index(drop=True)


def reroll_vs_placement(tables: Tables) -> pd.DataFrame:
    """Total rerolls per game against placement (Q5)."""
    t = tables.turns.groupby("game_id")["rerolls"].sum(min_count=1).rename("rerolls")
    g = tables.games.set_index("game_id")[["placement", "hero_name", "total_turns"]]
    out = g.join(t, how="inner").dropna(subset=["rerolls", "placement"]).reset_index()
    out["rerolls_per_turn"] = (out["rerolls"] / out["total_turns"]).round(2)
    return out


def minion_type_stats(tables: Tables) -> pd.DataFrame:
    """Placement by the main type of the final player board (Q7), plus how the run was played:
    median turn the final type became (and stayed) the main type, average number of pivots."""
    ph = type_phases(tables).dropna(subset=["placement", "final_type"])
    cols = [
        "minion_type",
        "games",
        "avg_placement",
        "top4_rate",
        "first_rate",
        "avg_share",
        "median_commit_turn",
        "avg_pivots",
        "mmr_change",
    ]
    if ph.empty:
        return pd.DataFrame(columns=cols)
    grp = ph.groupby("final_type")
    out = pd.DataFrame(
        {
            "games": grp.size(),
            "avg_placement": grp["placement"].mean().round(2),
            "top4_rate": grp["placement"].apply(lambda s: float((s <= 4).mean())).round(3),
            "first_rate": grp["placement"].apply(lambda s: float((s == 1).mean())).round(3),
            "avg_share": grp["final_share"].mean().round(2),
            "median_commit_turn": grp["commit_turn"].median(),
            "avg_pivots": grp["pivots"].mean().round(1),
            "mmr_change": grp["mmr_delta"].sum(min_count=1),
        }
    ).reset_index()
    out = out.rename(columns={"final_type": "minion_type"})
    return (
        out[cols]
        .sort_values(["games", "avg_placement"], ascending=[False, True])
        .reset_index(drop=True)
    )


def losing_opponent_board_types(tables: Tables) -> pd.DataFrame:
    """Dominant minion type of the opponent board in combats you lost (Q6)."""
    lost = tables.combats[tables.combats["result"] == "loss"][["game_id", "turn"]]
    m = tables.board_minions[tables.board_minions["side"] == "opponent"]
    if lost.empty or m.empty:
        return pd.DataFrame(columns=["minion_type", "combats_lost", "share"])
    m = m.merge(lost, on=["game_id", "turn"], how="inner")
    exploded = m.assign(minion_type=m["minion_types"].str.split("|")).explode("minion_type")
    exploded = exploded[exploded["minion_type"].astype(str).str.len() > 0]
    dominant = (
        exploded.groupby(["game_id", "turn", "minion_type"])
        .size()
        .rename("n")
        .reset_index()
        .sort_values(["game_id", "turn", "n"], ascending=[True, True, False])
        .drop_duplicates(["game_id", "turn"])
    )
    out = dominant.groupby("minion_type").size().rename("combats_lost").reset_index()
    out["share"] = (out["combats_lost"] / out["combats_lost"].sum()).round(3)
    return out.sort_values("combats_lost", ascending=False).reset_index(drop=True)


def recent_games(tables: Tables, n: int = 10) -> pd.DataFrame:
    g = tables.games.sort_values("started_at", ascending=False).head(n)
    return g[
        [
            "game_id",
            "started_at",
            "hero_name",
            "placement",
            "mmr_before",
            "mmr_after",
            "mmr_delta",
            "final_tier",
            "total_turns",
            "duration_sec",
            "status",
            "path",
        ]
    ].reset_index(drop=True)


# ---------------------------------------------------------------- minion types (tribes)
#
# "Main type" (主軸種族) of a board = the type with the most minions on it. Dual-type minions count
# for both types, "all"-type minions (Amalgam-like) count for whichever type wins, typeless minions
# only count toward the board size. Ties go to the type with more total stats, then to the token.
# `dominant_type` (pure Python, one board) and `main_type_by_turn` (pandas, all boards) implement
# the same rule; keep them in sync.

PHASES: dict[str, tuple[int, int]] = {"early": (1, 5), "mid": (6, 10), "late": (11, 999)}
PIVOT_MIN_TURN = 4  # boards before this turn are too small to call a change of plan a "pivot"


def dominant_type(minions: list[dict[str, Any]] | None) -> tuple[str | None, int, int]:
    """(main type, its minion count, board size) of one board from the log's minion dicts."""
    minions = minions or []
    count: dict[str, int] = {}
    stats: dict[str, int] = {}
    wild = 0
    for m in minions:
        types = [t for t in (m.get("minion_types") or []) if t]
        if "all" in types:
            wild += 1
            continue
        for t in types:
            count[t] = count.get(t, 0) + 1
            stats[t] = stats.get(t, 0) + int(m.get("attack") or 0) + int(m.get("health") or 0)
    if not count:
        return None, 0, len(minions)
    best = sorted(count, key=lambda t: (-count[t], -stats[t], t))[0]
    return best, count[best] + wild, len(minions)


def _explode_types(m: pd.DataFrame) -> pd.DataFrame:
    """board_minions rows -> one row per (minion, type). Typeless and 'all' minions are dropped."""
    ex = m.assign(minion_type=m["minion_types"].str.split("|")).explode("minion_type")
    ex = ex[ex["minion_type"].astype(str).str.len() > 0]
    return ex[ex["minion_type"] != "all"]


def board_type_counts(tables: Tables, side: str = "player") -> pd.DataFrame:
    """Per (game, turn, type): minion count, total stats, board size and share of the board."""
    cols = ["game_id", "turn", "minion_type", "n", "stats", "board_size", "share"]
    m = tables.board_minions[tables.board_minions["side"] == side]
    if m.empty:
        return pd.DataFrame(columns=cols)
    keys = ["game_id", "turn"]
    size = m.groupby(keys).size().rename("board_size")
    wild = (
        m[m["minion_types"].str.split("|").apply(lambda ts: "all" in ts)]
        .groupby(keys)
        .size()
        .rename("wild")
    )
    ex = _explode_types(m)
    if ex.empty:
        return pd.DataFrame(columns=cols)
    ex = ex.assign(stat=ex["attack"].fillna(0) + ex["health"].fillna(0))
    grp = ex.groupby([*keys, "minion_type"])
    out = pd.DataFrame({"n": grp.size(), "stats": grp["stat"].sum()}).reset_index()
    out = out.join(size, on=keys).join(wild, on=keys)
    out["n"] = (out["n"] + out["wild"].fillna(0)).astype(int)
    out["share"] = (out["n"] / out["board_size"]).round(3)
    return out[cols]


def main_type_by_turn(tables: Tables, side: str = "player") -> pd.DataFrame:
    """Per (game, turn): the main type of that side's board (see the note above)."""
    cols = ["game_id", "turn", "minion_type", "n", "board_size", "share"]
    counts = board_type_counts(tables, side)
    if counts.empty:
        return pd.DataFrame(columns=cols)
    ordered = counts.sort_values(
        ["game_id", "turn", "n", "stats", "minion_type"],
        ascending=[True, True, False, False, True],
        kind="stable",
    )
    return ordered.drop_duplicates(["game_id", "turn"])[cols].reset_index(drop=True)


def type_timeline(tables: Tables) -> pd.DataFrame:
    """Player's main type for every (game, turn), with the game's label columns. Turns without a
    recorded board keep NaN in minion_type."""
    main = main_type_by_turn(tables, "player")[["game_id", "turn", "minion_type", "n", "share"]]
    t = tables.turns[["game_id", "turn"]]
    g = tables.games[["game_id", "started_at", "hero_name", "placement", "total_turns"]]
    out = t.merge(main, on=["game_id", "turn"], how="left").merge(g, on="game_id", how="inner")
    return out.sort_values(["started_at", "turn"]).reset_index(drop=True)


def type_phases(tables: Tables) -> pd.DataFrame:
    """One row per game: main type at the end of each phase (early T1-5 / mid T6-10 / late T11+),
    the final main type and its share, `commit_turn` (first turn from which the final type stayed
    the main type) and `pivots` (main-type changes from T{PIVOT_MIN_TURN} on)."""
    cols = [
        "game_id",
        "started_at",
        "hero_name",
        "placement",
        "mmr_delta",
        "total_turns",
        "early_type",
        "mid_type",
        "late_type",
        "final_type",
        "final_share",
        "commit_turn",
        "pivots",
    ]
    main = main_type_by_turn(tables, "player")
    if main.empty:
        return pd.DataFrame(columns=cols)
    games = tables.games.set_index("game_id")
    rows: list[dict[str, Any]] = []
    for game_id, grp in main.groupby("game_id"):
        grp = grp.sort_values("turn")
        seq = list(zip(grp["turn"].astype(int), grp["minion_type"], strict=True))
        final_turn, final = seq[-1]
        commit = final_turn
        for turn, mt in reversed(seq):
            if mt != final:
                break
            commit = turn
        pivots = 0
        prev: str | None = None
        for turn, mt in seq:
            if turn < PIVOT_MIN_TURN:
                continue
            if prev is not None and mt != prev:
                pivots += 1
            prev = mt
        phase_types = {}
        for name, (lo, hi) in PHASES.items():
            part = [mt for turn, mt in seq if lo <= turn <= hi]
            phase_types[name] = part[-1] if part else None
        game = games.loc[game_id]
        rows.append(
            {
                "game_id": game_id,
                "started_at": game["started_at"],
                "hero_name": game["hero_name"],
                "placement": game["placement"],
                "mmr_delta": game["mmr_delta"],
                "total_turns": game["total_turns"],
                "early_type": phase_types["early"],
                "mid_type": phase_types["mid"],
                "late_type": phase_types["late"],
                "final_type": final,
                "final_share": float(grp["share"].iloc[-1]),
                "commit_turn": commit,
                "pivots": pivots,
            }
        )
    return pd.DataFrame(rows, columns=cols).sort_values("started_at").reset_index(drop=True)


def type_availability_stats(tables: Tables) -> pd.DataFrame:
    """Per type: the games it was offered in (`game.minion_types`) and how they went, against the
    games where it ended up as my final main type ("played"). `pick_rate` = played / offered."""
    cols = [
        "minion_type",
        "offered_games",
        "offered_avg_placement",
        "offered_top4_rate",
        "played_games",
        "pick_rate",
        "played_avg_placement",
        "not_played_avg_placement",
    ]
    g = tables.games.dropna(subset=["placement"])
    if g.empty:
        return pd.DataFrame(columns=cols)
    ex = g.assign(minion_type=g["minion_types"].str.split("|")).explode("minion_type")
    ex = ex[ex["minion_type"].astype(str).str.len() > 0]
    if ex.empty:
        return pd.DataFrame(columns=cols)
    final = type_phases(tables)[["game_id", "final_type"]]
    ex = ex.merge(final, on="game_id", how="left")
    ex["played"] = ex["minion_type"] == ex["final_type"]
    ex["played_place"] = ex["placement"].where(ex["played"])
    ex["not_played_place"] = ex["placement"].where(~ex["played"])
    grp = ex.groupby("minion_type")
    out = pd.DataFrame(
        {
            "offered_games": grp.size(),
            "offered_avg_placement": grp["placement"].mean().round(2),
            "offered_top4_rate": grp["placement"].apply(lambda s: float((s <= 4).mean())).round(3),
            "played_games": grp["played"].sum().astype(int),
            "played_avg_placement": grp["played_place"].mean().round(2),
            "not_played_avg_placement": grp["not_played_place"].mean().round(2),
        }
    ).reset_index()
    out["pick_rate"] = (out["played_games"] / out["offered_games"]).round(3)
    return (
        out[cols]
        .sort_values(["played_games", "offered_games"], ascending=[False, False])
        .reset_index(drop=True)
    )


def type_transitions(tables: Tables, from_phase: str = "early") -> pd.DataFrame:
    """How often the main type at the end of `from_phase` became the final type, and the average
    placement of each (from -> final) pair."""
    cols = ["from_type", "final_type", "games", "avg_placement", "changed"]
    ph = type_phases(tables).dropna(subset=["placement", f"{from_phase}_type", "final_type"])
    if ph.empty:
        return pd.DataFrame(columns=cols)
    grp = ph.groupby([f"{from_phase}_type", "final_type"])
    out = pd.DataFrame(
        {"games": grp.size(), "avg_placement": grp["placement"].mean().round(2)}
    ).reset_index()
    out = out.rename(columns={f"{from_phase}_type": "from_type"})
    out["changed"] = out["from_type"] != out["final_type"]
    return out[cols].sort_values("games", ascending=False).reset_index(drop=True)


def _combat_types(tables: Tables) -> pd.DataFrame:
    c = tables.combats.dropna(subset=["result"])[["game_id", "turn", "result", "damage_taken"]]
    me = main_type_by_turn(tables, "player")[["game_id", "turn", "minion_type"]]
    op = main_type_by_turn(tables, "opponent")[["game_id", "turn", "minion_type"]]
    return c.merge(me.rename(columns={"minion_type": "my_type"}), on=["game_id", "turn"]).merge(
        op.rename(columns={"minion_type": "opp_type"}), on=["game_id", "turn"]
    )


def _result_counts(grp: Any) -> dict[str, pd.Series]:
    return {
        "combats": grp.size(),
        "wins": grp["result"].apply(lambda s: int((s == "win").sum())),
        "losses": grp["result"].apply(lambda s: int((s == "loss").sum())),
        "ties": grp["result"].apply(lambda s: int((s == "tie").sum())),
    }


def type_matchups(tables: Tables) -> pd.DataFrame:
    """Combat record of (my main type) vs (opponent's main type)."""
    cols = ["my_type", "opp_type", "combats", "wins", "losses", "ties", "win_rate"]
    df = _combat_types(tables)
    if df.empty:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(_result_counts(df.groupby(["my_type", "opp_type"]))).reset_index()
    out["win_rate"] = (out["wins"] / out["combats"]).round(3)
    return out[cols].sort_values("combats", ascending=False).reset_index(drop=True)


def opponent_type_stats(tables: Tables) -> pd.DataFrame:
    """Combat record against each opponent main type, whatever I was playing."""
    cols = ["opp_type", "combats", "wins", "losses", "ties", "win_rate", "avg_damage_taken"]
    df = _combat_types(tables)
    if df.empty:
        return pd.DataFrame(columns=cols)
    grp = df.groupby("opp_type")
    out = pd.DataFrame(
        {**_result_counts(grp), "avg_damage_taken": grp["damage_taken"].mean().round(1)}
    ).reset_index()
    out["win_rate"] = (out["wins"] / out["combats"]).round(3)
    return (
        out[cols]
        .sort_values(["combats", "win_rate"], ascending=[False, True])
        .reset_index(drop=True)
    )


def type_runs(log: dict[str, Any]) -> list[tuple[int, int, str | None]]:
    """Main-type runs of one game as (first_turn, last_turn, type), for the game-detail caption."""
    runs: list[tuple[int, int, str | None]] = []
    for t in log.get("turns") or []:
        board = t.get("board_end_of_shop")
        if not board:
            continue
        mt, _, _ = dominant_type(board)
        turn = int(t["turn"])
        if runs and runs[-1][2] == mt:
            runs[-1] = (runs[-1][0], turn, mt)
        else:
            runs.append((turn, turn, mt))
    return runs


# ---------------------------------------------------------------- deity (神祇, schema 1.2.0)
#
# The Deity (C'Thun, Y'Shaarj, ...) is not on the board but awakens mid-combat once 4 friendly
# Aberrations die (3 before patch 36.6.3 on 2026-10-02), so board stats alone understate combat
# power (docs/log-schema.md §神祇). "Stats" below are attack + health, the same measure for the
# Deity and for a board total.

DEITY_TURN_COLUMNS = [
    "turn",
    "deity_name",
    "deity_attack",
    "deity_health",
    "deity_attack_after",
    "deity_health_after",
    "deity_awakened",
    "deity_golden",
    "deity_stats",
    "deity_stats_after",
    "deity_growth_shop",
    "deity_growth_combat",
    "board_attack",
    "board_health",
    "board_stats",
    "opponent_hero_name",
    "result",
    "opponent_board_stats",
    "opponent_deity_attack",
    "opponent_deity_health",
    "opponent_deity_attack_after",
    "opponent_deity_health_after",
    "opponent_deity_awakened",
    "opponent_deity_golden",
    "opponent_deity_stats",
]


def _sum2(a: pd.Series, b: pd.Series) -> pd.Series:
    """a + b, NaN when either is missing (a Deity with no reading is not 0)."""
    return pd.to_numeric(a, errors="coerce") + pd.to_numeric(b, errors="coerce")


def deity_by_turn(tables: Tables, game_id: str) -> pd.DataFrame:
    """One game, per turn: my Deity (at shop end / after combat, growth in shop / in combat),
    my board total, and the combat opponent's Deity and board total. Games without Deity data (no
    aberration in the lobby, old logs) still get the board totals with the Deity columns NaN; empty
    only when neither is recorded."""
    t = tables.turns[tables.turns["game_id"] == game_id].sort_values("turn")
    if t.empty or (t["deity_attack"].isna().all() and t["board_attack"].isna().all()):
        return pd.DataFrame(columns=DEITY_TURN_COLUMNS)
    c = tables.combats[tables.combats["game_id"] == game_id]
    df = t.merge(
        c[
            [
                "turn",
                "opponent_hero_name",
                "result",
                "opponent_board_attack",
                "opponent_board_health",
                "opponent_deity_attack",
                "opponent_deity_health",
                "opponent_deity_attack_after",
                "opponent_deity_health_after",
                "opponent_deity_awakened",
                "opponent_deity_golden",
            ]
        ],
        on="turn",
        how="left",
    ).reset_index(drop=True)
    df["deity_stats"] = _sum2(df["deity_attack"], df["deity_health"])
    df["deity_stats_after"] = _sum2(df["deity_attack_after"], df["deity_health_after"])
    # shop growth = this shop's end minus the previous combat's end; combat growth = after - before
    df["deity_growth_shop"] = df["deity_stats"] - df["deity_stats_after"].shift(1)
    df.loc[0, "deity_growth_shop"] = df.loc[0, "deity_stats"]
    df["deity_growth_combat"] = df["deity_stats_after"] - df["deity_stats"]
    df["board_stats"] = _sum2(df["board_attack"], df["board_health"])
    df["opponent_board_stats"] = _sum2(df["opponent_board_attack"], df["opponent_board_health"])
    df["opponent_deity_stats"] = _sum2(df["opponent_deity_attack"], df["opponent_deity_health"])
    return df[DEITY_TURN_COLUMNS]


def deity_game_stats(tables: Tables) -> pd.DataFrame:
    """Per game with Deity data: which Deity, first turn it awakened, how many combats it awakened
    in, its final size (after the last combat) and the placement."""
    t = tables.turns.dropna(subset=["deity_attack"])
    cols = [
        "game_id",
        "started_at",
        "hero_name",
        "placement",
        "deity_name",
        "first_awaken_turn",
        "awakened_combats",
        "golden_awakenings",
        "combats",
        "final_deity_attack",
        "final_deity_health",
        "deity_stats_t8",
    ]
    if t.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    for gid, g in t.sort_values("turn").groupby("game_id", sort=False):
        aw = g[g["deity_awakened"] == True]  # noqa: E712 (None/NaN are "unknown", not False)
        last = g.iloc[-1]
        final_a = last["deity_attack_after"]
        final_h = last["deity_health_after"]
        if pd.isna(final_a):
            final_a, final_h = last["deity_attack"], last["deity_health"]
        t8 = g[g["turn"] <= 8].tail(1)
        rows.append(
            {
                "game_id": gid,
                "deity_name": last["deity_name"],
                "first_awaken_turn": int(aw["turn"].min()) if not aw.empty else None,
                "awakened_combats": len(aw),
                "golden_awakenings": int((g["deity_golden"] == True).sum()),  # noqa: E712
                "combats": int(g["deity_awakened"].notna().sum()),
                "final_deity_attack": final_a,
                "final_deity_health": final_h,
                "deity_stats_t8": (
                    float(t8["deity_attack"].iloc[0] + t8["deity_health"].iloc[0])
                    if not t8.empty
                    else None
                ),
            }
        )
    df = pd.DataFrame(rows)
    games = tables.games[["game_id", "started_at", "hero_name", "placement"]]
    return games.merge(df, on="game_id").sort_values("started_at").reset_index(drop=True)[cols]


def deity_stats(tables: Tables) -> pd.DataFrame:
    """By Deity: games, average placement, median first-awaken turn, median final size."""
    g = deity_game_stats(tables)
    if g.empty:
        return pd.DataFrame(
            columns=[
                "deity_name",
                "games",
                "avg_placement",
                "top4_rate",
                "median_first_awaken_turn",
                "median_final_stats",
            ]
        )
    g = g.assign(final_stats=g["final_deity_attack"] + g["final_deity_health"])
    out = (
        g.groupby("deity_name")
        .agg(
            games=("game_id", "count"),
            avg_placement=("placement", "mean"),
            top4_rate=("placement", lambda s: (s <= 4).mean()),
            median_first_awaken_turn=("first_awaken_turn", "median"),
            median_final_stats=("final_stats", "median"),
        )
        .reset_index()
        .sort_values("games", ascending=False)
    )
    out["avg_placement"] = out["avg_placement"].round(2)
    return out.reset_index(drop=True)


# ---------------------------------------------------------------- single game


_KEY_MOMENT_TEXT = {
    "en": {
        "tier_up": "T{turn}: tier up to {tier}{rel}",
        "early": " (early vs your median T{med:g})",
        "late": " (late vs your median T{med:g})",
        "typical": " (typical vs your median T{med:g})",
        "hit": "T{turn}: largest hit taken, {dmg} damage from {hero}",
        "upset_loss": "T{turn}: lost a combat Bob's Buddy rated {p:.0%} win",
        "upset_win": "T{turn}: won a combat Bob's Buddy rated {p:.0%} loss",
        "rerolls": "T{turn}: {n} rerolls, no buy",
        "eliminated": "T{turn}: eliminated by {hero}",
        "board": " (board: {board})",
        "deity_first": "T{turn}: {deity} awakened for the first time ({a}/{h} at combat start)",
        "deity_golden": "T{turn}: {deity} awakened golden for the first time (double effect)",
        "deity_over_board": "T{turn}: {deity} ({a}/{h}) outgrew the whole board ({ba}/{bh} total)",
        "deity_last": "T{turn} last combat: my {deity} {a}/{h} vs opponent's {oa}/{oh}",
    },
    "ja": {
        "tier_up": "T{turn}: ティア {tier} に上げた{rel}",
        "early": "（自分の中央値 T{med:g} より早い）",
        "late": "（自分の中央値 T{med:g} より遅い）",
        "typical": "（自分の中央値 T{med:g} と同じ）",
        "hit": "T{turn}: 最大の被ダメージ {dmg}（相手: {hero}）",
        "upset_loss": "T{turn}: Bob's Buddy 勝率 {p:.0%} の戦闘に負けた",
        "upset_win": "T{turn}: Bob's Buddy 敗率 {p:.0%} の戦闘に勝った",
        "rerolls": "T{turn}: リロール {n} 回で購入なし",
        "eliminated": "T{turn}: {hero} に敗退",
        "board": "（相手盤面: {board}）",
        "deity_first": "T{turn}: {deity}が初めて目覚めた（戦闘開始時 {a}/{h}）",
        "deity_golden": "T{turn}: {deity}が初めて金色で目覚めた（効果が 2 倍）",
        "deity_over_board": "T{turn}: {deity}（{a}/{h}）が盤面全体（合計 {ba}/{bh}）を上回った",
        "deity_last": "T{turn} 最後の戦闘: 自分の{deity} {a}/{h} vs 相手 {oa}/{oh}",
    },
}


def key_moments(log: dict[str, Any], history: Tables | None = None, lang: str = "en") -> list[str]:
    """Rule-based highlights for one game (docs/analysis-and-visualization.md §4).
    `history` = the player's other games.

    `lang` picks the sentence templates ("en" for AI input, "ja" for the dashboard); the rules and
    numbers are identical.
    """
    tx = _KEY_MOMENT_TEXT.get(lang, _KEY_MOMENT_TEXT["en"])
    moments: list[str] = []
    turns = log.get("turns") or []
    medians = tier_reach_median(history) if history is not None else {}
    prev_tier = None
    for t in turns:
        tier = t.get("tavern_tier")
        turn = t.get("turn")
        if tier is not None and prev_tier is not None and tier > prev_tier:
            med = medians.get(int(tier))
            rel = ""
            if med is not None:
                key = "early" if turn < med else "late" if turn > med else "typical"
                rel = tx[key].format(med=med)
            moments.append(tx["tier_up"].format(turn=turn, tier=tier, rel=rel))
        if tier is not None:
            prev_tier = tier
    combats = [(t.get("turn"), t.get("combat")) for t in turns if t.get("combat")]
    if combats:
        worst = max(combats, key=lambda tc: tc[1].get("damage_taken") or 0)
        if (worst[1].get("damage_taken") or 0) > 0:
            oh = (worst[1].get("opponent_hero") or {}).get("name") or "?"
            moments.append(tx["hit"].format(turn=worst[0], dmg=worst[1]["damage_taken"], hero=oh))
        for turn, c in combats:
            bb = c.get("bobs_buddy") or {}
            res = c.get("result")
            if res == "loss" and (bb.get("win") or 0) >= 0.8:
                moments.append(tx["upset_loss"].format(turn=turn, p=bb["win"]))
            if res == "win" and (bb.get("loss") or 0) >= 0.8:
                moments.append(tx["upset_win"].format(turn=turn, p=bb["loss"]))
    for t in turns:
        a = t.get("actions") or {}
        if (a.get("rerolls") or 0) >= 3 and (a.get("buys") or 0) == 0:
            moments.append(tx["rerolls"].format(turn=t["turn"], n=a["rerolls"]))
    moments += _deity_moments(turns, tx)
    result = log.get("result") or {}
    if result.get("placement") and result.get("placement") != 1 and combats:
        last_turn, last = combats[-1]
        oh = (last.get("opponent_hero") or {}).get("name") or "?"
        board = ", ".join(
            f"{m.get('name')} {m.get('attack')}/{m.get('health')}"
            for m in (last.get("opponent_board") or [])[:7]
        )
        moments.append(
            tx["eliminated"].format(turn=last_turn, hero=oh)
            + (tx["board"].format(board=board) if board else "")
        )
    return moments


def _deity_moments(turns: list[dict[str, Any]], tx: dict[str, str]) -> list[str]:
    out: list[str] = []
    with_deity = [t for t in turns if t.get("deity")]
    if not with_deity:
        return out
    first = next((t for t in with_deity if t["deity"].get("awakened")), None)
    if first:
        d = first["deity"]
        name = d.get("name") or d.get("card_id") or "Deity"
        out.append(
            tx["deity_first"].format(
                turn=first["turn"], deity=name, a=d.get("attack"), h=d.get("health")
            )
        )
    gold = next((t for t in with_deity if t["deity"].get("golden")), None)
    if gold:
        d = gold["deity"]
        out.append(
            tx["deity_golden"].format(
                turn=gold["turn"], deity=d.get("name") or d.get("card_id") or "Deity"
            )
        )
    for t in with_deity:
        d = t["deity"]
        board = t.get("board_end_of_shop") or []
        ba = sum(int(m.get("attack") or 0) for m in board)
        bh = sum(int(m.get("health") or 0) for m in board)
        if board and (d.get("attack") or 0) > ba and (d.get("health") or 0) > bh:
            name = d.get("name") or d.get("card_id") or "Deity"
            out.append(
                tx["deity_over_board"].format(
                    turn=t["turn"], deity=name, a=d.get("attack"), h=d.get("health"), ba=ba, bh=bh
                )
            )
            break
    last = with_deity[-1]
    od = (last.get("combat") or {}).get("opponent_deity")
    if od and last is turns[-1]:
        d = last["deity"]
        out.append(
            tx["deity_last"].format(
                turn=last["turn"],
                deity=d.get("name") or d.get("card_id") or "Deity",
                a=d.get("attack"),
                h=d.get("health"),
                oa=od.get("attack"),
                oh=od.get("health"),
            )
        )
    return out


# ------------------------------------------------------- early game per game
#
# Per-game early-game features (tier timing, early boards, HP, rerolls / buys / sells / Dark
# Discoveries, gold left over) and a bottom-4 vs top-4 comparison of any of them. Which features
# matter, thresholds and conditions belong to the user's lenses (workspace lenses/, hsbg.lens).
EARLY_LAST_TURN = 8  # "early game" totals are T1..T8

EARLY_FEATURE_COLUMNS = [
    "game_id",
    "started_at",
    "hero_name",
    "placement",
    "group",
    "final_type",
    "tier3_turn",
    "tier4_turn",
    "tier5_turn",
    "board_t3",
    "board_total_t3",
    "board_t4",
    "hp_t6",
    "hp_t8",
    "board_total_t10",
    "board_total_t11",
    "board_diff_t8",
    "board_diff_t10",
    "losses_t3_7",
    "damage_t3_8",
    "rerolls_t1_8",
    "buys_t1_8",
    "sells_t1_8",
    "dark_gifts_t1_8",
    "unspent_gold_t1_8",
]


def _first_turn(turns: pd.Series) -> float:
    return float(turns.min()) if len(turns) else float("nan")


def placement_group(placement: Any) -> str:
    """ "top4" for 1st-4th, "bottom4" otherwise (also when the placement is unknown)."""
    return "top4" if pd.notna(placement) and placement <= 4 else "bottom4"


def card_tiers(tables: Tables) -> dict[str, int]:
    """Tavern tier per base card id (golden `_G` folded in), from every board in the tables."""
    m = tables.board_minions[["card_id", "tier"]].dropna()
    if m.empty:
        return {}
    base = m["card_id"].astype(str).str.replace(r"_G$", "", regex=True)
    tiers = pd.to_numeric(m["tier"], errors="coerce").groupby(base).max().dropna()
    return {k: int(v) for k, v in tiers.items()}


def early_game_features(tables: Tables) -> pd.DataFrame:
    """One row per game: controllable early-game actions and their outcomes.

    `group` = `placement_group`. `board_t3` / `board_total_t3` = my board's size and attack +
    health at the T3 shop end. `board_total_t10` / `board_total_t11` = my board's attack + health
    at that shop end. `board_diff_t8` / `board_diff_t10` = my board's attack + health minus that
    turn's combat opponent's (compare across MMR bands with this, not the absolute totals).
    Values that the log does not have (old schema) stay NaN."""
    games = tables.games[tables.games["placement"].notna()]
    if games.empty:
        return pd.DataFrame(columns=EARLY_FEATURE_COLUMNS)
    turns = tables.turns
    combats = tables.combats[
        [
            "game_id",
            "turn",
            "result",
            "damage_taken",
            "opponent_board_attack",
            "opponent_board_health",
        ]
    ]
    t = turns.merge(combats, on=["game_id", "turn"], how="left").sort_values(["game_id", "turn"])
    final_types = type_phases(tables).set_index("game_id")["final_type"]

    rows: list[dict[str, Any]] = []
    for _, game in games.iterrows():
        gid = game["game_id"]
        g = t[t["game_id"] == gid].set_index("turn")
        if g.empty:
            continue
        early = g[g.index <= EARLY_LAST_TURN]

        def at(col: str, turn: int, g: pd.DataFrame = g) -> float:
            return float(g[col].get(turn, float("nan")))

        def reach(tier: int, g: pd.DataFrame = g) -> float:
            return _first_turn(g.index[g["tavern_tier"] >= tier].to_series())

        hp = g["health"] + g["armor"].fillna(0)
        board_total = _sum2(g["board_attack"], g["board_health"])
        board_diff = board_total - _sum2(g["opponent_board_attack"], g["opponent_board_health"])
        lost = g["result"] == "loss"
        gold_left = (early["gold_available"] - early["gold_spent"]).clip(lower=0)
        size3 = at("board_size", 3)
        total3 = float(board_total.get(3, float("nan")))
        rows.append(
            {
                "game_id": gid,
                "started_at": game["started_at"],
                "hero_name": game["hero_name"],
                "placement": game["placement"],
                "group": placement_group(game["placement"]),
                "final_type": final_types.get(gid),
                "tier3_turn": reach(3),
                "tier4_turn": reach(4),
                "tier5_turn": reach(5),
                "board_t3": size3,
                "board_total_t3": total3,
                "board_t4": at("board_size", 4),
                "hp_t6": float(hp.get(6, float("nan"))),
                "hp_t8": float(hp.get(8, float("nan"))),
                "board_total_t10": float(board_total.get(10, float("nan"))),
                "board_total_t11": float(board_total.get(11, float("nan"))),
                "board_diff_t8": float(board_diff.get(8, float("nan"))),
                "board_diff_t10": float(board_diff.get(10, float("nan"))),
                "losses_t3_7": int(lost[(g.index >= 3) & (g.index <= 7)].sum()),
                "damage_t3_8": float(
                    g.loc[(g.index >= 3) & (g.index <= 8) & lost, "damage_taken"].sum()
                ),
                "rerolls_t1_8": early["rerolls"].sum(min_count=1),
                "buys_t1_8": early["buys"].sum(min_count=1),
                "sells_t1_8": early["sells"].sum(min_count=1),
                "dark_gifts_t1_8": early["dark_gifts"].sum(min_count=1),
                "unspent_gold_t1_8": gold_left.sum(min_count=1),
            }
        )
    if not rows:
        return pd.DataFrame(columns=EARLY_FEATURE_COLUMNS)
    df = pd.DataFrame(rows, columns=EARLY_FEATURE_COLUMNS)
    return df.sort_values("started_at").reset_index(drop=True)


COMPARE_COLUMNS = ["key", "feature", "bottom4", "top4", "diff", "games_bottom4", "games_top4"]


def compare_groups(features: pd.DataFrame, columns: dict[str, str]) -> pd.DataFrame:
    """Per numeric column of a per-game table that has a `group` column (`placement_group`):
    median in bottom-4 games vs top-4 games, their difference and how many games had the value.
    `columns` maps column -> label, in display order. Columns the table lacks are skipped."""
    if features.empty or "group" not in features:
        return pd.DataFrame(columns=COMPARE_COLUMNS)
    rows = []
    for key, label in columns.items():
        if key not in features:
            continue
        s = pd.to_numeric(features[key], errors="coerce")
        bot = s[features["group"] == "bottom4"]
        top = s[features["group"] == "top4"]
        rows.append(
            {
                "key": key,
                "feature": label,
                "bottom4": bot.median(),
                "top4": top.median(),
                "diff": bot.median() - top.median(),
                "games_bottom4": int(bot.notna().sum()),
                "games_top4": int(top.notna().sum()),
            }
        )
    return pd.DataFrame(rows, columns=COMPARE_COLUMNS)


def hero_key(card_id: str | None) -> str | None:
    """Convenience re-export for presentation layers."""
    return base_hero_id(card_id)
