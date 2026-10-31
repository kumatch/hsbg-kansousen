---
name: hsbg-lens
description: Create, change or retire the player's analysis lenses (workspace lenses/<name>/ — lens.md with the questions for the AI, metrics.py with @lens_table tables) together with the player. Use when the player wants to look at an angle every time ("毎回〜を見たい", "この観点を表にして"), when an analysis ends with Proposed lens changes the player agreed to, or when a lens fails `hsbg lens check`.
---

# HSBG lenses

A lens is one angle of analysis the player wants looked at every time. It belongs to the player
(their workspace), so **every change starts from a conversation and needs their OK**. The analysis
skill (`hsbg-analysis`) reads each active lens's `lens.md` and its tables in `hsbg stats`; the
dashboard shows the tables on its マイ分析 page.

```
lenses/<name>/
├── lens.toml    # label, description, status (active / retired), api (= hsbg.lens.LENS_API)
├── lens.md      # for the analysis: questions, tables to read, how to judge, running list, game check
├── metrics.py   # optional: @lens_table functions returning DataFrames (import only from hsbg.lens)
└── test_*.py    # optional: pytest tests, run by `hsbg lens check` when pytest is installed
```

## 1. Agree on the angle first

Before writing anything, settle with the player, in their language:

- **The question** in one sentence (e.g. "do I lose more when I level right after two losses?").
- **What decides it**: which numbers, compared how (bottom 4 vs top 4, yes / no split, per turn),
  and from how many games a difference counts (n < 5 is anecdote).
- **Controllable or not**: lenses look for what the player chooses; offers are random.
- **What carries over**: does it keep a running list in the trend files' Standing summary (name,
  item format, statuses such as candidate / confirmed / dropped)?
- **Whether a table is needed at all.** Many angles work from the core `hsbg stats` tables; then the
  lens is `lens.md` only. Check what `hsbg stats` already has before adding code.

Read `profile.md` and `hsbg lens list` so the new lens fits the player's goals and does not repeat
another lens. Propose the plan (files, tables, columns) and wait for the OK.

## 2. Write it

1. `hsbg lens new <name>` (lower case, digits, `-`, `_`). It copies a working example; replace it.
2. `lens.toml`: `label` (shown in stats / dashboard, the player's language), `description`.
3. `lens.md`: sections the analysis skill relies on —
   `## 表` / tables (each table's name and how to read it), the questions to answer in a trend
   analysis, how to judge (thresholds, sample size, cause vs symptom), `## Standing summary に持ち越すリスト`
   (or the equivalent) when it keeps a list, the check for a single-game analysis, and how the tables
   may change (proposals only, with the player's OK). Write it in the player's language.
4. `metrics.py`, when tables are needed:
   - import only from `hsbg.lens` (`Tables`, `lens_table`, `early_game_features`, `compare_groups`,
     `placement_group`, `card_tiers`, `apply_filter`, `LogFilter`); the normalized tables
     (`t.games`, `t.turns`, `t.combats`, `t.board_minions`, `t.opponents`, `t.discovers`, `t.hand`,
     `t.shop_offers`, `t.lobby`, `t.sells`) are described in the log schema docs (`hsbg export`
     writes the same tables to look at)
   - each `@lens_table(name, label, chart=..., x=..., y=..., color=..., description=..., ...)`
     function takes the tables of the current filter and returns a DataFrame. `chart` is `table`,
     `bar`, `barh` (horizontal, for long category names) or `line`; never call plotly. Column names,
     values, `label` and `description` are what the AI reads in `hsbg stats` (keep them English and
     short)
   - **the dashboard page is in the player's language**: give `title` / `note` (heading and caption
     there), `display` (a function from the returned DataFrame to the shown one: map values such as
     "yes" → "はい", format times, `minion_type_name` for minion types; keep numbers as numbers so the
     chart still works) and `columns` (shown headers). `hsbg lens check` runs `display` too
   - round values for display (`round(1)` etc.) and return percentages as 0–100 when the header says %
   - handle empty tables (return an empty DataFrame with the columns)
   - keep thresholds and their reasons as named constants with a dated comment (what the numbers were
     when it was chosen and that the player agreed), so later analyses can revisit them
5. Tests (`test_<name>.py`) for any logic beyond a group-by: small synthetic logs through
   `hsbg.normalize.normalize([...])`, asserting the numbers.

## 3. Check and show

- `hsbg lens check <name>` must print `ok`. It runs every table on the player's own logs and reports
  errors, chart columns missing from the result and a missing lens.md, and runs the tests.
- Show the player the new section of `hsbg stats --last 20` (the `## Lens:` part) and say what it
  says, before calling the lens done. Mention the マイ分析 page (`hsbg serve`).
- When the lens replaces how earlier analyses counted something, say what changed so the next trend
  analysis can tell old numbers from new ones.

## Changing and retiring

- Change a lens only after the player agrees to a concrete proposal (usually `## Proposed lens
  changes` at the end of an analysis). Keep the numbers comparable: when a definition changes, note
  the date and the old definition in `metrics.py` and `lens.md`.
- Retire instead of deleting: `status = "retired"` in `lens.toml` keeps it as a record and hides it
  from stats, the dashboard and the analyses. Say in the next trend analysis that it was retired.
- Never edit another lens or the core hsbg code from this skill. If a lens needs something
  `hsbg.lens` does not offer, compute it in the lens from the tables, or tell the player it would be
  a change to hsbg itself.
- The workspace is the player's git repository: list the files you changed and leave committing to
  them (or commit only when they ask).
