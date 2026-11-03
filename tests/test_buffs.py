"""'This game' buffs (schema 1.7.0 beetle, 1.8.0 blood gem / tavern spell / tavern minions):
Power.log replay, backfill and the turns / combats columns."""

import copy
import json
import os
from pathlib import Path

from hsbg import charts, loader, metrics, normalize, powerlog, summarize
from hsbg.normalize import Tables

FIXTURES = Path(__file__).parent / "fixtures"

_P = "D 20:00:00.0000000 GameState.DebugPrintPower() - "
_G = "D 20:00:00.0000000 GameState.DebugPrintGame() - "
_ME = "Someone#1234"  # check_private: ok (a made-up BattleTag)
_ENCH = (
    "[entityName=Beetle Army Player Enchant [DNT] id={id} zone=PLAY zonePos=0 "
    "cardId=BG31_808pe player={p}]"
)


def _l(text: str, indent: int = 4) -> str:
    return _P + " " * indent + text + "\n"


def _turn(n: int) -> str:
    return _l(f"TAG_CHANGE Entity=GameEntity tag=TURN value={n}")


def _sd(entity: str, atk: int, hp: int) -> list[str]:
    return [
        _l(f"TAG_CHANGE Entity={entity} tag=TAG_SCRIPT_DATA_NUM_1 value={atk}"),
        _l(f"TAG_CHANGE Entity={entity} tag=TAG_SCRIPT_DATA_NUM_2 value={hp}"),
    ]


def _tags(entity: str, tags: dict[str, int]) -> list[str]:
    return [_l(f"TAG_CHANGE Entity={entity} tag={k} value={v}") for k, v in tags.items()]


def _block(head: str, tags: dict[str, object]) -> list[str]:
    return [_l(head)] + [_l(f"tag={k} value={v}", 8) for k, v in tags.items()]


def _own_enchant(eid: int, card: str = "BG31_808pe") -> list[str]:
    # as in the real log: FULL_ENTITY without a card, SHOW_ENTITY in SETASIDE, then ZONE -> PLAY
    return [
        *_block(f"FULL_ENTITY - Creating ID={eid} CardID=", {"ZONE": "SETASIDE", "CONTROLLER": 5}),
        *_block(
            f"SHOW_ENTITY - Updating Entity={eid} CardID={card}",
            {"CONTROLLER": 5, "CARDTYPE": "ENCHANTMENT", "ATTACHED": 14, "ZONE": "SETASIDE"},
        ),
        _l(f"TAG_CHANGE Entity={eid} tag=ZONE value=PLAY"),
    ]


def _opp_copy(eid: int, card: str, tags: dict[str, int]) -> list[str]:
    # the opponent's value copied onto their player entity for the combat
    return _block(
        f"SHOW_ENTITY - Updating Entity={eid} CardID={card}",
        {"CONTROLLER": 13, "CARDTYPE": "ENCHANTMENT", **tags, "ATTACHED": 15, "ZONE": "PLAY"},
    )


def _header() -> list[str]:
    return [
        *_block(
            "Player EntityID=14 PlayerID=5 GameAccountId=[hi=1 lo=12345]",
            {"CONTROLLER": 5, "CARDTYPE": "PLAYER"},
        ),
        *_block(
            "Player EntityID=15 PlayerID=13 GameAccountId=[hi=0 lo=0]",
            {"CONTROLLER": 13, "CARDTYPE": "PLAYER"},
        ),
        _G + f"PlayerID=5, PlayerName={_ME}\n",
        _G + "PlayerID=13, PlayerName=Bob\n",
    ]


def synthetic_power_log() -> list[str]:
    """Three turns. T1: no Beetles anywhere. T2: my enchantment is created in combat (no shop-end
    value) and the opponent's copy grows in combat. T3: mine grows in the shop and in combat; the
    previous combat's copy (now REMOVEDFROMGAME) must not count; the game ends during combat."""
    own = _ENCH.format(id=600, p=5)
    old = _ENCH.format(id=700, p=13)
    return [
        *_header(),
        _turn(1),
        _turn(2),
        _turn(3),
        _turn(4),
        *_own_enchant(600),
        *_sd("600", 4, 4),
        *_opp_copy(700, "BG31_808pe", {"TAG_SCRIPT_DATA_NUM_1": 270, "TAG_SCRIPT_DATA_NUM_2": 268}),
        *_sd(old, 383, 381),
        _l(f"TAG_CHANGE Entity={old} tag=ZONE value=REMOVEDFROMGAME"),
        _turn(5),
        *_sd(own, 40, 38),
        _turn(6),
        *_sd(own, 81, 79),
    ]


def other_buffs_power_log() -> list[str]:
    """Two turns of Blood Gems, Tavern spells and Tavern minions.
    T1: my gem tags say +3/+2 while the enchantment lags at +1/+1 (seen in a real game), Tavern
    spells +1/+1 (tags only); the opponent's Tavern spells come on the TagTransferPlayerEnchant.
    The opponent's player entity (named Bob here) carries stale gem tags: they must be ignored.
    T2: my Shop Buff is created; the opponent's gem enchantment copy is seen."""
    return [
        *_header(),
        _turn(1),
        *_own_enchant(610, "BG26_159pe"),
        *_sd("610", 1, 1),
        *_tags(_ME, {"BACON_BLOODGEMBUFFATKVALUE": 3, "BACON_BLOODGEMBUFFHEALTHVALUE": 2}),
        *_tags(_ME, {"TAVERN_SPELL_ATTACK_INCREASE": 1, "TAVERN_SPELL_HEALTH_INCREASE": 1}),
        *_tags("Bob", {"BACON_BLOODGEMBUFFATKVALUE": 9, "BACON_BLOODGEMBUFFHEALTHVALUE": 9}),
        _turn(2),
        *_opp_copy(
            710,
            "Bacon_TagTransferPlayerE",
            {"TAVERN_SPELL_ATTACK_INCREASE": 23, "TAVERN_SPELL_HEALTH_INCREASE": 16},
        ),
        *_tags(_ME, {"BACON_BLOODGEMBUFFATKVALUE": 4}),  # grows in combat
        _turn(3),
        *_own_enchant(620, "BG_ShopBuff"),
        *_sd("620", 4, 4),
        _turn(4),
        *_opp_copy(720, "BG26_159pe", {"TAG_SCRIPT_DATA_NUM_1": 6, "TAG_SCRIPT_DATA_NUM_2": 3}),
    ]


def test_parse_beetle_synthetic() -> None:
    b = powerlog.parse_buffs(synthetic_power_log())
    assert sorted(b) == [2, 3]
    t2, t3 = b[2], b[3]
    me2, opp2, me3 = t2.player["beetle"], t2.opponent["beetle"], t3.player["beetle"]
    # created during the T2 combat: no shop-end value, base 2/2 added to the 4/4 buff
    assert (me2.attack, me2.health) == (None, None)
    assert (me2.attack_after_combat, me2.health_after_combat) == (6, 6)
    assert (opp2.attack, opp2.health) == (272, 270)
    assert (opp2.attack_after_combat, opp2.health_after_combat) == (385, 383)
    assert (me3.attack, me3.health) == (42, 40)
    assert (me3.attack_after_combat, me3.health_after_combat) == (83, 81)
    assert "beetle" not in t3.opponent
    assert set(t2.player) == {"beetle"}


def test_parse_other_buffs() -> None:
    b = powerlog.parse_buffs(other_buffs_power_log())
    t1, t2 = b[1], b[2]
    gem = t1.player["blood_gem"]
    # the larger of tags (3/2) and enchantment (1/1), plus the gem's base +1/+1
    assert (gem.attack, gem.health) == (4, 3)
    assert (gem.attack_after_combat, gem.health_after_combat) == (5, 3)
    spell = t1.player["tavern_spell"]
    assert (spell.attack, spell.health, spell.attack_after_combat) == (1, 1, 1)
    assert (t1.opponent["tavern_spell"].attack, t1.opponent["tavern_spell"].health) == (23, 16)
    assert "blood_gem" not in t1.opponent  # stale tags on the opponent's player entity
    assert (t2.player["tavern_minion"].attack, t2.player["tavern_minion"].health) == (4, 4)
    assert (t2.opponent["blood_gem"].attack, t2.opponent["blood_gem"].health) == (7, 4)
    assert "tavern_elemental" not in t2.player


def test_parse_buffs_none() -> None:
    lines = [*_header(), _turn(1), _turn(2), _turn(3)]
    assert powerlog.parse_buffs(lines) == {}


def test_buff_keys_match_normalize() -> None:
    assert powerlog.BUFF_KEYS == normalize.BUFF_KEYS


def _fixture_log() -> dict:
    path = sorted(FIXTURES.glob("20260110-122609_*.json"))[0]
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(log: dict) -> tuple[bool, str | None]:
    errors = loader._Validator().errors(log)
    return not errors, "; ".join(errors) or None


def test_apply_buffs_is_schema_valid() -> None:
    log = _fixture_log()
    version = log["schema_version"]
    original = copy.deepcopy(log)
    assert powerlog.missing_buff_keys(original) == list(powerlog.BUFF_KEYS)
    filled = powerlog.apply_buffs(log, powerlog.parse_buffs(synthetic_power_log()))
    assert filled == 2
    assert log["schema_version"] == version  # older keys keep their older meaning
    assert any(n.startswith(powerlog.BUFF_BACKFILL_NOTE) for n in log["notes"])
    t1, t2, t3 = log["turns"][:3]
    assert list(t2)[-6:] == [*powerlog.BUFF_KEYS, "combat"]
    assert t1["beetle"] is None and t1["combat"]["opponent_beetle"] is None
    assert t2["beetle"] == {
        "attack": None,
        "health": None,
        "attack_after_combat": 6,
        "health_after_combat": 6,
    }
    assert t2["blood_gem"] is None and t2["combat"]["opponent_tavern_spell"] is None
    assert t2["combat"]["opponent_beetle"]["attack"] == 272
    assert t3["beetle"]["attack"] == 42
    assert powerlog.missing_buff_keys(log) == []
    ok, reason = _validate(log)
    assert ok, reason
    notes = list(log["notes"])
    powerlog.apply_buffs(log, powerlog.parse_buffs(synthetic_power_log()))
    assert log["notes"] == notes


def test_apply_buffs_keeps_the_plugins_beetle() -> None:
    # a plugin 0.12.0 log (schema 1.7.0) has beetle only: add the others, keep its beetle values
    log = _fixture_log()
    powerlog.apply_buffs(log, powerlog.parse_buffs(synthetic_power_log()), ["beetle"])
    log["turns"][2]["beetle"]["attack"] = 1000  # pretend the plugin saw something else
    keys = powerlog.missing_buff_keys(log)
    assert keys == [k for k in powerlog.BUFF_KEYS if k != "beetle"]
    powerlog.apply_buffs(log, powerlog.parse_buffs(other_buffs_power_log()), keys)
    t1, t3 = log["turns"][0], log["turns"][2]
    assert t3["beetle"]["attack"] == 1000
    assert t1["blood_gem"]["attack"] == 4
    assert t1["combat"]["opponent_tavern_spell"]["health"] == 16
    assert list(t1)[-6:] == [*powerlog.BUFF_KEYS, "combat"]
    assert list(t1["combat"])[-5:] == [f"opponent_{k}" for k in powerlog.BUFF_KEYS]
    ok, reason = _validate(log)
    assert ok, reason


def test_normalize_buff_columns(tables: Tables) -> None:
    for k in normalize.BUFF_KEYS:
        for s in normalize.BUFF_STATS:
            assert f"{k}_{s}" in tables.turns.columns
            assert f"opponent_{k}_{s}" in tables.combats.columns
    # the fixtures predate schema 1.7.0
    assert tables.turns["beetle_attack"].isna().all()

    log = _fixture_log()
    powerlog.apply_buffs(log, powerlog.parse_buffs(other_buffs_power_log()))
    t = normalize.normalize([log])
    turns = t.turns.set_index("turn")
    assert turns.loc[1, "blood_gem_attack"] == 4
    assert turns.loc[1, "blood_gem_attack_after"] == 5
    assert turns.loc[2, "tavern_minion_health"] == 4
    combats = t.combats.set_index("turn")
    assert combats.loc[1, "opponent_tavern_spell_attack"] == 23


def _buff_log() -> dict:
    log = _fixture_log()
    powerlog.apply_buffs(log, powerlog.parse_buffs(other_buffs_power_log()))
    return log


def test_buffs_by_turn() -> None:
    log = _buff_log()
    t = normalize.normalize([log])
    gid = log["game"]["game_id"]
    df = metrics.buffs_by_turn(t, gid)
    assert list(df.columns) == metrics.BUFF_TURN_COLUMNS
    t1 = df[df["turn"] == 1].iloc[0]
    assert (
        t1["blood_gem_stats"]
        == log["turns"][0]["blood_gem"]["attack"] + log["turns"][0]["blood_gem"]["health"]
    )
    assert t1["opponent_tavern_spell_stats"] == 23 + 16
    assert "blood_gem" in metrics.buff_keys(df, "mine")
    assert "tavern_spell" in metrics.buff_keys(df, "opponent")
    assert "beetle" not in metrics.buff_keys(df)
    assert metrics.buffs_by_turn(t, "no-such-game").empty
    # older logs (no buff keys): nothing to show
    old_t = normalize.normalize([_fixture_log()])
    assert metrics.buff_keys(metrics.buffs_by_turn(old_t, gid)) == []


def test_buff_presentation() -> None:
    log = _buff_log()
    md = summarize.summarize(log)
    assert "## This-game buffs (not on the board)" in md
    assert "| T | My board total | My blood gem |" in md
    assert "Blood gem = what one Blood Gem gives" in md
    assert "Beetle =" not in md  # only the kinds in the game
    t1 = log["turns"][0]["blood_gem"]
    assert f"| {t1['attack']}/{t1['health']} → 5/" in md  # grew in combat
    assert "## This-game buffs" not in summarize.summarize(_fixture_log())

    t = normalize.normalize([log])
    df = metrics.buffs_by_turn(t, log["game"]["game_id"])
    keys = metrics.buff_keys(df)
    fig = charts.buff_growth_line(df, keys)
    names = [tr.name for tr in fig.data]
    assert "自分の血の宝石" in names and "相手の酒場の呪文（戦闘開始時）" in names
    opp = next(tr for tr in fig.data if tr.name == "相手の酒場の呪文（戦闘開始時）")
    assert opp.mode == "markers"
    assert fig.layout.xaxis.range[0] == 0.5  # the whole game, not just the buffed turns
    assert charts.buff_growth_line(df, [], log_y=True).data == ()


_GAME_DETAIL_SCRIPT = """
import os
from pathlib import Path
from hsbg.dashboard import data
from hsbg.dashboard.filters import FilterState
from hsbg.dashboard.views import game_detail
game_detail.render(data.load_context(Path(os.environ["HSBG_LOGS"]), FilterState()))
"""


def test_game_detail_shows_buffs(tmp_path: Path) -> None:
    from streamlit.testing.v1 import AppTest

    log = _buff_log()
    (tmp_path / "game.json").write_text(json.dumps(log), encoding="utf-8")
    os.environ["HSBG_LOGS"] = str(tmp_path)
    try:
        at = AppTest.from_string(_GAME_DETAIL_SCRIPT, default_timeout=60)
        at.run()
        assert not at.exception, [str(e) for e in at.exception]
        at.select_slider[0].set_value(1).run()
        assert not at.exception, [str(e) for e in at.exception]
        texts = [m.value for m in at.markdown]
        assert any(s.startswith("**自分の強化**: 血の宝石 ") for s in texts), texts
        assert any(s.startswith("**相手の強化**: ") and "酒場の呪文 23/16" in s for s in texts)
        assert any("血の宝石＝1 個が与える量" in c.value for c in at.caption)
        columns = list(at.dataframe[0].value.columns)
        assert "blood_gem_attack" in columns and "beetle_attack" not in columns
    finally:
        os.environ.pop("HSBG_LOGS", None)
