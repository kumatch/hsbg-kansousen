# Prompt: analyze one Battlegrounds game

Used by the hsbg-analysis skill with the Markdown produced by `hsbg summarize <log.json>` (or
`latest`), plus the "What to try next time" sections of earlier analyses (from the analysis folder).
Answer in the player's language. The player's goals (`profile.md`) and the active lenses' game checks
(`lens.md`) come on top of the angles (a)–(d) below. Save the result as described in the skill.

---

You are reviewing one Hearthstone Battlegrounds game of mine. The summary below was generated from a
log recorded by my own tracker plugin; it contains everything I know about the game and nothing else.

Rules:
1. **Cite evidence.** Every claim must point at a turn number and a value from the summary
   (e.g. "T7: took 10 from Felwarden Omu with a 7-minion board of 5/2 Mummifiers"). Never invent
   information that is not in the summary: you do not know my hand or my shop unless the
   `## Hand and shop` table lists them (logs from plugin 0.9.0 / schema 1.5.0), the opponents'
   shops or hands, the discover options, or what the hero powers do beyond their names. Card facts (tier,
   stats, text, what a patch changed) may come from the player's knowledge folder; cite the file when
   you use one.
2. **Do not recompute statistics.** Use the numbers as given. If a number is missing (`-` or null),
   say it is unavailable.
3. **Four angles, in this order, then the active lenses' game checks:**
   - (a) Tier strategy: when I reached each tier vs. my own median (the "Key moments" list marks
     early/late), and what my HP was at each tier-up.
   - (b) Economy: gold spent vs. available per turn, rerolls, sells, turns where gold was left over.
     "Gift" in the actions column is the Dark Discovery button (悪夢の発見): 3 gold for a discovered
     minion that carries a Dark Gift (悪夢の恵み, an extra effect on the minion) and never passes
     through the shop, so it is not a buy. Treat it as a purchase when judging
     board-filling; `-` means the log predates the field.
   - (c) Board building: how the board changed turn by turn, when the composition committed, golden
     minions, keywords, board size (turns with fewer than 7 minions after T8 are suspicious). Name the
     minion type the board was built around ("Types:" in the header lists the five offered this game)
     and, if the type changed mid-game, the turn it changed and what that cost (sold minions, tempo).
     When the summary has a `## Deity` table, the Deity (神祇, e.g. C'Thun) is part of the board's
     strength even though it is not on the board: it awakens mid-combat after 4 friendly Aberrations
     die in that combat (3 before patch 36.6.3, 2026-10-02; since 36.6.3 the Deity is also tier 1 for
     hero damage, 3 before), so do not compare awakening turns across that boundary. Judge combat power as board total + Deity, say how fast the Deity grew (in the shop vs. in
     combat, from the "at combat start" / "after combat" columns) and from which turn it outgrew the
     board. Read the ability line under the table: C'Thun's value is its size (it splits its stats
     among the other minions), Y'Shaarj's is its size plus the first Aberrations that die (it
     resummons them), so for Y'Shaarj also look at which Aberrations sit on the board. "(golden)" =
     the Deity is golden (Mask of Ancient Ones): C'Thun splits twice its stats, Y'Shaarj resummons 4.
   - (c2) When the summary has a `## Hand and shop` table: what the shop offered and what I took or
     left (a key card that was offered and not bought is a choice; one that never appeared is not),
     spells or minions left in hand at the end of the shop, and my tier vs. the combat opponent's
     ("Opp tier") and the lobby's ("Lobby tiers") on the turns I leveled or lost.
   - (d) Combat matchups: the results, the damage taken, Bob's Buddy odds vs. actual results
     (an upset is when the predicted side lost), which opponents beat me and with what.
     Compare my Deity with the opponent's Deity in the same combat before calling a result lucky.
   - (e) and on: each active lens's "game analysis" check (its `lens.md`), in the order of
     `hsbg lens list`, e.g. going through the running list the newest trend file keeps for that lens
     and saying for each item whether this game did it, citing the turn. Keep controllable actions
     separate from bad luck in what was offered.
4. **Output format:**
   - `## Summary` — two sentences: what happened and the single most important reason for the placement.
   - `## Timeline` — a compact list of the 3–6 turning points, each with turn number and numbers.
   - `## Hypotheses` — the top 3 causes of the placement, ordered by confidence, each as a hypothesis
     ("H1 (high confidence): ...") with the evidence lines that support it and what would have been
     the alternative decision.
   - `## Follow-up on previous advice` — only when previous analyses are provided: for each earlier
     "What to try next time" item, say whether this game shows it was applied (cite the turn) and
     whether it helped, was neutral, or could not be judged.
   - `## What to try next time` — 1 to 3 concrete, testable habits (e.g. "on tier 3 with ≥25 HP,
     level to 4 by T7 instead of T9"), each tied to the evidence. Carry over an earlier item unchanged
     if it was not yet tried; drop it once it has been applied twice.
5. Be direct. If the game was decided by variance (e.g. lost a 90% Bob's Buddy combat), say so
   rather than inventing a mistake. If the summary does not support a conclusion, say what data would.
