"""Per-game Markdown summary for AI input (docs/analysis-and-visualization.md §4). Presentation only."""

from __future__ import annotations

from typing import Any

from . import metrics
from .normalize import BUFF_KEYS, Tables, divine_shields


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


_BUFF_LABEL = {
    "beetle": "beetle",
    "blood_gem": "blood gem",
    "tavern_spell": "tavern spell",
    "tavern_minion": "tavern minion",
    "tavern_elemental": "tavern elemental",
    "blood_gem_barrage": "blood gem barrage",
}
_BUFF_MEANING = {
    "beetle": "Beetle = the stats of each Beetle I summon (base 2/2 included).",
    "blood_gem": "Blood gem = what one Blood Gem gives (base +1/+1 included).",
    "tavern_spell": "Tavern spell = added to what Tavern spells give (includes auras of minions "
    "on the board, so it drops when such a minion is sold or dies).",
    "tavern_minion": "Tavern minion = added to the stats of minions in the Tavern.",
    "tavern_elemental": "Tavern elemental = added to Elementals in the Tavern (on top of Tavern "
    "minion).",
    "blood_gem_barrage": "Blood gem barrage = Blood Gem stats given to every Tavern minion after "
    "each refresh (Blood Gem Barrage; grows with each one played; not part of Tavern minion).",
}


def _buff(d: dict[str, Any] | None) -> str:
    """'5/7', '5/7 → 6/8' (grew in combat), '- → 3/3' (appeared in combat), '-' (none)."""
    if not d:
        return "-"
    start = _stats(d)
    after = _stats(d, after=True)
    return start if after in ("-", start) else f"{start} → {after}"


def _buff_section(turns: list[dict[str, Any]]) -> list[str]:
    """schema 1.7.0 / 1.8.0: buffs for the rest of the game that no minion shows (BUFF_KEYS).
    Only the kinds that appear in the game; nothing for a game (or older log) without any."""
    mine = [k for k in BUFF_KEYS if any(t.get(k) for t in turns)]
    theirs = [
        k for k in BUFF_KEYS if any((t.get("combat") or {}).get("opponent_" + k) for t in turns)
    ]
    if not mine and not theirs:
        return []
    head = ["T", "My board total"]
    head += [f"My {_BUFF_LABEL[k]}" for k in mine]
    head += ["Opp board total"] + [f"Opp {_BUFF_LABEL[k]}" for k in theirs]
    lines = [
        "",
        "## This-game buffs (not on the board)",
        "Permanent buffs for the rest of the game that no minion on the board shows, so read them "
        "next to the board totals. Mine = at the end of my shop (→ after combat when it grew in "
        "combat); Opp = the combat opponent's at combat start, visible only when they had it. "
        + " ".join(_BUFF_MEANING[k] for k in BUFF_KEYS if k in mine or k in theirs)
        + (" The Deity is in the Deity table." if any(t.get("deity") for t in turns) else ""),
        "",
        "| " + " | ".join(head) + " |",
        "|" + "---|" * len(head),
    ]
    for t in turns:
        c = t.get("combat") or {}
        row = [str(t.get("turn")), _board_total(t.get("board_end_of_shop"))]
        row += [_buff(t.get(k)) for k in mine]
        row += [_board_total(c.get("opponent_board"))]
        row += [_buff(c.get("opponent_" + k)) for k in theirs]
        lines.append("| " + " | ".join(row) + " |")
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


_CHOICE_SOURCE = {
    "triple": "Triple Reward",
    "hero_power": "Hero power",
    "dark_gift": "Dark Gift",
    "trinket": "Trinket",
    "timewarp": "Timewarp",
}


def _choice_label(c: dict[str, Any], hero_power_ids: set[str]) -> tuple[str, str]:
    """(source, kind) for one choice. A hero power choice made by another card than my hero powers
    (e.g. Getaway Galewing's destination, which discovers on arrival) is shown as
    "Hero power → <that card>". hero_power_ids = every hero power I held (the first one and, from
    schema 1.12.0, `turns[].hero_powers[]`: Genn's discovered ones, ...). kind = "discover" when a
    minion is offered, else "pick" (destination, secret, trinket, ...)."""
    sc = c.get("source_card") or {}
    card = sc.get("name") or sc.get("card_id")
    source = c.get("source") or ""
    label = _CHOICE_SOURCE.get(source)
    if source == "hero_power" and card:
        via = hero_power_ids and sc.get("card_id") and sc.get("card_id") not in hero_power_ids
        text = f"{label} → {card}" if via else f"{label} ({card})"
    elif label and card and source not in ("triple", "dark_gift"):
        text = f"{label} ({card})"
    else:
        text = label or card or source or "?"
    offered = c.get("offered") or []
    if source == "timewarp":
        return text, "buy"  # schema 1.12.0: a Timewarp purchase (paid with Chronum)
    kind = "discover" if any(o.get("card_type") == "minion" for o in offered) else "pick"
    return text, kind


def _hero_power_ids(log: dict[str, Any]) -> set[str]:
    """Card ids of the hero powers I held: the first one and, from `turns[].hero_powers[]` (1.12.0),
    the other hero powers I got (Genn's discovered ones, a Timewarp "Power of X", Nguyen's picks).
    Other forms of the first hero power (card id starting with it: Galewing's destination
    BG20_HERO_283p_t3, Inge's BG26_HERO_102p2) are left out, so that a choice made on arrival
    stays "Hero power → <destination>"."""
    first = ((log.get("player") or {}).get("hero_power") or {}).get("card_id")
    ids = {first} if first else set()
    for t in log.get("turns") or []:
        for h in t.get("hero_powers") or []:
            cid = h.get("card_id")
            if cid and not (first and cid.startswith(first)):
                ids.add(cid)
    return ids


def _held(t: dict[str, Any]) -> str:
    held = t.get("hero_powers") or []
    main = [_name(h) for h in held if h.get("slot") == "main"]
    extra = [_name(h) for h in held if h.get("slot") == "additional"]
    return (", ".join(main) or "-") + (f" + {', '.join(extra)}" if extra else "")


def _hero_power_section(log: dict[str, Any]) -> list[str]:
    """schema 1.12.0: the turns where the hero powers I held changed (a second one from Genn or a
    Timewarp "Power of X", swapped or chosen again, or gone because it became a trinket / quest).
    Older logs have no `hero_powers`, and a game that kept its first hero power prints nothing."""
    turns = [t for t in log.get("turns") or [] if "hero_powers" in t]
    first = ((log.get("player") or {}).get("hero_power") or {}).get("card_id")
    rows: list[tuple[Any, str]] = []
    before: list[tuple[Any, Any]] = [("main", first)]
    for t in turns:
        now = [(h.get("slot"), h.get("card_id")) for h in t.get("hero_powers") or []]
        if now != before:
            rows.append((t.get("turn"), _held(t)))
        before = now
    if not rows:
        return []
    return [
        "",
        "## Hero powers",
        f"Hero powers held at the end of the shop, on the turns they changed (first: "
        f"{_name((log.get('player') or {}).get('hero_power'))}). + = an additional hero power "
        '(e.g. Genn\'s second discover, a Timewarp "Power of X"); "-" = none held (it became a '
        "trinket or quest).",
        "",
        "| T | Hero powers |",
        "|---|---|",
        *(f"| {turn} | {held} |" for turn, held in rows),
    ]


def _timewarp_section(turns: list[dict[str, Any]]) -> list[str]:
    """schema 1.12.0: each Timewarp visit (Chronum, what was offered with its cost, what I bought).
    Older logs and games without a visit print nothing."""
    rows = [t for t in turns if t.get("timewarp")]
    if not rows:
        return []
    lines = [
        "",
        "## Timewarp",
        "Timewarp visits (a special shop paid with Chronum, not gold). Offered = the cards as shown "
        "with their Chronum cost; the ones I bought are marked → (1st, 2nd, ... in buying order). "
        'Via = the hero power that took me there ("-" = the visit every player gets).',
        "",
        "| T | Kind | Via | Chronum (left) | Offered | Bought |",
        "|---|---|---|---|---|---|",
    ]
    for t in rows:
        tw = t["timewarp"]
        offered = tw.get("offered") or []
        bought = [b.get("index") for b in tw.get("bought") or []]
        opts = []
        for i, o in enumerate(offered):
            mark = f"→{bought.index(i) + 1} " if i in bought else ""
            opts.append(f"{mark}{_card(o)} [{_int(o.get('cost'))}]")
        picked = [_card(offered[i]) for i in bought if isinstance(i, int) and 0 <= i < len(offered)]
        via = _name(tw.get("source_card")) if tw.get("source_card") else "-"
        lines.append(
            f"| {t.get('turn')} | {tw.get('kind') or '?'} | {via} | {_int(tw.get('chronum'))} "
            f"({_int(tw.get('chronum_left'))}) | {', '.join(opts) or '-'} | "
            f"{', '.join(picked) or '-'} |"
        )
    return lines


def _choice_section(
    turns: list[dict[str, Any]], hero_power_ids: set[str] | None = None
) -> list[str]:
    """schema 1.11.0: every choice (discover, trinket pick, ...) with what was offered and what I
    picked. Older logs have none, so print nothing."""
    rows = [(t, c) for t in turns for c in t.get("choices") or []]
    if not rows:
        return []
    lines = [
        "",
        "## Choices",
        'Every choice I was offered, in order. Source = what made the choice; "Hero power → X" = '
        "made later by X, a card my hero power created earlier (e.g. a destination that discovers "
        "on arrival), not by using the hero power that turn. Kind = discover (minions offered), "
        "pick (destinations, secrets, trinkets, ...) or buy (a Timewarp purchase paid with "
        "Chronum). Offered = the options as shown (minions: tier and stats when offered); the one "
        "I picked is marked →.",
        "",
        "| T | Source | Kind | Offered | Picked |",
        "|---|---|---|---|---|",
    ]
    for t, c in rows:
        source, kind = _choice_label(c, hero_power_ids or set())
        idx = c.get("chosen_index")
        offered = c.get("offered") or []
        opts = ", ".join(("→ " if i == idx else "") + _card(o) for i, o in enumerate(offered))
        picked = _card(offered[idx]) if isinstance(idx, int) and 0 <= idx < len(offered) else "-"
        lines.append(f"| {t.get('turn')} | {source} | {kind} | {opts or '-'} | {picked} |")
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
        # schema 1.10.0: the damage above was blocked by an Ice Block (HP not reduced)
        if c and c.get("ice_block"):
            dmg += " (my Ice Block)"
        if c and c.get("opponent_ice_block"):
            dmg += " (opp. Ice Block)"
        bb = c.get("bobs_buddy") or {}
        bbs = f"{bb['win']:.0%}/{bb['tie']:.0%}/{bb['loss']:.0%}" if bb else "-"
        lines.append(
            f"| {t.get('turn')} | {_int(t.get('tavern_tier'))} | {hp} | {gold} | {acts} | "
            f"{_name(c.get('opponent_hero')) if c else '-'} | {res} | {dmg} | {bbs} | "
            f"{_board(t.get('board_end_of_shop'))} |"
        )

    lines += _hand_shop_section(log.get("turns") or [])
    lines += _hero_power_section(log)
    lines += _timewarp_section(log.get("turns") or [])
    lines += _choice_section(log.get("turns") or [], _hero_power_ids(log))
    lines += _deity_section(log.get("turns") or [])
    lines += _buff_section(log.get("turns") or [])

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
