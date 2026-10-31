"""Find, load and run the lenses of a workspace (`<lenses_dir>/<name>/`, docs/lenses.md).

A lens folder holds `lens.toml` (label, description, status, api), `lens.md` (what the AI should
look at; read by the analysis skill, not by this module) and optionally `metrics.py` with
`@lens_table` functions (hsbg.lens). The lens code is the user's own Python and runs in this
process. Nothing here raises for a broken lens: problems become warnings or per-table errors.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .lens import LENS_API, TableFn, TableSpec, table_spec
from .normalize import Tables

LENS_FILE = "lens.toml"
GUIDE_FILE = "lens.md"
CODE_FILE = "metrics.py"
STATUSES = ("active", "retired")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
TEMPLATE_DIR = Path(__file__).with_name("templates") / "lens"


@dataclass
class Lens:
    name: str
    folder: Path
    label: str
    description: str = ""
    status: str = "active"
    api: int = LENS_API
    tables: list[tuple[TableSpec, TableFn]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return self.status == "active"

    @property
    def guide(self) -> Path:
        return self.folder / GUIDE_FILE


@dataclass(frozen=True)
class TableResult:
    spec: TableSpec
    df: pd.DataFrame | None
    error: str | None = None


def discover(lenses_dir: Path | None) -> list[Lens]:
    """Every folder with a lens.toml under `lenses_dir`, by name. None / missing folder -> []."""
    if lenses_dir is None or not lenses_dir.is_dir():
        return []
    return [load(p.parent) for p in sorted(lenses_dir.glob(f"*/{LENS_FILE}"))]


def _read_toml(folder: Path, lens: Lens) -> None:
    try:
        with (folder / LENS_FILE).open("rb") as f:
            meta = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        lens.warnings.append(f"{LENS_FILE}: {e}")
        return
    for key, value in meta.items():
        if key == "api":
            if isinstance(value, int):
                lens.api = value
            else:
                lens.warnings.append(f"{LENS_FILE}: api must be an integer")
        elif key in ("label", "description", "status"):
            if isinstance(value, str):
                setattr(lens, key, value.strip())
            else:
                lens.warnings.append(f"{LENS_FILE}: {key} must be a string")
        elif key != "name":
            lens.warnings.append(f"{LENS_FILE}: unknown key '{key}' (ignored)")
    if lens.status not in STATUSES:
        lens.warnings.append(f"{LENS_FILE}: status must be active or retired: {lens.status!r}")
        lens.status = "active"
    if lens.api > LENS_API:
        lens.warnings.append(
            f"{LENS_FILE}: api = {lens.api} is newer than this hsbg (lens API {LENS_API}); "
            "update hsbg"
        )
    elif lens.api < LENS_API:
        lens.warnings.append(f"{LENS_FILE}: written for lens API {lens.api}, hsbg has {LENS_API}")


def _load_code(folder: Path, lens: Lens) -> None:
    path = folder / CODE_FILE
    if not path.is_file():
        return
    module_name = "hsbg_lens_" + re.sub(r"\W", "_", lens.name)
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as e:  # the lens is the user's code: report, never crash
        sys.modules.pop(module_name, None)
        lens.warnings.append(f"{CODE_FILE}: {type(e).__name__}: {e}")
        return
    seen: set[str] = set()
    for obj in vars(module).values():
        ts = table_spec(obj)
        if ts is None or not callable(obj):
            continue
        if ts.name in seen:
            lens.warnings.append(f"{CODE_FILE}: table name '{ts.name}' is used twice")
            continue
        seen.add(ts.name)
        lens.tables.append((ts, obj))


def load(folder: Path) -> Lens:
    name = folder.name
    lens = Lens(name=name, folder=folder, label=name)
    if not NAME_RE.match(name):
        lens.warnings.append(
            f"folder name '{name}' should be lower case letters, digits, '-' or '_'"
        )
    _read_toml(folder, lens)
    _load_code(folder, lens)
    return lens


def run(lens: Lens, tables: Tables) -> list[TableResult]:
    """Run every table of the lens on `tables`. An exception or a non-DataFrame result becomes
    that table's error; the other tables still run."""
    results: list[TableResult] = []
    for ts, fn in lens.tables:
        try:
            df = fn(tables)
        except Exception as e:  # the lens is the user's code: report, never crash
            results.append(TableResult(ts, None, f"{type(e).__name__}: {e}"))
            continue
        if not isinstance(df, pd.DataFrame):
            results.append(
                TableResult(ts, None, f"returned {type(df).__name__}, not a pandas DataFrame")
            )
            continue
        results.append(TableResult(ts, df))
    return results


@dataclass(frozen=True)
class ShownTable:
    """A table as the dashboard shows it, with the chart columns under their shown names."""

    df: pd.DataFrame | None
    x: str | None = None
    y: str | None = None
    color: str | None = None
    error: str | None = None


def shown_table(result: TableResult) -> ShownTable:
    """The spec's `display` (when given) and then its `columns` renames, applied to the result.
    An exception or a non-DataFrame from `display` becomes the error."""
    spec = result.spec
    if result.df is None:
        return ShownTable(None, error=result.error)
    df = result.df
    if spec.display is not None:
        try:
            df = spec.display(df.copy())
        except Exception as e:  # the lens is the user's code: report, never crash
            return ShownTable(None, error=f"display: {type(e).__name__}: {e}")
        if not isinstance(df, pd.DataFrame):
            return ShownTable(None, error=f"display returned {type(df).__name__}, not a DataFrame")
    names = spec.columns

    def name(col: str | None) -> str | None:
        return names.get(col, col) if col else None

    return ShownTable(df.rename(columns=names), name(spec.x), name(spec.y), name(spec.color))


def problems(lens: Lens, results: list[TableResult]) -> list[str]:
    """What `hsbg lens check` reports: load warnings, table errors, chart columns the result
    lacks, a missing lens.md. A lens without tables (lens.md only) is fine."""
    out = list(lens.warnings)
    if not lens.guide.is_file():
        out.append(f"{GUIDE_FILE} is missing (the analysis skill reads it)")
    for r in results:
        if r.error:
            out.append(f"{r.spec.name}: {r.error}")
            continue
        assert r.df is not None
        for col in (r.spec.x, r.spec.y, r.spec.color):
            if col and not r.df.empty and col not in r.df.columns:
                out.append(f"{r.spec.name}: chart column '{col}' is not in the result")
        shown = shown_table(r)
        if shown.error:
            out.append(f"{r.spec.name}: {shown.error}")
        elif shown.df is not None and not shown.df.empty:
            for col in (shown.x, shown.y, shown.color):
                if col and col not in shown.df.columns:
                    out.append(f"{r.spec.name}: chart column '{col}' is lost by display / columns")
    return out


def create(lenses_dir: Path, name: str) -> Path:
    """Copy the lens template to `<lenses_dir>/<name>/`. Raises ValueError for a bad name and
    FileExistsError when the folder exists."""
    if not NAME_RE.match(name):
        raise ValueError("use lower case letters, digits, '-' or '_' (e.g. my-lens)")
    dest = lenses_dir / name
    if dest.exists():
        raise FileExistsError(dest)
    dest.mkdir(parents=True)
    for src in sorted(TEMPLATE_DIR.iterdir()):
        if src.is_file():
            text = src.read_text(encoding="utf-8").replace("__NAME__", name)
            (dest / src.name).write_text(text, encoding="utf-8", newline="\n")
    return dest
