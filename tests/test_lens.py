"""Lenses (docs/lenses.md): loading, running, failure isolation, stats / dashboard / CLI."""

import os
import textwrap
from pathlib import Path

import pandas as pd
import pytest
from conftest import FIXTURES
from streamlit.testing.v1 import AppTest
from typer.testing import CliRunner

from hsbg import charts, config, lens, lenses, markdown, metrics
from hsbg.cli import app
from hsbg.normalize import Tables

GOOD = """
import pandas as pd
from hsbg.lens import Tables, lens_table

@lens_table("per_hero", "Games per hero", chart="bar", x="hero_name", y="games")
def per_hero(t: Tables) -> pd.DataFrame:
    return t.games.groupby("hero_name").size().reset_index(name="games")

@lens_table("boom", "Raises")
def boom(t: Tables) -> pd.DataFrame:
    raise RuntimeError("bad lens")

@lens_table("not_df", "Not a DataFrame")
def not_df(t: Tables):
    return [1, 2]

@lens_table("bad_chart", "Chart column missing", chart="line", x="turn", y="nope")
def bad_chart(t: Tables) -> pd.DataFrame:
    return pd.DataFrame({"turn": [1, 2], "value": [3, 4]})

def helper(t):  # not a lens table
    return None
"""


def _lens(root: Path, name: str, code: str | None, toml: str = 'label = "L"\n') -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "lens.toml").write_text(toml, encoding="utf-8")
    (folder / "lens.md").write_text("# guide\n", encoding="utf-8")
    if code is not None:
        (folder / "metrics.py").write_text(textwrap.dedent(code), encoding="utf-8")
    return folder


@pytest.fixture
def filtered(tables: Tables) -> Tables:
    return metrics.apply_filter(tables, metrics.LogFilter())


def test_lens_table_validates_its_arguments() -> None:
    with pytest.raises(ValueError):
        lens.lens_table("x", "X", chart="pie")
    with pytest.raises(ValueError):
        lens.lens_table("x", "X", chart="bar", x="a")


def test_discover_load_and_run_isolate_failures(tmp_path: Path, filtered: Tables) -> None:
    _lens(tmp_path, "good", GOOD)
    [ln] = lenses.discover(tmp_path)
    assert ln.name == "good" and ln.label == "L" and ln.active and ln.warnings == []
    # definition order, helpers without @lens_table are ignored
    assert [ts.name for ts, _ in ln.tables] == ["per_hero", "boom", "not_df", "bad_chart"]
    results = {r.spec.name: r for r in lenses.run(ln, filtered)}
    assert results["per_hero"].error is None
    assert results["per_hero"].df is not None
    assert results["per_hero"].df["games"].sum() == len(filtered.games)
    assert results["boom"].error == "RuntimeError: bad lens"
    assert "not a pandas DataFrame" in (results["not_df"].error or "")
    problems = lenses.problems(ln, list(results.values()))
    assert any(p.startswith("boom:") for p in problems)
    assert any("'nope' is not in the result" in p for p in problems)
    assert not any(p.startswith("per_hero") for p in problems)


def test_broken_code_and_toml_become_warnings(tmp_path: Path) -> None:
    _lens(tmp_path, "syntax", "def broken(:\n")
    _lens(tmp_path, "badtoml", None, toml="label = \n")
    _lens(tmp_path, "future", None, toml='label = "F"\napi = 99\nstatus = "paused"\ncolor = 1\n')
    _lens(
        tmp_path,
        "bad-chart",
        'from hsbg.lens import lens_table\n@lens_table("a", "A", chart="pie")\ndef a(t): ...\n',
    )
    by_name = {ln.name: ln for ln in lenses.discover(tmp_path)}
    assert any("SyntaxError" in w for w in by_name["syntax"].warnings)
    assert by_name["badtoml"].warnings and by_name["badtoml"].label == "badtoml"
    future = by_name["future"]
    assert future.status == "active"  # unknown status falls back
    assert any("newer than this hsbg" in w for w in future.warnings)
    assert any("unknown key 'color'" in w for w in future.warnings)
    assert any("ValueError" in w for w in by_name["bad-chart"].warnings)
    assert by_name["syntax"].tables == []


def test_lens_md_only_lens_is_fine(tmp_path: Path) -> None:
    _lens(tmp_path, "notes", None)
    [ln] = lenses.discover(tmp_path)
    assert ln.tables == [] and lenses.problems(ln, []) == []


def test_discover_without_folder() -> None:
    assert lenses.discover(None) == []
    assert lenses.discover(Path("no-such-folder")) == []


def test_template_lens_runs_cleanly_on_the_fixtures(tmp_path: Path, filtered: Tables) -> None:
    folder = lenses.create(tmp_path, "starter")
    assert {p.name for p in folder.iterdir()} == {"lens.toml", "lens.md", "metrics.py"}
    assert "__NAME__" not in (folder / "lens.md").read_text(encoding="utf-8")
    [ln] = lenses.discover(tmp_path)
    assert ln.label == "starter" and ln.warnings == []
    results = lenses.run(ln, filtered)
    assert [r.spec.name for r in results] == ["top4_vs_bottom4", "placement_by_final_tier"]
    assert lenses.problems(ln, results) == []
    for r in results:
        assert r.df is not None and not r.df.empty
        fig = charts.lens_figure(r.df, r.spec.chart, r.spec.x, r.spec.y, r.spec.color, "t")
        assert fig is not None and len(fig.data) == 1


def test_create_rejects_bad_or_existing_names(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        lenses.create(tmp_path, "My Lens")
    lenses.create(tmp_path, "ok")
    with pytest.raises(FileExistsError):
        lenses.create(tmp_path, "ok")


def test_compare_groups(tables: Tables) -> None:
    f = metrics.early_game_features(tables)
    comp = metrics.compare_groups(f, {"hp_t8": "HP T8", "no_such_column": "x", "tier4_turn": "T4"})
    assert list(comp["feature"]) == ["HP T8", "T4"]  # order kept, missing columns skipped
    bot = f.loc[f["group"] == "bottom4", "hp_t8"]
    row = comp.iloc[0]
    assert row["bottom4"] == bot.median() and row["games_bottom4"] == bot.notna().sum()
    assert row["diff"] == row["bottom4"] - row["top4"]
    assert metrics.compare_groups(pd.DataFrame(), {"tier3_turn": "x"}).empty


def test_lens_figure_kinds() -> None:
    df = pd.DataFrame({"turn": [1, 2, 1, 2], "v": [1, 2, 3, 4], "who": ["a", "a", "b", "b"]})
    assert charts.lens_figure(df, "table", None, None) is None
    assert len(charts.lens_figure(df, "line", "turn", "v", "who").data) == 2
    assert len(charts.lens_figure(df, "bar", "turn", "v").data) == 1
    missing = charts.lens_figure(df, "bar", "turn", "nope")
    assert missing is not None and not missing.data
    barh = charts.lens_figure(df, "barh", "turn", "v", "who")
    assert barh is not None and barh.data[0].orientation == "h"


SHOWN = """
import pandas as pd
from hsbg.lens import Tables, lens_table

def _ja(df):
    df["answer"] = df["answer"].map({"yes": "はい", "no": "いいえ"})
    return df

@lens_table("yn", "Yes / no", chart="barh", x="answer", y="n", title="はい / いいえ",
            note="説明", display=_ja, columns={"answer": "答え", "n": "数"})
def yn(t: Tables) -> pd.DataFrame:
    return pd.DataFrame({"answer": ["yes", "no"], "n": [3, 4]})

@lens_table("broken_display", "Broken", display=lambda df: 1 / 0)
def broken(t: Tables) -> pd.DataFrame:
    return pd.DataFrame({"a": [1]})

@lens_table("lost_column", "Lost", chart="bar", x="a", y="b", display=lambda df: df[["a"]])
def lost(t: Tables) -> pd.DataFrame:
    return pd.DataFrame({"a": [1], "b": [2]})
"""


def test_shown_table_display_and_columns(tmp_path: Path, filtered: Tables) -> None:
    _lens(tmp_path, "shown", SHOWN)
    [ln] = lenses.discover(tmp_path)
    results = {r.spec.name: r for r in lenses.run(ln, filtered)}
    yn = results["yn"]
    assert yn.spec.title == "はい / いいえ" and yn.spec.note == "説明"
    shown = lenses.shown_table(yn)
    assert shown.error is None and shown.df is not None
    assert list(shown.df.columns) == ["答え", "数"]
    assert list(shown.df["答え"]) == ["はい", "いいえ"]
    assert (shown.x, shown.y) == ("答え", "数")
    assert list(yn.df["answer"]) == ["yes", "no"]  # stats keeps the returned values
    assert "ZeroDivisionError" in (lenses.shown_table(results["broken_display"]).error or "")
    problems = lenses.problems(ln, list(results.values()))
    assert any(p.startswith("broken_display: display:") for p in problems)
    assert any("'b' is lost by display" in p for p in problems)
    assert not any(p.startswith("yn") for p in problems)


def test_stats_markdown_sections(tmp_path: Path, filtered: Tables) -> None:
    _lens(tmp_path, "good", GOOD, toml='label = "My lens"\ndescription = "why"\n')
    [ln] = lenses.discover(tmp_path)
    text = markdown.lenses_markdown([(ln, lenses.run(ln, filtered))])
    assert "## Lens: My lens (`good`)" in text
    assert "why" in text and "lens.md" in text
    assert "### Games per hero" in text and "| hero_name | games |" in text
    assert "_error: RuntimeError: bad lens_" in text


def _workspace(root: Path) -> Path:
    ws = root / "ws"
    config.init_workspace(ws, knowledge=False)
    return ws


def test_cli_lens_commands_and_stats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _workspace(tmp_path)
    runner = CliRunner()
    env = {"HSBG_WORKSPACE": str(ws), "HSBG_LOGS": str(FIXTURES)}
    result = runner.invoke(app, ["lens", "list"], env=env)
    assert result.exit_code == 0 and "(none" in result.output
    result = runner.invoke(app, ["lens", "new", "starter"], env=env)
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["lens", "check"], env=env)
    assert result.exit_code == 0, result.output
    assert "ok    starter (2 tables)" in result.output
    result = runner.invoke(app, ["stats"], env=env)
    assert result.exit_code == 0
    assert "## Lens: starter (`starter`)" in result.output
    assert "## Lens:" not in runner.invoke(app, ["stats", "--no-lenses"], env=env).output
    # a retired lens is listed but not shown
    toml = ws / "lenses" / "starter" / "lens.toml"
    toml.write_text(toml.read_text("utf-8").replace('"active"', '"retired"'), encoding="utf-8")
    assert "## Lens:" not in runner.invoke(app, ["stats"], env=env).output
    assert "retired" in runner.invoke(app, ["lens", "list"], env=env).output
    # a failing lens fails the check
    _lens(ws / "lenses", "good", GOOD)
    result = runner.invoke(app, ["lens", "check", "good"], env=env)
    assert result.exit_code == 1 and "FAIL  good" in result.output


def test_cli_lens_needs_a_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["lens", "list"], env={"HSBG_WORKSPACE": ""})
    assert result.exit_code == 2
    assert "no workspace" in result.output


_PAGE_SCRIPT = """
import os
from pathlib import Path
from hsbg import config
from hsbg.dashboard import data
from hsbg.dashboard.filters import FilterState
from hsbg.dashboard.views import my_lenses
ctx = data.load_context(Path(os.environ["HSBG_LOGS"]), FilterState())
my_lenses.render(ctx, config.load().lenses_dir)
"""


def test_dashboard_page_renders_lens_tables(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    lenses.create(ws / "lenses", "starter")
    _lens(ws / "lenses", "good", GOOD)
    os.environ["HSBG_LOGS"] = str(FIXTURES)
    os.environ["HSBG_WORKSPACE"] = str(ws)
    try:
        at = AppTest.from_string(_PAGE_SCRIPT, default_timeout=60)
        at.run()
    finally:
        del os.environ["HSBG_WORKSPACE"]
    assert not at.exception, [str(e) for e in at.exception]
    assert at.title[0].value == "マイ分析"
    assert [h.value for h in at.header] == ["L", "starter"]
    assert len(at.error) == 2  # boom, not_df
    assert len(at.dataframe) == 2 + 2  # good: per_hero, bad_chart; starter: 2


def test_dashboard_page_without_workspace() -> None:
    os.environ["HSBG_LOGS"] = str(FIXTURES)
    script = _PAGE_SCRIPT.replace("config.load().lenses_dir", "None")
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    assert not at.exception
    assert "hsbg init" in at.info[0].value
