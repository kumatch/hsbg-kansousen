"""`hsbg` command line (docs/architecture.md §6): validate / report / summarize / stats / export /
serve / backfill-deity, plus config / init for the settings and the workspace (config.py)."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from . import (
    cache,
    cards,
    config,
    lenses,
    loader,
    markdown,
    metrics,
    normalize,
    powerlog,
    report,
    summarize,
)
from .normalize import Tables

app = typer.Typer(help="Hearthstone Battlegrounds log analysis", no_args_is_help=True)

LogDir = Annotated[
    Path | None,
    typer.Option(
        "--dir",
        "-d",
        help="Log folder (default: $HSBG_LOGS, hsbg.toml logs_dir, or Documents\\HSBG-Logs)",
    ),
]


def _settings(log_dir: Path | None) -> config.Settings:
    settings = config.load(log_dir)
    for w in settings.warnings:
        typer.echo(f"warning: {w}", err=True)
    return settings


def _root(log_dir: Path | None) -> Path:
    return _settings(log_dir).logs_dir


def _load(root: Path, *, quiet: bool = False) -> tuple[Tables, loader.LoadResult]:
    result = loader.load_logs(root)
    if not quiet:
        for w in result.warnings:
            typer.echo(f"warning: {w}", err=True)
    return normalize.normalize(result.logs), result


def _filter(
    last: int | None,
    since: datetime | None,
    until: datetime | None,
    hero: list[str] | None,
    include_incomplete: bool,
    min_mmr: int | None = None,
    max_mmr: int | None = None,
) -> metrics.LogFilter:
    names = cards.default()
    heroes = {names.base_id(h) or h for h in (hero or [])}
    return metrics.LogFilter(
        since=since,
        until=until,
        heroes=heroes,
        include_incomplete=include_incomplete,
        last=last,
        min_mmr=min_mmr,
        max_mmr=max_mmr,
    )


MinMmr = Annotated[
    int | None, typer.Option(help="Only games whose starting MMR is at least this, e.g. 7400")
]
MaxMmr = Annotated[
    int | None, typer.Option(help="Only games whose starting MMR is at most this, e.g. 7399")
]


@app.command()
def validate(log_dir: LogDir = None) -> None:
    """Check every log against the JSON schema and list incomplete games."""
    root = _root(log_dir)
    result = loader.load_logs(root)
    typer.echo(f"folder: {root}")
    typer.echo(f"valid logs: {len(result.logs)}  invalid: {len(result.warnings)}")
    for w in result.warnings:
        typer.echo(f"  INVALID {w}")
    if result.aborted:
        typer.echo(f"ended before turn 1 (ignored): {len(result.aborted)}")
        for p in result.aborted:
            typer.echo(f"  {p}")
    incomplete = result.incomplete
    typer.echo(f"incomplete: {len(incomplete)}")
    for g in incomplete:
        typer.echo(f"  {g['_path']}  ({g['status']}; {'; '.join(g.get('notes') or [])[:120]})")
    with_notes = [g for g in result.logs if g.get("notes")]
    if with_notes:
        typer.echo(f"logs with notes: {len(with_notes)}")
        for g in with_notes[:20]:
            typer.echo(f"  {Path(g['_path']).name}: {'; '.join(g['notes'])[:160]}")
    raise typer.Exit(code=1 if result.warnings else 0)


@app.command("report")
def report_cmd(
    log_dir: LogDir = None,
    last: Annotated[int | None, typer.Option(help="Only the N most recent games")] = None,
    since: Annotated[datetime | None, typer.Option(help="From date, e.g. 2026-09-01")] = None,
    until: Annotated[datetime | None, typer.Option(help="To date")] = None,
    hero: Annotated[list[str] | None, typer.Option(help="Hero card id (repeatable)")] = None,
    include_incomplete: Annotated[bool, typer.Option(help="Include incomplete logs")] = False,
    min_mmr: MinMmr = None,
    max_mmr: MaxMmr = None,
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Output HTML path")] = None,
    open_browser: Annotated[bool, typer.Option("--open/--no-open", help="Open the report")] = False,
) -> None:
    """Build the static HTML report (default: <reports_dir>/report-<date>.html; `hsbg config`)."""
    settings = _settings(log_dir)
    root = settings.logs_dir
    tables, result = _load(root)
    flt = _filter(last, since, until, hero, include_incomplete, min_mmr, max_mmr)
    filtered = metrics.apply_filter(tables, flt)
    excluded = 0 if include_incomplete else int((tables.games["status"] != "complete").sum())
    html_text = report.build_report(filtered, excluded_incomplete=excluded)
    out = out or settings.reports_dir / f"report-{datetime.now():%Y%m%d-%H%M}.html"
    report.write_report(html_text, out)
    typer.echo(
        f"games: {len(filtered.games)} (of {len(tables.games)} loaded, "
        f"{len(result.warnings)} invalid)"
    )
    typer.echo(f"report: {out}")
    if open_browser:
        typer.launch(str(out))


@app.command("summarize")
def summarize_cmd(
    log: Annotated[Path, typer.Argument(help="A game log .json (or 'latest')")],
    log_dir: LogDir = None,
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Write Markdown here")] = None,
    no_history: Annotated[bool, typer.Option(help="Skip comparison with your other games")] = False,
) -> None:
    """Markdown summary of one game for AI analysis."""
    root = _root(log_dir)
    path = log
    if str(log) == "latest":
        result = loader.load_logs(root)
        complete = [g for g in result.logs if g.get("status") == "complete"]
        if not complete:
            typer.echo("no complete logs found", err=True)
            raise typer.Exit(code=1)
        path = Path(max(complete, key=lambda g: g["game"]["started_at"])["_path"])
    game, reason = loader.load_log(path)
    if game is None:
        typer.echo(f"error: {path}: {reason}", err=True)
        raise typer.Exit(code=1)
    history = None
    if not no_history:
        tables, _ = _load(root, quiet=True)
        history = metrics.apply_filter(tables, metrics.LogFilter())
    text = summarize.summarize(cards.default().localize(game), history)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        typer.echo(f"summary: {out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        typer.echo(text)


@app.command()
def stats(
    log_dir: LogDir = None,
    last: Annotated[int | None, typer.Option(help="Only the N most recent games")] = None,
    since: Annotated[datetime | None, typer.Option(help="From date, e.g. 2026-09-01")] = None,
    until: Annotated[datetime | None, typer.Option(help="To date")] = None,
    hero: Annotated[list[str] | None, typer.Option(help="Hero card id (repeatable)")] = None,
    include_incomplete: Annotated[bool, typer.Option(help="Include incomplete logs")] = False,
    min_mmr: MinMmr = None,
    max_mmr: MaxMmr = None,
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Write Markdown here")] = None,
    with_lenses: Annotated[
        bool, typer.Option("--lenses/--no-lenses", help="Append the active lenses' tables")
    ] = True,
) -> None:
    """Pre-computed metrics as Markdown tables (input for AI trend analysis), followed by the
    tables of the workspace's active lenses (`## Lens: ...`)."""
    settings = _settings(log_dir)
    tables, _ = _load(settings.logs_dir, quiet=True)
    flt = _filter(last, since, until, hero, include_incomplete, min_mmr, max_mmr)
    filtered = metrics.apply_filter(tables, flt)
    title = "HSBG stats"
    if min_mmr is not None or max_mmr is not None:
        title += f" (starting MMR {min_mmr or ''}-{max_mmr or ''})"
    text = markdown.stats_markdown(filtered, title=title)
    if with_lenses and not filtered.games.empty:
        active = [ln for ln in lenses.discover(settings.lenses_dir) if ln.active]
        if active:
            text += "\n" + markdown.lenses_markdown(
                [(ln, lenses.run(ln, filtered)) for ln in active]
            )
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        typer.echo(f"stats: {out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        typer.echo(text)


@app.command()
def export(
    log_dir: LogDir = None,
    fmt: Annotated[str, typer.Option("--format", "-f", help="parquet | csv")] = "parquet",
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="Output folder (default: export_dir)")
    ] = None,
    last: Annotated[int | None, typer.Option(help="Only the N most recent games")] = None,
    include_incomplete: Annotated[bool, typer.Option(help="Include incomplete logs")] = False,
) -> None:
    """Write the normalized tables (`cache.TABLE_NAMES`: games, turns, combats, board_minions,
    opponents, discovers, hand, shop_offers, lobby, sells)."""
    if fmt not in ("parquet", "csv"):
        typer.echo("format must be parquet or csv", err=True)
        raise typer.Exit(code=2)
    settings = _settings(log_dir)
    tables, _ = _load(settings.logs_dir)
    filtered = metrics.apply_filter(tables, _filter(last, None, None, None, include_incomplete))
    out = out or settings.export_dir
    out.mkdir(parents=True, exist_ok=True)
    for name in cache.TABLE_NAMES:
        df = getattr(filtered, name)
        path = out / f"{name}.{fmt}"
        if fmt == "parquet":
            df.to_parquet(path, index=False)
        else:
            df.to_csv(path, index=False, encoding="utf-8")
        typer.echo(f"{path} ({len(df)} rows)")


@app.command("backfill-deity")
def backfill_deity(
    log_dir: LogDir = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Only report, write nothing")] = False,
    force: Annotated[
        bool, typer.Option(help="Also redo logs that already have deity keys")
    ] = False,
) -> None:
    """Add the Deity stats (schema 1.3.0) to older logs from their saved power.log.

    Logs that already have them (plugin 0.6.0 or an earlier backfill) only get `golden` added.

    Originals are copied to <logs>/.backup/deity-<timestamp>/ before being rewritten.
    """
    import json
    import shutil

    root = _root(log_dir)
    backup = root / ".backup" / f"deity-{datetime.now():%Y%m%d-%H%M%S}"
    done = skipped = 0
    for path in loader.find_logs(root):
        log, reason = loader.load_log(path)
        if log is None:
            typer.echo(f"skip (invalid: {reason}) {path.name}")
            skipped += 1
            continue
        # Logs that already have deity values and lack the schema 1.3.0 `golden` key: the ones the
        # plugin wrote (0.6.0) keep their values and only get `golden`; the ones an earlier backfill
        # wrote are rebuilt (it read the opponent's card after the combat cleanup had reset it)
        has_keys = powerlog.has_deity_keys(log) and not force
        if has_keys and not powerlog.needs_golden(log):
            skipped += 1
            continue
        golden_only = has_keys and powerlog.BACKFILL_NOTE not in (log.get("notes") or [])
        plog = powerlog.power_log_for(path)
        if plog is None:
            typer.echo(f"skip (no power.log) {path.name}")
            skipped += 1
            continue
        deity = powerlog.parse_deity(powerlog.open_power_log(plog))
        if not deity:
            typer.echo(f"skip (no Deity in power.log) {path.name}")
            skipped += 1
            continue
        verb = "would fill" if dry_run else "filled"
        if golden_only:
            golden = powerlog.apply_golden(log, deity)
            typer.echo(f"{verb} golden ({golden} golden records) {path.name}")
        else:
            filled = powerlog.apply_deity(log, deity)
            awake = sum(1 for t in log["turns"] if (t.get("deity") or {}).get("awakened"))
            typer.echo(f"{verb} {filled} turns ({awake} awakenings) {path.name}")
        done += 1
        if dry_run:
            continue
        dest = backup / path.relative_to(root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        # the plugin writes CRLF + 2-space indent; keep the file looking the same
        text = json.dumps(log, ensure_ascii=False, indent=2).replace("\n", "\r\n")
        tmp = path.with_suffix(".json.tmp")
        tmp.write_bytes(text.encode("utf-8"))
        tmp.replace(path)
    typer.echo(f"{'would update' if dry_run else 'updated'}: {done}  skipped: {skipped}")
    if done and not dry_run:
        typer.echo(f"backup: {backup}")


@app.command()
def serve(
    log_dir: LogDir = None,
    port: Annotated[int, typer.Option(help="Port on 127.0.0.1")] = 8501,
    open_browser: Annotated[bool, typer.Option("--open/--no-open")] = True,
) -> None:
    """Start the local dashboard (Streamlit, bound to 127.0.0.1 only) and open the browser."""
    import subprocess
    import threading
    import webbrowser

    settings = _settings(log_dir)
    root = settings.logs_dir
    app_path = Path(__file__).with_name("dashboard") / "app.py"
    env = dict(os.environ, HSBG_LOGS=str(root))
    # Streamlit runs in analysis/, so hand over the workspace found from the current folder
    if settings.workspace:
        env[config.WORKSPACE_ENV] = str(settings.workspace)
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--server.fileWatcherType",
        "none",
        "--browser.gatherUsageStats",
        "false",
        "--browser.serverAddress",
        "127.0.0.1",
        # .streamlit/config.toml is not found when hsbg is installed as a package (uv tool install)
        "--theme.base",
        "light",
    ]
    url = f"http://127.0.0.1:{port}"
    typer.echo(f"dashboard: {url}  (logs: {root})  Ctrl+C to stop")
    if open_browser:
        threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    try:
        raise typer.Exit(code=subprocess.call(cmd, env=env, cwd=str(app_path.parents[2])))
    except KeyboardInterrupt:
        raise typer.Exit(code=0) from None


@app.command("config")
def config_cmd(
    log_dir: LogDir = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print as JSON (for scripts)")] = False,
) -> None:
    """Show the folders and language in effect, and where each value came from."""
    import json

    settings = _settings(log_dir)
    values = settings.as_dict()
    if as_json:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        typer.echo(json.dumps(values, ensure_ascii=False, indent=2))
        return
    ws = settings.workspace
    typer.echo(f"workspace: {ws / config.CONFIG_FILE if ws else '(none; defaults)'}")
    for key in config.ENV_VARS:
        value = values[key]
        mark = ""
        if key in config.PATH_KEYS and value is not None and not Path(value).exists():
            mark = "  (missing)"
        typer.echo(f"  {key:<14} {value or '-'}  [{settings.sources.get(key, 'default')}]{mark}")


@app.command()
def init(
    folder: Annotated[Path, typer.Argument(help="Workspace folder to create (or complete)")] = Path(
        "."
    ),
    knowledge: Annotated[
        bool,
        typer.Option(
            "--knowledge/--no-knowledge",
            help="Also create your own knowledge folder (knowledge/) and point knowledge_dir at it",
        ),
    ] = True,
) -> None:
    """Create a workspace: hsbg.toml (defaults, commented), analysis/, README.md, .gitignore and
    your own, empty knowledge folder (knowledge/). Files that already exist are left as they are."""
    for path, created in config.init_workspace(folder, knowledge=knowledge):
        typer.echo(f"{'created' if created else 'exists '}  {path}")
    typer.echo(f"next: cd {folder}; hsbg config")


skills_app = typer.Typer(
    help="hsbg's Claude Code skills in the workspace (.claude/skills/hsbg-*).", no_args_is_help=True
)
app.add_typer(skills_app, name="skills")


@skills_app.command("update")
def skills_update(log_dir: LogDir = None) -> None:
    """Copy this hsbg's skills into the workspace's .claude/skills/ (overwrites hsbg-* copies; run
    it after updating hsbg)."""
    settings = _settings(log_dir)
    if settings.workspace is None:
        typer.echo("no workspace: run hsbg init <folder> first (or from the workspace)", err=True)
        raise typer.Exit(code=2)
    for path, status in config.install_skills(settings.workspace):
        typer.echo(f"{status:<9}  {path}")


lens_app = typer.Typer(
    help="Your lenses: one folder per angle of analysis under the workspace's lenses/ "
    "(lens.toml, lens.md for the AI, metrics.py with @lens_table functions from hsbg.lens).",
    no_args_is_help=True,
)
app.add_typer(lens_app, name="lens")


def _lenses_dir(settings: config.Settings) -> Path:
    if settings.lenses_dir is None:
        typer.echo(
            "no workspace: lenses live in a workspace (hsbg init <folder>, then run hsbg there "
            f"or set {config.WORKSPACE_ENV})",
            err=True,
        )
        raise typer.Exit(code=2)
    return settings.lenses_dir


@lens_app.command("list")
def lens_list(log_dir: LogDir = None) -> None:
    """List the lenses with their status and tables."""
    folder = _lenses_dir(_settings(log_dir))
    found = lenses.discover(folder)
    typer.echo(f"lenses: {folder}")
    if not found:
        typer.echo("  (none; create one with: hsbg lens new <name>)")
    for ln in found:
        names = ", ".join(ts.name for ts, _ in ln.tables) or "-"
        typer.echo(f"  {ln.name:<20} {ln.status:<8} {ln.label}  [tables: {names}]")
        for w in ln.warnings:
            typer.echo(f"    warning: {w}")


@lens_app.command("new")
def lens_new(
    name: Annotated[str, typer.Argument(help="Folder name: lower case, digits, '-', '_'")],
    log_dir: LogDir = None,
) -> None:
    """Create a lens from the template (an example comparing top-4 and bottom-4 games)."""
    folder = _lenses_dir(_settings(log_dir))
    try:
        dest = lenses.create(folder, name)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from None
    except FileExistsError:
        typer.echo(f"error: {folder / name} already exists", err=True)
        raise typer.Exit(code=1) from None
    for p in sorted(dest.iterdir()):
        typer.echo(f"created  {p}")
    typer.echo(f"next: edit them, then hsbg lens check {name}")


@lens_app.command("check")
def lens_check(
    name: Annotated[str | None, typer.Argument(help="Only this lens")] = None,
    log_dir: LogDir = None,
) -> None:
    """Load every lens (or one), run its tables on your logs and report problems; runs the lens's
    test_*.py with pytest when pytest is installed. Exit code 1 when something is wrong."""
    import importlib.util
    import subprocess

    settings = _settings(log_dir)
    found = lenses.discover(_lenses_dir(settings))
    if name:
        found = [ln for ln in found if ln.name == name]
        if not found:
            typer.echo(f"error: no lens '{name}' in {settings.lenses_dir}", err=True)
            raise typer.Exit(code=1)
    tables, _ = _load(settings.logs_dir, quiet=True)
    filtered = metrics.apply_filter(tables, metrics.LogFilter())
    typer.echo(f"games: {len(filtered.games)} ({settings.logs_dir})")
    failed = False
    for ln in found:
        found_problems = lenses.problems(ln, lenses.run(ln, filtered))
        tests = sorted(ln.folder.glob("test_*.py"))
        if tests and importlib.util.find_spec("pytest") is None:
            found_problems.append("test_*.py not run: pytest is not installed")
        elif tests:
            code = subprocess.call([sys.executable, "-m", "pytest", "-q", str(ln.folder)])
            if code != 0:
                found_problems.append(f"pytest failed (exit {code})")
        failed |= bool(found_problems)
        tables_note = f"{len(ln.tables)} tables" if ln.tables else "lens.md only"
        typer.echo(f"{'FAIL' if found_problems else 'ok  '}  {ln.name} ({tables_note})")
        for p in found_problems:
            typer.echo(f"      {p}")
    if not found:
        typer.echo("no lenses")
    raise typer.Exit(code=1 if failed else 0)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
