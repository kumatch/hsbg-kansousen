import pandas as pd
import pytest

from hsbg import charts


@pytest.mark.parametrize("avg", [1.0, 1.5, 1.99, 2.0, 8.0])
def test_avg_placement_bars_are_not_clipped(avg: float) -> None:
    # Bars grow from 0, so an axis starting at 1 hid a 1.0 average entirely.
    heroes = pd.DataFrame({"hero_name": ["A"], "avg_placement": [avg], "games": [1]})
    types = pd.DataFrame({"minion_type": ["BEAST"], "avg_placement": [avg], "games": [1]})
    for fig in (charts.hero_bar(heroes), charts.type_placement_bar(types)):
        lo, hi = fig.layout.xaxis.range
        assert lo <= 0 and hi >= avg
        assert fig.data[0].base is None
