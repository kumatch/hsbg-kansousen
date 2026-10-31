"""cards.py: HDT CardDefs -> localized names, skin -> base hero, graceful fallback."""

from pathlib import Path

from conftest import CARDDEFS

from hsbg import cards, labels, normalize
from hsbg.normalize import Tables


def test_load_reads_base_and_locale() -> None:
    names = cards.load(CARDDEFS, "jaJP")
    assert names.available and names.locale == "jaJP"
    assert [p.name for p in names.sources] == ["CardDefs.base.xml", "CardDefs.jaJP.xml"]
    assert names.name("BG36_HERO_002") == "キシックス"
    assert names.name("BG36_110") == "ルンルン"
    assert names.name("NOT_A_CARD", "fallback") == "fallback"
    assert names.name(None, "x") == "x"


def test_skin_resolves_to_base_hero_via_parent_tag() -> None:
    names = cards.load(CARDDEFS, "jaJP")
    assert names.base_id("TB_BaconShop_HERO_76_SKIN_E") == "TB_BaconShop_HERO_76"
    assert names.base_name("TB_BaconShop_HERO_76_SKIN_E") == "アラキア"
    assert names.name("TB_BaconShop_HERO_76_SKIN_E") == "弾嵐のアラキア"
    # not a skin -> itself
    assert names.base_id("BG36_HERO_002") == "BG36_HERO_002"
    # unknown skin id -> regex fallback
    assert names.base_id("BG99_HERO_001_SKIN_Z") == "BG99_HERO_001"
    assert normalize.base_hero_id("TB_BaconShop_HERO_34_SKIN_C") == "TB_BaconShop_HERO_34"


def test_english_locale_uses_base_names() -> None:
    names = cards.load(CARDDEFS, "enUS")
    assert names.name("BG36_HERO_002") == "Kith'ix"
    assert names.base_name("TB_BaconShop_HERO_76_SKIN_E") == "Al'Akir"


def test_missing_folder_is_empty_and_harmless(tmp_path: Path) -> None:
    names = cards.load(tmp_path, "jaJP")
    assert names is cards.EMPTY
    assert not names.available
    assert names.name("BG36_HERO_002", "Kith'ix") == "Kith'ix"
    assert names.base_name("TB_BaconShop_HERO_76_SKIN_E", "Bulletstorm Al'Akir") == (
        "Bulletstorm Al'Akir"
    )
    assert names.base_id("TB_BaconShop_HERO_76_SKIN_E") == "TB_BaconShop_HERO_76"
    log = {"player": {"hero": {"card_id": "BG36_HERO_002", "name": "Kith'ix"}}}
    assert names.localize(log) == log


def test_localize_renames_every_card_ref_without_touching_the_original() -> None:
    names = cards.load(CARDDEFS, "jaJP")
    log = {
        "player": {
            "hero": {"card_id": "TB_BaconShop_HERO_76_SKIN_E", "name": "Bulletstorm Al'Akir"}
        },
        "turns": [
            {
                "board_end_of_shop": [
                    {"card_id": "BG36_110", "name": "Joyous", "minion_types": ["aberration"]}
                ],
                "combat": {"opponent_hero": {"card_id": "BG36_HERO_002", "name": "Kith'ix"}},
            }
        ],
    }
    out = names.localize(log)
    assert out["player"]["hero"]["name"] == "弾嵐のアラキア"  # skin keeps its own (localized) name
    assert out["turns"][0]["board_end_of_shop"][0]["name"] == "ルンルン"
    assert out["turns"][0]["board_end_of_shop"][0]["minion_types"] == ["aberration"]
    assert out["turns"][0]["combat"]["opponent_hero"]["name"] == "キシックス"
    assert log["player"]["hero"]["name"] == "Bulletstorm Al'Akir"


def test_signature_changes_with_locale() -> None:
    ja = cards.load(CARDDEFS, "jaJP").signature()
    en = cards.load(CARDDEFS, "enUS").signature()
    assert ja != en and "CardDefs.jaJP.xml" in ja


def test_tables_use_base_hero_names(tables: Tables) -> None:
    g = tables.games
    row = g[g["hero_card_id"] == "TB_BaconShop_HERO_76_SKIN_E"].iloc[0]
    assert row["hero_name"] == "アラキア"
    assert row["hero_skin_name"] == "Bulletstorm Al'Akir"
    assert row["hero_base_card_id"] == "TB_BaconShop_HERO_76"
    # one base hero id -> exactly one display name
    assert (g.groupby("hero_base_card_id")["hero_name"].nunique() <= 1).all()
    assert (tables.opponents.groupby("hero_base_card_id")["hero_name"].nunique() <= 1).all()
    assert (
        tables.board_minions.loc[tables.board_minions["card_id"] == "BG36_110", "name"]
        .eq("ルンルン")
        .all()
    )


def test_labels() -> None:
    assert labels.minion_types(["beast", "aberration"]) == "獣・異形"
    assert labels.minion_types("pirate|undead", "、") == "海賊、アンデッド"
    assert labels.minion_type("unknown_type") == "unknown_type"
    assert labels.keyword("divine_shield") == "聖なる盾"
    assert labels.result("win") == "勝ち" and labels.result(None) == "-"
    assert labels.status("incomplete") == "未完了"
