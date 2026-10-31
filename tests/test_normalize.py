from hsbg import normalize
from hsbg.normalize import Tables


def test_base_hero_id() -> None:
    assert normalize.base_hero_id("TB_BaconShop_HERO_34_SKIN_C") == "TB_BaconShop_HERO_34"
    assert normalize.base_hero_id("BG22_HERO_002_SKIN_E") == "BG22_HERO_002"
    assert normalize.base_hero_id("BG36_HERO_002") == "BG36_HERO_002"
    assert normalize.base_hero_id(None) is None


def test_tables_shapes(tables: Tables) -> None:
    assert list(tables.games.columns) == normalize.GAME_COLUMNS
    assert len(tables.games) >= 6
    assert tables.games["started_at"].is_monotonic_increasing
    complete = tables.games[tables.games["status"] == "complete"]
    assert complete["placement"].between(1, 8).all()
    # every turn row belongs to a game
    assert set(tables.turns["game_id"]) <= set(tables.games["game_id"])
    # v0.3+ games have combats for every turn
    v3 = tables.games[tables.games["plugin_version"] >= "0.3.0"]
    for gid, total in zip(v3["game_id"], v3["total_turns"], strict=True):
        assert (tables.combats["game_id"] == gid).sum() == total
    assert set(tables.board_minions["side"]) == {"player", "opponent"}
    assert (tables.opponents.groupby("game_id").size() == 7).all()


def test_divine_shields() -> None:
    # schema 1.4.0: the count (Dark Paradox stacks them)
    assert normalize.divine_shields({"keywords": ["divine_shield"], "divine_shields": 3}) == 3
    assert normalize.divine_shields({"keywords": ["taunt"], "divine_shields": 0}) == 0
    # 1.3.x and older: no key, derived from the keyword
    assert normalize.divine_shields({"keywords": ["taunt", "divine_shield"]}) == 1
    assert normalize.divine_shields({"keywords": []}) == 0


def test_board_minions_divine_shields(tables: Tables) -> None:
    bm = tables.board_minions
    assert list(bm.columns) == normalize.MINION_COLUMNS
    has_kw = bm["keywords"].str.split("|").apply(lambda ks: "divine_shield" in ks)
    assert (bm.loc[has_kw, "divine_shields"] >= 1).all()
    assert (bm.loc[~has_kw, "divine_shields"] == 0).all()


def test_subset(tables: Tables) -> None:
    gid = tables.games["game_id"].iloc[0]
    sub = tables.subset([gid])
    assert len(sub.games) == 1
    assert set(sub.turns["game_id"]) == {gid}
    assert set(sub.opponents["game_id"]) == {gid}


def test_empty_normalize() -> None:
    t = normalize.normalize([])
    assert t.games.empty and list(t.games.columns) == normalize.GAME_COLUMNS


def test_dark_gifts_column(tables: Tables) -> None:
    # schema 1.0.0 fixtures have no dark_gifts key -> column exists, all null
    assert "dark_gifts" in tables.turns.columns
    assert tables.turns["dark_gifts"].isna().all()


def test_dark_gifts_from_1_1_log() -> None:
    import copy
    import json
    from pathlib import Path

    src = sorted(Path(__file__).parent.glob("fixtures/2026*_*-*.json"))[0]
    log = copy.deepcopy(json.loads(src.read_text(encoding="utf-8")))
    log["schema_version"] = "1.1.0"
    for i, t in enumerate(log["turns"]):
        if t.get("actions"):
            t["actions"]["dark_gifts"] = i % 2
    t = normalize.normalize([log])
    got = t.turns.set_index("turn")["dark_gifts"]
    for i, turn in enumerate(log["turns"]):
        if turn.get("actions"):
            assert got.loc[turn["turn"]] == i % 2


def test_gold_gained_from_1_6_log(tables: Tables) -> None:
    import copy
    import json
    from pathlib import Path

    # older fixtures have no gold_gained key -> column exists, all null
    assert tables.turns["gold_gained"].isna().all()
    src = sorted(Path(__file__).parent.glob("fixtures/2026*_*-*.json"))[0]
    log = copy.deepcopy(json.loads(src.read_text(encoding="utf-8")))
    log["schema_version"] = "1.6.0"
    for i, t in enumerate(log["turns"]):
        if t.get("actions"):
            t["actions"]["gold_gained"] = i % 3
    got = normalize.normalize([log]).turns.set_index("turn")["gold_gained"]
    for i, turn in enumerate(log["turns"]):
        if turn.get("actions"):
            assert got.loc[turn["turn"]] == i % 3
