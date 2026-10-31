---
name: hsbg-setup
description: First-time setup of an hsbg workspace with the player — check that the HDT plugin's logs are found, the settings (hsbg.toml), the knowledge folder and git, and interview the player about their goals to write profile.md. Use when the player starts using hsbg ("セットアップして", "使い始めたい"), when profile.md is missing, or when the player wants to change their goals.
---

# HSBG setup

Talk with the player in their language, one step at a time; each step ends with what you found.
Do not change anything outside this workspace folder.

## 1. Tools and logs

1. `hsbg config` — shows the workspace and the folders in effect. If `hsbg` is not found, point to
   the install steps of the hsbg README and stop.
2. `hsbg validate` — how many logs were found in `logs_dir`.
   - None: ask whether the HDT plugin is installed and enabled (HDT: Options > Tracker > Plugins) and
     where its Settings > Log folder points. If it is not the default, set `logs_dir` in `hsbg.toml`
     to the same folder. If they have not played since installing it, ask them to play a game.
   - Invalid logs: report them; they are skipped, not fatal.
3. Languages — three independent choices; explain them in one or two lines each:
   - **Card / hero names** (summaries, stats, dashboard): `locale` in `hsbg.toml`. It can be English
     (`enUS`, always available) or the language of their **Hearthstone client**: HDT downloads only
     `CardDefs.base.xml` (English) and `CardDefs.<client language>.xml`, so a Japanese name needs a
     Japanese client. A locale whose file is missing falls back to English. `hsbg config` shows
     `carddefs_dir`; if the folder is missing (HDT has not downloaded its card data yet), names stay
     English until it exists. The plugin's logs themselves are the same for every language.
   - **Analysis text** (replies and saved analyses): any language; record it in `profile.md`.
   - **Dashboard / report screens**: Japanese for now, whatever the other two are.
   Default `locale` is `jaJP`; set `locale = 'enUS'` for English names.

## 2. Knowledge folder and git

1. `knowledge_dir` (normally `knowledge/` in this workspace, created by `hsbg init`). If it is
   missing, offer to create it with `hsbg init --knowledge .` (existing files are kept). Explain in two
   lines what it is for (facts about the game: rules, season, patches; they grow it by pasting patch
   notes) and that it is theirs alone.
2. Git: suggest making this workspace a **private** git repository (`git init`, then their own private
   remote if they want one). Analyses record the knowledge folder's commit, so knowledge changes should
   be committed. Do not create remotes or push; commit only when they ask.
3. Claude Code access: if the logs or the knowledge folder are outside this workspace, offer to add
   them to `.claude/settings.json` → `permissions.additionalDirectories` so analyses can read them.

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

## 4. Next steps

- With fewer than about 10 games, analyse single games first (`hsbg-analysis`); trends need more.
- Lenses come later: after a few analyses, when an angle keeps coming up, the `hsbg-lens` skill turns
  it into a lens. Mention `lenses/README.md`.
- Dashboard: `hsbg serve` (127.0.0.1 only; the マイ分析 page shows the lenses).
