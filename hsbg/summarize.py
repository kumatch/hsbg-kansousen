"""Per-game Markdown summary for AI input (docs/analysis-and-visualization.md §4). Presentation only."""

from __future__ import annotations

from typing import Any

from . import metrics
from .normalize import Tables, divine_shields


def _name(ref: dict[str, Any] | None) -> str:
    if not ref:
        return "-"
    return ref.get("name") or ref.get("card_id") or "-"


def _minion(m: dict[str, Any]) -> str:
    shields = divine_shields(m)
    codes = {
        "taunt": "T",
        # Stacked Divine Shields (Dark Paradox) show their count: "D3"
        "divine_shield": f"D{shields}" if shields > 1 else "D",
        "poisonous": "P",
        "venomous": "V",
        "reborn": "R",
        "windfury": "W",
        "stealth": "S",
    }
    kw = "".join(codes.get(k, "") for k in m.get("keywords") or [])
    golden = "★" if m.get("golden") else ""
    return f"{m.get('name') or m.get('card_id')}{golden} {m.get('attack')}/{m.get('health')}" + (
        f" [{kw}]" if kw else ""
    )


def _board(minions: list[dict[str, Any]] | None, limit: int = 7) -> str:
    if not minions:
        return "-"
    return ", ".join(_minion(m) for m in minions[:limit])


def _int(v: Any) -> str:
    return "-" if v is None else str(v)


def _stats(d: dict[str, Any] | None, after: bool = False) -> str:
    if not d:
        return "-"
    a, h = ("attack_after_combat", "health_after_combat") if after else ("attack", "health")
    return "-" if d.get(a) is None else f"{d[a]}/{d[h]}"


def _awake(d: dict[str, Any] | None) -> str:
    if not d:
        return "-"
    text = {True: "yes", False: "no"}.get(d.get("awakened"), "-")
    return text + " (golden)" if d.get("golden") else text


# What each Deity does once awakened (keyed by the non-golden card id). Golden = Mask of Ancient Ones.
_DEITY_ABILITY = {
    "BGFYM_000": "C'Thun: when it awakens it splits its Attack/Health among your other minions "
    "(golden: twice its stats), so its size is what matters.",
    "BGFYM_011": "Y'Shaarj: Deathrattle — resummons the first 2 friendly Aberrations that died this "
    "combat (not Deities) at their max stats (golden: 4). Its value depends on which Aberrations die "
    "first as well as on its own size.",
}


def _deity_ability(card_id: str | None) -> str:
    base = card_id[:-2] if card_id and card_id.endswith("_G") else card_id
    return _DEITY_ABILITY.get(base or "", "See the card text for what it does when it awakens.")


def _board_total(minions: list[dict[str, Any]] | None) -> str:
    if not minions:
        return "-"
    a = sum(int(m.get("attack") or 0) for m in minions)
    h = sum(int(m.get("health") or 0) for m in minions)
    return f"{a}/{h}"


def _deity_section(turns: list[dict[str, Any]]) -> list[str]:
    """schema 1.2.0: the Deity is not on the board, so print it next to the board totals."""
    if not any(t.get("deity") for t in turns):
        return []
    first = next(t["deity"] for t in turns if t.get("deity"))
    lines = [
        "",
        f"## Deity ({_name(first)})",
        "Not on the board: it awakens mid-combat once 4 friendly Aberrations have died in that combat "
        "(3 before patch 36.6.3 on 2026-10-02), "
        f"with the stats below. {_deity_ability(first.get('card_id'))} "
        '"(golden)" = the Deity is golden (Mask of Ancient Ones), doubling the effect. '
        "Compare it with the board totals — a large Deity can win combats a weaker-looking board would lose.",
        "",
        "| T | My deity at combat start | After combat | Awakened | My board total | Opp deity at combat start | After combat | Awakened | Opp board total |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for t in turns:
        d = t.get("deity")
        c = t.get("combat") or {}
        od = c.get("opponent_deity")
        lines.append(
            f"| {t.get('turn')} | {_stats(d)} | {_stats(d, after=True)} | {_awake(d)} | "
            f"{_board_total(t.get('board_end_of_shop'))} | {_stats(od)} | {_stats(od, after=True)} | "
            f"{_awake(od)} | {_board_total(c.get('opponent_board'))} |"
        )
    return lines


def _card(c: dict[str, Any]) -> str:
    """Hand / shop card (schema 1.5.0): minions with tier and stats, spells marked."""
    name = c.get("name") or c.get("card_id") or "?"
    if c.get("card_type") == "spell":
        return f"{name} (spell)"
    golden = "★" if c.get("golden") else ""
    tier = f"t{c['tier']} " if c.get("tier") else ""
    stats = f"{c['attack']}/{c['health']}" if c.get("attack") is not None else ""
    return f"{name}{golden} ({tier}{stats})".replace(" )", ")").replace(" ()", "")


_TRIGGER = {"turn_start": "start", "reroll": "roll", "refill": "refill", "added": "added"}


def _shops(offers: list[dict[str, Any]] | None) -> str:
    if not offers:
        return "-"
    return " / ".join(
        f"[{_TRIGGER.get(o.get('trigger') or '', o.get('trigger'))}] "
        + ", ".join(_card(c) for c in o.get("cards") or [])
        for o in offers
    )


def _lobby_tiers(lobby: list[dict[str, Any]] | None) -> str:
    if not lobby:
        return "-"
    tiers = sorted(
        (e["tavern_tier"] for e in lobby if not e.get("eliminated") and e.get("tavern_tier")),
        reverse=True,
    )
    return ", ".join(str(t) for t in tiers) or "-"


def _hand_shop_section(turns: list[dict[str, Any]]) -> list[str]:
    """schema 1.5.0: hand at the end of the shop, what the shop offered, the combat opponent's
    tier and the other players' tiers. Older logs have none of these, so print nothing."""
    if not any(t.get("hand_end_of_shop") or t.get("shop_offers") or t.get("lobby") for t in turns):
        return []
    lines = [
        "",
        "## Hand and shop",
        "Hand = my hand at the end of the shop (minions: tier and current stats). Shop = every shop "
        "I saw that turn: [start] at turn start, [roll] after each reroll, [refill] after buying it "
        "out, [added] cards added mid-turn. Lobby tiers = the other living players' tavern tiers "
        "at my shop start (public leaderboard).",
        "",
        "| T | Hand (end of shop) | Shop offers | Opp tier | Lobby tiers |",
        "|---|---|---|---|---|",
    ]
    for t in turns:
        c = t.get("combat") or {}
        hand = t.get("hand_end_of_shop")
        hand_text = "-" if hand is None else (", ".join(_card(h) for h in hand) or "(empty)")
        lines.append(
            f"| {t.get('turn')} | {hand_text} | {_shops(t.get('shop_offers'))} | "
            f"{_int(c.get('opponent_tavern_tier'))} | {_lobby_tiers(t.get('lobby'))} |"
        )
    return lines


def summarize(log: dict[str, Any], history: Tables | None = None) -> str:
    g = log.get("game") or {}
    p = log.get("player") or {}
    r = log.get("result") or {}
    started = (g.get("started_at") or "")[:16].replace("T", " ")
    mmr = (
        f"{r.get('mmr_before')} → {r.get('mmr_after')} ({r.get('mmr_delta'):+d})"
        if r.get("mmr_delta") is not None
        else f"{_int(r.get('mmr_before'))} → {_int(r.get('mmr_after'))}"
    )
    lines = [
        f"# Game {started} — Hero: {_name(p.get('hero'))} — Placement: "
        f"{_int(r.get('placement'))}/{_int(g.get('lobby_size') or 8)} — MMR {mmr}",
        f"Status: {log.get('status')} / Anomaly: {_name(g.get('anomaly'))} / Old god: "
        f"{_name(g.get('global_old_god'))} / Types: {', '.join(g.get('minion_types') or []) or '-'} / "
        f"Duration: {round((g.get('duration_sec') or 0) / 60)}m / Turns: {_int(r.get('total_turns'))}",
        f"Hero power: {_name(p.get('hero_power'))} / Start: {_int(p.get('starting_health'))} HP + "
        f"{_int(p.get('starting_armor'))} armor / Trinkets: "
        + (", ".join(f"{_name(t)} (T{t.get('turn')})" for t in p.get("trinkets") or []) or "-"),
    ]
    choices = ", ".join(_name(c) for c in p.get("hero_choices") or [])
    if choices:
        before = p.get("hero_choices_before_reroll")
        lines.append(
            f"Hero choices: {choices}"
            + (f" (rerolled from: {', '.join(_name(c) for c in before)})" if before else "")
        )

    lines += ["", "## Lobby"]
    for o in sorted(log.get("opponents") or [], key=lambda o: o.get("estimated_placement") or 9):
        place = o.get("placement") or f"~{o.get('estimated_placement')}"
        elim = f"out T{o['eliminated_turn']}" if o.get("eliminated_turn") else "alive"
        trinkets = ", ".join(_name(t) for t in o.get("trinkets") or []) or "-"
        lines.append(
            f"- #{place} {_name(o.get('hero'))} (player {o.get('player_id')}): {elim}, "
            f"tier {_int(o.get('final_tavern_tier'))}, HP {_int(o.get('final_health'))}, "
            f"trinkets: {trinkets}"
        )

    lines += ["", "## Turn-by-turn"]
    if any(((t.get("actions") or {}).get("gold_gained") or 0) > 0 for t in log.get("turns") or []):
        # schema 1.6.0: gold_spent は売却・ゴールド獲得で戻った分を差し引いた正味
        lines.append(
            "Gold = net gold used / gold at turn start (refunds subtracted, so the difference is "
            "the gold left over); +N = gold gained without selling (Tavern Coin etc.)."
        )
    lines += [
        "| T | Tier | HP | Gold | Buy/Sell/Roll/Up/HP/Spell/Gift | Opponent | Result | Dmg | Bob's Buddy | Board (end of shop) |",
        "|---|------|----|------|--------------------------------|----------|--------|-----|-------------|---------------------|",
    ]
    for t in log.get("turns") or []:
        a = t.get("actions") or {}
        c = t.get("combat") or {}
        hp = f"{_int(t.get('health'))}" + (f"+{t['armor']}" if t.get("armor") else "")
        gold = f"{_int(a.get('gold_spent'))}/{_int(t.get('gold_available'))}"
        if a.get("gold_gained"):
            gold += f" +{a['gold_gained']}"
        # Gift = 悪夢の発見（Dark Discovery ボタン BG36_Button_DarkGift。ミニオンに付く悪夢の恵み = Dark Gift とは別。3 ゴールドでミニオンを発見。schema 1.1.0 より前のログは "-"）
        acts = "/".join(
            _int(a.get(k))
            for k in (
                "buys",
                "sells",
                "rerolls",
                "tier_ups",
                "hero_power_uses",
                "spells_played",
                "dark_gifts",
            )
        )
        res = c.get("result") or "-"
        dmg = (
            (
                f"+{c['damage_dealt']}"
                if c.get("damage_dealt")
                else f"-{c['damage_taken']}"
                if c.get("damage_taken")
                else "0"
            )
            if c
            else "-"
        )
        bb = c.get("bobs_buddy") or {}
        bbs = f"{bb['win']:.0%}/{bb['tie']:.0%}/{bb['loss']:.0%}" if bb else "-"
        lines.append(
            f"| {t.get('turn')} | {_int(t.get('tavern_tier'))} | {hp} | {gold} | {acts} | "
            f"{_name(c.get('opponent_hero')) if c else '-'} | {res} | {dmg} | {bbs} | "
            f"{_board(t.get('board_end_of_shop'))} |"
        )

    lines += _hand_shop_section(log.get("turns") or [])
    lines += _deity_section(log.get("turns") or [])

    moments = metrics.key_moments(log, history)
    lines += ["", "## Key moments (auto-detected)"]
    lines += [f"- {m}" for m in moments] or ["- (none)"]

    turns = log.get("turns") or []
    final_board = next(
        (t.get("board_end_of_shop") for t in reversed(turns) if t.get("board_end_of_shop")), None
    )
    lines += ["", "## Final board", _board(final_board)]
    last_combat = next((t.get("combat") for t in reversed(turns) if t.get("combat")), None)
    if last_combat and last_combat.get("opponent_board"):
        lines += [
            "",
            "## Last opponent board",
            f"{_name(last_combat.get('opponent_hero'))}: {_board(last_combat.get('opponent_board'))}",
        ]
    notes = log.get("notes") or []
    if notes:
        lines += ["", "## Notes"] + [f"- {n}" for n in notes]
    return "\n".join(lines) + "\n"
