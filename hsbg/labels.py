"""Japanese display labels for enum-like values in the logs (minion types, keywords, results).

Presentation helpers only: metrics.py keeps the English tokens from docs/log-schema.md,
the dashboard and the static report translate them at render time. Unknown tokens are returned
unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable

MINION_TYPES = {
    "beast": "獣",
    "pet": "獣",
    "demon": "悪魔",
    "dragon": "ドラゴン",
    "elemental": "エレメンタル",
    "mechanical": "メカ",
    "mech": "メカ",
    "murloc": "マーロック",
    "pirate": "海賊",
    "quilboar": "キルボア",
    "naga": "ナーガ",
    "undead": "アンデッド",
    "aberration": "異形",
    "totem": "トーテム",
    "all": "全種族",
}

KEYWORDS = {
    "taunt": "挑発",
    "divine_shield": "聖なる盾",
    "poisonous": "猛毒",
    "venomous": "毒袋",
    "reborn": "蘇り",
    "windfury": "疾風",
    "stealth": "隠れ身",
    # schema 1.5.0 (plugin 0.9.0)
    "deathrattle": "断末魔",
    "rally": "勝鬨",
}

PHASES = {"early": "序盤", "mid": "中盤", "late": "終盤"}

# 神祇（global_old_god）の能力。キーは金色を除いたカード ID（BGFYM_000_G -> BGFYM_000）
DEITY_ABILITIES = {
    "BGFYM_000": "目覚めると、自身を除く全ての味方に"
    "自身の攻撃力・体力を分配する（金色は 2 倍を分配）。"
    "神祇が大きいほど盤面全体が強くなる",
    "BGFYM_011": "断末魔: この戦闘で最初に死亡した味方の異形 2 体（金色は 4 体）を"
    "最大攻撃力・体力で召喚する（神祇は除く）。"
    "本体の大きさに加え、先に死ぬ異形の強さが効く",
}
DEITY_ABILITY_DEFAULT = "目覚めたときの能力はカードテキストを参照"


def deity_base_id(card_id: str | None) -> str | None:
    if not card_id:
        return None
    return card_id[:-2] if card_id.endswith("_G") else card_id


def deity_ability(card_id: str | None) -> str:
    return DEITY_ABILITIES.get(deity_base_id(card_id) or "", DEITY_ABILITY_DEFAULT)


RESULTS = {"win": "勝ち", "loss": "負け", "tie": "引き分け"}
STATUS = {"complete": "完了", "incomplete": "未完了"}


def minion_type(token: str | None) -> str:
    if not token:
        return ""
    return MINION_TYPES.get(str(token), str(token))


def minion_types(tokens: Iterable[str] | str | None, sep: str = "・") -> str:
    """List or 'a|b' string of type tokens -> 'ア・イ'."""
    if not tokens:
        return ""
    if isinstance(tokens, str):
        tokens = [t for t in tokens.split("|") if t]
    return sep.join(minion_type(t) for t in tokens)


def phase(token: str | None) -> str:
    if not token:
        return ""
    return PHASES.get(str(token), str(token))


def keyword(token: str | None) -> str:
    if not token:
        return ""
    return KEYWORDS.get(str(token), str(token))


def result(token: str | None) -> str:
    if not token:
        return "-"
    return RESULTS.get(str(token), str(token))


def status(token: str | None) -> str:
    if not token:
        return "-"
    return STATUS.get(str(token), str(token))
