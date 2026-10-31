from datetime import datetime

import pandas as pd

from hsbg import metrics
from hsbg.normalize import Tables


def test_apply_filter_excludes_incomplete_by_default(tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    assert (f.games["status"] == "complete").all()
    assert len(f.games) == len(tables.games) - 1
    g = metrics.apply_filter(tables, metrics.LogFilter(include_incomplete=True))
    assert len(g.games) == len(tables.games)


def test_apply_filter_last_and_hero_and_dates(tables: Tables) -> None:
    last2 = metrics.apply_filter(tables, metrics.LogFilter(last=2))
    assert len(last2.games) == 2
    assert last2.games["started_at"].iloc[-1] == tables.games["started_at"].max()
    hero = tables.games["hero_base_card_id"].iloc[0]
    only = metrics.apply_filter(tables, metrics.LogFilter(heroes={hero}, include_incomplete=True))
    assert (only.games["hero_base_card_id"] == hero).all()
    none = metrics.apply_filter(tables, metrics.LogFilter(since=datetime(2030, 1, 1)))
    assert none.games.empty
    assert metrics.kpis(none)["games"] == 0


def test_apply_filter_mmr_range(tables: Tables) -> None:
    mmr = tables.games.loc[tables.games["status"] == "complete", "mmr_before"].dropna()
    mid = int(mmr.median())
    low = metrics.apply_filter(tables, metrics.LogFilter(max_mmr=mid))
    high = metrics.apply_filter(tables, metrics.LogFilter(min_mmr=mid + 1))
    assert (low.games["mmr_before"] <= mid).all() and (high.games["mmr_before"] > mid).all()
    assert len(low.games) + len(high.games) == len(mmr)
    both = metrics.apply_filter(tables, metrics.LogFilter(min_mmr=mid, max_mmr=mid))
    assert (both.games["mmr_before"] == mid).all()
    # the filtered tables only hold the selected games
    assert set(low.turns["game_id"]) <= set(low.games["game_id"])


def test_kpis_and_distribution_consistent(tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    k = metrics.kpis(f)
    dist = metrics.placement_distribution(f)
    assert dist["count"].sum() == k["games"]
    assert list(dist["placement"]) == list(range(1, 9))
    expected_top4 = dist[dist["placement"] <= 4]["count"].sum() / k["games"]
    assert abs(k["top4_rate"] - expected_top4) < 1e-6
    assert k["mmr_change"] == int(f.games["mmr_delta"].dropna().sum())
    assert isinstance(k["period_start"], pd.Timestamp)


def test_hero_stats_sum_to_games(tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    hs = metrics.hero_stats(f)
    assert hs["games"].sum() == len(f.games)
    assert hs["avg_placement"].between(1, 8).all()
    assert hs["top4_rate"].between(0, 1).all()


def test_tier_reach_turns_monotonic(tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    df = metrics.tier_reach_turns(f)
    for _, grp in df.groupby("game_id"):
        grp = grp.sort_values("tier")
        assert grp["turn"].is_monotonic_increasing
    med = metrics.tier_reach_median(f)
    assert 2 in med and med[2] >= 1


def test_combat_winrate_by_turn(tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    df = metrics.combat_winrate_by_turn(f)
    assert not df.empty
    assert ((df["wins"] + df["ties"] + df["losses"]) == df["combats"]).all()
    assert df["win_rate"].between(0, 1).all()


def test_health_by_turn_and_opponents(tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    hb = metrics.health_by_turn(f)
    assert set(hb["group"]) <= {"top4", "bottom4"}
    assert (hb["q1"] <= hb["median"]).all() and (hb["median"] <= hb["q3"]).all()
    opp = metrics.opponent_hero_stats(f)
    assert opp["combats"].sum() == len(
        f.combats.dropna(subset=["result", "opponent_hero_base_card_id"])
    )


def test_reroll_and_minion_type_stats(tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    rr = metrics.reroll_vs_placement(f)
    assert (rr["rerolls"] >= 0).all()
    mt = metrics.minion_type_stats(f)
    assert not mt.empty
    assert mt["games"].sum() <= len(f.games)


def test_key_moments(complete_logs: list[dict], tables: Tables) -> None:
    log = max(complete_logs, key=lambda g: g["game"]["started_at"])
    moments = metrics.key_moments(log, metrics.apply_filter(tables, metrics.LogFilter()))
    assert any("tier up" in m for m in moments)
    assert any("eliminated by" in m or "largest hit" in m for m in moments)
    assert metrics.key_moments({"turns": [], "result": {}}) == []


# ---------------------------------------------------------------- minion types (tribes)


def test_dominant_type_rule() -> None:
    board = [
        {"minion_types": ["beast"], "attack": 1, "health": 1},
        {"minion_types": ["beast"], "attack": 1, "health": 1},
        {"minion_types": ["dragon", "demon"], "attack": 9, "health": 9},
        {"minion_types": ["demon"], "attack": 1, "health": 1},
        {"minion_types": ["all"], "attack": 1, "health": 1},
        {"minion_types": [], "attack": 1, "health": 1},
    ]
    # beast 2 vs demon 2 (dual-type counted for both): tie -> more stats -> demon; "all" adds 1
    assert metrics.dominant_type(board) == ("demon", 3, 6)
    assert metrics.dominant_type([{"minion_types": ["all"]}]) == (None, 0, 1)
    assert metrics.dominant_type(None) == (None, 0, 0)


def test_main_type_by_turn_matches_pure_rule(complete_logs: list[dict], tables: Tables) -> None:
    """The pandas path and the per-board Python rule must agree on every recorded board."""
    f = metrics.apply_filter(tables, metrics.LogFilter())
    main = metrics.main_type_by_turn(f, "player").set_index(["game_id", "turn"])
    checked = 0
    for log in complete_logs:
        for t in log["turns"]:
            board = t.get("board_end_of_shop")
            if not board:
                continue
            expected, n, size = metrics.dominant_type(board)
            key = (log["game"]["game_id"], t["turn"])
            if expected is None:
                assert key not in main.index
                continue
            row = main.loc[key]
            assert row["minion_type"] == expected and row["n"] == n and row["board_size"] == size
            checked += 1
    assert checked > 20


def test_type_phases_and_final_stats(tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    ph = metrics.type_phases(f)
    assert not ph.empty and len(ph) <= len(f.games)
    assert (ph["commit_turn"] <= ph["total_turns"]).all() and (ph["pivots"] >= 0).all()
    assert ph["final_share"].between(0, 1).all()
    # the final type is the main type of the game's last recorded board
    main = metrics.main_type_by_turn(f, "player")
    last = main.sort_values("turn").groupby("game_id").last()
    for r in ph.itertuples():
        assert last.loc[r.game_id, "minion_type"] == r.final_type
    mt = metrics.minion_type_stats(f)
    assert mt["games"].sum() == len(ph)
    assert set(mt["minion_type"]) == set(ph["final_type"])
    assert mt["top4_rate"].between(0, 1).all()


def test_type_availability_stats(tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    av = metrics.type_availability_stats(f)
    assert not av.empty
    # every game offers 5 types
    assert av["offered_games"].sum() == 5 * len(f.games.dropna(subset=["placement"]))
    assert (av["played_games"] <= av["offered_games"]).all()
    assert av["pick_rate"].between(0, 1).all()
    played = av.dropna(subset=["played_avg_placement"])
    assert (played["played_games"] > 0).all()


def test_type_transitions_and_matchups(tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    tr = metrics.type_transitions(f, "early")
    assert tr["games"].sum() == len(metrics.type_phases(f).dropna(subset=["early_type"]))
    assert (tr["changed"] == (tr["from_type"] != tr["final_type"])).all()
    mu = metrics.type_matchups(f)
    assert ((mu["wins"] + mu["losses"] + mu["ties"]) == mu["combats"]).all()
    opp = metrics.opponent_type_stats(f)
    assert opp["combats"].sum() == mu["combats"].sum()
    assert opp["win_rate"].between(0, 1).all()


def test_type_timeline_and_runs(complete_logs: list[dict], tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    tl = metrics.type_timeline(f)
    assert len(tl) == len(f.turns)
    assert tl["minion_type"].notna().sum() == len(metrics.main_type_by_turn(f, "player"))
    log = max(complete_logs, key=lambda g: g["game"]["started_at"])
    runs = metrics.type_runs(log)
    assert runs and runs[0][0] <= runs[-1][1]
    for (_, b, t1), (a, _, t2) in zip(runs, runs[1:], strict=False):
        assert b < a and t1 != t2


def test_tribe_metrics_on_empty_tables(tables: Tables) -> None:
    empty = tables.subset([])
    for fn in (
        metrics.type_phases,
        metrics.minion_type_stats,
        metrics.type_availability_stats,
        metrics.type_transitions,
        metrics.type_matchups,
        metrics.opponent_type_stats,
        metrics.type_timeline,
    ):
        assert fn(empty).empty, fn.__name__


def test_early_game_features(tables: Tables) -> None:
    f = metrics.early_game_features(tables)
    games = tables.games[tables.games["placement"].notna()]
    assert set(f["game_id"]) <= set(games["game_id"])
    assert len(f) == len(set(tables.turns["game_id"]) & set(games["game_id"]))
    assert (f["group"] == f["placement"].map(lambda p: "top4" if p <= 4 else "bottom4")).all()
    assert (f["losses_t3_7"] >= 0).all()
    reached = f.dropna(subset=["tier3_turn", "tier4_turn"])
    assert (reached["tier3_turn"] <= reached["tier4_turn"]).all()
    # T3 board = that turn's board size and attack + health
    t3 = tables.turns[tables.turns["turn"] == 3].set_index("game_id")
    size3 = f.set_index("game_id")["board_t3"].dropna()
    assert len(size3) > 0 and ((size3 >= 0) & (size3 <= 7)).all()
    assert (size3 == t3["board_size"].reindex(size3.index)).all()
    total3 = f.set_index("game_id")["board_total_t3"].dropna()
    assert (total3 == (t3["board_attack"] + t3["board_health"]).reindex(total3.index)).all()
    # board totals are the turn's board attack + health
    t10 = tables.turns[tables.turns["turn"] == 10].set_index("game_id")
    total10 = f.set_index("game_id")["board_total_t10"].dropna()
    expected = (t10["board_attack"] + t10["board_health"]).reindex(total10.index)
    assert (total10 == expected).all()
    assert len(total10) > 0
    # board diff = my board total minus that turn's combat opponent's board total
    c10 = tables.combats[tables.combats["turn"] == 10].set_index("game_id")
    diff10 = f.set_index("game_id")["board_diff_t10"].dropna()
    opp10 = (c10["opponent_board_attack"] + c10["opponent_board_health"]).reindex(diff10.index)
    assert len(diff10) > 0
    assert (diff10 == total10.reindex(diff10.index) - opp10).all()


def test_early_game_features_on_empty_tables(tables: Tables) -> None:
    empty = tables.subset([])
    assert metrics.early_game_features(empty).empty
    assert metrics.compare_groups(metrics.early_game_features(empty), {"hp_t8": "HP T8"}).empty
