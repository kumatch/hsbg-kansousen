r"""Make game logs safe to share as test fixtures or in a bug report.

A log (docs/log-schema.md) has no BattleTag, player name or account id, but its times show when you
play and its MMR values are your rating. This rewrites, for the given logs together:

- `game.started_at` / `game.ended_at`: the first game starts at --start, the gaps between the games
  and every game's duration are kept (the UTC offset too)
- `result.mmr_before` / `mmr_after`: the first game's mmr_before becomes --mmr-base, every other
  value keeps its difference to it (mmr_delta is unchanged)
- `game.game_id`: a new id derived from the old one (the same input gives the same output)
- the file name: `<started_at as YYYYMMDD-HHMMSS>_<game id>.json` (a name without a game id, e.g.
  `..._incomplete.json`, keeps its suffix)

Only the .json logs: events.jsonl and power.log(.gz) are not handled (a power.log contains every
player's BattleTag; never share it).

Usage (Python 3.12, standard library only):
  python scripts\anonymize_log.py <log.json> [...] --out <folder> [--start 2026-01-10T10:00:00]
                                  [--mmr-base 5000]
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

NAMESPACE = uuid.UUID("6f3c1e0a-6a43-4b8e-9a4c-2f1d0c9e7b55")
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_FRACTION_RE = re.compile(r"\.(\d+)")


def _parse(ts: str) -> datetime:
    # .NET writes 7 fractional digits; Python takes at most 6
    return datetime.fromisoformat(_FRACTION_RE.sub(lambda m: "." + m.group(1)[:6], ts, count=1))


def anonymize(logs: list[dict], start: datetime, mmr_base: int) -> list[dict]:
    """Rewrite the logs in place (sorted by start time) and return them."""
    logs = sorted(logs, key=lambda g: _parse(g["game"]["started_at"]))
    first = _parse(logs[0]["game"]["started_at"])
    origin = start.replace(tzinfo=first.tzinfo)
    first_mmr = next(
        (g["result"]["mmr_before"] for g in logs if g.get("result", {}).get("mmr_before")), None
    )
    for g in logs:
        game = g["game"]
        for key in ("started_at", "ended_at"):
            if game.get(key):
                game[key] = (origin + (_parse(game[key]) - first)).isoformat()
        if game.get("game_id"):
            game["game_id"] = str(uuid.uuid5(NAMESPACE, game["game_id"]))
        result = g.get("result") or {}
        for key in ("mmr_before", "mmr_after"):
            if result.get(key) is not None and first_mmr is not None:
                result[key] = mmr_base + (result[key] - first_mmr)
    return logs


def file_name(log: dict, old_name: str) -> str:
    started = _parse(log["game"]["started_at"])
    stem = old_name.removesuffix(".json")
    suffix = stem.split("_", 1)[1] if "_" in stem else stem
    if _UUID_RE.fullmatch(suffix) and log["game"].get("game_id"):
        suffix = log["game"]["game_id"]
    return f"{started:%Y%m%d-%H%M%S}_{suffix}.json"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("logs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--start", default="2026-01-10T10:00:00", help="start of the first game")
    ap.add_argument("--mmr-base", type=int, default=5000, help="mmr_before of the first game")
    args = ap.parse_args()

    loaded = [(p, json.loads(p.read_text(encoding="utf-8-sig"))) for p in args.logs]
    by_id = {id(log): p for p, log in loaded}
    logs = anonymize([log for _, log in loaded], datetime.fromisoformat(args.start), args.mmr_base)
    args.out.mkdir(parents=True, exist_ok=True)
    for log in logs:
        src = by_id[id(log)]
        dest = args.out / file_name(log, src.name)
        dest.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{src.name} -> {dest.name}")


if __name__ == "__main__":
    main()
