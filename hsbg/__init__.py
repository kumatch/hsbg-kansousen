"""HSBG Logger analysis package.

Layers (docs/architecture.md §1, §6):
    loader    -> read + validate game-log JSON files
    normalize -> pandas tables (games, turns, combats, board_minions, opponents, discovers,
    hand, shop_offers, lobby, sells)
    metrics   -> every aggregation lives here (report / dashboard / summarize only call these)
    charts    -> every plotly figure lives here
    report    -> static single-file HTML
    summarize -> per-game Markdown for AI input
    cli       -> typer entry point (`hsbg`)
"""

__version__ = "0.1.0"
