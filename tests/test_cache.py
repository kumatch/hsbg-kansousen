import shutil
import time
from pathlib import Path

from conftest import FIXTURES

from hsbg import cache, metrics


def _copy_fixtures(tmp_path: Path) -> Path:
    root = tmp_path / "logs" / "2026" / "09"
    root.mkdir(parents=True)
    for p in FIXTURES.glob("2026*.json"):
        shutil.copy(p, root / p.name)
    return tmp_path / "logs"


def test_signature_changes_when_a_log_is_added(tmp_path: Path) -> None:
    root = _copy_fixtures(tmp_path)
    s1 = cache.folder_signature(root)
    assert s1.count == 6
    time.sleep(0.01)
    shutil.copy(next(FIXTURES.glob("2026*.json")), root / "2026" / "09" / "zz_copy.json")
    s2 = cache.folder_signature(root)
    assert s2.count == 7 and s2 != s1


def test_cache_roundtrip_and_invalidation(tmp_path: Path) -> None:
    root = _copy_fixtures(tmp_path)
    first = cache.load_tables(root, use_cache=True)
    assert not first.from_cache
    assert (root / cache.CACHE_DIR / "games.parquet").exists()

    second = cache.load_tables(root, use_cache=True)
    assert second.from_cache
    assert len(second.tables.games) == len(first.tables.games)
    f = metrics.apply_filter(first.tables, metrics.LogFilter())
    s = metrics.apply_filter(second.tables, metrics.LogFilter())
    assert metrics.kpis(f) == metrics.kpis(s)
    assert metrics.hero_stats(f).equals(metrics.hero_stats(s))

    time.sleep(0.01)
    shutil.copy(next(FIXTURES.glob("2026*.json")), root / "2026" / "09" / "zz_copy.json")
    third = cache.load_tables(root, use_cache=True)
    assert not third.from_cache
    assert len(third.tables.games) == len(first.tables.games) + 1

    cache.clear_cache(root)
    assert not (root / cache.CACHE_DIR).exists()


def test_small_folder_skips_cache_by_default(tmp_path: Path) -> None:
    root = _copy_fixtures(tmp_path)
    data = cache.load_tables(root)
    assert not data.from_cache
    assert not (root / cache.CACHE_DIR).exists()
