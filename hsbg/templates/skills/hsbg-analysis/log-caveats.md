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
- **hsbg-kifu logs.** From 2026-11 the logs can be written by hsbg-kifu, the recorder that replaces
  the HDT plugin (`generator.plugin` = `"hsbg-kifu"`, `hdt_version` null; same schema). Its
  `shop_offers` are the shop as it actually stood, after start-of-turn effects and Tavern buffs, while
  the plugin often caught the turn-start shop before the buffs landed (smaller stats, sometimes a
  missing card). Compare shop stats only between logs of the same recorder. Its buys / sells / rerolls /
  spells / hero powers are counted from the player's own actions and are exact; the plugin's were
  estimated and are off by one on a few turns. MMR comes from HDT's file and is null when HDT was not
  running (note "mmr_before unavailable").
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
- **Beetles (甲虫).** "Your Beetles have +X/+Y this game" (Turquoise Skitterer, Ravaging Scorpid ...)
  is not on any minion, so `board_end_of_shop` totals hide a Beetle build's strength (a 354-stat
  board can beat a 6236-stat one). Recorded from schema 1.7.0 (plugin 0.12.0) as the Beetle's stats
  (base 2/2 included) at shop end and after combat: `turns.beetle_*` and, when the combat opponent
  has a Beetle buff, `combats.opponent_beetle_*` (`hsbg export` / lenses; null = no Beetle buff).
  The values also grow during combat. Older logs got them from their saved power.log
  (`hsbg backfill-buffs`, note "buffs backfilled from power.log: ...").
- **Other "this game" buffs.** Recorded from schema 1.8.0 (plugin 0.13.0) the same way, mine at shop
  end / after combat and the combat opponent's when they have one: `blood_gem_*` (what one Blood Gem
  gives, base +1/+1 included), `tavern_spell_*` (added to what Tavern spells give; includes auras of
  minions on the board, so it can drop when such a minion is sold or dies), `tavern_minion_*` and
  `tavern_elemental_*` (added to Tavern minions / Tavern Elementals). Null means no such buff. Eonar's
  Favor (per minion type) is not recorded.
- **Blood Gem Barrage.** From schema 1.9.0 (plugin 0.14.0): `blood_gem_barrage_*` = the Blood Gem stats
  every Tavern minion gets after each refresh (it adds up with each Barrage played). It is separate
  from `tavern_minion_*` (that one applies to every minion in the Tavern; Barrage only after a refresh),
  so add both when judging how big the shop minions were. No opponent value (never visible).
- **Ice Block.** From schema 1.10.0 (hsbg-kifu 0.2.0): `combat.ice_block` = my Ice Block
  (`TB_Bacon_Secrets_12`, e.g. from Safety Patch) prevented damage that would have killed me, and
  `combat.opponent_ice_block` = the opponent's prevented my lethal damage. `damage_taken` /
  `damage_dealt` still count the blocked damage, so on those turns the HP did not drop by that amount.
  The summary marks them "(my Ice Block)" / "(opp. Ice Block)" and Key moments lists them. An Ice
  Block that saved me from elimination is worth a lot of placement; weigh it when judging the build.
  Older logs and plugin logs have no such key (null): a lost combat whose damage did not lower the next
  turn's HP is usually an Ice Block there.
- **Missing discovers in early hsbg-kifu logs.** hsbg-kifu 0.1.0 – 0.2.0 (`generator.plugin_version`)
  missed most `discover` rows for Triple Rewards and hero powers (about 2 of 3: the choice was made
  before the recorder looked again), and the `offered` of Dark Gifts. Fixed in 0.2.1. In those logs a
  tier-up after a Triple Reward can look like a tier-up "without a reason"; check the `triple` /
  `spell` (TB_BaconShop_Triples_01) rows of the same turn before calling it a mistake.
- **Choices (what was offered and what I picked).** From schema 1.11.0 (hsbg-kifu 0.3.0) every
  choice is recorded in `turns[].choices[]`: Triple Rewards, hero powers (also secret picks), Dark
  Gifts, trinket picks and discovers from minions / spells (`source` = triple / hero_power /
  dark_gift / trinket / card, `source_card` = what made it). Each has the offered cards as shown
  (tier and stats when offered) and `chosen_index`. The summary's `## Choices` table and the
  `choices` / `choice_offers` tables of `hsbg export` show them. To judge a pick, compare it with
  the other options (tier, stats, fit with the board) rather than with the result alone. Trinket
  picks are not tied to turns 6 and 9 (some heroes get extra picks, some get the greater one early).
  A `hero_power` choice whose `source_card` is not the hero power itself was made later by a card
  the hero power created earlier, not by using the hero power that turn (e.g. Getaway Galewing:
  Dungar's Gryphon picks a destination, and Eastern Plaguelands discovers a minion when the flight
  arrives some turns later). The summary shows these as "Hero power → <card>". Kind "pick" (no
  minion offered: destinations, secrets, trinkets) and "discover" (minions offered) are told apart
  by the offered `card_type`.
  From 1.11.0 the `discover` rows also cover these choices and list `offered` in screen order (before:
  entity order); older logs have choices only for Triple Rewards and hero powers, without offers of
  the other kinds.
- **Hero powers held (a second hero power, swaps).** From schema 1.12.0 (hsbg-kifu) every turn has
  `turns[].hero_powers[]`: the hero powers held at the end of the shop, `slot` = main / additional.
  `player.hero_power` stays the first one. A second (additional) hero power comes from Genn, Worgen
  King (turn 4: the first discover goes to the additional slot, the second replaces the main one), a
  Timewarp "Power of X", or other effects. The main one also changes when the hero picks a new one
  every turn (Sunwell Nguyen), switches every turn (Warsong Inge), turns into a flight destination
  (Getaway Galewing), and is gone (`[]`) once it became a trinket or quest (Marin, Buttons,
  Whodunit?). The summary's `## Hero powers` table (only when they changed) and the
  `hero_power_card_id` / `additional_hero_power_card_id` columns of the `turns` table show them.
  `actions.hero_power_uses` counts both hero powers together; the events.jsonl `hero_power` rows
  have `source_card_id` (which one was used) and `hero_power_changed` rows mark each change.
  Older logs have no `hero_powers` (the columns are empty), so a Genn game there shows only the first
  hero power and the two hero power choices of turn 4.
- **Aberration in the type tables.** Aberration was in every lobby from 36.6.1 until 36.6.3
  (2026-10-02) and is in about half the lobbies since, so before 36.6.3 it is only compared on played
  vs not played and after it also on offered vs not offered.
