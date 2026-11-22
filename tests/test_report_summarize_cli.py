from pathlib import Path

from conftest import FIXTURES
from typer.testing import CliRunner

from hsbg import metrics, report, summarize
from hsbg.cli import app
from hsbg.normalize import Tables

runner = CliRunner()


def test_build_report_contains_sections(tables: Tables) -> None:
    f = metrics.apply_filter(tables, metrics.LogFilter())
    html = report.build_report(f, excluded_incomplete=1)
    for section in (
        "KPI",
        "MMR 推移",
        "順位分布",
        "ヒーロー別成績",
        "種族",
        "ティア到達ターン",
        "ターン別 戦闘勝率",
        "体力の推移",
        "相手ヒーロー別 戦闘成績",
        "直近のゲーム",
    ):
        assert f"<h2>{section}</h2>" in html
    assert "plotly" in html.lower()
    assert "未完了ログ 1 件を除外" in html
    assert "file:///" in html  # link to the json


def test_build_report_with_no_games(tables: Tables) -> None:
    empty = tables.subset([])
    html = report.build_report(empty)
    assert "ゲームなし" in html


def test_summarize_markdown(complete_logs: list[dict], tables: Tables) -> None:
    log = max(complete_logs, key=lambda g: g["game"]["started_at"])
    md = summarize.summarize(log, metrics.apply_filter(tables, metrics.LogFilter()))
    assert md.startswith("# Game 2026-")
    assert "## Turn-by-turn" in md and "## Key moments" in md and "## Final board" in md
    rows = [line for line in md.splitlines() if line.startswith("| ") and line[2].isdigit()]
    assert len(rows) == log["result"]["total_turns"]
    assert "Placement: 3/8" in md or "Placement:" in md


def test_summarize_minion_divine_shields() -> None:
    base = {"name": "Dark Paradox", "attack": 10, "health": 10, "golden": False}
    stacked = {**base, "keywords": ["taunt", "divine_shield"], "divine_shields": 3}
    assert summarize._minion(stacked) == "Dark Paradox 10/10 [TD3]"
    # 1.3.x logs have no count: a single shield
    assert summarize._minion({**base, "keywords": ["divine_shield"]}) == "Dark Paradox 10/10 [D]"


def test_summarize_hand_and_shop_section() -> None:
    # schema 1.5.0 only: older logs print no section
    assert summarize._hand_shop_section([{"turn": 1, "hand_end_of_shop": None}]) == []
    gem = {"name": "Blood Gem", "card_type": "spell", "tier": 1}
    boar = {"name": "Felboar", "card_type": "minion", "tier": 5, "attack": 6, "health": 7}
    turn = {
        "turn": 6,
        "hand_end_of_shop": [gem, {**boar, "golden": True}],
        "shop_offers": [
            {"trigger": "turn_start", "cards": [boar]},
            {"trigger": "reroll", "cards": [gem]},
        ],
        "lobby": [
            {"tavern_tier": 3, "eliminated": False},
            {"tavern_tier": 5, "eliminated": False},
            {"tavern_tier": 6, "eliminated": True},
        ],
        "combat": {"opponent_tavern_tier": 4},
    }
    lines = summarize._hand_shop_section([turn])
    assert "## Hand and shop" in lines
    assert lines[-1] == (
        "| 6 | Blood Gem (spell), Felboar★ (t5 6/7) | [start] Felboar (t5 6/7) / "
        "[roll] Blood Gem (spell) | 4 | 5, 3 |"
    )


def test_cli_validate_reports_invalid() -> None:
    result = runner.invoke(app, ["validate", "--dir", str(FIXTURES)])
    assert result.exit_code == 1  # broken.json
    assert "INVALID" in result.stdout and "incomplete: 1" in result.stdout


def test_cli_report_and_export(tmp_path: Path) -> None:
    out = tmp_path / "r.html"
    result = runner.invoke(
        app, ["report", "--dir", str(FIXTURES), "--last", "3", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert out.exists() and out.stat().st_size > 100_000
    assert "games: 3" in result.stdout

    result = runner.invoke(
        app, ["export", "--dir", str(FIXTURES), "--format", "csv", "--out", str(tmp_path / "exp")]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "exp" / "games.csv").exists()
    assert (tmp_path / "exp" / "combats.csv").exists()


def test_cli_summarize_latest(tmp_path: Path) -> None:
    out = tmp_path / "s.md"
    result = runner.invoke(app, ["summarize", "latest", "--dir", str(FIXTURES), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.read_text("utf-8").startswith("# Game ")


def test_cli_stats_markdown(tmp_path: Path) -> None:
    out = tmp_path / "stats.md"
    result = runner.invoke(app, ["stats", "--dir", str(FIXTURES), "--out", str(out)])
    assert result.exit_code == 0, result.output
    md = out.read_text("utf-8")
    for section in (
        "## Heroes",
        "## Combat win rate by turn",
        "## Opponent heroes",
        "## Minion types offered vs played",
        "## Final board main type vs placement",
        "## Main type by phase",
        "## Type matchups",
        "## Opponent main types",
        "## Recent games",
    ):
        assert section in md
    assert "| キシックス |" in md  # Japanese name from the CardDefs fixture
    result = runner.invoke(app, ["stats", "--dir", str(FIXTURES), "--since", "2030-01-01"])
    assert result.exit_code == 0 and "no games" in result.stdout
    result = runner.invoke(app, ["stats", "--dir", str(FIXTURES), "--min-mmr", "99999"])
    assert result.exit_code == 0 and "no games" in result.stdout
    assert "starting MMR 99999-" in result.stdout


def test_summarize_gold_gained(complete_logs: list[dict], tables: Tables) -> None:
    import copy

    log = copy.deepcopy(max(complete_logs, key=lambda g: g["game"]["started_at"]))
    filtered = metrics.apply_filter(tables, metrics.LogFilter())
    # schema 1.5.x and older: no legend, no "+N"
    assert "gold gained without selling" not in summarize.summarize(log, filtered)
    turn = next(t for t in log["turns"] if t.get("actions"))
    turn["actions"]["gold_gained"] = 4
    md = summarize.summarize(log, filtered)
    assert "gold gained without selling" in md
    assert any(
        line.startswith(f"| {turn['turn']} |") and " +4 |" in line for line in md.splitlines()
    )


def test_summarize_and_key_moments_mark_ice_block(
    complete_logs: list[dict], tables: Tables
) -> None:
    import copy

    log = copy.deepcopy(max(complete_logs, key=lambda g: g["game"]["started_at"]))
    filtered = metrics.apply_filter(tables, metrics.LogFilter())
    # schema 1.9.x and older: no key, nothing marked
    assert "Ice Block" not in summarize.summarize(log, filtered)
    turn = next(t for t in log["turns"] if t.get("combat"))
    turn["combat"].update(
        {"result": "loss", "damage_dealt": 0, "damage_taken": 15, "ice_block": True}
    )
    md = summarize.summarize(log, filtered)
    assert any(
        line.startswith(f"| {turn['turn']} |") and "-15 (my Ice Block)" in line
        for line in md.splitlines()
    )
    moments = metrics.key_moments(log)
    assert any(f"T{turn['turn']}: my Ice Block prevented lethal damage (15" in m for m in moments)
    ja = metrics.key_moments(log, lang="ja")
    assert any("自分のアイスブロック" in m for m in ja)

    turn["combat"].update(
        {"result": "win", "damage_dealt": 23, "damage_taken": 0, "ice_block": False}
    )
    turn["combat"]["opponent_ice_block"] = True
    md = summarize.summarize(log, filtered)
    assert any("+23 (opp. Ice Block)" in line for line in md.splitlines())
    assert any("Ice Block prevented my lethal damage (23)" in m for m in metrics.key_moments(log))


def test_choices_are_summarized_and_normalized(complete_logs: list[dict], tables: Tables) -> None:
    import copy

    from hsbg import normalize

    log = copy.deepcopy(max(complete_logs, key=lambda g: g["game"]["started_at"]))
    filtered = metrics.apply_filter(tables, metrics.LogFilter())
    # schema 1.10.x and older: no choices, no section, empty tables
    assert "## Choices" not in summarize.summarize(log, filtered)
    assert normalize.normalize([log]).choices.empty
    turn = log["turns"][0]

    def card(cid: str, tier: int, atk: int, hp: int) -> dict:
        return {
            "card_id": cid, "name": cid, "dbf_id": None, "card_type": "minion",
            "tier": tier, "attack": atk, "health": hp, "golden": False,
        }  # fmt: skip

    turn["choices"] = [
        {
            "source": "triple",
            "source_card": {"card_id": "TB_BaconShop_Triples_01", "name": "Triple Reward"},
            "offered": [card("BG_A", 3, 3, 3), card("BG_B", 3, 4, 5), card("BG_C", 3, 2, 2)],
            "chosen_index": 1,
        },
        {
            "source": "card",
            "source_card": {"card_id": "BG31_890", "name": "Some Minion"},
            "offered": [card("BG_D", 2, 2, 2), card("BG_E", 2, 1, 3)],
            "chosen_index": None,
        },
    ]
    md = summarize.summarize(log, filtered)
    assert "## Choices" in md
    assert any("Triple Reward" in line and "→ BG_B (t3 4/5)" in line for line in md.splitlines())
    assert any("Some Minion" in line and line.endswith("| - |") for line in md.splitlines())

    t = normalize.normalize([log])
    assert list(t.choices["source"]) == ["triple", "card"]
    assert list(t.choices["chosen_card_id"].fillna("")) == ["BG_B", ""]
    assert list(t.choices["offered_count"]) == [3, 2]
    offers = t.choice_offers
    assert len(offers) == 5
    first = offers[offers["choice"] == 1]
    assert list(first["chosen"]) == [False, True, False]
    assert offers[offers["choice"] == 2]["chosen"].isna().all()

    # Getaway Galewing: the hero power picks a destination (pick); the destination card discovers
    # on arrival ("Hero power → <destination>")
    log["player"]["hero_power"] = {"card_id": "BG20_HERO_283p", "name": "Dungar's Gryphon"}
    dest = {"card_id": "BG20_HERO_283p_t3", "name": "Eastern Plaguelands", "card_type": "other"}
    turn["choices"] = [
        {
            "source": "hero_power",
            "source_card": {"card_id": "BG20_HERO_283p", "name": "Dungar's Gryphon"},
            "offered": [dest],
            "chosen_index": 0,
        },
        {
            "source": "hero_power",
            "source_card": {"card_id": "BG20_HERO_283p_t3", "name": "Eastern Plaguelands"},
            "offered": [card("BG_F", 2, 2, 2)],
            "chosen_index": 0,
        },
    ]
    rows = [
        line
        for line in summarize.summarize(log, filtered).splitlines()
        if line.startswith("| ") and "Hero power" in line
    ]
    assert "| Hero power (Dungar's Gryphon) | pick |" in rows[0]
    assert "| Hero power → Eastern Plaguelands | discover |" in rows[1]
