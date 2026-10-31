"""Deity (神祇, schema 1.2.0): Power.log replay, backfill, tables, metrics and presentation."""

import copy
import json
from pathlib import Path

import pandas as pd

from hsbg import charts, loader, metrics, normalize, powerlog, summarize
from hsbg.normalize import Tables

FIXTURES = Path(__file__).parent / "fixtures"

_P = "D 20:00:00.0000000 GameState.DebugPrintPower() - "
_SIGIL = "[entityName=Secret Deity [DNT] id={id} zone={zone} zonePos=0 cardId=BG_OldGod player={p}]"


def _l(text: str, indent: int = 4) -> str:
    return _P + " " * indent + text + "\n"


def _turn(n: int) -> str:
    return _l(f"TAG_CHANGE Entity=GameEntity tag=TURN value={n}")


def _stats(entity: str, atk: int, hp: int) -> list[str]:
    return [
        _l(f"TAG_CHANGE Entity={entity} tag=BACON_EVOLUTION_CARD_OVERWRITE_ATK value={atk}"),
        _l(f"TAG_CHANGE Entity={entity} tag=BACON_EVOLUTION_CARD_OVERWRITE_HEALTH value={hp}"),
    ]


def _create(eid: int, card: str, tags: dict[str, object], show: bool = False) -> list[str]:
    head = (
        f"SHOW_ENTITY - Updating Entity={eid} CardID={card}"
        if show
        else f"FULL_ENTITY - Creating ID={eid} CardID={card}"
    )
    return [_l(head)] + [_l(f"tag={k} value={v}", 8) for k, v in tags.items()]


def _opp_copy(eid: int) -> list[str]:
    # created in SETASIDE under our controller, then handed to the opponent (as in the real log)
    return _create(
        eid,
        "BG_OldGod",
        {
            "CONTROLLER": 5,
            "CARDTYPE": "SPELL",
            "ZONE": "SETASIDE",
            "BACON_EVOLUTION_CARD_ID": 130610,
        },
    ) + [
        _l(
            f"TAG_CHANGE Entity={_SIGIL.format(id=eid, zone='SETASIDE', p=5)} "
            "tag=CONTROLLER value=13"
        )
    ]


def synthetic_power_log() -> list[str]:
    """Two turns. T1: nobody awakens. T2: both awaken, mine grows in combat, the opponent's copy is
    zeroed at cleanup, and the game ends during that combat."""
    own = _SIGIL.format(id=445, zone="SECRET", p=5)
    lines = [
        _l("Player EntityID=14 PlayerID=5 GameAccountId=[hi=1 lo=12345]"),
        _l("Player EntityID=15 PlayerID=13 GameAccountId=[hi=0 lo=0]"),
        _turn(1),
        *_create(
            445,
            "BG_OldGod",
            {
                "CONTROLLER": 5,
                "CARDTYPE": "SPELL",
                "ZONE": "SECRET",
                "BACON_EVOLUTION_CARD_ID": 130610,
            },
        ),
        *_stats("445", 3, 3),
        _turn(2),
        *_opp_copy(558),
        *_stats("558", 1, 1),
        _turn(3),
        *_stats(own, 7, 15),
        _turn(4),
        *_opp_copy(900),
        *_stats("900", 16, 22),
        *_create(950, "", {"ZONE": "SETASIDE", "CONTROLLER": 13}),
        *_create(
            950, "BGFYM_000", {"CONTROLLER": 13, "CARDTYPE": "MINION", "CREATOR": 900}, show=True
        ),
        *_stats("900", 20, 24),
        *_create(960, "BGFYM_000", {"CONTROLLER": 5, "CARDTYPE": "MINION", "CREATOR": 445}),
        *_create(961, "BGFYM_000", {"CONTROLLER": 5, "CARDTYPE": "MINION", "CREATOR": 445}),
        *_create(970, "BG36_110", {"CONTROLLER": 5, "CARDTYPE": "MINION", "CREATOR": 20163}),
        *_stats(own, 41, 69),
        *_stats("900", 0, 0),
    ]
    return lines


def test_parse_deity_synthetic() -> None:
    d = powerlog.parse_deity(synthetic_power_log())
    assert sorted(d) == [1, 2]
    t1, t2 = d[1], d[2]
    assert (t1.player.attack, t1.player.health) == (3, 3)
    assert (t1.player.attack_after_combat, t1.player.health_after_combat) == (3, 3)
    assert t1.player.awakened is False
    assert (t1.opponent.attack, t1.opponent.health, t1.opponent.awakened) == (1, 1, False)
    assert t1.player.dbf_id == 130610

    assert (t2.player.attack, t2.player.health) == (7, 15)
    assert (t2.player.attack_after_combat, t2.player.health_after_combat) == (41, 69)
    assert t2.player.awakened is True
    # opponent's copy: first non-zero at combat start, last non-zero before the cleanup zeroes it
    assert (t2.opponent.attack, t2.opponent.health) == (16, 22)
    assert (t2.opponent.attack_after_combat, t2.opponent.health_after_combat) == (20, 24)
    assert t2.opponent.awakened is True


def test_parse_deity_no_deity_season() -> None:
    lines = [
        _l("Player EntityID=14 PlayerID=5 GameAccountId=[hi=1 lo=2]"),
        _turn(1),
        _turn(2),
        _turn(3),
    ]
    assert powerlog.parse_deity(lines) == {}


def _fixture_log() -> dict:
    path = sorted(FIXTURES.glob("20260110-122609_*.json"))[0]
    return json.loads(path.read_text(encoding="utf-8"))


def test_apply_deity_is_schema_valid() -> None:
    log = _fixture_log()
    log["game"]["global_old_god"] = {"card_id": "BGFYM_000", "name": "C'Thun", "dbf_id": 130610}
    filled = powerlog.apply_deity(log, powerlog.parse_deity(synthetic_power_log()))
    assert filled == 2
    assert log["schema_version"] == "1.3.0"
    assert powerlog.BACKFILL_NOTE in log["notes"]
    t1, t2, t3 = log["turns"][:3]
    assert list(t1).index("deity") == list(t1).index("combat") - 1
    assert t2["deity"]["name"] == "C'Thun"
    assert t2["deity"]["attack_after_combat"] == 41
    assert t2["combat"]["opponent_deity"]["attack"] == 16
    assert t3["deity"] is None and t3["combat"]["opponent_deity"] is None
    assert powerlog.has_deity_keys(log)
    ok, reason = _validate(log)
    assert ok, reason
    # idempotent note
    powerlog.apply_deity(log, powerlog.parse_deity(synthetic_power_log()))
    assert log["notes"].count(powerlog.BACKFILL_NOTE) == 1


def _validate(log: dict) -> tuple[bool, str | None]:
    errors = loader._Validator().errors(log)
    return not errors, "; ".join(errors) or None


def test_old_logs_have_no_deity_keys(complete_logs: list[dict]) -> None:
    assert not any(powerlog.has_deity_keys(g) for g in complete_logs)


def _deity_tables() -> tuple[dict, Tables]:
    log = _fixture_log()
    log["game"]["global_old_god"] = {"card_id": "BGFYM_000", "name": "C'Thun", "dbf_id": 130610}
    powerlog.apply_deity(log, powerlog.parse_deity(synthetic_power_log()))
    return log, normalize.normalize([log])


def test_normalize_deity_columns(tables: Tables) -> None:
    for col in ("deity_attack", "deity_awakened", "board_attack", "board_health"):
        assert col in tables.turns.columns
    assert "opponent_deity_attack" in tables.combats.columns
    # fixtures predate 1.2.0: no Deity values, but board totals are computed
    assert tables.turns["deity_attack"].isna().all()
    assert (tables.turns["board_attack"] >= 0).all()

    log, t = _deity_tables()
    row = t.turns[t.turns["turn"] == 2].iloc[0]
    assert (row["deity_attack"], row["deity_attack_after"], row["deity_awakened"]) == (7, 41, True)
    c = t.combats[t.combats["turn"] == 2].iloc[0]
    assert (c["opponent_deity_attack"], c["opponent_deity_awakened"]) == (16, True)


def test_deity_by_turn_and_game_stats(tables: Tables) -> None:
    gid = tables.games["game_id"].iloc[0]
    # no Deity data (no aberration in the lobby / old log): board totals only
    no_deity = metrics.deity_by_turn(tables, gid)
    assert not no_deity.empty
    assert no_deity["deity_stats"].isna().all()
    assert no_deity["board_stats"].notna().any()
    assert metrics.deity_by_turn(tables, "no-such-game").empty
    assert metrics.deity_game_stats(tables).empty

    log, t = _deity_tables()
    gid = log["game"]["game_id"]
    df = metrics.deity_by_turn(t, gid)
    assert list(df.columns) == metrics.DEITY_TURN_COLUMNS
    t2 = df[df["turn"] == 2].iloc[0]
    assert t2["deity_stats"] == 22 and t2["deity_stats_after"] == 110
    assert t2["deity_growth_shop"] == 22 - 6  # 7/15 at T2 shop end vs 3/3 after the T1 combat
    assert t2["deity_growth_combat"] == 110 - 22
    assert t2["opponent_deity_stats"] == 38
    assert pd.isna(df[df["turn"] == 3].iloc[0]["deity_stats"])

    g = metrics.deity_game_stats(t)
    assert len(g) == 1
    row = g.iloc[0]
    assert row["first_awaken_turn"] == 2 and row["awakened_combats"] == 1
    assert (row["final_deity_attack"], row["final_deity_health"]) == (41, 69)
    by_deity = metrics.deity_stats(t)
    assert by_deity.iloc[0]["games"] == 1


def test_deity_presentation() -> None:
    log, t = _deity_tables()
    md = summarize.summarize(log)
    assert "## Deity (C'Thun)" in md
    assert "| 2 | 7/15 | 41/69 | yes |" in md
    moments = metrics.key_moments(log, lang="en")
    assert any("awakened for the first time" in m for m in moments)
    fig = charts.deity_growth_line(metrics.deity_by_turn(t, log["game"]["game_id"]), log_y=True)
    assert len(fig.data) == 4
    assert fig.layout.yaxis.type == "log"
    # games without Deity data keep the old summary, and the chart shows the two board totals only
    old = _fixture_log()
    assert "## Deity" not in summarize.summarize(old)
    old_t = normalize.normalize([old])
    fig = charts.deity_growth_line(metrics.deity_by_turn(old_t, old["game"]["game_id"]))
    assert [tr.name for tr in fig.data] == ["自分の盤面合計", "相手の盤面合計"]
    assert fig.layout.title.text.startswith("盤面ステータス")
    assert charts.deity_growth_line(pd.DataFrame(columns=metrics.DEITY_TURN_COLUMNS)).data == ()


def test_apply_does_not_touch_input_copy() -> None:
    log = _fixture_log()
    before = copy.deepcopy(log)
    powerlog.apply_deity(copy.deepcopy(log), powerlog.parse_deity(synthetic_power_log()))
    assert log == before


_GAME_DETAIL_SCRIPT = """
import os
from pathlib import Path
from hsbg.dashboard import data
from hsbg.dashboard.filters import FilterState
from hsbg.dashboard.views import game_detail
game_detail.render(data.load_context(Path(os.environ["HSBG_LOGS"]), FilterState()))
"""


def test_game_detail_renders_deity(tmp_path: Path) -> None:
    import os

    from streamlit.testing.v1 import AppTest

    log, _ = _deity_tables()
    out = tmp_path / "2026" / "09"
    out.mkdir(parents=True)
    (out / "20260925-192636_deity.json").write_text(json.dumps(log), encoding="utf-8")
    os.environ["HSBG_LOGS"] = str(tmp_path)
    at = AppTest.from_string(_GAME_DETAIL_SCRIPT, default_timeout=60)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    assert [c.label for c in at.checkbox] == ["グラフを対数目盛にする"]
    at.checkbox[0].check().run()
    assert not at.exception, [str(e) for e in at.exception]
    # last turn (14) has no Deity reading in the synthetic log; pick T2 on the slider
    at.select_slider[0].set_value(2).run()
    assert not at.exception, [str(e) for e in at.exception]
    assert any("自分のクトゥーン" in m.value for m in at.markdown)
    assert any("相手のクトゥーン" in m.value for m in at.markdown)


# ---------------------------------------------------------------- golden (schema 1.3.0) / Y'Shaarj


def _golden_power_log() -> list[str]:
    """Same game, but my Deity awakens golden in T2 (Mask of Ancient Ones)."""
    return [
        line.replace("CardID=BGFYM_000\n", "CardID=BGFYM_000_G\n") if "ID=96" in line else line
        for line in synthetic_power_log()
    ]


def test_parse_deity_golden() -> None:
    plain = powerlog.parse_deity(synthetic_power_log())
    assert plain[2].player.golden is False and plain[2].opponent.golden is False
    assert plain[1].player.golden is None  # did not awaken -> unknown
    gold = powerlog.parse_deity(_golden_power_log())
    assert gold[2].player.golden is True
    assert gold[2].opponent.golden is False


def test_apply_golden_keeps_plugin_values() -> None:
    # a 1.2.0 log written by plugin 0.6.0: deity values present, `golden` missing
    log = _fixture_log()
    log["game"]["global_old_god"] = {"card_id": "BGFYM_000", "name": "C'Thun", "dbf_id": 130610}
    powerlog.apply_deity(log, powerlog.parse_deity(synthetic_power_log()))
    log["schema_version"] = "1.2.0"
    log["notes"] = []
    for t in log["turns"]:
        for d in (t.get("deity"), (t.get("combat") or {}).get("opponent_deity")):
            if d:
                d.pop("golden")
                d["attack"] += 1000  # pretend the plugin saw something else: must be kept
    assert powerlog.needs_golden(log)
    assert powerlog.apply_golden(log, powerlog.parse_deity(_golden_power_log())) == 1
    t1, t2 = log["turns"][:2]
    assert t2["deity"]["golden"] is True and t2["deity"]["attack"] == 1007
    assert t2["combat"]["opponent_deity"]["golden"] is False
    assert t1["deity"]["golden"] is False
    assert log["schema_version"] == "1.3.0"
    assert log["notes"] == [powerlog.GOLDEN_BACKFILL_NOTE]
    assert not powerlog.needs_golden(log)
    ok, reason = _validate(log)
    assert ok, reason


def test_golden_and_yshaarj_presentation() -> None:
    from hsbg import labels

    log = _fixture_log()
    log["game"]["global_old_god"] = {"card_id": "BGFYM_000", "name": "C'Thun", "dbf_id": 130610}
    powerlog.apply_deity(log, powerlog.parse_deity(_golden_power_log()))
    md = summarize.summarize(log)
    assert "| 2 | 7/15 | 41/69 | yes (golden) |" in md
    assert "splits its Attack/Health" in md
    assert any("awakened golden" in m for m in metrics.key_moments(log, lang="en"))
    t = normalize.normalize([log])
    df = metrics.deity_by_turn(t, log["game"]["game_id"])
    assert bool(df[df["turn"] == 2].iloc[0]["deity_golden"])
    fig = charts.deity_growth_line(df)
    assert "star" in list(fig.data[0].marker.symbol)
    assert metrics.deity_game_stats(t).iloc[0]["golden_awakenings"] == 1

    # Y'Shaarj: same records, different ability text
    for tr in log["turns"]:
        if tr.get("deity"):
            tr["deity"]["card_id"], tr["deity"]["name"] = "BGFYM_011", "Y'Shaarj"
    md = summarize.summarize(log)
    assert "## Deity (Y'Shaarj)" in md and "resummons the first 2 friendly Aberrations" in md
    assert "召喚する" in labels.deity_ability("BGFYM_011_G")
    assert "分配" in labels.deity_ability("BGFYM_000")
    assert labels.deity_ability(None) == labels.DEITY_ABILITY_DEFAULT


def test_golden_sigil_card_before_awakening() -> None:
    """Mask of Ancient Ones switches the sigil's card to the golden version (C'Thun 130610 ->
    134633) before it ever awakens golden; the backfill names it BGFYM_000_G and marks it golden."""
    lines = []
    for line in synthetic_power_log():
        lines.append(line)
        if "TURN value=3" in line:  # bought the Mask in the T2 shop
            lines.append(_l("TAG_CHANGE Entity=445 tag=BACON_EVOLUTION_CARD_ID value=134633"))
    d = powerlog.parse_deity(lines)
    assert d[1].player.dbf_id == 130610 and d[2].player.dbf_id == 134633
    log = _fixture_log()
    log["game"]["global_old_god"] = {"card_id": "BGFYM_000", "name": "C'Thun", "dbf_id": 130610}
    powerlog.apply_deity(log, d)
    t1, t2 = log["turns"][:2]
    assert (t1["deity"]["card_id"], t1["deity"]["golden"]) == ("BGFYM_000", False)
    assert (t2["deity"]["card_id"], t2["deity"]["name"], t2["deity"]["golden"]) == (
        "BGFYM_000_G",
        "C'Thun",
        True,
    )
    # a 1st-backfill record with the golden dbf but no name is repaired by apply_golden
    t2["deity"].update(card_id=None, name=None)
    del t2["deity"]["golden"]
    assert powerlog.needs_golden(log)
    powerlog.apply_golden(log, d)
    assert (t2["deity"]["card_id"], t2["deity"]["golden"]) == ("BGFYM_000_G", True)
    assert not powerlog.needs_golden(log)


def test_opponent_card_survives_cleanup_reset() -> None:
    """Y'Shaarj lobby: the cleanup resets the opponent's copy to 0 and then to C'Thun (130610);
    the recorded card must be the one it held during the combat."""
    lines = [
        line.replace("BACON_EVOLUTION_CARD_ID value=130610", "BACON_EVOLUTION_CARD_ID value=132532")
        for line in synthetic_power_log()
    ]
    for eid in (558, 900):
        idx = max(i for i, x in enumerate(lines) if f"Entity={eid} " in x)
        lines[idx + 1 : idx + 1] = [
            _l(f"TAG_CHANGE Entity={eid} tag=BACON_EVOLUTION_CARD_ID value=0"),
            _l(f"TAG_CHANGE Entity={eid} tag=BACON_EVOLUTION_CARD_ID value=130610"),
        ]
    d = powerlog.parse_deity(lines)
    assert d[1].opponent.dbf_id == 132532 and d[2].opponent.dbf_id == 132532
    log = _fixture_log()
    log["game"]["global_old_god"] = {"card_id": "BGFYM_011", "name": "Y'Shaarj", "dbf_id": 132532}
    powerlog.apply_deity(log, d)
    od = log["turns"][1]["combat"]["opponent_deity"]
    assert (od["card_id"], od["golden"]) == ("BGFYM_011", False)
