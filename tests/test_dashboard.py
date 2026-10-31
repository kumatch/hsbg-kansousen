"""Dashboard tests: filter helpers, KPI parity with the static report, AppTest smoke run,
and the 500-game performance budget."""

import json
import os
import shutil
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from conftest import FIXTURES
from streamlit.testing.v1 import AppTest

from hsbg import cache, metrics, normalize, report
from hsbg.dashboard.filters import FilterState, date_range, to_log_filter

APP = Path(__file__).resolve().parents[1] / "hsbg" / "dashboard" / "app.py"


def test_date_range_presets() -> None:
    today = date(2026, 9, 25)
    assert date_range(FilterState("All time"), today) == (None, None)
    since, until = date_range(FilterState("Today"), today)
    assert since == datetime(2026, 9, 25) and until is not None and until.date() == today
    since, until = date_range(FilterState("Last 7 days"), today)
    assert since == datetime(2026, 9, 19) and until is None
    since, until = date_range(FilterState("Custom", date(2026, 9, 1), date(2026, 9, 10)), today)
    assert since == datetime(2026, 9, 1) and until is not None and until.date() == date(2026, 9, 10)


def test_to_log_filter_carries_heroes_and_incomplete() -> None:
    f = to_log_filter(FilterState("All time", heroes=("BG36_HERO_002",), include_incomplete=True))
    assert f.heroes == {"BG36_HERO_002"} and f.include_incomplete and f.since is None


def test_dashboard_kpis_equal_report_kpis(tables) -> None:
    """Same filter -> same numbers in both presentation layers (they share metrics.py)."""
    flt = to_log_filter(FilterState("All time"))
    filtered = metrics.apply_filter(tables, flt)
    html = report.build_report(filtered)
    k = metrics.kpis(filtered)
    assert f'<div class="value">{k["games"]}</div>' in html
    assert f'<div class="value">{k["avg_placement"]}</div>' in html


def test_app_smoke_run() -> None:
    os.environ["HSBG_LOGS"] = str(FIXTURES)
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    assert at.title[0].value == "概要"
    assert at.metric[0].label == "ゲーム数"
    assert at.metric[0].value == "5"  # incomplete excluded by default
    assert at.sidebar.selectbox[0].label == "期間"
    # include incomplete -> 6 games
    at.sidebar.checkbox[0].check().run()
    assert not at.exception
    assert at.metric[0].value == "6"


def _synthesize(root: Path, n: int) -> None:
    logs = [json.loads(p.read_text("utf-8")) for p in sorted(FIXTURES.glob("2026*.json"))]
    logs = [g for g in logs if g["status"] == "complete"]
    out = root / "2026" / "10"
    out.mkdir(parents=True)
    t0 = datetime(2026, 10, 1, 12, 0, 0)
    for i in range(n):
        g = json.loads(json.dumps(logs[i % len(logs)]))
        gid = str(uuid.uuid4())
        started = t0 + timedelta(minutes=30 * i)
        g["game"]["game_id"] = gid
        g["game"]["started_at"] = started.isoformat() + "+09:00"
        g["game"]["ended_at"] = (started + timedelta(minutes=25)).isoformat() + "+09:00"
        (out / f"{started:%Y%m%d-%H%M%S}_{gid}.json").write_text(json.dumps(g), encoding="utf-8")


@pytest.mark.slow
def test_500_games_performance_budget(tmp_path: Path) -> None:
    root = tmp_path / "logs"
    _synthesize(root, 500)
    t = time.perf_counter()
    data = cache.load_tables(root)  # 500 >= threshold -> builds the parquet cache
    first_load = time.perf_counter() - t
    assert len(data.tables.games) == 500
    assert first_load < 5.0, f"first load took {first_load:.1f}s"

    t = time.perf_counter()
    cached = cache.load_tables(root)
    cached_load = time.perf_counter() - t
    assert cached.from_cache and cached_load < 1.0

    t = time.perf_counter()
    f = metrics.apply_filter(cached.tables, to_log_filter(FilterState("Last 30 days")))
    metrics.kpis(f)
    metrics.hero_stats(f)
    metrics.combat_winrate_by_turn(f)
    metrics.health_by_turn(f)
    filter_time = time.perf_counter() - t
    assert filter_time < 1.0, f"filter + metrics took {filter_time:.2f}s"
    shutil.rmtree(root, ignore_errors=True)


def test_normalize_500_games_directly_is_fast() -> None:
    logs = [json.loads(p.read_text("utf-8")) for p in sorted(FIXTURES.glob("2026*.json"))]
    many = [json.loads(json.dumps(logs[i % len(logs)])) for i in range(500)]
    t = time.perf_counter()
    tables = normalize.normalize(many)
    assert len(tables.games) == 500
    assert time.perf_counter() - t < 5.0


_TRIBES_SCRIPT = """
import os
from pathlib import Path
from hsbg.dashboard import data
from hsbg.dashboard.filters import FilterState
from hsbg.dashboard.views import tribes
tribes.render(data.load_context(Path(os.environ["HSBG_LOGS"]), FilterState()))
"""


def test_tribes_page_renders() -> None:
    os.environ["HSBG_LOGS"] = str(FIXTURES)
    at = AppTest.from_string(_TRIBES_SCRIPT, default_timeout=60)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    assert at.title[0].value == "種族"
    assert [s.value for s in at.subheader] == [
        "出現した種族と成績",
        "最終盤面の主軸種族と順位",
        "ゲーム内の主軸種族の推移",
        "種族の相性（戦闘）",
    ]
    assert len(at.dataframe) == 5


_GAME_DETAIL_SCRIPT = """
import os
from pathlib import Path
from hsbg.dashboard import data
from hsbg.dashboard.filters import FilterState
from hsbg.dashboard.views import game_detail
game_detail.render(data.load_context(Path(os.environ["HSBG_LOGS"]), FilterState()))
"""


def test_game_detail_select_follows_every_change() -> None:
    # regression: a keyless selectbox with a moving `index` was recreated on every other
    # rerun and silently reverted the user's choice
    os.environ["HSBG_LOGS"] = str(FIXTURES)
    at = AppTest.from_string(_GAME_DETAIL_SCRIPT, default_timeout=60)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    assert len(at.selectbox[0].options) >= 3
    seen = []
    for pick in [1, 2, 0, 2, 1]:
        at.selectbox[0].select_index(pick).run()
        assert not at.exception, [str(e) for e in at.exception]
        assert at.selectbox[0].index == pick
        assert at.session_state["selected_game_id"] == at.selectbox[0].value
        seen.append(at.selectbox[0].value)
    assert len(set(seen)) == 3
    # a selection made on the games page (selected_game_id) is honored on the next run
    at.session_state["selected_game_id"] = seen[2]
    at.run()
    assert at.selectbox[0].value == seen[2]
