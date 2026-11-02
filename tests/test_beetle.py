"""Beetles (甲虫, schema 1.7.0): Power.log replay, backfill and the turns / combats columns."""

import copy
import json
from pathlib import Path

from hsbg import loader, normalize, powerlog
from hsbg.normalize import Tables

FIXTURES = Path(__file__).parent / "fixtures"

_P = "D 20:00:00.0000000 GameState.DebugPrintPower() - "
_ENCH = (
    "[entityName=Beetle Army Player Enchant [DNT] id={id} zone={zone} zonePos=0 "
    "cardId=BG31_808pe player={p}]"
)


def _l(text: str, indent: int = 4) -> str:
    return _P + " " * indent + text + "\n"


def _turn(n: int) -> str:
    return _l(f"TAG_CHANGE Entity=GameEntity tag=TURN value={n}")


def _buff(entity: str, atk: int, hp: int) -> list[str]:
    return [
        _l(f"TAG_CHANGE Entity={entity} tag=TAG_SCRIPT_DATA_NUM_1 value={atk}"),
        _l(f"TAG_CHANGE Entity={entity} tag=TAG_SCRIPT_DATA_NUM_2 value={hp}"),
    ]


def _block(head: str, tags: dict[str, object]) -> list[str]:
    return [_l(head)] + [_l(f"tag={k} value={v}", 8) for k, v in tags.items()]


def _own_enchant(eid: int) -> list[str]:
    # as in the real log: FULL_ENTITY without a card, SHOW_ENTITY in SETASIDE, then ZONE -> PLAY
    return [
        *_block(f"FULL_ENTITY - Creating ID={eid} CardID=", {"ZONE": "SETASIDE", "CONTROLLER": 5}),
        *_block(
            f"SHOW_ENTITY - Updating Entity={eid} CardID=BG31_808pe",
            {"CONTROLLER": 5, "CARDTYPE": "ENCHANTMENT", "ATTACHED": 14, "ZONE": "SETASIDE"},
        ),
        _l(f"TAG_CHANGE Entity={eid} tag=ZONE value=PLAY"),
    ]


def _opp_copy(eid: int, atk: int, hp: int) -> list[str]:
    # the opponent's enchantment copied onto their player entity for the combat, values included
    return _block(
        f"SHOW_ENTITY - Updating Entity={eid} CardID=BG31_808pe",
        {
            "CONTROLLER": 13,
            "CARDTYPE": "ENCHANTMENT",
            "TAG_SCRIPT_DATA_NUM_1": atk,
            "TAG_SCRIPT_DATA_NUM_2": hp,
            "ATTACHED": 15,
            "ZONE": "PLAY",
        },
    )


def synthetic_power_log() -> list[str]:
    """Three turns. T1: no Beetles anywhere. T2: my enchantment is created in combat (no shop-end
    value) and the opponent's copy grows in combat. T3: mine grows in the shop and in combat; the
    previous combat's copy (now REMOVEDFROMGAME) must not count; the game ends during combat."""
    own = _ENCH.format(id=600, zone="PLAY", p=5)
    old = _ENCH.format(id=700, zone="PLAY", p=13)
    return [
        _l("Player EntityID=14 PlayerID=5 GameAccountId=[hi=1 lo=12345]"),
        _l("Player EntityID=15 PlayerID=13 GameAccountId=[hi=0 lo=0]"),
        _turn(1),
        _turn(2),
        _turn(3),
        _turn(4),
        *_own_enchant(600),
        *_buff("600", 4, 4),
        *_opp_copy(700, 270, 268),
        *_buff(old, 383, 381),
        _l(f"TAG_CHANGE Entity={old} tag=ZONE value=REMOVEDFROMGAME"),
        _turn(5),
        *_buff(own, 40, 38),
        _turn(6),
        *_buff(own, 81, 79),
    ]


def test_parse_beetle_synthetic() -> None:
    b = powerlog.parse_beetle(synthetic_power_log())
    assert sorted(b) == [2, 3]
    t2, t3 = b[2], b[3]
    # created during the T2 combat: no shop-end value, base 2/2 added to the 4/4 buff
    assert (t2.player.attack, t2.player.health) == (None, None)
    assert (t2.player.attack_after_combat, t2.player.health_after_combat) == (6, 6)
    assert (t2.opponent.attack, t2.opponent.health) == (272, 270)
    assert (t2.opponent.attack_after_combat, t2.opponent.health_after_combat) == (385, 383)
    assert (t3.player.attack, t3.player.health) == (42, 40)
    assert (t3.player.attack_after_combat, t3.player.health_after_combat) == (83, 81)
    assert t3.opponent is None


def test_parse_beetle_none() -> None:
    lines = [
        _l("Player EntityID=14 PlayerID=5 GameAccountId=[hi=1 lo=2]"),
        _turn(1),
        _turn(2),
        _turn(3),
    ]
    assert powerlog.parse_beetle(lines) == {}


def _fixture_log() -> dict:
    path = sorted(FIXTURES.glob("20260110-122609_*.json"))[0]
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(log: dict) -> tuple[bool, str | None]:
    errors = loader._Validator().errors(log)
    return not errors, "; ".join(errors) or None


def test_apply_beetle_is_schema_valid() -> None:
    log = _fixture_log()
    version = log["schema_version"]
    original = copy.deepcopy(log)
    filled = powerlog.apply_beetle(log, powerlog.parse_beetle(synthetic_power_log()))
    assert filled == 2
    assert log["schema_version"] == version  # older keys keep their older meaning
    assert powerlog.BEETLE_BACKFILL_NOTE in log["notes"]
    t1, t2, t3 = log["turns"][:3]
    assert list(t2).index("beetle") == list(t2).index("combat") - 1
    assert t1["beetle"] is None and t1["combat"]["opponent_beetle"] is None
    assert t2["beetle"] == {
        "attack": None,
        "health": None,
        "attack_after_combat": 6,
        "health_after_combat": 6,
    }
    assert t2["combat"]["opponent_beetle"]["attack"] == 272
    assert t3["beetle"]["attack"] == 42
    assert powerlog.has_beetle_keys(log) and not powerlog.has_beetle_keys(original)
    ok, reason = _validate(log)
    assert ok, reason
    powerlog.apply_beetle(log, powerlog.parse_beetle(synthetic_power_log()))
    assert log["notes"].count(powerlog.BEETLE_BACKFILL_NOTE) == 1


def test_normalize_beetle_columns(tables: Tables) -> None:
    for col in ("beetle_attack", "beetle_health", "beetle_attack_after", "beetle_health_after"):
        assert col in tables.turns.columns
    for col in ("opponent_beetle_attack", "opponent_beetle_health_after"):
        assert col in tables.combats.columns
    # the fixtures predate schema 1.7.0
    assert tables.turns["beetle_attack"].isna().all()

    log = _fixture_log()
    powerlog.apply_beetle(log, powerlog.parse_beetle(synthetic_power_log()))
    t = normalize.normalize([log])
    turns = t.turns.set_index("turn")
    assert turns.loc[3, "beetle_attack"] == 42
    assert turns.loc[3, "beetle_health_after"] == 81
    combats = t.combats.set_index("turn")
    assert combats.loc[2, "opponent_beetle_attack_after"] == 385
