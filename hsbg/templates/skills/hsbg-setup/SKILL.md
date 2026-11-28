---
name: hsbg-setup
description: First-time setup of an hsbg workspace with the player — check that the game recorder's (hsbg-kifu's) logs are found, the settings (hsbg.toml) and the knowledge folder, and interview the player about their goals to write profile.md. Use when the player starts using hsbg ("セットアップして", "使い始めたい"), when profile.md is missing, or when the player wants to change their goals.
---

# HSBG setup

Talk with the player in their language, one step at a time; each step ends with what you found.
Do not change anything outside this workspace folder.

## 1. Tools and logs

1. `hsbg config` — shows the workspace and the folders in effect. If `hsbg` is not found, point to
   the install steps of the hsbg README and stop.
2. `hsbg validate` — how many logs were found in `logs_dir`.
   - None: ask whether the recorder **hsbg-kifu** is installed and running (its "BG" icon in the
     task tray; it records only while running, alongside HDT and Hearthstone) and where its output
     folder points (tray icon → 設定...; the default is `Documents\HSBG-Logs`). If it is not the
     default, set `logs_dir` in `hsbg.toml` to the same folder. If they have not played since
     installing it, ask them to play a game. Logs of the older HDT plugin
     (hdt-plugin-hsbg-kansousen) in the same folder are read too.
   - Invalid logs: report them; they are skipped, not fatal.
3. Languages — three independent choices; explain them in one or two lines each:
   - **Card / hero names** (summaries, stats, dashboard): `locale` in `hsbg.toml`. It can be English
     (`enUS`, always available) or the language of their **Hearthstone client**: HDT downloads only
     `CardDefs.base.xml` (English) and `CardDefs.<client language>.xml`, so a Japanese name needs a
     Japanese client. A locale whose file is missing falls back to English. `hsbg config` shows
     `carddefs_dir`; if the folder is missing (HDT has not downloaded its card data yet), names stay
     English until it exists. The recorder's logs themselves are the same for every language.
   - **Analysis text** (replies and saved analyses): any language; record it in `profile.md`.
   - **Dashboard / report screens**: Japanese for now, whatever the other two are.
   Default `locale` is `jaJP`; set `locale = 'enUS'` for English names.

## 2. Knowledge folder and history

1. `knowledge_dir` (normally `knowledge/` in this workspace, created by `hsbg init`). If it is
   missing, offer to create it with `hsbg init --knowledge .` (existing files are kept). Explain in two
   lines what it is for (facts about the game: rules, season, patches; they grow it by pasting patch
   notes) and that it is theirs alone. If `knowledge/CHANGELOG.md` is missing (a workspace made by an
   older hsbg), `hsbg init .` adds it.
2. History needs no setup: analyses are kept as files in `analysis/`, and every change to the
   knowledge folder is written to `knowledge/CHANGELOG.md`, which analyses read. Do not bring up git
   (installing it, `git init`, remotes): whether to use it is entirely the player's choice. If the
   folder already is a repository (their choice): do not create remotes or push; commit only when
   they ask.
3. Claude access: `.claude/settings.json` (from `hsbg init`; `hsbg init .` adds it if missing)
   lets hsbg's read-only commands run without asking; other commands still ask. If the logs or the
   knowledge folder are outside this workspace (the logs usually are), offer to add their absolute
   paths (from `hsbg config`) to `permissions.additionalDirectories` in
   `.claude/settings.local.json` (create it; keep any existing keys) so analyses can read them.

## 3. Goals → profile.md

Interview briefly (they can skip any question), then write `profile.md` and show it:

- What they want from analyses: climb MMR, avoid bad placements (5th–8th), win more often, learn a
  hero or a type, understand losses — and which comes first.
- Their usual MMR range and region, how much they play, whether they play Duos.
- How they like advice: how many items, how concrete, what to check before advising (e.g. "look at my
  HP before telling me to level").
- Language for replies and saved analyses.

`profile.md` format: `## 目標と優先度` / `## 助言の前に確かめること` / `## プレイヤーの環境` (headings in
the player's language are fine). Write dated facts ("2026-10-31: ..."). It holds the player's goals
and preferences only — no statistics (those are in the analyses) and no game facts (knowledge).

## 4. What to do next (the end of the setup)

End the setup with a short guide the player can act on right away. Make it the **last part of your
last message**, after the setup report and after anything else you have to tell them (e.g. the
install steps' "restart the app next time"), so it is not buried. Write it as a numbered list; each
item says in one line what it is for, gives a request they can copy, and offers to do it now. Then
ask which one to start with (or anything else). Do not start any of them without their answer.

1. **What they want to find out** — turn the top goal in `profile.md` into a first question to look
   at (e.g. for "fewer 5th–8th places": 「5 位以下になったゲームに共通することを見たい」).
2. **Analyse their games** (`hsbg-analysis`) — use the count from `hsbg validate`: with fewer than
   about 10 games, the latest game (「さっきのゲームを分析して」); with more, also a trend over recent
   games (「直近 30 ゲームの傾向を見て」).
3. **Start the knowledge folder (recommended)** — it is empty now, and that is normal. Say why it
   matters: analyses check card tiers, numbers, patch changes and the current season's mechanics
   against it instead of guessing, and recent seasons are often beyond what Claude knows; facts not
   in it are marked unchecked. The easiest start: paste the current patch notes (or show the season's
   mechanics from the game) and ask to record them (「パッチノートを貼るので knowledge に記録して」);
   you write `patches/` or `season/current.md` following `knowledge/CLAUDE.md` and add a
   `CHANGELOG.md` line. It grows a little with each patch.
4. **The dashboard** — charts of their games in the browser (overview, heroes, tribes, play trends,
   opponents, each game; the マイ分析 page shows their lenses), local only (127.0.0.1). In the Claude
   desktop app: offer to open it now in the Browser pane (「ダッシュボードを開いて」), and say they can
   also start / stop it themselves from the pane's Dev servers menu → "hsbg dashboard"
   (`.claude/launch.json`; the menu appears once the session has a message). In a terminal:
   `hsbg serve`.

After the list, one line: lenses come later — when an angle keeps coming up in analyses, the
`hsbg-lens` skill turns it into a lens (`lenses/README.md`).
