# Log caveats (what older plugin / schema versions record differently)

Read before judging a missing or odd value. Versions: `generator.plugin_version` and
`schema_version` in each log (`hsbg summarize` prints them). Facts about the game itself (patches,
season mechanics) belong to the knowledge folder; the season notes here are only what is needed to
read these logs.

- **Hand and shop.** My hand at the end of each shop, the shops I saw (turn start / each reroll), the
  other players' tiers and the combat opponent's tier are in logs from plugin 0.9.0 (schema 1.5.0,
  2026-10-11): the summary's `## Hand and shop` table and the `hand` / `shop_offers` / `lobby` /
  `sells` tables of `hsbg export`. Hands alone (card names, no stats) exist from 2026-10-11 with
  plugin 0.8.0. Older logs have none of these; say so instead of guessing what was offered.
- **Turns without actions.** On turns where the player cannot act (A. F. Kay's first two turns, etc.)
  `gold_available` / `gold_spent` are null and the summary shows `-`. This is not a defect.
- **Dark Discovery.** Logs written before plugin 0.5.0 (schema 1.0.0) have no `dark_gifts` count: the
  Dark Discovery button (悪夢の発見, 3 gold for a discovered minion with a Dark Gift / 悪夢の恵み on it)
  shows up only as gold spent plus a later `play`, so "gold spent with no recorded action" in those
  logs is usually that, not a bug.
- **Sells.** Sells are inflated in logs before schema 1.6.0 (plugin 0.9.2, 2026-10-12): gold gained
  without selling (Tavern Coin, Tortollan Blue Shell, …) was counted as a sell, up to 25 per game
  (most with Bookie Barov). The logs are not rewritten. Compare sells only between 1.6.0+ logs, and do
  not read a high sell count in an older log as re-buying. From 1.6.0 the gold gained is its own count
  (`gold_gained`, "+N" in the summary's Gold column).
- **Changed cards.** In logs before schema 1.6.1 (plugin 0.9.4, 2026-10-17) a card that changed during
  the game keeps its old card id and name: an opened Locked Box (鍵付きの箱) still shows as the box,
  and a minion that transformed shows as what it was before. Its stats and `golden` are correct. Do not
  read such an entry as the card itself (a one-off differing tier row for a `card_id` is usually this).
- **Blood Gems.** Blood Gem `BG20_GEM` is `CARDTYPE`=5 (a spell, not a Tavern spell), so
  `spells_played` counts Blood Gems played from hand (HDT `IsSpell`). Gems that minion effects apply
  directly never enter the hand and are not counted.
- **Deity (神祇, season 14, e.g. C'Thun / Y'Shaarj).** Recorded from schema 1.2.0 (plugin 0.6.0): the
  summary's `## Deity` table (mine and the combat opponent's, at combat start / after combat, awakened
  or not, next to both board totals) and the `hsbg stats` table "Deity (神祇) by game". A game whose
  board looks weaker than the opponent's can still be won by a bigger Deity, so compare both before
  calling a combat lucky. Older logs got it from their saved power.log (`hsbg backfill-deity`, note
  "deity backfilled from power.log"); logs without a power.log have none. There are two Deities with
  different abilities (C'Thun splits its stats; Y'Shaarj resummons the first 2 Aberrations that died)
  and either can be golden (schema 1.3.0 `golden`, Mask of Ancient Ones / 古なる者の仮面: C'Thun ×2,
  Y'Shaarj resummons 4); the summary prints the matching ability line. Patch 36.6.3 (2026-10-02)
  changed the rules: the Deity needs 4 friendly Aberration deaths in a combat (3 before) and counts as
  tier 1 for hero damage (3 before). Deity awakening turns, awakened combats and damage taken from
  Deity boards are not comparable across that date; split the period.
- **Aberration in the type tables.** Aberration was in every lobby from 36.6.1 until 36.6.3
  (2026-10-02) and is in about half the lobbies since, so before 36.6.3 it is only compared on played
  vs not played and after it also on offered vs not offered.
