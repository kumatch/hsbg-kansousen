"""Read the Deity (神祇, e.g. C'Thun) stats out of a saved Power.log
(docs/log-schema.md §turns[].deity).

The plugin records the Deity from v0.6.0 on. Older games only have it in `<name>.power.log(.gz)`,
so `hsbg backfill-deity` replays the log with this module and writes the same keys.

How the Deity shows up in Power.log (checked on 2026-09-26 logs, HDT 1.58.3):
- Each player has a "Secret Deity [DNT]" sigil (`BG_OldGod`) in the SECRET zone. Its
  `BACON_EVOLUTION_CARD_OVERWRITE_ATK/HEALTH` tags are the Deity's current total stats and
  `BACON_EVOLUTION_CARD_ID` is the Deity's dbfId. The local player's sigil lives all game.
- The combat opponent's sigil is copied into every combat (a new `BG_OldGod` entity created with
  our controller and switched to theirs right away), so it is only readable during that combat.
- When a Deity awakens in combat, a minion is created with `CREATOR` = the sigil (plus a transient
  copy). No such minion is created in combats where it does not awaken.
- Golden (Mask of Ancient Ones): the sigil's `BACON_EVOLUTION_CARD_ID` switches to the golden card
  (C'Thun 130610 -> 134633 `BGFYM_000_G`, Y'Shaarj 132532 -> 134634 `BGFYM_011_G`) as soon as the
  trinket is taken, and the awakened minion's CardID ends in `_G`.
- `GameEntity TURN` is 2n-1 in the shop of turn n and 2n in its combat.
"""

from __future__ import annotations

import gzip
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

SIGIL_CARD_ID = "BG_OldGod"

_TURN = re.compile(r"TAG_CHANGE Entity=GameEntity tag=TURN value=(\d+)")
_PLAYER = re.compile(r"Player EntityID=\d+ PlayerID=(\d+) GameAccountId=\[hi=(\d+)")
_CREATE = re.compile(
    r"(?:FULL_ENTITY - Creating ID|SHOW_ENTITY - Updating Entity)=(\d+) CardID=(\S*)"
)
_BLOCK_TAG = re.compile(r"\) -\s+tag=(\S+) value=(\S+)\s*$")
_TAG_CHANGE = re.compile(r"TAG_CHANGE Entity=(\[.*?\bid=(\d+) .*?\]|\d+) tag=(\S+) value=(\S+)")

_WATCHED = {
    "CONTROLLER",
    "CARDTYPE",
    "CREATOR",
    "BACON_EVOLUTION_CARD_ID",
    "BACON_EVOLUTION_CARD_OVERWRITE_ATK",
    "BACON_EVOLUTION_CARD_OVERWRITE_HEALTH",
    "PREMIUM",
}


@dataclass
class DeitySide:
    """One player's Deity in one turn (same keys as docs/log-schema.md `deity`)."""

    dbf_id: int | None = None
    attack: int | None = None
    health: int | None = None
    attack_after_combat: int | None = None
    health_after_combat: int | None = None
    awakened: bool | None = None
    # awakened as a golden minion (None when it did not awaken). The JSON `golden` also counts a
    # golden sigil card (see _deity_json), which is known before it awakens
    golden: bool | None = None


@dataclass
class DeityTurn:
    turn: int
    player: DeitySide | None = None
    opponent: DeitySide | None = None


@dataclass
class _Entity:
    card_id: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    created_in: int = 0  # GameEntity TURN at creation

    def int_tag(self, name: str) -> int | None:
        v = self.tags.get(name)
        return int(v) if v is not None and v.lstrip("-").isdigit() else None


def open_power_log(path: Path) -> Iterator[str]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:  # type: ignore[operator]
        yield from f


def power_log_for(json_path: Path) -> Path | None:
    """`<name>.json` -> `<name>.power.log.gz` or `<name>.power.log`, if present."""
    base = json_path.with_suffix("")
    for suffix in (".power.log.gz", ".power.log"):
        p = base.with_name(base.name + suffix)
        if p.exists():
            return p
    return None


class _Replay:
    def __init__(self) -> None:
        self.entities: dict[int, _Entity] = {}
        self.local_player: int | None = None
        self.turn_tag = 0
        self.turns: dict[int, DeityTurn] = {}
        self._block: _Entity | None = None

    # -------------------------------------------------------------- state
    def _sigils(self, controller: int) -> list[_Entity]:
        return [
            e
            for e in self.entities.values()
            if e.card_id == SIGIL_CARD_ID and e.int_tag("CONTROLLER") == controller
        ]

    def _own_sigil(self) -> _Entity | None:
        if self.local_player is None:
            return None
        # the persistent sigil is created straight into SECRET; the combat copy of the opponent's
        # sigil is created in SETASIDE and carries our controller for a moment, so skip it
        own = [e for e in self._sigils(self.local_player) if e.tags.get("_zone0") == "SECRET"]
        return min(own, key=lambda e: e.int_tag("ENTITY_ID") or 0, default=None)

    def _side(self, sigil: _Entity) -> DeitySide:
        return DeitySide(
            dbf_id=sigil.int_tag("BACON_EVOLUTION_CARD_ID"),
            attack=sigil.int_tag("BACON_EVOLUTION_CARD_OVERWRITE_ATK"),
            health=sigil.int_tag("BACON_EVOLUTION_CARD_OVERWRITE_HEALTH"),
        )

    def _turn(self, n: int) -> DeityTurn:
        return self.turns.setdefault(n, DeityTurn(turn=n))

    # -------------------------------------------------------------- transitions
    def _on_turn_change(self, new: int) -> None:
        old = self.turn_tag
        self.turn_tag = new
        if new % 2 == 0 and new > 0:  # shop of turn new/2 ends, its combat starts
            sigil = self._own_sigil()
            if sigil is not None:
                self._turn(new // 2).player = self._side(sigil)
        if old % 2 == 0 and old > 0:  # combat of turn old/2 is over
            self._close_combat(old)

    def _close_combat(self, combat_tag: int) -> None:
        rec = self._turn(combat_tag // 2)
        me = self.local_player
        sigil = self._own_sigil()
        if rec.player is not None and sigil is not None:
            rec.player.attack_after_combat = sigil.int_tag("BACON_EVOLUTION_CARD_OVERWRITE_ATK")
            rec.player.health_after_combat = sigil.int_tag("BACON_EVOLUTION_CARD_OVERWRITE_HEALTH")
        sigil_ids = {i for i, e in self.entities.items() if e.card_id == SIGIL_CARD_ID}
        awakened: set[int] = set()
        golden: set[int] = set()
        for e in self.entities.values():
            if e.created_in != combat_tag or e.tags.get("CARDTYPE") != "MINION":
                continue
            if e.int_tag("CREATOR") in sigil_ids:
                controller = e.int_tag("CONTROLLER")
                if controller is not None:
                    awakened.add(controller)
                    if e.card_id.endswith("_G") or (e.int_tag("PREMIUM") or 0) > 0:
                        golden.add(controller)
        if rec.player is not None and me is not None:
            rec.player.awakened = me in awakened
            rec.player.golden = (me in golden) if me in awakened else None
        # the opponent's sigil copy created in this combat
        copies = [
            e
            for e in self.entities.values()
            if e.card_id == SIGIL_CARD_ID
            and e.created_in == combat_tag
            and e.int_tag("CONTROLLER") not in (None, me)
        ]
        if copies:
            copy = max(copies, key=lambda e: e.int_tag("ENTITY_ID") or 0)
            opp = copy.tags.get("_first_atk"), copy.tags.get("_first_health")
            rec.opponent = DeitySide(
                dbf_id=copy.int_tag("_first_dbf"),
                attack=int(opp[0]) if opp[0] else None,
                health=int(opp[1]) if opp[1] else None,
                attack_after_combat=copy.int_tag("_last_atk"),
                health_after_combat=copy.int_tag("_last_health"),
                awakened=copy.int_tag("CONTROLLER") in awakened,
                golden=(copy.int_tag("CONTROLLER") in golden)
                if copy.int_tag("CONTROLLER") in awakened
                else None,
            )

    # -------------------------------------------------------------- lines
    def feed(self, line: str) -> None:
        if self._block is not None:
            m = _BLOCK_TAG.search(line)
            if m:
                self._set(self._block, m.group(1), m.group(2), in_block=True)
                return
            self._block = None
        if "PlayerID=" in line and self.local_player is None:
            m = _PLAYER.search(line)
            if m and m.group(2) != "0":
                self.local_player = int(m.group(1))
                return
        m = _CREATE.search(line)
        if m:
            eid = int(m.group(1))
            e = self.entities.get(eid)
            if e is None:
                e = _Entity(created_in=self.turn_tag)
                e.tags["ENTITY_ID"] = str(eid)
                self.entities[eid] = e
            if m.group(2):
                e.card_id = m.group(2)
            self._block = e
            return
        if "TAG_CHANGE" not in line:
            return
        m = _TURN.search(line)
        if m:
            self._on_turn_change(int(m.group(1)))
            return
        m = _TAG_CHANGE.search(line)
        if m:
            tag = m.group(3)
            if tag not in _WATCHED:
                return
            eid = int(m.group(2) or m.group(1))
            e = self.entities.get(eid)
            if e is not None:
                self._set(e, tag, m.group(4), in_block=False)

    def _set(self, e: _Entity, tag: str, value: str, *, in_block: bool) -> None:
        if in_block and tag == "ZONE":
            e.tags.setdefault("_zone0", value)
        if tag not in _WATCHED:
            return
        e.tags[tag] = value
        if e.card_id == SIGIL_CARD_ID and tag.startswith("BACON_EVOLUTION_CARD_OVERWRITE_"):
            suffix = "atk" if tag.endswith("_ATK") else "health"
            if value != "0":
                # the combat copy is zeroed when the combat is cleaned up, so keep what it last held
                e.tags.setdefault("_first_" + suffix, value)
                e.tags["_last_" + suffix] = value
        if e.card_id == SIGIL_CARD_ID and tag == "BACON_EVOLUTION_CARD_ID" and value != "0":
            # the cleanup also resets the copy's card: 0, then C'Thun (130610) whatever the Deity
            # was (seen in Y'Shaarj games), so the opponent's Deity is the first card it held
            e.tags.setdefault("_first_dbf", value)

    def finish(self) -> dict[int, DeityTurn]:
        if self.turn_tag % 2 == 0 and self.turn_tag > 0:
            self._close_combat(self.turn_tag)
        return dict(sorted(self.turns.items()))


def parse_deity(lines: Iterable[str]) -> dict[int, DeityTurn]:
    """Per-turn Deity stats for the local player and the combat opponent.

    Empty when the game has no Deity (seasons without Old Gods) or the log is truncated before
    the first sigil.
    """
    replay = _Replay()
    for line in lines:
        replay.feed(line)
    return {n: t for n, t in replay.finish().items() if t.player or t.opponent}


# ---------------------------------------------------------------- backfill (hsbg backfill-deity)

BACKFILL_NOTE = "deity backfilled from power.log"
GOLDEN_BACKFILL_NOTE = "deity golden backfilled from power.log"
DEITY_SCHEMA_VERSION = "1.3.0"


def _version_tuple(v: str | None) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return (0,)


def has_deity_keys(log: dict) -> bool:
    """True when the log already has 1.2.0 deity keys (plugin v0.6.0+ or an earlier backfill)."""
    return any("deity" in t for t in log.get("turns") or [])


def _deity_records(log: dict) -> list[tuple[int, str, dict]]:
    out = []
    for t in log.get("turns") or []:
        if t.get("deity"):
            out.append((t.get("turn"), "player", t["deity"]))
        od = (t.get("combat") or {}).get("opponent_deity")
        if od:
            out.append((t.get("turn"), "opponent", od))
    return out


def needs_golden(log: dict) -> bool:
    """True for 1.2.0 deity records without the 1.3.0 `golden` key (plugin 0.6.0 / 1st backfill),
    or with a golden sigil card the 1st backfill could not name (card_id null, dbf_id set)."""
    return any(
        "golden" not in d or (d.get("card_id") is None and d.get("dbf_id") is not None)
        for _, _, d in _deity_records(log)
    )


def _deity_card(dbf_id: int | None, god: dict) -> tuple[str | None, str | None, bool]:
    """(card_id, name, golden) for a sigil's BACON_EVOLUTION_CARD_ID. The lobby shares one Deity
    (`game.global_old_god`), so any other dbf is its golden version (Mask of Ancient Ones)."""
    if dbf_id is None or not god.get("card_id"):
        return None, None, False
    if dbf_id == god.get("dbf_id"):
        return god["card_id"], god.get("name"), False
    return god["card_id"] + "_G", god.get("name"), True


def _bump_schema(log: dict) -> None:
    if _version_tuple(log.get("schema_version")) < _version_tuple(DEITY_SCHEMA_VERSION):
        log["schema_version"] = DEITY_SCHEMA_VERSION


def apply_golden(log: dict, deity: dict[int, DeityTurn]) -> int:
    """Add only `golden` to existing deity records (the other values are kept as the plugin or the
    first backfill wrote them). Returns how many records are golden."""
    god = (log.get("game") or {}).get("global_old_god") or {}
    count = 0
    for turn, side, d in _deity_records(log):
        dt = deity.get(turn)
        src = (dt.player if side == "player" else dt.opponent) if dt else None
        card_id, name, golden_card = _deity_card(d.get("dbf_id"), god)
        if d.get("card_id") is None and card_id is not None:
            d["card_id"], d["name"] = card_id, name
        golden = golden_card or bool(src is not None and src.golden)
        d["golden"] = golden
        count += golden
    _bump_schema(log)
    notes = log.setdefault("notes", [])
    if GOLDEN_BACKFILL_NOTE not in notes:
        notes.append(GOLDEN_BACKFILL_NOTE)
    return count


def _deity_json(side: DeitySide | None, global_old_god: dict) -> dict | None:
    if side is None or side.attack is None:
        return None
    card_id, name, golden_card = _deity_card(side.dbf_id, global_old_god)
    return {
        "card_id": card_id,
        "name": name,
        "dbf_id": side.dbf_id,
        "attack": side.attack,
        "health": side.health,
        "attack_after_combat": side.attack_after_combat,
        "health_after_combat": side.health_after_combat,
        "awakened": side.awakened,
        "golden": golden_card or bool(side.golden),
    }


def apply_deity(log: dict, deity: dict[int, DeityTurn]) -> int:
    """Write `turns[].deity` / `combat.opponent_deity` in place (docs/log-schema.md 1.3.0).
    Returns the number of turns that got a value. `deity` comes from `parse_deity`."""
    god = (log.get("game") or {}).get("global_old_god") or {}
    filled = 0
    new_turns = []
    for t in log.get("turns") or []:
        dt = deity.get(t.get("turn"))
        mine = _deity_json(dt.player if dt else None, god)
        filled += mine is not None
        # keep the documented key order: ..., hand_end_of_shop, deity, combat
        rebuilt = {k: v for k, v in t.items() if k not in ("deity", "combat")}
        rebuilt["deity"] = mine
        if "combat" in t:
            combat = t["combat"]
            if combat is not None:
                combat["opponent_deity"] = _deity_json(dt.opponent if dt else None, god)
            rebuilt["combat"] = combat
        new_turns.append(rebuilt)
    log["turns"] = new_turns
    _bump_schema(log)
    notes = log.setdefault("notes", [])
    if BACKFILL_NOTE not in notes:
        notes.append(BACKFILL_NOTE)
    return filled


# ------------------------------------------------ "this game" buffs (hsbg backfill-buffs)
#
# docs/log-schema.md "この対戦中の強化" (schema 1.7.0 beetle, 1.8.0 the others; plugin 0.12.0 /
# 0.13.0). These buffs are not on any minion: they accumulate on a hidden enchantment attached to
# the player entity and/or on tags of the player entity.
# - The local player's enchantment is created the first time the buff happens and stays all game.
#   Its TAG_SCRIPT_DATA_NUM_1/2 is the buff. Blood Gems also keep it in player tags (the larger of
#   the two is used, as HDT does); Tavern spells only have the player tags.
# - The combat opponent's value comes in a copy made for every combat (their controller, created
#   during the combat): a copy of their enchantment, or for Tavern spells the tags of the
#   TagTransferPlayerEnchant. Copies go to REMOVEDFROMGAME afterwards with the values kept. Nothing
#   is made when the opponent has no such buff.
# - The values also change during combat, so the value when the combat ends is the after-combat
#   value, like the Deity.


@dataclass(frozen=True)
class BuffKind:
    key: str  # the JSON key: turns[].<key>, combat.opponent_<key>
    enchant: str | None  # the player enchantment's card id
    tags: tuple[str, str] | None  # player entity tags (as power.log names them)
    from_transfer: bool  # the opponent's value is on the TagTransferPlayerEnchant (tags)
    base: tuple[int, int]  # added to the buff: the Beetle's 2/2, the Blood Gem's +1/+1


BUFF_KINDS = (
    BuffKind("beetle", "BG31_808pe", None, False, (2, 2)),  # Beetle token BG28_603t
    BuffKind(
        "blood_gem",
        "BG26_159pe",
        ("BACON_BLOODGEMBUFFATKVALUE", "BACON_BLOODGEMBUFFHEALTHVALUE"),
        False,
        (1, 1),
    ),
    BuffKind(
        "tavern_spell",
        None,
        ("TAVERN_SPELL_ATTACK_INCREASE", "TAVERN_SPELL_HEALTH_INCREASE"),
        True,
        (0, 0),
    ),
    BuffKind("tavern_minion", "BG_ShopBuff", None, False, (0, 0)),
    BuffKind("tavern_elemental", "BG_ShopBuff_Elemental", None, False, (0, 0)),
    # schema 1.9.0: Blood Gem Barrage (BG34_689), given to each Tavern minion after a refresh
    BuffKind("blood_gem_barrage", "BG34_689e2", None, False, (0, 0)),
)
BUFF_KEYS = tuple(k.key for k in BUFF_KINDS)
TAG_TRANSFER_CARD_ID = "Bacon_TagTransferPlayerE"
BUFF_BACKFILL_NOTE = "buffs backfilled from power.log"

_PLAYER_ENTITY = re.compile(r"Player EntityID=(\d+) PlayerID=(\d+) GameAccountId=\[hi=(\d+)")
_PLAYER_NAME = re.compile(r"DebugPrintGame\(\) - PlayerID=(\d+), PlayerName=(.*)$")
_TAG_CHANGE_ANY = re.compile(r"TAG_CHANGE Entity=(\[.*?\bid=(\d+) .*?\]|\S+) tag=(\S+) value=(\S+)")
_BUFF_ENCHANTS = {k.enchant: k for k in BUFF_KINDS if k.enchant}
_BUFF_WATCHED = {
    "CONTROLLER",
    "ATTACHED",
    "ZONE",
    "TAG_SCRIPT_DATA_NUM_1",
    "TAG_SCRIPT_DATA_NUM_2",
    *(t for k in BUFF_KINDS if k.tags for t in k.tags),
}


@dataclass
class BuffSide:
    """One player's stats of one buff in one turn (same keys as docs/log-schema.md `beetle`)."""

    attack: int | None = None
    health: int | None = None
    attack_after_combat: int | None = None
    health_after_combat: int | None = None


@dataclass
class BuffTurn:
    turn: int
    player: dict[str, BuffSide] = field(default_factory=dict)
    opponent: dict[str, BuffSide] = field(default_factory=dict)


def _stats(kind: BuffKind, a: int | None, h: int | None) -> tuple[int, int] | None:
    """Base + buff, or None without a buff (0/0, e.g. right after the enchantment is made)."""
    a, h = a or 0, h or 0
    if a <= 0 and h <= 0:
        return None
    return kind.base[0] + a, kind.base[1] + h


def _larger(x: int | None, y: int | None) -> int | None:
    return max(x, y) if x is not None and y is not None else x if x is not None else y


class _BuffReplay:
    def __init__(self) -> None:
        self.entities: dict[int, _Entity] = {}
        self.local_entity: int | None = None
        self.local_player: int | None = None
        self.local_name: str | None = None
        self.turn_tag = 0
        self.turns: dict[int, BuffTurn] = {}
        # copy entity id -> [first, last] stats seen (the opponent's per-combat copies)
        self._seen: dict[tuple[str, int], list[tuple[int, int]]] = {}
        self._block: _Entity | None = None
        self._block_id = 0

    def _turn(self, n: int) -> BuffTurn:
        return self.turns.setdefault(n, BuffTurn(turn=n))

    # -------------------------------------------------------------- reading
    def _own_enchant(self, kind: BuffKind) -> _Entity | None:
        own = [
            (eid, e)
            for eid, e in self.entities.items()
            if e.card_id == kind.enchant
            and e.int_tag("ATTACHED") == self.local_entity
            and e.int_tag("CONTROLLER") == self.local_player
            and e.tags.get("ZONE") == "PLAY"
        ]
        return max(own, key=lambda x: x[0])[1] if own else None

    def _own(self, kind: BuffKind) -> tuple[int, int] | None:
        if self.local_entity is None:
            return None
        a = h = None
        if kind.enchant:
            e = self._own_enchant(kind)
            if e is not None:
                a, h = (
                    e.int_tag("TAG_SCRIPT_DATA_NUM_1") or 0,
                    e.int_tag("TAG_SCRIPT_DATA_NUM_2") or 0,
                )
        if kind.tags:
            pe = self.entities.get(self.local_entity)
            if pe is not None:
                a = _larger(a, pe.int_tag(kind.tags[0]) or 0)
                h = _larger(h, pe.int_tag(kind.tags[1]) or 0)
        return _stats(kind, a, h)

    def _copy_stats(self, kind: BuffKind, e: _Entity) -> tuple[int, int] | None:
        if kind.from_transfer and kind.tags:
            return _stats(kind, e.int_tag(kind.tags[0]), e.int_tag(kind.tags[1]))
        return _stats(kind, e.int_tag("TAG_SCRIPT_DATA_NUM_1"), e.int_tag("TAG_SCRIPT_DATA_NUM_2"))

    def _copy_kinds(self, e: _Entity) -> list[BuffKind]:
        if e.card_id == TAG_TRANSFER_CARD_ID:
            return [k for k in BUFF_KINDS if k.from_transfer]
        k = _BUFF_ENCHANTS.get(e.card_id)
        return [k] if k is not None and not k.from_transfer else []

    # -------------------------------------------------------------- transitions
    def _on_turn_change(self, new: int) -> None:
        old = self.turn_tag
        self.turn_tag = new
        if new % 2 == 0 and new > 0:  # shop of turn new/2 ends
            for kind in BUFF_KINDS:
                stats = self._own(kind)
                if stats is not None:
                    self._turn(new // 2).player[kind.key] = BuffSide(
                        attack=stats[0], health=stats[1]
                    )
        if old % 2 == 0 and old > 0:
            self._close_combat(old)

    def _close_combat(self, combat_tag: int) -> None:
        n = combat_tag // 2
        for kind in BUFF_KINDS:
            after = self._own(kind)
            if after is not None:
                rec = self.turns.get(n)
                side = rec.player.get(kind.key) if rec is not None else None
                if side is None:  # first buffed during this combat
                    side = self._turn(n).player[kind.key] = BuffSide()
                side.attack_after_combat, side.health_after_combat = after
            copies = [
                eid
                for (key, eid) in self._seen
                if key == kind.key
                and self.entities[eid].created_in == combat_tag
                and self.entities[eid].int_tag("CONTROLLER") not in (None, self.local_player)
            ]
            if copies:
                (fa, fh), (la, lh) = self._seen[(kind.key, max(copies))]
                self._turn(n).opponent[kind.key] = BuffSide(
                    attack=fa, health=fh, attack_after_combat=la, health_after_combat=lh
                )

    def _observe(self, eid: int, e: _Entity) -> None:
        for kind in self._copy_kinds(e):
            stats = self._copy_stats(kind, e)
            if stats is None:
                continue
            seen = self._seen.setdefault((kind.key, eid), [stats, stats])
            seen[1] = stats

    def _end_block(self) -> None:
        if self._block is not None:
            self._observe(self._block_id, self._block)
        self._block = None

    def _entity_id(self, token: str, id_group: str | None) -> int | None:
        if id_group:
            return int(id_group)
        if token.isdigit():
            return int(token)
        if self.local_name is not None and token == self.local_name:
            return self.local_entity
        return None  # GameEntity, the opponent's player entity (its tags can be stale), ...

    # -------------------------------------------------------------- lines
    def feed(self, line: str) -> None:
        if self._block is not None:
            m = _BLOCK_TAG.search(line)
            if m:
                if m.group(1) in _BUFF_WATCHED:
                    self._block.tags[m.group(1)] = m.group(2)
                return
            self._end_block()
        if "Player EntityID=" in line:
            m = _PLAYER_ENTITY.search(line)
            if m:
                eid = int(m.group(1))
                e = self.entities.setdefault(eid, _Entity(created_in=self.turn_tag))
                if m.group(3) != "0" and self.local_entity is None:
                    self.local_entity, self.local_player = eid, int(m.group(2))
                self._block, self._block_id = e, eid
            return
        if "PlayerName=" in line:
            m = _PLAYER_NAME.search(line)
            if m and self.local_player is not None and int(m.group(1)) == self.local_player:
                self.local_name = m.group(2).strip()
            return
        m = _CREATE.search(line)
        if m:
            eid = int(m.group(1))
            e = self.entities.get(eid)
            if e is None:
                e = _Entity(created_in=self.turn_tag)
                self.entities[eid] = e
            if m.group(2):
                e.card_id = m.group(2)
            self._block, self._block_id = e, eid
            return
        if "TAG_CHANGE" not in line:
            return
        m = _TURN.search(line)
        if m:
            self._on_turn_change(int(m.group(1)))
            return
        m = _TAG_CHANGE_ANY.search(line)
        if m and m.group(3) in _BUFF_WATCHED:
            eid = self._entity_id(m.group(1), m.group(2))
            e = self.entities.get(eid) if eid is not None else None
            if e is not None:
                e.tags[m.group(3)] = m.group(4)
                self._observe(eid, e)  # type: ignore[arg-type]

    def finish(self) -> dict[int, BuffTurn]:
        self._end_block()
        if self.turn_tag % 2 == 0 and self.turn_tag > 0:
            self._close_combat(self.turn_tag)
        return dict(sorted(self.turns.items()))


def parse_buffs(lines: Iterable[str]) -> dict[int, BuffTurn]:
    """Per-turn stats of each "this game" buff for the local player and the combat opponent
    (only turns with any). Empty when neither we nor any combat opponent had one."""
    replay = _BuffReplay()
    for line in lines:
        replay.feed(line)
    return {n: t for n, t in replay.finish().items() if t.player or t.opponent}


def missing_buff_keys(log: dict) -> list[str]:
    """The buff keys (`BUFF_KEYS`) the log does not have yet. A plugin 0.12.0 log (schema 1.7.0)
    has `beetle` only; 0.13.0+ (1.8.0) has all of them."""
    turns = log.get("turns") or []
    return [k for k in BUFF_KEYS if not any(k in t for t in turns)]


def _buff_json(side: BuffSide | None) -> dict | None:
    if side is None:
        return None
    return {
        "attack": side.attack,
        "health": side.health,
        "attack_after_combat": side.attack_after_combat,
        "health_after_combat": side.health_after_combat,
    }


def apply_buffs(log: dict, buffs: dict[int, BuffTurn], keys: Iterable[str] = BUFF_KEYS) -> int:
    """Write `turns[].<key>` / `combat.opponent_<key>` for `keys` in place (docs/log-schema.md
    1.8.0). The other keys (e.g. the plugin's own `beetle`) are kept. Returns the number of
    (turn, key) values of mine written. `buffs` comes from `parse_buffs`.

    `schema_version` is left as it is: the other keys of an older log keep their older meaning
    (e.g. `sells` before 1.6.0), and the note says which keys were added afterwards."""
    keys = [k for k in BUFF_KEYS if k in set(keys)]
    filled = 0
    new_turns = []
    for t in log.get("turns") or []:
        bt = buffs.get(t.get("turn"))
        rebuilt = {k: v for k, v in t.items() if k != "combat" and k not in keys}
        # keep the documented key order: ..., deity, beetle, blood_gem, ..., combat
        for k in BUFF_KEYS:
            if k in keys:
                rebuilt[k] = _buff_json(bt.player.get(k) if bt else None)
                filled += rebuilt[k] is not None
            elif k in t:
                rebuilt[k] = rebuilt.pop(k)
        if "combat" in t:
            combat = t["combat"]
            if combat is not None:
                for k in BUFF_KEYS:
                    ck = "opponent_" + k
                    if k in keys:
                        combat[ck] = _buff_json(bt.opponent.get(k) if bt else None)
                    elif ck in combat:
                        combat[ck] = combat.pop(ck)
            rebuilt["combat"] = combat
        new_turns.append(rebuilt)
    log["turns"] = new_turns
    notes = log.setdefault("notes", [])
    note = f"{BUFF_BACKFILL_NOTE}: {', '.join(keys)}"
    if note not in notes:
        notes.append(note)
    return filled
