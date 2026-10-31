import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CARDDEFS = FIXTURES / "carddefs"

# Card names come from the small CardDefs fixtures (never from the machine's HDT folder), so test
# output is the same everywhere: Japanese names, skins resolved to their base hero.
os.environ["HSBG_CARDDEFS"] = str(CARDDEFS)
os.environ["HSBG_LOCALE"] = "jaJP"
# ...and never from the machine's workspace / knowledge folder (config.py)
for _name in ("HSBG_WORKSPACE", "HSBG_KNOWLEDGE"):
    os.environ.pop(_name, None)

from hsbg import loader, normalize  # noqa: E402
from hsbg.normalize import Tables  # noqa: E402


@pytest.fixture(scope="session")
def load_result() -> loader.LoadResult:
    return loader.load_logs(FIXTURES)


@pytest.fixture(scope="session")
def tables(load_result: loader.LoadResult) -> Tables:
    return normalize.normalize(load_result.logs)


@pytest.fixture(scope="session")
def complete_logs(load_result: loader.LoadResult) -> list[dict]:
    return [g for g in load_result.logs if g["status"] == "complete"]
