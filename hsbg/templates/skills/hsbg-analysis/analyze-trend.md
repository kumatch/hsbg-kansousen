# Prompt: analyze trends over many games

Used by the hsbg-analysis skill with the output of `hsbg stats [--last N] [--since DATE] [--min-mmr N]
[--max-mmr N]` (pre-computed metrics tables, ending with the active lenses' `## Lens: ...` tables) and
optionally `hsbg export --format csv`. The model must interpret the tables, not recompute them.
Answer in the player's language. The player's goals (`profile.md`) and the active lenses' questions
(`lens.md`) come on top of the questions below.

---

You are reviewing my recent Hearthstone Battlegrounds results. Below are metrics computed from my own
game logs (hero results, placement distribution, tier timing medians, combat win rate by turn, health
curves for top-4 vs bottom-4 games, opponent hero records, rerolls per game, minion types offered vs
played, final board main type, main type by phase per game, type matchups, recent games). Treat them
as facts; do not recompute or "correct" them.

"Main type" of a board = the type with the most minions on it at the end of the shop phase. Five types
are offered per game (the "Offered" column). Season-specific notes on reading the type tables (e.g. a
type that was in every lobby for a while) are in `log-caveats.md`.

Rules:
1. **Cite the table and the number** for every statement ("Heroes table: Kith'ix 1 game, 7th").
2. **Respect sample size.** Anything with n < 5 is anecdote; say so explicitly and do not build a
   recommendation on it alone. Prefer patterns that show up in several tables at once.
3. **Answer these questions, in order** (skip a question if the data cannot answer it and say why):
   - Q1 Is the overall trend up or down? (recent games table: MMR before/after, placement sequence)
   - Q2 Which heroes are working and which are not? (heroes table; n and avg placement)
   - Q3 Is tier timing healthy? (median turn per tier; compare with the health curve: if HP collapses
     around the turn tier 4/5 is reached, leveling may be too greedy; if tiers come late and win rate
     is fine early but collapses mid-game, too slow)
   - Q4 Where do losses start? (combat win rate by turn and the health curves; which turns separate
     top-4 from bottom-4)
   - Q5 Rerolls: is there a relationship between rerolls per turn and placement in the rerolls table?
   - Q6 Opponent heroes and board types that beat me (opponent heroes table: low win %, high avg
     damage taken; opponent main types table)
   - Q7 Minion types: (a) which offered types I win with and which I lose with ("offered vs played"
     table: compare "Avg place (played)" with "Avg place (not played)" for the same type; a type I do
     well with but rarely pick is a missed opportunity, a type I pick often and place badly with is a
     habit to break); (b) how the main type moves inside a game ("Main type by phase" table: early ->
     final, commit turn, pivots) and whether late commits or many pivots go with bad placements;
     (c) matchups ("Type matchups" table: which opponent main types beat my usual main type).
     Recommend which type to look for next game and when to commit, only when n allows.
   - Q8 and on: **the active lenses' questions**, one per lens, in the order of `hsbg lens list`,
     answered from that lens's tables (`## Lens: <label>`) as its `lens.md` says. Name each `Q8 <lens
     label>`, `Q9 <lens label>`, ...
4. **Output format:**
   - `## Knowledge changes since last analysis` — only when my knowledge folder changed since the
     previous trend file: new patches (version, time, what they changed in one line each, which side
     of the period split each game is on) and corrections to earlier facts, each with the Standing
     summary items it puts in doubt. Facts about the game come from that folder; never treat them as
     findings from my games.
   - `## Headline` — one paragraph: the single most important pattern, with numbers.
   - `## Findings` — one short section per question above (Q1–Q7 and the lens questions), each with
     cited numbers and a confidence label (high / medium / low, based on sample size).
   - `## Follow-up on previous advice` — only when an earlier trend analysis is provided: did its
     recommendations show up in the numbers since then?
   - `## Recommendations` — at most 3, each testable within the next 10 games, each tied to a finding.
     Order them by the player's priorities in `profile.md`.
   - `## Standing summary` — **always present, cumulative.** The next analysis reads only the newest
     trend file, so this section must let a reader who has no other file know the whole state of the
     review so far. Build it by carrying over the previous file's Standing summary and updating it with
     this analysis; when there is no previous file, build it from this analysis alone. Every item in
     the three lists names the patch it was measured under (`under 36.6.2`; for items carried over
     from files written before this rule, the patch in effect during their games). When a newer patch
     touches what an item relies on (a card it changed, a key card, a mechanic), set the item to
     `needs re-check (<version>)` and keep it until enough post-patch games confirm or contradict it;
     post-patch numbers alone decide that. Lists:
     - `### Established patterns` — at most 6 bullets. Each: the pattern in one sentence, the first
       analysis date that reported it, how many analyses / games it has held across, and the latest
       number that supports (or now contradicts) it. Drop a pattern only after it has been contradicted
       in two consecutive analyses, and say so in the file that drops it.
     - `### Recommendation ledger` — every recommendation that is still open, plus the ones closed in
       this analysis. Each: the habit in one sentence, the date first issued, its status
       (`new` / `continuing since <date>` / `achieved` / `dropped`), and the evidence for the status
       (what was observed, in how many games). The three entries in `## Recommendations` must appear
       here. A recommendation is `achieved` when the numbers it targets moved in the intended direction
       in at least 5 games; `dropped` needs a reason. Closed items appear only in the file that closes
       them; the next file omits them.
     - One running list per active lens that keeps one (its `lens.md` names the list and its format),
       carried over and updated every time like the other two lists.
   - `## What to log or watch next` — if a question could not be answered, what would answer it.
   - `## Proposed lens changes` — lens tables change only when the player agrees. Propose adding a
     row for a finding that became `confirmed` in a lens's list but has no row yet, removing a
     condition that was dropped or showed no difference in two analyses, or a new lens for an angle
     that keeps coming up. One line each with the reason and numbers, then ask. Write "none" when there
     is nothing to propose.
5. Do not moralize and do not pad. Numbers first, interpretation second.
6. Never state as new something that the previous Standing summary already listed; cite it as
   continuing and add the new number.
