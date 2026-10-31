---
name: hsbg-analysis
description: Analyze the player's Hearthstone Battlegrounds games from the HDT plugin's logs with the hsbg CLI, following the workspace's profile.md and active lenses, and save every analysis as Markdown in the analysis folder. Use when the user asks about their BG results, a specific game ("昨日の最後のゲーム", "さっきの 6 位"), a hero's performance, or trends over recent games.
---

# HSBG analysis

This skill is part of hsbg (copied into the workspace by `hsbg init` / `hsbg skills update`; edits
here are overwritten). The player's own goals and angles live in the workspace, not here:

- `profile.md` — goals, priorities and how they want advice checked. **Read it before every analysis**
  and follow it over the defaults below when they differ.
- Active lenses — `hsbg lens list`; for each active lens read its `lens.md`. A lens adds questions,
  tables (`## Lens: ...` at the end of `hsbg stats`), running lists for the Standing summary and a
  check for game analyses. Creating or changing lenses is the `hsbg-lens` skill.

## Folders

Run `hsbg` from the workspace folder (the one with `hsbg.toml`). First run `hsbg config` once: it
prints the folders in effect; this skill calls them `<logs>` (logs_dir; the plugin writes
`<logs>\YYYY\MM\*.json`), `<analysis>` (analysis_dir; where analyses are saved, create it if missing)
and `<knowledge>` (knowledge_dir). If `hsbg` is not found, the user has not installed it (README);
from a clone of hsbg, `uv run --project <clone>\analysis hsbg ...` also works.

## Game knowledge (the player's own knowledge folder)

Facts about the game itself (rule assumptions, the current season's systems and minion pool, every
patch / hotfix with its time) live in the player's own knowledge folder `<knowledge>` (none set =
unavailable). `hsbg init` creates it as `knowledge/` inside the workspace; it may also be a separate
git repository. Typical layout: `basics/` (glossary, assumptions), `season/current.md`,
`season/pool/`, `patches/YYYY-MM-DD_<version>.md`. It is updated on its own schedule, so every
analysis records which commit it read and the next trend analysis checks what changed since then.
Limit every git command to that folder with `-- .`, so commits of the rest of a workspace repository
do not count.

- Record: `git -C <knowledge> log -1 --format=%h -- .`, plus `-dirty` when
  `git -C <knowledge> status --porcelain -- .` is not empty. Write it as the second line of the saved
  file: `Knowledge: knowledge@<hash>` (older files may say `hsbg-knowledge@<hash>`; same meaning).
  If the folder exists but is not under git, write `Knowledge: knowledge@untracked` and say once that
  changes cannot be followed until it is committed.
- Use it for card facts (tier, stats, text, what a patch changed) instead of guessing, and cite the
  file. It contains no conclusions from the player's games; those stay in the analyses.
- **Card facts go stale with every patch; judge their validity here, not in the knowledge folder.**
  Facts there carry `確認: <build> / <patch>` (and a generated pool snapshot, if there is one, its
  `meta.build_base` / `meta.patch` / `meta.warnings`). Before using a fact for a game, compare the
  game's `started_at` with the patches: if a patch file is dated after the fact's `確認:` patch and
  before the game, and no newer snapshot exists, treat the fact as unverified for that game and say
  so. A fact marked `要再確認（<version>）` is unverified for games after that version.
- **The logs are the check.** `board_minions` has each minion's real `tier` / `attack` / `health` at
  that time. When the knowledge folder's tier for a `card_id` differs from what the logs of games after
  its patch show, mention it and suggest updating the knowledge folder. Buffed stats on the board
  differ from base stats by design; compare tiers, not stats.
- If the folder is missing, write `Knowledge: unavailable`, say so once in the reply, and continue.
- Never write to the knowledge folder from an analysis. If a fact there looks wrong, tell the user.

## One game

1. Pick the log. `latest` = newest complete game. For "yesterday's last game" or "the 6th-place one",
   look at the Recent games table of `hsbg stats --last 20` (started time, hero, placement), or
   `Get-ChildItem "<logs>" -Recurse -Filter *.json`.
2. `hsbg summarize <path or latest>` (add `--out <scratch>\game.md` if it is long).
3. Read the **previous analyses** (up to the 3 newest `*_game.md` in `<analysis>\`) and note their
   "What to try next time" items. Skip if none exist. Also read the newest `trend-*.md`: its Standing
   summary, including the running lists the active lenses keep there (each lens's `lens.md` names
   its list and says how a game analysis uses it).
   From the knowledge folder, read the newest `patches/` file whose time is before the game's
   `started_at` and the ones after it, so you know which patch the game was played under; mention it
   when that patch is newer than the newest trend file's period.
4. Apply `analyze-game.md` (next to this file; the part after `---`) to the summary, then each active
   lens's "game analysis" check. Include `## Follow-up on previous advice` when step 3 found items.
5. **Save the analysis** to `<analysis>\<YYYYMMDD-HHMMSS>_<gameId first 8>_game.md`, where the
   timestamp is the game's `started_at` (same prefix as the log file, so they sort together). Start the
   file with a header line: `# Analysis: <hero> #<placement> — <started_at> — log: <log file name>`,
   then the `Knowledge:` line. Then show the same analysis in the reply and end with the saved path.

## Trends

1. `hsbg stats --last N` (or `--since 2026-09-01`, `--hero <card id>`, `--min-mmr 7400` /
   `--max-mmr 7399` for a starting-MMR band) → Markdown tables, ending with the active lenses' tables.
2. Optional: `hsbg export --format csv --out <scratch>\exp` for row-level data.
3. Read the newest `trend-*.md` in `<analysis>\` (if any). It is the **only** earlier file the trend
   analysis reads, so its `## Standing summary` is the accumulated state of all earlier analyses. Take
   its ledger as the recommendations to follow up and its patterns as the baseline. The user does not
   need to point at the file; find it yourself. If the user names an older file, read that one too, but
   still carry the newest Standing summary forward.
4. If the user gave no range, use the games started after the period in that newest trend file's
   header (`--since <date>`); otherwise `--last N` / `--since` as asked.
5. **Knowledge changes.** Take the `Knowledge:` hash from the previous trend file and run
   `git -C <knowledge> log --oneline <hash>..HEAD -- .` and
   `git -C <knowledge> diff --stat <hash>..HEAD -- .` (read the changed files). When the previous file
   has no hash, treat every `patches/` file dated after its period as new. Then:
   - a new patch inside or before the period → split the period at its time (run `hsbg stats` once
     per side with `--since` / `--until`) and compare the post-patch numbers with the post-patch side
     only; mark the Standing summary items that the patch touches (cards it changed, key cards, the
     mechanics they rely on) `needs re-check (<version>)`;
   - a `fix:` commit or other change to an existing file → say what changed and which earlier
     conclusions relied on it.
6. Apply `analyze-trend.md` (next to this file) to the tables, then each active lens's questions. The
   output **must** contain `## Knowledge changes since last analysis` (when step 5 ran),
   `## Follow-up on previous advice` (when step 3 found a file) and `## Standing summary` (always;
   carried over from the previous file and updated, never rebuilt from scratch when one exists).
7. **Save** to `<analysis>\trend-<YYYYMMDD-HHMM>_last<N>.md` (or `_since<date>`), header
   `# Trend analysis — <period> — <N> games`, then the `Knowledge:` line. Show it in the reply and end
   with the path.

## Lenses in analyses

- Answer every active lens's questions with its tables; cite them like the core tables.
- Keep each lens's running list in the Standing summary (the lens says its name and format).
- A lens's tables change only when the player agrees. When an analysis finds that a lens should
  change (a confirmed finding has no row, a condition stopped differing, a new angle keeps coming
  up), end with `## Proposed lens changes`: one line each with the reason and numbers, then ask.
  Write "none" when there is nothing to propose. Make the change with the `hsbg-lens` skill.

## Rules

- Follow `profile.md` for the player's priorities and for how advice must be checked before it is
  given. Without one, treat the player's goal as "place better" and say once that `hsbg-setup` can
  record their goals.
- Before recommending a tempo or leveling change, check what it does to when key cards reach the
  board (`board_minions`, player side) and to results a few turns later, not only that turn's combat,
  and ask whether the "good" cases were simply already-strong boards (correlation). Treat the player's
  own read of the game as a hypothesis to test against the logs.
- Cite turn numbers and values from the summary / tables in every claim. Never invent what is not in
  the log (opponents' hands and shops, discover options, hero power text).
- Do not recompute statistics by hand; hsbg already did. If a number is missing, say so.
- Minion-type questions ("どの種族で勝てている", "序盤の種族を最後まで使うべきか", "次は何を狙う") are
  answered from the `hsbg stats` tables "Minion types offered vs played", "Final board main type",
  "Main type by phase" and "Type matchups" (Q7 in analyze-trend.md). "Main type" = the type with the
  most minions on the board. Never recommend a type as a default from these alone.
- Sample size: n < 5 is anecdote. Say it.
- Log versions: read `log-caveats.md` (next to this file) before judging a missing or odd value; it
  lists what older plugin / schema versions did not record or recorded differently.
- A game with a `reconnect:` note (plugin 0.9.5+, or `reconnect merge:` for a game stitched together
  by hand) was interrupted by a Hearthstone crash / disconnect and resumed. The combat of the turn it
  dropped in was not observed: its result and damage are inferred from health + armor (the note says
  so and gives the numbers), Bob's Buddy may be missing, and the opponent board may be empty. Do not
  judge that turn's combat or a gap in the shop record as a play mistake.
- Whether a reconnected game stays in the analysis is the player's call, game by game. When you find
  a `reconnect:` note in a game you analyse (or in a trend period), say which turns were missed and
  ask whether to exclude it before drawing conclusions. To exclude, move all of that game's files
  (`.json`, `.events.jsonl`, `.power.log.gz`, and any incomplete part from before the reconnect) from
  `<logs>\YYYY\MM\` to `<logs>\.excluded\YYYY\MM\` (the CLI skips folders starting with `.`) and add a
  row with the reason to `<logs>\.excluded\README.md`. Moving files needs the player's OK.
- Always end a game analysis with `## What to try next time` (1–3 concrete, testable habits). The
  player reads these before the next game; they must be specific enough to act on.
- Answer in the player's language (`profile.md`, else the language they write in), and keep card and
  hero names exactly as they appear in the summary / tables. They come from HDT's CardDefs in the
  configured `locale` when the file exists, English otherwise. Hero rows in `hsbg stats` are the base
  hero (skins merged); the summary header shows the skin name the player used.
- Write the file with UTF-8 (no BOM). Never write into `<logs>\YYYY\MM\` (that is the plugin's
  folder) and never modify the JSON logs.
- Charts exist in the static report (`hsbg report --last 50 --open`) and the dashboard
  (`hsbg serve`; lens tables are on its マイ分析 page); mention them once, do not run them unless asked.
- If a log fails validation or is `incomplete`, say so and analyze what is there.
