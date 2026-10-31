import json
import re
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hsbg import cards, config, loader
from hsbg.cli import app

ENV_NAMES = ["HSBG_WORKSPACE", *(e for e in config.ENV_VARS.values() if e)]


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """No hsbg environment variables, a fake home, and a current folder without hsbg.toml."""
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return tmp_path


def test_defaults_without_workspace_match_the_old_behaviour(clean_env: Path) -> None:
    s = config.load()
    logs = clean_env / "home" / "Documents" / "HSBG-Logs"
    assert s.workspace is None
    assert s.logs_dir == logs
    assert s.analysis_dir == logs / "analysis"
    assert s.reports_dir == logs / "reports"
    assert s.export_dir == logs / "export"
    assert s.knowledge_dir is None
    assert s.carddefs_dir == clean_env / "appdata" / "HearthstoneDeckTracker" / "CardDefs"
    assert s.locale == "jaJP"
    assert set(s.sources.values()) == {"default"}
    assert s.warnings == ()


def test_cli_dir_moves_the_derived_folders_without_workspace(clean_env: Path) -> None:
    s = config.load(clean_env / "logs")
    assert s.sources["logs_dir"] == "option"
    assert s.reports_dir == clean_env / "logs" / "reports"


def test_workspace_found_above_the_current_folder(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = clean_env / "ws"
    (ws / "deep" / "er").mkdir(parents=True)
    (ws / "hsbg.toml").write_text("", encoding="utf-8")
    monkeypatch.chdir(ws / "deep" / "er")
    s = config.load()
    assert s.workspace == ws.resolve()
    # with a workspace, analyses / reports / exports default to it; logs stay at the plugin's folder
    assert s.analysis_dir == ws.resolve() / "analysis"
    assert s.reports_dir == ws.resolve() / "reports"
    assert s.logs_dir == clean_env / "home" / "Documents" / "HSBG-Logs"


def test_toml_values_relative_paths_and_env_expansion(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = clean_env / "ws"
    ws.mkdir()
    monkeypatch.setenv("HSBG_TEST_DRIVE", str(clean_env / "drive"))
    (ws / "hsbg.toml").write_text(
        "logs_dir = '%HSBG_TEST_DRIVE%\\HSBG-Logs'\n"
        "analysis_dir = 'notes'\n"
        "knowledge_dir = '../knowledge'\n"
        "locale = 'enUS'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HSBG_WORKSPACE", str(ws))
    s = config.load()
    assert s.logs_dir == Path(str(clean_env / "drive") + "\\HSBG-Logs")
    assert s.analysis_dir == ws / "notes"
    assert s.knowledge_dir == ws / "../knowledge"
    assert s.locale == "enUS"
    assert s.sources["logs_dir"] == "hsbg.toml"
    assert s.sources["reports_dir"] == "default"


def test_env_beats_toml_and_option_beats_env(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = clean_env / "ws"
    ws.mkdir()
    (ws / "hsbg.toml").write_text("logs_dir = 'from-toml'\nlocale = 'enUS'\n", encoding="utf-8")
    monkeypatch.setenv("HSBG_WORKSPACE", str(ws))
    monkeypatch.setenv("HSBG_LOGS", str(clean_env / "from-env"))
    monkeypatch.setenv("HSBG_LOCALE", "jaJP")
    s = config.load()
    assert s.logs_dir == clean_env / "from-env"
    assert s.sources["logs_dir"] == "env HSBG_LOGS"
    assert s.locale == "jaJP"
    assert config.load(clean_env / "opt").logs_dir == clean_env / "opt"


def test_bad_settings_warn_and_fall_back(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = clean_env / "ws"
    ws.mkdir()
    (ws / "hsbg.toml").write_text("logs = 'typo'\nlocale = 3\n", encoding="utf-8")
    monkeypatch.setenv("HSBG_WORKSPACE", str(ws))
    s = config.load()
    assert s.locale == "jaJP"
    assert any("unknown setting 'logs'" in w for w in s.warnings)
    assert any("'locale'" in w for w in s.warnings)

    (ws / "hsbg.toml").write_text("logs_dir = 'unclosed\n", encoding="utf-8")
    s = config.load()
    assert s.logs_dir == clean_env / "home" / "Documents" / "HSBG-Logs"
    assert len(s.warnings) == 1


def test_workspace_env_without_toml_warns(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HSBG_WORKSPACE", str(clean_env / "nowhere"))
    s = config.load()
    assert s.workspace == clean_env / "nowhere"
    assert s.analysis_dir == clean_env / "nowhere" / "analysis"
    assert any("no hsbg.toml" in w for w in s.warnings)


def test_unknown_variables_are_left_as_they_are() -> None:
    assert config.expand("%HSBG_NO_SUCH_VAR%\\x") == Path("%HSBG_NO_SUCH_VAR%\\x")


def test_loader_and_cards_follow_the_settings(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = clean_env / "ws"
    ws.mkdir()
    (ws / "hsbg.toml").write_text(
        "logs_dir = 'logs'\ncarddefs_dir = 'cd'\nlocale = 'enUS'\n", encoding="utf-8"
    )
    monkeypatch.setenv("HSBG_WORKSPACE", str(ws))
    assert loader.default_log_dir() == ws / "logs"
    assert cards.default_dir() == ws / "cd"
    assert cards.default_locale() == "enUS"


def _rel(ws: Path, items: list[tuple[Path, bool]]) -> dict[str, bool]:
    return {p.relative_to(ws).as_posix(): c for p, c in items}


def test_init_creates_the_workspace_with_its_own_knowledge_folder(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = clean_env / "ws"
    created = _rel(ws, config.init_workspace(ws))
    assert all(created.values())
    for name in ["hsbg.toml", ".gitignore", "README.md", "analysis"]:
        assert name in created
    for name in ["README.md", "CLAUDE.md", "patches/_template.md", "season/README.md"]:
        assert f"knowledge/{name}" in created
    assert "gitignore" not in created  # stored under another name in the package only
    # valid TOML; the only active line points at the knowledge folder it just created
    assert tomllib.loads((ws / "hsbg.toml").read_text(encoding="utf-8")) == {
        "knowledge_dir": "knowledge"
    }
    monkeypatch.setenv("HSBG_WORKSPACE", str(ws))
    s = config.load()
    assert s.knowledge_dir == ws / "knowledge"
    assert s.sources["knowledge_dir"] == "hsbg.toml"
    # every setting is documented in the template
    text = (ws / "hsbg.toml").read_text(encoding="utf-8")
    for key in config.ENV_VARS:
        assert f"{key} = " in text


def test_init_keeps_existing_files(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    config.init_workspace(ws)
    (ws / "hsbg.toml").write_text("locale = 'enUS'\n", encoding="utf-8")
    (ws / "knowledge" / "README.md").write_text("mine\n", encoding="utf-8")
    again = config.init_workspace(ws)
    assert not any(c for _, c in again)
    assert (ws / "hsbg.toml").read_text(encoding="utf-8") == "locale = 'enUS'\n"
    assert (ws / "knowledge" / "README.md").read_text(encoding="utf-8") == "mine\n"


def test_init_without_knowledge(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    created = _rel(ws, config.init_workspace(ws, knowledge=False))
    assert not any(name.startswith("knowledge") for name in created)
    assert not (ws / "knowledge").exists()
    text = (ws / "hsbg.toml").read_text(encoding="utf-8")
    assert tomllib.loads(text) == {}
    assert "# knowledge_dir = 'knowledge'" in text


def test_template_lines_uncommented_are_valid_and_resolve(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = clean_env / "ws"
    config.init_workspace(ws)
    lines = (ws / "hsbg.toml").read_text(encoding="utf-8").splitlines()
    settings = [line.removeprefix("# ") for line in lines if " = '" in line]
    (ws / "hsbg.toml").write_text("\n".join(settings) + "\n", encoding="utf-8")
    monkeypatch.setenv("HSBG_WORKSPACE", str(ws))
    monkeypatch.setenv("USERPROFILE", str(clean_env / "home"))
    s = config.load()
    assert s.warnings == ()
    assert s.logs_dir == Path(str(clean_env / "home") + "\\Documents\\HSBG-Logs")
    assert s.analysis_dir == ws / "analysis"
    assert s.knowledge_dir == ws / "knowledge"


def test_cli_config_and_init(clean_env: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["init", "ws"])
    assert result.exit_code == 0, result.output
    assert "created" in result.output
    result = runner.invoke(app, ["config", "--json"], env={"HSBG_WORKSPACE": "ws"})
    assert result.exit_code == 0, result.output
    values = json.loads(result.output)
    assert values["workspace"] == "ws"
    assert values["analysis_dir"] == str(Path("ws") / "analysis")
    assert values["knowledge_dir"] == str(Path("ws") / "knowledge")
    result = runner.invoke(app, ["init", "bare", "--no-knowledge"])
    assert result.exit_code == 0, result.output
    assert not Path("bare", "knowledge").exists()
    result = runner.invoke(app, ["config"], env={"HSBG_WORKSPACE": "ws"})
    assert "analysis_dir" in result.output and "[default]" in result.output


def test_init_installs_the_skills_and_update_refreshes_them(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    created = _rel(ws, config.init_workspace(ws, knowledge=False))
    for name in ("hsbg-analysis/SKILL.md", "hsbg-analysis/analyze-game.md", "hsbg-lens/SKILL.md"):
        assert created[f".claude/skills/{name}"] is True
    skill = ws / ".claude" / "skills" / "hsbg-analysis" / "SKILL.md"
    skill.write_text("edited\n", encoding="utf-8")
    status = {p.relative_to(ws).as_posix(): s for p, s in config.install_skills(ws)}
    assert status[".claude/skills/hsbg-analysis/SKILL.md"] == "updated"
    assert status[".claude/skills/hsbg-lens/SKILL.md"] == "unchanged"
    assert skill.read_text(encoding="utf-8").startswith("---\nname: hsbg-analysis")


def test_cli_skills_update(clean_env: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["skills", "update"]).exit_code == 2  # no workspace
    runner.invoke(app, ["init", "ws", "--no-knowledge"])
    result = runner.invoke(app, ["skills", "update"], env={"HSBG_WORKSPACE": "ws"})
    assert result.exit_code == 0 and "unchanged" in result.output


def test_templates_hold_no_personal_data() -> None:
    """What hsbg init / lens new / skills update hand out is the same for every player: no user
    folder, e-mail address or one player's analysis lists (scripts/check_private.py checks the
    words only a deny list knows)."""
    personal = [
        re.compile(r"[A-Za-z]:\\Users\\(?!<|%)\w", re.IGNORECASE),  # a real user folder
        re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE),  # an e-mail address
        re.compile(r"Bottom-4 NG behaviours"),  # the author's running list
    ]
    for path in (Path(config.__file__).parent / "templates").rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            text = path.read_text(encoding="utf-8")
            for pattern in personal:
                assert not pattern.search(text), f"{path}: {pattern.pattern}"


def test_knowledge_template_pool_tool_runs(tmp_path: Path) -> None:
    """The knowledge folder's tools/pool.py runs inside a fresh workspace (stdlib only)."""
    import subprocess
    import sys

    from conftest import CARDDEFS

    ws = tmp_path / "ws"
    config.init_workspace(ws)
    tool = ws / "knowledge" / "tools" / "pool.py"
    done = subprocess.run(
        [sys.executable, "-I", str(tool), "snapshot", "--carddefs", str(CARDDEFS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert done.returncode == 0, done.stderr
    assert sorted(p.suffix for p in (ws / "knowledge" / "season" / "pool").glob("*_build*")) == [
        ".json",
        ".md",
    ]


def test_knowledge_template_pool_tool_without_a_localized_carddefs(tmp_path: Path) -> None:
    """An English client has only CardDefs.base.xml: the snapshot is English only."""
    import shutil
    import subprocess
    import sys

    from conftest import CARDDEFS

    ws = tmp_path / "ws"
    config.init_workspace(ws)
    cd = tmp_path / "cd"
    cd.mkdir()
    shutil.copy(CARDDEFS / "CardDefs.base.xml", cd)
    tool = ws / "knowledge" / "tools" / "pool.py"

    def run(*extra: str) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, "-I", str(tool), "snapshot", "--carddefs", str(cd), *extra]
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    done = run()
    assert done.returncode == 0, done.stderr
    [snap] = (ws / "knowledge" / "season" / "pool").glob("*_build*.json")
    meta = json.loads(snap.read_text(encoding="utf-8"))["meta"]
    assert "build_base" in meta and not any(k.startswith("build_ja") for k in meta)
    assert run("--locale", "jaJP").returncode != 0  # asked for a language HDT did not download
