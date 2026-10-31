import json
from pathlib import Path

import pytest
from conftest import FIXTURES

from hsbg import loader


def test_package_schema_matches_repo_copy() -> None:
    """In a checkout that has the plugin's schema/ next to this package (the development monorepo),
    the package copy must be the same. A stand-alone checkout has no schema/ to compare with."""
    repo = Path(__file__).resolve().parents[2] / "schema" / "game-log.schema.json"
    if not repo.exists():
        pytest.skip("no schema/ next to the package (stand-alone checkout)")
    pkg = Path(loader.__file__).with_name("game-log.schema.json")
    assert json.loads(repo.read_text("utf-8")) == json.loads(pkg.read_text("utf-8"))


def test_find_logs_skips_hidden_dirs(tmp_path: Path) -> None:
    (tmp_path / "2026" / "09").mkdir(parents=True)
    (tmp_path / ".partial").mkdir()
    (tmp_path / ".spike" / "x").mkdir(parents=True)
    (tmp_path / "2026" / "09" / "a.json").write_text("{}")
    (tmp_path / "2026" / "09" / "a.events.jsonl").write_text("")
    (tmp_path / ".partial" / "b.json").write_text("{}")
    (tmp_path / ".spike" / "x" / "c.json").write_text("{}")
    assert [p.name for p in loader.find_logs(tmp_path)] == ["a.json"]


def test_load_logs_reports_invalid_and_keeps_valid(load_result: loader.LoadResult) -> None:
    assert len(load_result.logs) >= 5
    names = [w.path.name for w in load_result.warnings]
    assert names == ["broken.json"]
    assert "schema violation" in load_result.warnings[0].message
    assert all("_path" in g for g in load_result.logs)
    assert len(load_result.incomplete) == 1


def _kicked_during_hero_pick() -> dict:
    """A real plugin 0.9.0 log (2026-10-12): removed from the game during hero selection."""
    return {
        "schema_version": "1.5.0",
        "status": "incomplete",
        "generator": {"plugin": "HsbgKansousen", "plugin_version": "0.9.0"},
        "game": {
            "game_id": "b9843e0f-8086-4402-8272-a59192a6d354",
            "mode": "battlegrounds",
            "started_at": "2026-10-12T12:54:23.4912907+09:00",
            "ended_at": "2026-10-12T12:55:16.522201+09:00",
            "lobby_size": 1,
        },
        "player": {"hero": {"card_id": None, "name": None, "dbf_id": None}, "hero_choices": []},
        "result": {"placement": None, "mmr_before": 7401, "eliminated_turn": 0, "total_turns": 0},
        "opponents": [],
        "turns": [],
        "notes": ["placement unavailable at OnGameEnd", "mmr_after unavailable"],
    }


def test_game_ended_before_turn_1_is_skipped_without_warning(tmp_path: Path) -> None:
    src = sorted(FIXTURES.glob("2026*.json"))[1]
    (tmp_path / src.name).write_bytes(src.read_bytes())
    aborted = tmp_path / "20261012-125423_b9843e0f.json"
    aborted.write_text(json.dumps(_kicked_during_hero_pick()), encoding="utf-8")
    result = loader.load_logs(tmp_path)
    assert result.warnings == []
    assert result.aborted == [aborted]
    assert len(result.logs) == 1
    assert loader.load_log(aborted) == (None, loader.ABORTED_REASON)


def test_aborted_needs_no_turns_no_hero_and_no_placement() -> None:
    assert loader.is_aborted_before_first_turn(_kicked_during_hero_pick())
    with_hero = _kicked_during_hero_pick()
    with_hero["player"]["hero"]["card_id"] = "TB_BaconShop_HERO_34"
    with_turn = _kicked_during_hero_pick()
    with_turn["turns"] = [{"turn": 1}]
    with_placement = _kicked_during_hero_pick()
    with_placement["result"]["placement"] = 8
    for log in (with_hero, with_turn, with_placement):
        assert not loader.is_aborted_before_first_turn(log)
    for path in [*FIXTURES.glob("2026*.json"), FIXTURES / "broken.json"]:
        assert not loader.is_aborted_before_first_turn(json.loads(path.read_text("utf-8")))


def test_unsupported_major_version(tmp_path: Path) -> None:
    p = tmp_path / "v2.json"
    p.write_text(json.dumps({"schema_version": "2.0.0"}), encoding="utf-8")
    log, reason = loader.load_log(p)
    assert log is None
    assert "unsupported schema_version" in (reason or "")


def test_unreadable_file(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{ not json", encoding="utf-8")
    log, reason = loader.load_log(p)
    assert log is None and "unreadable" in (reason or "")


def test_discovers_come_from_events_jsonl(tmp_path: Path) -> None:
    src = sorted(FIXTURES.glob("2026*.json"))[1]
    log = tmp_path / src.name
    log.write_bytes(src.read_bytes())
    events = [
        {"turn": 3, "type": "spell", "card_id": "TB_BaconShop_Triples_01"},
        {"turn": 3, "type": "discover", "card_id": "BG36_764", "source": "triple"},
        {"turn": 5, "type": "discover", "card_id": "BG33_823", "source": "hero_power"},
    ]
    text = "\n".join(json.dumps(e) for e in events) + "\n{ broken line\n"
    loader.events_path(log).write_text(text, encoding="utf-8")
    result = loader.load_logs(tmp_path)
    assert [(e["turn"], e["source"]) for e in result.logs[0]["_discovers"]] == [
        (3, "triple"),
        (5, "hero_power"),
    ]
    # no events file -> no discovers, not an error
    assert loader.read_discovers(tmp_path / "missing.json") == []


def test_fixture_folder_has_real_logs() -> None:
    assert len(list(FIXTURES.glob("2026*.json"))) >= 5


def _v150_log(tmp_path: Path) -> Path:
    """A real fixture upgraded to schema 1.5.0 (hand with stats, shop, lobby, opponent tier)."""
    src = sorted(FIXTURES.glob("2026*.json"))[1]
    data = json.loads(src.read_text(encoding="utf-8"))
    data["schema_version"] = "1.5.0"
    turn = data["turns"][0]
    turn["hand_end_of_shop"] = [
        {
            "card_id": "BG20_GEM",
            "name": "Blood Gem",
            "dbf_id": 1,
            "card_type": "spell",
            "tier": 1,
            "attack": None,
            "health": None,
            "golden": None,
        },
        {
            "card_id": "BG28_633",
            "name": "Felboar",
            "dbf_id": 2,
            "card_type": "minion",
            "tier": 5,
            "attack": 6,
            "health": 7,
            "golden": False,
        },
    ]
    turn["shop_offers"] = [
        {
            "trigger": "turn_start",
            "cards": [
                {
                    "card_id": "BG35_814",
                    "name": "M",
                    "dbf_id": 3,
                    "card_type": "minion",
                    "tier": 1,
                    "attack": 3,
                    "health": 3,
                    "golden": False,
                }
            ],
        },
        {
            "trigger": "reroll",
            "cards": [
                {
                    "card_id": "BG28_518",
                    "name": "Chef's Choice",
                    "dbf_id": 4,
                    "card_type": "spell",
                    "tier": 1,
                    "attack": None,
                    "health": None,
                    "golden": None,
                },
                {
                    "card_id": "BG36_764",
                    "name": "Gearfin",
                    "dbf_id": 5,
                    "card_type": "minion",
                    "tier": 4,
                    "attack": 4,
                    "health": 5,
                    "golden": False,
                },
            ],
        },
    ]
    turn["lobby"] = [
        {
            "player_id": 3,
            "tavern_tier": 2,
            "health": 30,
            "armor": 5,
            "leaderboard_place": 1,
            "eliminated": False,
        },
        {
            "player_id": 4,
            "tavern_tier": 1,
            "health": 0,
            "armor": 0,
            "leaderboard_place": 8,
            "eliminated": True,
        },
    ]
    if turn.get("combat"):
        turn["combat"]["opponent_tavern_tier"] = 2
    path = tmp_path / src.name
    path.write_text(json.dumps(data), encoding="utf-8")
    events = [
        {"turn": 1, "type": "sell", "card_id": "BG35_814", "name": "M", "value": 1},
        {"turn": 1, "type": "sell", "card_id": None, "name": None, "value": 1},
    ]
    loader.events_path(path).write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    return path


def test_schema_150_log_loads_and_normalizes(tmp_path: Path) -> None:
    from hsbg import normalize

    _v150_log(tmp_path)
    result = loader.load_logs(tmp_path)
    assert result.warnings == [] and len(result.logs) == 1
    tables = normalize.normalize(result.logs)
    assert list(tables.hand["card_type"]) == ["spell", "minion"]
    assert tables.hand.iloc[1][["tier", "attack", "health"]].tolist() == [5, 6, 7]
    shop = tables.shop_offers
    assert list(zip(shop["offer"], shop["trigger"], shop["position"], strict=True)) == [
        (1, "turn_start", 1),
        (2, "reroll", 1),
        (2, "reroll", 2),
    ]
    assert list(tables.lobby["eliminated"]) == [False, True]
    assert list(tables.sells["card_id"].fillna("-")) == ["BG35_814", "-"]
    first = tables.combats[tables.combats["turn"] == 1]
    if not first.empty:
        assert first["opponent_tavern_tier"].iloc[0] == 2


def test_older_logs_have_empty_new_tables(load_result: loader.LoadResult) -> None:
    from hsbg import normalize

    tables = normalize.normalize(load_result.logs)
    assert tables.shop_offers.empty and tables.lobby.empty
    assert "opponent_tavern_tier" in tables.combats.columns
