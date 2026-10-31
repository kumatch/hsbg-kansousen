"""Where things are: logs, saved analyses, reports, exports, the knowledge folder, CardDefs and the
card-name language (docs/architecture.md §3).

Precedence for each setting: CLI option > environment variable > the workspace's `hsbg.toml` >
default. The workspace is the folder named by `$HSBG_WORKSPACE`, else the nearest folder at or above
the current directory that holds `hsbg.toml`. Without one everything behaves as before the
workspace existed: analyses, reports and exports live under the log folder.

Values may use `%VAR%` (Windows style, expanded on every OS) and `~`. Relative paths in `hsbg.toml`
are relative to the workspace. Problems (unreadable file, unknown key, wrong type) become warnings
and the default is used; nothing here raises for a bad config.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE = "hsbg.toml"
WORKSPACE_ENV = "HSBG_WORKSPACE"
DEFAULT_LOCALE = "jaJP"

# setting -> environment variable that overrides hsbg.toml (None: hsbg.toml / default only)
ENV_VARS: dict[str, str | None] = {
    "logs_dir": "HSBG_LOGS",
    "analysis_dir": None,
    "reports_dir": None,
    "export_dir": None,
    "lenses_dir": None,
    "knowledge_dir": "HSBG_KNOWLEDGE",
    "carddefs_dir": "HSBG_CARDDEFS",
    "locale": "HSBG_LOCALE",
}
PATH_KEYS = [k for k in ENV_VARS if k.endswith("_dir")]

_VAR_RE = re.compile(r"%([^%\\/]+)%")

TEMPLATE_DIR = Path(__file__).with_name("templates") / "workspace"
SKILLS_TEMPLATE_DIR = Path(__file__).with_name("templates") / "skills"
KNOWLEDGE_DIR_NAME = "knowledge"
# files kept under another name in the package (a real .gitignore there would apply to this repo)
_TEMPLATE_RENAMES = {"gitignore": ".gitignore"}


@dataclass(frozen=True)
class Settings:
    workspace: Path | None
    logs_dir: Path
    analysis_dir: Path
    reports_dir: Path
    export_dir: Path
    lenses_dir: Path | None  # None without a workspace: no lenses
    knowledge_dir: Path | None
    carddefs_dir: Path
    locale: str
    # setting -> "option" | "env <NAME>" | "hsbg.toml" | "default"
    sources: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, str | None]:
        out: dict[str, str | None] = {"workspace": str(self.workspace) if self.workspace else None}
        for key in ENV_VARS:
            value = getattr(self, key)
            out[key] = None if value is None else str(value)
        return out


def expand(value: str, base: Path | None = None) -> Path:
    """`%VAR%` (unknown ones are left as they are) and `~`; relative paths join `base`."""
    text = _VAR_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value.strip())
    path = Path(text).expanduser()
    if base is not None and not path.is_absolute():
        path = base / path
    return path


def find_workspace(start: Path | None = None) -> Path | None:
    env = os.environ.get(WORKSPACE_ENV)
    if env:
        return expand(env)
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if (folder / CONFIG_FILE).is_file():
            return folder
    return None


def _read_toml(workspace: Path, warnings: list[str]) -> dict[str, object]:
    path = workspace / CONFIG_FILE
    if not path.is_file():
        if os.environ.get(WORKSPACE_ENV):
            warnings.append(f"{WORKSPACE_ENV}={workspace}: no {CONFIG_FILE} there; using defaults")
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        warnings.append(f"{path}: {e}; using defaults")
        return {}
    for key in list(data):
        if key not in ENV_VARS:
            warnings.append(f"{path}: unknown setting '{key}' (ignored)")
            del data[key]
        elif not isinstance(data[key], str) or not data[key].strip():
            warnings.append(f"{path}: '{key}' must be a non-empty string (ignored)")
            del data[key]
    return data


def _default_carddefs() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "HearthstoneDeckTracker" / "CardDefs"


def load(logs_dir: Path | None = None, start: Path | None = None) -> Settings:
    """Resolve every setting. `logs_dir` is the CLI `--dir` (highest precedence)."""
    warnings: list[str] = []
    workspace = find_workspace(start)
    toml = _read_toml(workspace, warnings) if workspace else {}
    sources: dict[str, str] = {}

    def pick(key: str) -> tuple[str | None, Path | None]:
        """Raw value and the folder relative paths are resolved against."""
        env_name = ENV_VARS[key]
        if env_name and os.environ.get(env_name):
            sources[key] = f"env {env_name}"
            return os.environ[env_name], None
        if key in toml:
            sources[key] = CONFIG_FILE
            return str(toml[key]), workspace
        sources[key] = "default"
        return None, None

    if logs_dir is not None:
        sources["logs_dir"] = "option"
        logs = logs_dir
    else:
        raw, base = pick("logs_dir")
        logs = expand(raw, base) if raw else Path.home() / "Documents" / "HSBG-Logs"

    # analyses / reports / exports default to the workspace when there is one, else the log folder
    home = workspace or logs

    def folder(key: str, name: str) -> Path:
        raw, base = pick(key)
        return expand(raw, base) if raw else home / name

    raw, base = pick("lenses_dir")
    lenses = expand(raw, base) if raw else (workspace / "lenses" if workspace else None)
    raw, base = pick("knowledge_dir")
    knowledge = expand(raw, base) if raw else None
    raw, base = pick("carddefs_dir")
    carddefs = expand(raw, base) if raw else _default_carddefs()
    raw, _ = pick("locale")
    return Settings(
        workspace=workspace,
        logs_dir=logs,
        analysis_dir=folder("analysis_dir", "analysis"),
        reports_dir=folder("reports_dir", "reports"),
        export_dir=folder("export_dir", "export"),
        lenses_dir=lenses,
        knowledge_dir=knowledge,
        carddefs_dir=carddefs,
        locale=(raw or DEFAULT_LOCALE).strip(),
        sources=sources,
        warnings=tuple(warnings),
    )


def init_workspace(folder: Path, knowledge: bool = True) -> list[tuple[Path, bool]]:
    """Copy the workspace skeleton (`templates/workspace/`): hsbg.toml, README.md, .gitignore,
    analysis/, lenses/ and, unless `knowledge` is false, the user's own knowledge folder
    (knowledge/, with `knowledge_dir = 'knowledge'` in hsbg.toml). Existing files are left
    untouched. Returns (path, created) for every file / folder of the skeleton."""
    folder.mkdir(parents=True, exist_ok=True)
    result: list[tuple[Path, bool]] = []
    sub = folder / "analysis"
    result.append((sub, not sub.exists()))
    sub.mkdir(exist_ok=True)
    for src in sorted(TEMPLATE_DIR.rglob("*")):
        rel = src.relative_to(TEMPLATE_DIR)
        if not src.is_file() or "__pycache__" in rel.parts:
            continue
        if rel.parts[0] == KNOWLEDGE_DIR_NAME and not knowledge:
            continue
        dest = folder.joinpath(*rel.parts[:-1], _TEMPLATE_RENAMES.get(rel.name, rel.name))
        if dest.exists():
            result.append((dest, False))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8")
        if rel.name == CONFIG_FILE and not knowledge:
            line = f"knowledge_dir = '{KNOWLEDGE_DIR_NAME}'"
            text = text.replace(f"\n{line}", f"\n# {line}")
        dest.write_text(text, encoding="utf-8", newline="\n")
        result.append((dest, True))
    return result + [(p, status == "created") for p, status in install_skills(folder)]


def install_skills(folder: Path) -> list[tuple[Path, str]]:
    """Copy hsbg's Claude Code skills (`templates/skills/<name>/`) to `<folder>/.claude/skills/`.
    They belong to hsbg, so existing copies are overwritten (the player's own instructions go in
    profile.md or a lens). Returns (path, "created" | "updated" | "unchanged") per file."""
    result: list[tuple[Path, str]] = []
    for src in sorted(SKILLS_TEMPLATE_DIR.rglob("*")):
        if not src.is_file() or "__pycache__" in src.parts:
            continue
        dest = folder / ".claude" / "skills" / src.relative_to(SKILLS_TEMPLATE_DIR)
        text = src.read_text(encoding="utf-8")
        if dest.exists():
            status = "unchanged" if dest.read_text(encoding="utf-8") == text else "updated"
        else:
            status = "created"
        if status != "unchanged":
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8", newline="\n")
        result.append((dest, status))
    return result
