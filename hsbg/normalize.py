"""JSON logs -> pandas tables. This is the only place that knows the JSON layout
(docs/log-schema.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from . import cards
from .cards import CardNames, base_hero_id

__all__ = ["Tables", "normalize", "base_hero_id"]


@dataclass
class Tables:
    games: pd.DataFrame
    turns: pd.DataFrame
    combats: pd.DataFrame
    board_minions: pd.DataFrame
    opponents: pd.DataFrame
    discovers: pd.DataFrame  # discover events from events.jsonl (empty when the file is missing)
    # schema 1.5.0 (plugin 0.9.0). Empty for older logs; hand also needs snapshot_hand=true
    hand: pd.DataFrame
    shop_offers: pd.DataFrame
    lobby: pd.DataFrame
    sells: (
        pd.DataFrame
    )  # sell events from events.jsonl; card_id is null before 1.5.0 (1.5.x: null = gold gain)

    def game_ids(self) -> list[str]:
        return self.games["game_id"].tolist()

    def subset(self, game_ids: list[str] | set[str] | pd.Series) -> Tables:
        ids = set(game_ids)
        return Tables(
            games=self.games[self.games["game_id"].isin(ids)].reset_index(drop=True),
            turns=self.turns[self.turns["game_id"].isin(ids)].reset_index(drop=True),
            combats=self.combats[self.combats["game_id"].isin(ids)].reset_index(drop=True),
            board_minions=self.board_minions[self.board_minions["game_id"].isin(ids)].reset_index(
                drop=True
            ),
            opponents=self.opponents[self.opponents["game_id"].isin(ids)].reset_index(drop=True),
            discovers=self.discovers[self.discovers["game_id"].isin(ids)].reset_index(drop=True),
            hand=self.hand[self.hand["game_id"].isin(ids)].reset_index(drop=True),
            shop_offers=self.shop_offers[self.shop_offers["game_id"].isin(ids)].reset_index(
                drop=True
            ),
            lobby=self.lobby[self.lobby["game_id"].isin(ids)].reset_index(drop=True),
            sells=self.sells[self.sells["game_id"].isin(ids)].reset_index(drop=True),
        )


GAME_COLUMNS = [
    "game_id",
    "path",
    "status",
    "started_at",
    "ended_at",
    "duration_sec",
    "hero_card_id",
    "hero_base_card_id",
    "hero_name",
    "hero_skin_name",
    "placement",
    "mmr_before",
    "mmr_after",
    "mmr_delta",
    "total_turns",
    "final_tier",
    "minion_types",
    "anomaly_card_id",
    "anomaly_name",
    "global_old_god_name",
    "lobby_size",
    "plugin_version",
    "hero_choices",
    "hero_rerolled",
]
TURN_COLUMNS = [
    "game_id",
    "turn",
    "tavern_tier",
    "health",
    "armor",
    "gold_available",
    "gold_spent",
    "buys",
    "sells",
    "gold_gained",
    "rerolls",
    "tier_ups",
    "hero_power_uses",
    "spells_played",
    "dark_gifts",
    "board_size",
    "board_attack",
    "board_health",
    "deity_name",
    "deity_attack",
    "deity_health",
    "deity_attack_after",
    "deity_health_after",
    "deity_awakened",
    "deity_golden",
]
COMBAT_COLUMNS = [
    "game_id",
    "turn",
    "opponent_player_id",
    "opponent_hero_card_id",
    "opponent_hero_base_card_id",
    "opponent_hero_name",
    "opponent_hero_skin_name",
    "opponent_health",
    "opponent_armor",
    "opponent_tavern_tier",
    "opponent_board_size",
    "result",
    "damage_dealt",
    "damage_taken",
    "bb_win",
    "bb_tie",
    "bb_loss",
    "bb_avg_damage",
    "opponent_board_attack",
    "opponent_board_health",
    "opponent_deity_attack",
    "opponent_deity_health",
    "opponent_deity_attack_after",
    "opponent_deity_health_after",
    "opponent_deity_awakened",
    "opponent_deity_golden",
]
MINION_COLUMNS = [
    "game_id",
    "turn",
    "side",
    "position",
    "card_id",
    "name",
    "tier",
    "attack",
    "health",
    "golden",
    "keywords",
    "divine_shields",
    "minion_types",
]
OPPONENT_COLUMNS = [
    "game_id",
    "player_id",
    "hero_card_id",
    "hero_base_card_id",
    "hero_name",
    "hero_skin_name",
    "placement",
    "estimated_placement",
    "eliminated_turn",
    "final_tavern_tier",
    "final_health",
]
# discover events (events.jsonl, schema 1.1.0). source = "hero_power" | "triple"
DISCOVER_COLUMNS = ["game_id", "turn", "source", "card_id", "name"]
# schema 1.5.0: cards in my hand at the end of the shop / offered by the shop. card_type =
# "minion" | "spell" | "other"; attack / health / golden only for minions. Older hands have
# card_id and name only.
CARD_COLUMNS = ["card_id", "name", "card_type", "tier", "attack", "health", "golden"]
HAND_COLUMNS = ["game_id", "turn", "position", *CARD_COLUMNS]
# offer = 1-based index of the shop seen that turn; trigger = turn_start | reroll | refill | added
SHOP_COLUMNS = ["game_id", "turn", "offer", "trigger", "position", *CARD_COLUMNS]
# other players at the start of my shop (public leaderboard: tier and HP)
LOBBY_COLUMNS = [
    "game_id",
    "turn",
    "player_id",
    "tavern_tier",
    "health",
    "armor",
    "leaderboard_place",
    "eliminated",
]
SELL_COLUMNS = ["game_id", "turn", "card_id", "name"]


def _ts(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    return pd.Timestamp(datetime.fromisoformat(value))


def _actions(turn: dict[str, Any]) -> dict[str, Any]:
    return turn.get("actions") or {}


def _stat_sum(minions: list[dict[str, Any]] | None, key: str) -> int:
    return sum(int(m.get(key) or 0) for m in minions or [])


def _deity(d: dict[str, Any] | None, prefix: str) -> dict[str, Any]:
    """schema 1.2.0 の deity / opponent_deity。古いログや神祇の無いシーズンは全て None。"""
    d = d or {}
    return {
        f"{prefix}_attack": d.get("attack"),
        f"{prefix}_health": d.get("health"),
        f"{prefix}_attack_after": d.get("attack_after_combat"),
        f"{prefix}_health_after": d.get("health_after_combat"),
        f"{prefix}_awakened": d.get("awakened"),
        # schema 1.3.0。1.2.0 のログはキーが無いので None
        f"{prefix}_golden": d.get("golden"),
    }


def divine_shields(m: dict[str, Any]) -> int:
    """聖なる盾の枚数（schema 1.4.0 の `divine_shields`。闇のパラドックスは 2 枚以上になる）。
    1.3.x 以前のログはキーが無いので、keywords に divine_shield があれば 1 とみなす。"""
    if m.get("divine_shields") is not None:
        return int(m["divine_shields"])
    return 1 if "divine_shield" in (m.get("keywords") or []) else 0


def _card_row(c: dict[str, Any], names: CardNames) -> dict[str, Any]:
    return {
        "card_id": c.get("card_id"),
        "name": names.name(c.get("card_id"), c.get("name")),
        "card_type": c.get("card_type"),
        "tier": c.get("tier"),
        "attack": c.get("attack"),
        "health": c.get("health"),
        "golden": c.get("golden"),
    }


def _minion_rows(
    game_id: str, turn: int, side: str, minions: list[dict[str, Any]], names: CardNames
) -> list[dict]:
    return [
        {
            "game_id": game_id,
            "turn": turn,
            "side": side,
            "position": m.get("position"),
            "card_id": m.get("card_id"),
            "name": names.name(m.get("card_id"), m.get("name")),
            "tier": m.get("tier"),
            "attack": m.get("attack"),
            "health": m.get("health"),
            "golden": bool(m.get("golden")),
            "keywords": "|".join(m.get("keywords") or []),
            "divine_shields": divine_shields(m),
            "minion_types": "|".join(m.get("minion_types") or []),
        }
        for m in minions or []
    ]


def normalize(logs: list[dict[str, Any]], names: CardNames | None = None) -> Tables:
    """Flatten logs into tables.

    `names` localizes card names and resolves hero skins to their base hero (`hero_name` = base
    hero, `hero_skin_name` = what the log says). Default: `cards.default()`.
    """
    names = names if names is not None else cards.default()
    games: list[dict] = []
    turns: list[dict] = []
    combats: list[dict] = []
    minions: list[dict] = []
    opponents: list[dict] = []
    discovers: list[dict] = []
    hand: list[dict] = []
    shop: list[dict] = []
    lobby: list[dict] = []
    sells: list[dict] = []

    for log in logs:
        g = log.get("game") or {}
        p = log.get("player") or {}
        r = log.get("result") or {}
        hero = p.get("hero") or {}
        game_id = g.get("game_id")
        games.append(
            {
                "game_id": game_id,
                "path": log.get("_path"),
                "status": log.get("status"),
                "started_at": _ts(g.get("started_at")),
                "ended_at": _ts(g.get("ended_at")),
                "duration_sec": g.get("duration_sec"),
                "hero_card_id": hero.get("card_id"),
                "hero_base_card_id": names.base_id(hero.get("card_id")),
                "hero_name": names.base_name(hero.get("card_id"), hero.get("name")),
                "hero_skin_name": hero.get("name"),
                "placement": r.get("placement"),
                "mmr_before": r.get("mmr_before"),
                "mmr_after": r.get("mmr_after"),
                "mmr_delta": r.get("mmr_delta"),
                "total_turns": r.get("total_turns"),
                "final_tier": r.get("final_tavern_tier"),
                "minion_types": "|".join(g.get("minion_types") or []),
                "anomaly_card_id": (g.get("anomaly") or {}).get("card_id"),
                "anomaly_name": (g.get("anomaly") or {}).get("name"),
                "global_old_god_name": (g.get("global_old_god") or {}).get("name"),
                "lobby_size": g.get("lobby_size"),
                "plugin_version": (log.get("generator") or {}).get("plugin_version"),
                "hero_choices": "|".join(
                    str(c.get("card_id")) for c in (p.get("hero_choices") or [])
                ),
                "hero_rerolled": p.get("hero_choices_before_reroll") is not None,
            }
        )
        for t in log.get("turns") or []:
            a = _actions(t)
            turn_no = t.get("turn")
            turns.append(
                {
                    "game_id": game_id,
                    "turn": turn_no,
                    "tavern_tier": t.get("tavern_tier"),
                    "health": t.get("health"),
                    "armor": t.get("armor"),
                    "gold_available": t.get("gold_available"),
                    "gold_spent": a.get("gold_spent"),
                    "buys": a.get("buys"),
                    "sells": a.get("sells"),
                    # schema 1.6.0 で追加（売却以外で増えたゴールド）。
                    # 1.5.x 以前はキーが無く None で、sells がこれを含む
                    "gold_gained": a.get("gold_gained"),
                    "rerolls": a.get("rerolls"),
                    "tier_ups": a.get("tier_ups"),
                    "hero_power_uses": a.get("hero_power_uses"),
                    "spells_played": a.get("spells_played"),
                    # schema 1.1.0 で追加（悪夢の発見の回数）。古いログはキーが無いので None
                    "dark_gifts": a.get("dark_gifts"),
                    "board_size": len(t.get("board_end_of_shop") or []),
                    "board_attack": _stat_sum(t.get("board_end_of_shop"), "attack"),
                    "board_health": _stat_sum(t.get("board_end_of_shop"), "health"),
                    "deity_name": names.name(
                        (t.get("deity") or {}).get("card_id"), (t.get("deity") or {}).get("name")
                    )
                    if t.get("deity")
                    else None,
                    **_deity(t.get("deity"), "deity"),
                }
            )
            minions.extend(
                _minion_rows(game_id, turn_no, "player", t.get("board_end_of_shop"), names)
            )
            for i, card in enumerate(t.get("hand_end_of_shop") or [], start=1):
                hand.append(
                    {"game_id": game_id, "turn": turn_no, "position": i, **_card_row(card, names)}
                )
            for n, offer in enumerate(t.get("shop_offers") or [], start=1):
                for i, card in enumerate(offer.get("cards") or [], start=1):
                    shop.append(
                        {
                            "game_id": game_id,
                            "turn": turn_no,
                            "offer": n,
                            "trigger": offer.get("trigger"),
                            "position": i,
                            **_card_row(card, names),
                        }
                    )
            for e in t.get("lobby") or []:
                lobby.append(
                    {
                        "game_id": game_id,
                        "turn": turn_no,
                        "player_id": e.get("player_id"),
                        "tavern_tier": e.get("tavern_tier"),
                        "health": e.get("health"),
                        "armor": e.get("armor"),
                        "leaderboard_place": e.get("leaderboard_place"),
                        "eliminated": bool(e.get("eliminated")),
                    }
                )
            c = t.get("combat")
            if c:
                oh = c.get("opponent_hero") or {}
                bb = c.get("bobs_buddy") or {}
                combats.append(
                    {
                        "game_id": game_id,
                        "turn": turn_no,
                        "opponent_player_id": c.get("opponent_player_id"),
                        "opponent_hero_card_id": oh.get("card_id"),
                        "opponent_hero_base_card_id": names.base_id(oh.get("card_id")),
                        "opponent_hero_name": names.base_name(oh.get("card_id"), oh.get("name")),
                        "opponent_hero_skin_name": oh.get("name"),
                        "opponent_health": c.get("opponent_health"),
                        "opponent_armor": c.get("opponent_armor"),
                        # schema 1.5.0
                        "opponent_tavern_tier": c.get("opponent_tavern_tier"),
                        "opponent_board_size": len(c.get("opponent_board") or []),
                        "result": c.get("result"),
                        "damage_dealt": c.get("damage_dealt"),
                        "damage_taken": c.get("damage_taken"),
                        "bb_win": bb.get("win"),
                        "bb_tie": bb.get("tie"),
                        "bb_loss": bb.get("loss"),
                        "bb_avg_damage": bb.get("avg_damage"),
                        "opponent_board_attack": _stat_sum(c.get("opponent_board"), "attack"),
                        "opponent_board_health": _stat_sum(c.get("opponent_board"), "health"),
                        **_deity(c.get("opponent_deity"), "opponent_deity"),
                    }
                )
                minions.extend(
                    _minion_rows(game_id, turn_no, "opponent", c.get("opponent_board"), names)
                )
        for o in log.get("opponents") or []:
            oh = o.get("hero") or {}
            opponents.append(
                {
                    "game_id": game_id,
                    "player_id": o.get("player_id"),
                    "hero_card_id": oh.get("card_id"),
                    "hero_base_card_id": names.base_id(oh.get("card_id")),
                    "hero_name": names.base_name(oh.get("card_id"), oh.get("name")),
                    "hero_skin_name": oh.get("name"),
                    "placement": o.get("placement"),
                    "estimated_placement": o.get("estimated_placement"),
                    "eliminated_turn": o.get("eliminated_turn"),
                    "final_tavern_tier": o.get("final_tavern_tier"),
                    "final_health": o.get("final_health"),
                }
            )
        for e in log.get("_discovers") or []:
            discovers.append(
                {
                    "game_id": game_id,
                    "turn": e.get("turn"),
                    "source": e.get("source"),
                    "card_id": e.get("card_id"),
                    "name": names.name(e.get("card_id"), e.get("name")),
                }
            )
        for e in log.get("_sells") or []:
            sells.append(
                {
                    "game_id": game_id,
                    "turn": e.get("turn"),
                    "card_id": e.get("card_id"),
                    "name": names.name(e.get("card_id"), e.get("name"))
                    if e.get("card_id")
                    else None,
                }
            )

    games_df = pd.DataFrame(games, columns=GAME_COLUMNS)
    if not games_df.empty:
        games_df = games_df.sort_values("started_at", kind="stable").reset_index(drop=True)
    return Tables(
        games=games_df,
        turns=pd.DataFrame(turns, columns=TURN_COLUMNS),
        combats=pd.DataFrame(combats, columns=COMBAT_COLUMNS),
        board_minions=pd.DataFrame(minions, columns=MINION_COLUMNS),
        opponents=pd.DataFrame(opponents, columns=OPPONENT_COLUMNS),
        discovers=pd.DataFrame(discovers, columns=DISCOVER_COLUMNS),
        hand=pd.DataFrame(hand, columns=HAND_COLUMNS),
        shop_offers=pd.DataFrame(shop, columns=SHOP_COLUMNS),
        lobby=pd.DataFrame(lobby, columns=LOBBY_COLUMNS),
        sells=pd.DataFrame(sells, columns=SELL_COLUMNS),
    )
