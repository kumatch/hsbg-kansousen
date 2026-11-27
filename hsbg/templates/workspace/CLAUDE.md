# CLAUDE.md — hsbg workspace

This folder is a player's own Hearthstone Battlegrounds analysis workspace for hsbg. Everything here
is about this player only; nothing is shared with other players.

- `profile.md` — the player's goals, priorities and how advice must be checked. Read it before any
  analysis. Missing → offer the `hsbg-setup` skill.
- `lenses/` — the player's angles of analysis (`hsbg lens list`). Created / changed with the
  `hsbg-lens` skill, only after the player agrees.
- `analysis/` — saved analyses (the `hsbg-analysis` skill writes them). Do not rewrite old files.
- `knowledge/` — the player's own facts about the game (its own `CLAUDE.md` has the rules for editing
  it). Analyses only read it.
- `hsbg.toml` — folders and language; `hsbg config` shows what is in effect.
- `.claude/skills/hsbg-*` — copied from hsbg (`hsbg skills update` refreshes them; local edits there
  are overwritten). The player's own instructions go in `profile.md` or a lens, not in those skills.
- `.claude/launch.json` — the dashboard (`hsbg serve --no-open`) as a server the Claude desktop app
  can start from its Browser pane. `.claude/settings.json` — allows hsbg's read-only commands
  without asking. Both come from `hsbg init`; put this player's own additions (e.g. the logs folder
  in `permissions.additionalDirectories`) in `.claude/settings.local.json`.

Dashboard ("ダッシュボードを開いて"): in the Claude desktop app, start the `hsbg dashboard` server
of `.claude/launch.json` and show it in the Browser pane, and tell the player they can also start or
stop it themselves from the pane's Dev servers menu. Elsewhere (a terminal), run `hsbg serve` in the
background; it opens the browser at http://127.0.0.1:8501. Stop it when the player asks.

Rules:

- Reply in the player's language (`profile.md`).
- Run `hsbg` from this folder. Never modify the game logs (`hsbg config` → logs_dir) except moving a
  game to `.excluded` with the player's OK (see the analysis skill).
- Do not bring up git: whether to use it is the player's own choice. If this folder is a git
  repository, commit only when the player asks; never push or create remotes on your own.
