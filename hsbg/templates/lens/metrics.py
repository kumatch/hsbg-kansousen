"""Tables of this lens. Import only from hsbg.lens (the public lens API); return DataFrames.
`hsbg lens check` runs every table on your logs and reports problems."""

import pandas as pd

from hsbg.lens import Tables, compare_groups, early_game_features, lens_table

# column of early_game_features -> label (order = display order)
FEATURES = {
    "tier3_turn": "Tier 3 turn",
    "tier4_turn": "Tier 4 turn",
    "hp_t8": "HP T8",
    "rerolls_t1_8": "Rerolls T1-8",
    "buys_t1_8": "Buys T1-8",
}


@lens_table(
    "top4_vs_bottom4",
    "上位 4 と下位 4: 序盤の中央値",
    chart="bar",
    x="feature",
    y="diff",
    description="diff = 下位 4 の中央値 − 上位 4 の中央値",
)
def top4_vs_bottom4(t: Tables) -> pd.DataFrame:
    return compare_groups(early_game_features(t), FEATURES)


@lens_table(
    "placement_by_final_tier",
    "最終 Tier ごとの平均順位",
    chart="bar",
    x="final_tier",
    y="avg_placement",
)
def placement_by_final_tier(t: Tables) -> pd.DataFrame:
    g = t.games.dropna(subset=["final_tier", "placement"])
    out = (
        g.groupby("final_tier")["placement"].agg(games="count", avg_placement="mean").reset_index()
    )
    return out.astype({"final_tier": int}).round({"avg_placement": 2})
