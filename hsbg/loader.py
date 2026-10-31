"""Find, read and validate game logs (docs/log-schema.md). Invalid files are skipped with a warning;
games that ended before turn 1 are skipped silently (counted in `LoadResult.aborted`)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fastjsonschema

from . import config

SUPPORTED_SCHEMA_MAJOR = 1
SKIP_DIR_NAMES = {".partial", ".spike", ".cache", "reports", "analysis", "export"}
ABORTED_REASON = "ended before turn 1"

_PACKAGE_SCHEMA = Path(__file__).with_name("game-log.schema.json")
_REPO_SCHEMA = Path(__file__).resolve().parents[2] / "schema" / "game-log.schema.json"


def default_log_dir() -> Path:
    """$HSBG_LOGS > the workspace's hsbg.toml > %USERPROFILE%\\Documents\\HSBG-Logs (config.py)."""
    return config.load().logs_dir


def schema_path() -> Path:
    return _REPO_SCHEMA if _REPO_SCHEMA.exists() else _PACKAGE_SCHEMA


def load_schema() -> dict[str, Any]:
    with schema_path().open(encoding="utf-8") as f:
        return json.load(f)


@dataclass(frozen=True)
class LoadWarning:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass
class LoadResult:
    logs: list[dict[str, Any]] = field(default_factory=list)
    paths: list[Path] = field(default_factory=list)
    warnings: list[LoadWarning] = field(default_factory=list)
    aborted: list[Path] = field(default_factory=list)

    @property
    def incomplete(self) -> list[dict[str, Any]]:
        return [g for g in self.logs if g.get("status") != "complete"]


def find_logs(root: Path) -> list[Path]:
    """All *.json main logs under root (YYYY/MM/...).

    Skips .partial / .spike / reports and non-log files.
    """
    if not root.exists():
        return []
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES and not d.startswith(".")]
        for name in filenames:
            if name.endswith(".json") and not name.endswith(".events.jsonl"):
                found.append(Path(dirpath) / name)
    return sorted(found)


def is_aborted_before_first_turn(log: dict[str, Any]) -> bool:
    """No turns, no hero and no placement: the game ended during hero selection (e.g. the player
    was removed from the lobby). Nothing to analyse. Plugin 0.9.1 no longer writes these
    (Logic/AbortedGame.cs, same rule); older ones may have `lobby_size: 1` and fail the schema."""
    result, player, turns = log.get("result"), log.get("player"), log.get("turns")
    if not (isinstance(result, dict) and isinstance(player, dict) and isinstance(turns, list)):
        return False  # not the plugin's shape: leave it to the schema check
    hero = player.get("hero")
    if not isinstance(hero, dict):
        return False
    total_turns = result.get("total_turns")
    return (
        not turns
        and not (isinstance(total_turns, int) and total_turns > 0)
        and result.get("placement") is None
        and hero.get("card_id") is None
        and hero.get("dbf_id") is None
    )


class _Validator:
    """Compiled draft-07 validator (fastjsonschema: ~30x faster than jsonschema on 70 KB logs)."""

    def __init__(self) -> None:
        self._validate = fastjsonschema.compile(load_schema())

    def errors(self, log: dict[str, Any]) -> list[str]:
        try:
            self._validate(log)
        except fastjsonschema.JsonSchemaValueException as e:
            path = "/".join(str(p) for p in e.path[1:]) or "$"
            return [f"{path}: {e.message}"]
        return []


def load_log(
    path: Path, validator: _Validator | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    """Return (log, None) or (None, reason)."""
    try:
        with path.open(encoding="utf-8") as f:
            log = json.load(f)
    except (OSError, json.JSONDecodeError) as ex:
        return None, f"unreadable: {ex}"
    if not isinstance(log, dict):
        return None, "top-level is not an object"
    version = str(log.get("schema_version", ""))
    major = version.split(".")[0]
    if not major.isdigit() or int(major) != SUPPORTED_SCHEMA_MAJOR:
        return None, f"unsupported schema_version {version!r}"
    if is_aborted_before_first_turn(log):
        return None, ABORTED_REASON
    errors = (validator or _Validator()).errors(log)
    if errors:
        return None, "schema violation: " + "; ".join(errors[:3])
    return log, None


def events_path(path: Path) -> Path:
    """The `<name>.events.jsonl` written next to `<name>.json` (docs/log-schema.md §events)."""
    return path.with_name(path.stem + ".events.jsonl")


def read_events(path: Path, types: tuple[str, ...]) -> dict[str, list[dict[str, Any]]]:
    """Events of the given types from the log's events.jsonl, by type. Missing file or broken
    lines are skipped: the events are optional."""
    out: dict[str, list[dict[str, Any]]] = {t: [] for t in types}
    try:
        lines = events_path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    needles = [f'"{t}"' for t in types]
    for line in lines:
        if not any(n in line for n in needles):
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(e, dict) and e.get("type") in out:
            out[e["type"]].append(e)
    return out


def read_discovers(path: Path) -> list[dict[str, Any]]:
    """`discover` events (schema 1.1.0: hero power / triple reward picks) from events.jsonl."""
    return read_events(path, ("discover",))["discover"]


def load_logs(root: Path, *, paths: list[Path] | None = None) -> LoadResult:
    """Load every valid log under root. Schema violations become warnings, never exceptions;
    games that ended before turn 1 go to `aborted` without a warning.
    Each log gets `_path`, `_discovers` and `_sells` (those events of its events.jsonl; sells
    carry the sold minion's card_id from schema 1.5.0)."""
    result = LoadResult()
    validator = _Validator()
    for path in paths if paths is not None else find_logs(root):
        log, reason = load_log(path, validator)
        if log is None and reason == ABORTED_REASON:
            result.aborted.append(path)
            continue
        if log is None:
            result.warnings.append(LoadWarning(path, reason or "unknown error"))
            continue
        log["_path"] = str(path)
        events = read_events(path, ("discover", "sell"))
        log["_discovers"] = events["discover"]
        log["_sells"] = events["sell"]
        result.logs.append(log)
        result.paths.append(path)
    return result
