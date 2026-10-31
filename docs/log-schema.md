# ログファイル仕様（JSON スキーマ）

このドキュメントが **ログ形式の契約**。`schema/game-log.schema.json` はこれと同期させる。
フィールドを変更したら `schema_version` を上げ、Analysis CLI の `loader.py` に互換処理を入れる。

改訂履歴:
- 2026-09-15 初版
- 2026-09-25 Phase 1 の実プレイダンプ（hdt-plugin-hsbg-kansousen の docs/hdt-research.md §2.2, §3.15）を反映。未リリースのため `schema_version` は `1.0.0` のまま
- 2026-09-26 `1.1.0`: `turns[].actions.dark_gifts`（「悪夢の発見」の回数）を追加（任意キー。`1.0.x` のログには無い）。
  events.jsonl に `dark_gift` / `discover` を追加し、`hero_power` に選んだカードと 3 択を載せる。`loader.py` はメジャー 1 を全て受け付ける
- 2026-09-27 `1.2.0`: 神祇（クトゥーン、ヤシャラージュ等）のステータスを追加。`turns[].deity`（自分）と `turns[].combat.opponent_deity`（戦闘相手）。
  どちらも任意キー（`1.1.x` 以前のログには無い。`hsbg backfill-deity` で保存済みの power.log から補完できる。下の「神祇」節）。
- 2026-09-27 `1.3.0`: `deity` / `opponent_deity` に `golden`（神祇が金色か。古なる者の仮面）を追加（任意キー。`1.2.0` のログには無い）。
  events.jsonl の `combat_end` に deity_golden / opponent_deity_golden
  events.jsonl の `shop_end` / `combat_end` に神祇の値を追加
- 2026-09-28 `1.4.0`: ミニオン（`board_end_of_shop[]` / `opponent_board[]`）に `divine_shields`（聖なる盾の枚数。`DIVINE_SHIELD` の値、無ければ 0）を追加
  （任意キー。`1.3.x` 以前のログには無く、分析側は keywords の `divine_shield` から 0/1 とみなす）。闇のパラドックス（`BG36_360t4`）は盾を重ねて 2 枚以上になる
  （保存済み 30 ゲーム中 7 ゲームで 3 枚。HDT 1.58.4 も Bob's Buddy に枚数で渡すようになった）。`keywords` の `divine_shield` は従来どおり 1 枚以上で入る
- 2026-10-11 `1.5.0`（プラグイン 0.9.0）: 分析で「出なかった」と「取らなかった」を区別し、手札の呪文・投資カードと相手のティアを見るために追加。どれも任意キー（`1.4.x` 以前のログには無い）。
  (1) `turns[].hand_end_of_shop` の要素にミニオンの `card_type` / `tier` / `attack` / `health` / `golden` を追加（`snapshot_hand` は既定 true に）、
  (2) `turns[].shop_offers`（ショップに並んだカード。ターン開始時・リロールごと）、(3) `turns[].lobby`（ショップ開始時の他プレイヤーのティアと HP）、
  (4) `combat.opponent_tavern_tier`（戦闘開始時の相手のティア）、(5) ミニオンの `keywords` に `deathrattle` / `rally`（勝鬨。HDT 1.58.7 が表示し始めた `BACON_RALLY`）。events.jsonl に `shop` を追加し、`sell` に売ったミニオンの card_id を入れる（取れないときは null）
- 2026-10-12 `1.6.0`（プラグイン 0.9.2）: `turns[].actions.gold_gained`（売却以外で増えたゴールド）を追加し、`actions.sells` を「盤面のミニオンと対応が付いた売却」だけにした。
  酒場のコイン・青甲羅トートラン・Wealthy Bounty などのゴールド獲得も `RESOURCES_USED` を 1 減らすため（power.log で確認）、**`1.5.x` 以前の `sells` はゴールド獲得を含んで多い**
  （1.5.0 の 19 ゲームで 1 ゲーム 0〜25 件。ロード・バロフで最多）。1.5.x の events.jsonl で card_id = null の `sell` はほぼ全部（141 件中 139 件）がゴールド獲得。
  過去のログは書き換えず、分析側でも数え直さない（売りの比較は 1.6.0 以降のログどうしで行う）。events.jsonl に `gold_gain` を追加。
  `gold_spent` は変えない（戦闘開始時の `RESOURCES_USED` = 売却とゴールド獲得で戻った分を差し引いた正味。`gold_available - gold_spent` は使い残しで、どの版でも正しい）
  プラグイン 0.9.3（schema は 1.6.0 のまま）: 戻ったゴールドを `−ΔRESOURCES_USED + ΔTEMP_RESOURCES + ΔNUM_RESOURCES_SPENT_THIS_GAME` で数える。
  0.9.2 は HDT の `HasTag`（値 > 0）で `RESOURCES_USED` を読んでいたため 0 の tick が null になり、1 → 0 の売却と、満タン時の売却（`TEMP_RESOURCES` が増える）を取り逃した
  （0.9.2 の唯一のログ 2026-10-12 22:59 で 14 件中 2 件）。売却と購入が同じ tick に入る場合も払った累計で相殺を戻す。
  同じ理由で、使わなかったターンの `gold_spent` が 0 でなく null になっていた（0.9.2 までの 1817 ターン中 4 ターン）。0.9.3 から 0
- 2026-10-17 `1.6.1`（プラグイン 0.9.4）: キーは変えず、ミニオン・手札・ショップのカードと events.jsonl の `card_id` / `name` / `minion_types` / `tier` を
  **今のカード**（HDT の `Info.LatestCardId` / `LatestCard`。Bob's Buddy と同じ）で書くようにした。HDT は CHANGE_ENTITY で `CardId` を書き換えないので、
  `1.6.0` 以前はゲーム中に別のカードに変わったものが変わる前のまま残る: ゴールデン・タッチ等でゴールデンになったミニオン（`card_id` に `_G` が付かない。`golden` は PREMIUM タグなので正しい）、
  開いた後の鍵付きの箱（`BG36_520t` のまま）、盤面での変身（天空孵りの脱走者 → ロデオ名人 等。名前と種族も前のまま）。10 月の 45 ゲームで自分のカード 26 件。
  攻撃力・体力・キーワードは Entity のタグなので以前から正しい。HDT 1.58.10 → 1.59.3 で PowerHandler / Entity / EntityInfo は変わっていない（逆コンパイルで確認）
- 2026-10-18 `1.6.2`（プラグイン 0.9.5）: キーは変えず、**Hearthstone のクラッシュ / 切断から同じゲームに再接続したとき、1 本のログに続けて記録する**ようにした（P-22）。
  HDT は再接続したゲームで `OnGameStart` を出し直し、`GameStats.GameId` も新しくなる。`1.6.1` 以前は進行中の記録を捨てて別のゲームとして書き直していたので、
  再接続前のターンが `.partial` に残り（次の HDT 起動で `incomplete` として回収される）、再接続後のターンだけが別の game_id の `complete` になった
  （ヒーロー選択・開始時の HP / アーマーが空、トリンケットは再接続後のターンで記録）。サーバー側のゲーム番号（`MetaData.ServerInfo.GameHandle`）が同じなら同じゲームとみなし、
  game_id・`started_at`・ファイル名は最初の `OnGameStart` のものを使う。再接続中に終わった戦闘の結果は推定値（下の「再接続」節）。
  events.jsonl に `reconnect` を追加し、推定した `combat_end` に `inferred: true` を付ける。
  あわせて、記録中のゲームが `OnGameEnd` を経ずに別のゲーム（GameHandle が違う / 取れない）が始まったときは、捨てずに `incomplete` で書き出す

## 設計方針
- 1 ゲーム = 1 JSON。人間が読めて、AI にそのまま渡せる粒度
- 取得できなかった値は **キーを省略せず `null`**（「取れなかった」と「0」を区別する）
- 取得の確度が低い値には `*_confidence` や `source` を添えるのではなく、**取れた/取れないの二値**にする。推定値はフィールド名に `estimated_` を付ける
- カード ID（`card_id`）と表示名（`name`）を両方持つ。`name` は HDT の `Card.Name`（英語）で、機械処理は `card_id` を使う。
  ヒーローはスキン ID のまま記録し（例 `TB_BaconShop_HERO_34_SKIN_C`）、集計側でスキンを元ヒーローに正規化する。`dbf_id` も持つ
- ターン番号は HDT の `GetTurnNumber()`（自分視点のターン数、1 始まり。GameEntity `TURN` の (n+1)/2）
- BattleTag、プレイヤー名、アカウント ID は **記録しない**（hdt-plugin-hsbg-kansousen の docs/maintenance.md R8）

## 主ログ `<name>.json`

```jsonc
{
  "schema_version": "1.6.2",
  "status": "complete",                 // "complete" | "incomplete" | "not_battlegrounds"
  "generator": {
    "plugin": "HsbgKansousen",
    "plugin_version": "0.1.0",
    "hdt_version": "1.58.3",
    "hearthstone_build": 56608          // GameStats.HearthstoneBuild
  },

  "game": {
    "game_id": "c4802939-b0fa-4efd-ba85-d38ec4d11cb6",   // HDT の GameStats.GameId
    "mode": "battlegrounds",
    "variant": "solo",                   // "solo" | "duos"（Duos は MVP 対象外だが値は残す）
    "game_type": "GT_BATTLEGROUNDS",     // HDT の GameType 名（FRIENDLY / DUO の区別用）
    "started_at": "2026-09-25T15:56:22+09:00",
    "ended_at":   "2026-09-25T16:19:23+09:00",
    "duration_sec": 1381,
    "region": "ASIA",                    // GameStats.Region
    "anomaly": { "card_id": null, "name": null, "dbf_id": null },       // BACON_GLOBAL_ANOMALY_DBID。無しなら全て null
    "global_old_god": { "card_id": null, "name": null, "dbf_id": 130610 }, // BACON_GLOBAL_OLD_GOD_DBID（シーズン機構。無しなら null）
    "minion_types": ["beast", "dragon", "mechanical", "undead", "aberration"], // BattlegroundsUtils.GetAvailableRaces()
    "combat_damage_cap": 15,             // GameEntity BACON_COMBAT_DAMAGE_CAP（無効なら null）
    "lobby_size": 8                      // 対戦相手の数 + 1。相手を 1 人も見ていなければ null（プラグイン 0.9.1 から。0.9.0 は 1 を書いていた）
  },

  "player": {
    "hero": { "card_id": "TB_BaconShop_HERO_34_SKIN_C", "name": "...", "dbf_id": 83651 },
    "hero_choices": [                    // 提示されたヒーロー（最終的な 4 体）。取れなければ []
      { "card_id": "...", "name": "...", "dbf_id": 0, "starting_armor": 18 }
    ],
    "hero_choices_before_reroll": null,  // ヒーローの無料リロールを使った場合のみ、リロール前の 4 体。使っていなければ null
    "hero_power": { "card_id": "TB_BaconShop_HP_035", "name": "..." },
    "starting_health": 60,               // ヒーロー Entity の HEALTH（ヒーローにより異なる）
    "starting_armor": 0,
    "trinkets": [ { "card_id": "BG36_MagicItem_400", "name": "...", "turn": 7 } ],   // 取れなければ []
    "quest": { "card_id": null, "name": null, "reward_card_id": null, "completed_turn": null }  // クエスト非稼働シーズンは全て null
  },

  "result": {
    "placement": 6,                      // 1〜8。自ヒーロー Entity の PLAYER_LEADERBOARD_PLACE（OnGameEnd 時点）。null = 不明
    "mmr_before": 5000,                  // GameStats.BattlegroundsRating
    "mmr_after": 4957,                   // GameStats.BattlegroundsRatingAfter（数秒ポーリング）→ 取れなければ BgsLastGames.xml → それでも無ければ null
    "mmr_delta": -43,                    // after - before。after が null なら null
    "eliminated_turn": 12,               // 自分が敗退したターン。1 位なら最終ターン
    "final_tavern_tier": 5,
    "total_turns": 12
  },

  "opponents": [                         // ロビーの他プレイヤー（自分以外の 7 人）。SETASIDE のヒーロー Entity から
    {
      "player_id": 3,                    // Entity の PLAYER_ID（ゲーム内の番号。個人を特定しない）
      "hero": { "card_id": "BG31_HERO_005", "name": "...", "dbf_id": 0 },
      "placement": null,                 // 自分の敗退時点で確定している順位（自分より先に敗退した相手）。未確定なら null
      "estimated_placement": 1,          // 自分の敗退時点のリーダーボード順位（PLAYER_LEADERBOARD_PLACE）
      "eliminated_turn": null,           // HP が 0 以下になったターン。生存なら null
      "final_health": 15,                // 自分の敗退時点の HP
      "final_armor": 5,
      "final_tavern_tier": 5,
      "trinkets": [ { "card_id": "...", "name": "...", "dbf_id": 134639 } ]  // BACON_FIRST/SECOND_TRINKET_DATABASE_ID
    }
  ],

  "turns": [
    {
      "turn": 1,
      "tavern_tier": 1,                  // ショップ終了時（戦闘開始時）の PLAYER_TECH_LEVEL
      "health": 60,                      // ショップ開始時の HP（= 前戦闘の結果反映後）
      "armor": 0,
      "gold_available": 3,               // そのターンの所持ゴールド（戦闘開始時の RESOURCES）
      "actions": {                       // このターンのショップ行動の集計。取れなければ null
        "gold_spent": 3,                 // 戦闘開始時の RESOURCES_USED（売却とゴールド獲得で戻った分は差し引かれる正味。gold_available - gold_spent = 使い残し）
        "buys": 2, "sells": 0, "rerolls": 1, "tier_ups": 0,   // OnUpdate（100ms）の差分検出による推定。専用タグは無い（±1 の誤差を許容）
        "hero_power_uses": 1, "spells_played": 0,          // buys: ショップの Entity が手札へ / rerolls: ショップ全体の入れ替わり / sells: RESOURCES_USED の減少のうち、盤面から消えたミニオンと対応が付いたもの（1.5.x 以前は全部）
                                                           // tier_ups: PLAYER_TECH_LEVEL の増加 / hero_power_uses: そのターン PLAY 中だったヒーローパワー Entity ごとの EXHAUSTED 0→1（使用後に SETASIDE へ移る型も含む） / spells_played: 手札のスペルが消えた回数
        "gold_gained": 0,                                  // 1.6.0: RESOURCES_USED の減少のうち、売却と対応が付かなかったもの（酒場のコイン等で増えたゴールド）。実際に払った総額 = gold_spent + sells + gold_gained
        "dark_gifts": 1                                    // 1.1.0: 「悪夢の発見」（BG36_Button_DarkGift。ゴールドを払ってミニオンを 1 体発見）の回数。
                                                           // 得たミニオンはショップを経由せず手札に来るので buys には含まれない（作成元 CREATOR/DISPLAYED_CREATOR で判定）
      },
      "board_end_of_shop": [             // 戦闘に出した盤面（左から順）。戦闘開始時に取得
        {
          "position": 1,
          "card_id": "BG35_814", "name": "...",
          "tier": 1, "attack": 3, "health": 3,
          "golden": false,               // PREMIUM
          "keywords": ["taunt"],          // taunt, divine_shield, poisonous, venomous, reborn, windfury, stealth。1.5.0 から deathrattle（DEATHRATTLE）, rally（勝鬨、BACON_RALLY）も
          "divine_shields": 0,           // 1.4.0: 聖なる盾の枚数（DIVINE_SHIELD の値。無ければ 0。闇のパラドックスは 2 枚以上になる）
          "minion_types": ["beast"]       // CARDRACE（HDT の Card.RaceEnum / 複数種族は Card から）
        }
      ],
      "hand_end_of_shop": [              // config.snapshot_hand=true（既定）のときのみ配列。false なら null。左から順
        { "card_id": "BG20_GEM", "name": "Blood Gem", "dbf_id": 70136,
          "card_type": "spell", "tier": 1, "attack": null, "health": null, "golden": null },   // 1.5.0: card_type = minion | spell | other。tier は TECH_LEVEL（酒場の呪文にもある）
        { "card_id": "BG28_633", "name": "Felboar", "dbf_id": 0,
          "card_type": "minion", "tier": 5, "attack": 6, "health": 6, "golden": false }       // ミニオンは手札での現在値（強化されていることがある）
      ],                                 // 1.4.x 以前は card_id, name, dbf_id だけ
      "shop_offers": [                   // 1.5.0: このターンにショップへ並んだカード。観測できなければ []
        { "trigger": "turn_start",       // turn_start = ターンで最初に見えた酒場（凍結を含む） / reroll = 丸ごと入れ替わった /
          "cards": [ /* hand と同じ要素。酒場の並び順 */ ] },   // refill = 買い切って空になった後 / added = 途中から増えたカード（増えた分だけ）
        { "trigger": "reroll", "cards": [] }
      ],
      "lobby": [                         // 1.5.0: ショップ開始時の他プレイヤー（リーダーボードに出ている公開情報）。取れなければ null
        { "player_id": 3, "tavern_tier": 2, "health": 30, "armor": 5, "leaderboard_place": 1, "eliminated": false }
      ],                                 // SETASIDE のヒーロー Entity の PLAYER_TECH_LEVEL / HEALTH / ARMOR / PLAYER_LEADERBOARD_PLACE（opponents[] と同じ取り方）
      "deity": {                         // 1.2.0: 自分の神祇。神祇の無いシーズン / Sigil が取れなければ null（下の「神祇」節）
        "card_id": "BGFYM_000", "name": "C'Thun", "dbf_id": 130610,   // Sigil の BACON_EVOLUTION_CARD_ID
        "attack": 3703, "health": 3983,  // ショップ終了時 = 戦闘に持ち込む値（印刷値への加算ではなく合計値）
        "attack_after_combat": 6187, "health_after_combat": 6467,     // 戦闘終了時（戦闘中に異形が死ぬ等で伸びた分を含む）
        "awakened": true,                // この戦闘で目覚めたか（味方の異形が規定数死ぬと召喚される）。不明なら null
        "golden": false                  // 1.3.0: 神祇が金色か（古なる者の仮面）。Sigil の神祇カードが金色版（card_id が _G で終わる）か、金色で目覚めたら true
      },
      "combat": {
        "opponent_player_id": 7,         // 自ヒーロー Entity の NEXT_OPPONENT_PLAYER_ID（戦闘相手の PLAYER_ID と一致）
        "opponent_hero": { "card_id": "BG20_HERO_283_SKIN_G", "name": "...", "dbf_id": 0 },
        "opponent_board": [ /* board と同じ要素 */ ],
        "opponent_health": 30, "opponent_armor": 10,   // 戦闘開始時
        "opponent_tavern_tier": 4,       // 1.5.0: 戦闘開始時の相手ヒーロー（PLAY 中）の PLAYER_TECH_LEVEL。取れなければ null
        "result": "win",                 // "win" | "loss" | "tie" | null（OnEntityWillTakeDamage のヒーロー被弾から判定）
        "damage_dealt": 2,
        "damage_taken": 0,
        "bobs_buddy": {                  // 次ショップ開始時にリフレクションで取得。取れなければ null
          "win": 1.0, "tie": 0.0, "loss": 0.0,
          "lethal": 0.0, "opponent_lethal": 0.0,   // myDeathRate / theirDeathRate ではなく「相手を倒す/自分が倒される」確率
          "avg_damage": 2.0,             // 正 = 与ダメ期待値、負 = 被ダメ期待値
          "simulations": 10000
        },
        "opponent_deity": {              // 1.2.0: 戦闘相手の神祇（deity と同じ形）。attack/health は戦闘開始時。
          "card_id": "BGFYM_000", "name": "C'Thun", "dbf_id": 130610,   // 相手の Sigil は戦闘中だけ読めるので、読めなければ null
          "attack": 3578, "health": 3496,
          "attack_after_combat": 4626, "health_after_combat": 4544,
          "awakened": true,
          "golden": false
        }
      }
    }
  ],

  "notes": []                            // プラグインが検出した警告（"mmr_after unavailable" 等）
}
```

`bobs_buddy` の対応: `win`=winRate, `tie`=tieRate, `loss`=lossRate, `lethal`=theirDeathRate（相手を倒す確率）, `opponent_lethal`=myDeathRate（自分が倒される確率）, `avg_damage`=avDamage。

### 神祇（`turns[].deity` / `combat.opponent_deity`、1.2.0 / `golden` は 1.3.0）

2026 年のシーズンでは、異形（aberration）に「神祇」（ロビー共通の旧神。`game.global_old_god`）が付く。神祇は盤面にいないが
「各戦闘で味方の異形が 4 体死んだ後に {攻}/{体} の神祇を目覚めさせる」ので、**盤面のステータスだけでは戦闘力が分からない**。
目覚める条件は 36.6.3（2026-10-02）で 3 体 → 4 体、神祇の Tier（ヒーローへのダメージ計算）も 3 → 1 に変わった（hsbg-knowledge の
`patches/2026-10-02_36.6.3.md`）。ログは目覚めた事実（`awakened`）を観測しているので記録方法は変わらないが、日付の前後で覚醒の回数や時期を比べられない。
同じパッチで異形の全ロビー保証が終わった。異形が出ないロビーで神祇が無い（`deity` が null になる）かは要観察。
確認済みの神祇は 2 種（保存済み 29 ゲームで 1 ロビーに 1 種、全員共通）:

| 神祇 | card_id（金色） | dbfId（金色） | 目覚めたときの効果 |
|---|---|---|---|
| クトゥーン | `BGFYM_000`（`BGFYM_000_G`） | 130610（134633） | 自身を除く全ての味方に自身の攻撃力・体力を分配（金色は 2 倍） |
| ヤシャラージュ | `BGFYM_011`（`BGFYM_011_G`） | 132532（134634） | 断末魔: この戦闘で最初に死亡した味方の異形 2 体（金色は 4 体。神祇は除く）を最大攻撃力・体力で召喚 |

ヤシャラージュの召喚数は覚醒したミニオンの `TAG_SCRIPT_DATA_NUM_1`（通常 2、金色 4）。29 ゲームで他の値は無く、金色から決まるので記録しない。
クトゥーンは神祇の大きさがそのまま効くが、ヤシャラージュは本体の大きさに加えて **先に死ぬ異形の強さ** が効く（分析側の説明文はこの違いを出し分ける）。
値の置き場所（2026-09-26 の Power.log と HDT 1.58.3 のソースで確認）:

- 各プレイヤーは SECRET ゾーンに Sigil `BG_OldGod`（"Secret Deity [DNT]"、HearthDb `SecretDeityDnt`）を持つ。
  `BACON_EVOLUTION_CARD_OVERWRITE_ATK/HEALTH`（4906/4907）が神祇の **現在の合計値**、`BACON_EVOLUTION_CARD_ID` が神祇の dbfId。
  プレイヤー Entity の `BACON_OLD_GOD_ATTACK/HEALTH` も同じ値（HDT の Deity カウンターはこちら。デュオでは Sigil 側が正）
- 自分の Sigil はゲーム中ずっと存在する。戦闘相手の Sigil は **戦闘ごとに複製**され（一瞬こちらの制御で SETASIDE に作られてから相手の制御に移る）、
  戦闘の後片付けで値が 0 に戻される。したがって相手の値は戦闘中にしか読めない
- 目覚めると `CREATOR` = Sigil のミニオン（とその一時コピー）が作られる。**目覚めない戦闘ではこのミニオンは作られない**
  （保存済み 25 ゲームで、この判定と `BaconFX_*OverrrideSpawn` 演出の回数が 24 ゲームで一致。残る 1 回は演出なしの覚醒で、判定の方が正しい）
- 戦闘の前後で値は変わる（戦闘中に伸びる）。HDT は PowerTaskList（演出の進行）に合わせて Entity を更新するので、プラグインは
  戦闘中の毎 tick に Sigil を読み、最後の非 0 値を `*_after_combat` にする。相手は最初の非 0 値を `attack/health` にする
- ゴースト戦など相手の Sigil が無い戦闘では `opponent_deity` は null
- **金色**: 古なる者の仮面（Mask of Ancient Ones）を取った時点で Sigil の `BACON_EVOLUTION_CARD_ID` が金色版に切り替わる
  （2026-09-26 18:28 のゲームで T9 に 130610 → 134633。HDT 1.58.3 のコメントは「Sigil は金色にならない」だったが、カードは切り替わる。
  HDT 1.58.4 の `BobsBuddyUtils.GetDeityFromSigil` も金色版カードなら金色として扱うようになった）。
  覚醒したミニオンの CardID も `_G` で終わる。`golden` はこのどちらかで true（覚醒前から分かる）
- **相手の Sigil のコピーは後片付けでカードも戻される**: 同じブロックで `ZONE` → `REMOVEDFROMGAME`、攻撃・体力 → 0、
  `BACON_EVOLUTION_CARD_ID` が 0 → 130610（神祇に関係なくクトゥーン）の順（2026-09-27 23:34 のゲームで確認）。
  HDT 1.58.4 は `REMOVEDFROMGAME` の Sigil を読まないよう直した。プラグインも 0.8.0 から相手の Sigil を探すときに除外する（値 0 は従来から捨てている）。
  相手の神祇のカードは戦闘中に最初に読めた値を使う（プラグインは初めから、`hsbg backfill-deity` は 1.3.0 で修正）

### 必須フィールド（`status: "complete"` のとき）
`schema_version`, `status`, `generator.plugin_version`, `game.game_id`, `game.started_at`, `game.ended_at`,
`player.hero.card_id`, `result.placement`, `turns[]`（各要素の `turn`, `tavern_tier`, `health`）

それ以外は `null` / `[]` を許容する。

### `status` の意味
| 値 | 意味 |
|---|---|
| `complete` | `OnGameEnd` まで正常に到達し、順位が確定した |
| `incomplete` | 途中で HDT 終了・プラグイン停止・クラッシュが起きた。`turns` は取れた分だけ。1.6.2 から、終わる前に別のゲームが始まったときも（Hearthstone だけのクラッシュから同じゲームに戻ったときは `complete` まで続く） |
| `not_battlegrounds` | BG 以外のモード。原則としてファイルは書かないが、判定ミス時のセーフティ |

**ターン 1 の前に終わったゲームはファイルを書かない**（プラグイン 0.9.1 から）。ヒーロー選択中にゲームから外されたときなど、
`turns` が空・`total_turns` が 0・ヒーローも順位も無いゲームは、本体・power.log を書かず、逐次書いていた events.jsonl と `.partial` も消す
（`plugin.log` に `ended before turn 1; log discarded` を残す）。判定は `Logic/AbortedGame.cs`。分析側（`loader.is_aborted_before_first_turn`）も
同じ条件のログを警告なしで読み飛ばす（`hsbg validate` に `ended before turn 1 (ignored)` として件数だけ出る。0.9.0 以前のものは `lobby_size: 1` でスキーマに違反する）

### 再接続（`1.6.2`、プラグイン 0.9.5）

Hearthstone だけが落ちて（または切断して）同じゲームに戻ったとき、HDT は動いたままなのでプラグインは記録を続ける。HDT ごと落ちた場合はメモリ上の記録が消えるので対象外
（従来どおり次回起動時に `.partial` を `incomplete` で回収する）。再接続したゲームのログは次のようになる:

- `notes[]` に `reconnect: resumed the same server game (<GameHandle>) after turn N; ...`（再接続ごとに 1 行）
- **戦闘中に落ちたターン**: その戦闘のダメージ通知を見ていないので、戦闘直前（ショップ終了時 / 戦闘開始時）と次のショップ開始時（最終ターンはゲーム終了時）の
  HP + アーマーの差から `result` / `damage_dealt` / `damage_taken` を推定する（自分だけ減った = loss、相手だけ減った = win、どちらも 0 = tie。決められなければ null のまま）。
  `notes[]` に `reconnect: turn N combat ended while disconnected; result <loss|win|tie|unknown> inferred from health + armor (mine a -> b, opponent c -> d)`。
  `bobs_buddy` は再接続前の HDT のゲーム ID で引く（シミュレーションが終わっていれば入る）。神祇の戦闘後の値と覚醒は null
- **ショップ中に落ちたターン**: 落ちる前の行動回数を残し、同じショップに戻れたら再接続後の分を足す（`gold_spent` はショップ終了時の値）。戻ったときの最初の酒場は
  `shop_offers` に `turn_start` として二重に書かない。戻ったときにはもう戦闘・次のターンだったら、その戦闘は上と同じく推定する（戦闘直前の値はショップ開始時の HP + アーマー）
- **戦闘中に戻った**: その戦闘を始まりから見ていないので、上と同じく推定する。相手のヒーローがまだ分からなければ読むが、相手の盤面は戦闘の途中なので書かない（`opponent_board` は空）
- ヒーロー選択（`hero_choices` / `hero_choices_before_reroll`）、開始時の HP / アーマー、トリンケットを取ったターンは再接続前の値を残す
- power.log は再接続前の行（プラグインがターン開始ごとにコピーしたもの。落ちたターンの最後のターン開始以降の行は無い）と再接続後の行をつなげたもの。
  再接続後の区間は `CREATE_GAME` から始まらない

再接続したゲームを分析に使うかはユーザーが 1 件ずつ決める（瞬間的な切断でそのターン中に戻れたなら続けて使い、長く抜けて大事な場面をプレイできなかったなら外す）。外すゲームは `HSBG-Logs\.excluded\YYYY\MM\` に移し、理由を `.excluded\README.md` に書く（分析ツールは `.` で始まるフォルダを読まない）。

1.6.1 以前に分かれてしまったゲームは、Claude が `.partial` と再接続後のログ、events.jsonl、Hearthstone 本体の Power.log から 1 本にまとめ直した（2026-10-17 17:45 のゲーム。
`notes[]` に `reconnect merge: ...`）

## 補助ファイル 1: `<name>.events.jsonl`（任意）

ゲーム中の細粒度イベントを 1 行 1 JSON で追記する。**ゲーム中に逐次書く**（クラッシュ対策も兼ねる）。

```jsonl
{"t":"2026-09-25T15:56:27+09:00","turn":0,"type":"hero_choice","card_ids":["...","...","...","..."]}
{"t":"...","turn":0,"type":"hero_reroll","replaced_card_id":"...","new_card_id":"..."}
{"t":"...","turn":0,"type":"hero_selected","card_id":"TB_BaconShop_HERO_34_SKIN_C"}
{"t":"...","turn":1,"type":"turn_start","tier":1,"health":60,"armor":0}
{"t":"...","turn":1,"type":"buy","card_id":"BG35_814","name":"...","gold_after":0}
{"t":"...","turn":1,"type":"play","card_id":"BG35_814","position":1}
{"t":"...","turn":2,"type":"reroll","gold_after":1}
{"t":"...","turn":2,"type":"tier_up","tier":2,"gold_after":0}
{"t":"...","turn":3,"type":"sell","card_id":"BG_xx"}
{"t":"...","turn":3,"type":"combat_start","opponent_player_id":8,"opponent_hero_card_id":"BG36_HERO_000"}
{"t":"...","turn":3,"type":"combat_end","result":"win","damage_dealt":5,"damage_taken":0}
{"t":"...","turn":5,"type":"hero_power","card_id":"..."}
{"t":"...","turn":7,"type":"trinket","card_id":"BG36_MagicItem_400"}
{"t":"...","turn":8,"type":"triple","card_id":"BG36_112"}
{"t":"...","turn":9,"type":"player_eliminated","player_id":2}
{"t":"...","turn":12,"type":"game_end","placement":6}
```

`type` の語彙（Phase 4 で実装）:

| type | 主なフィールド | 発生源 |
|---|---|---|
| `game_start` | game_id, game_type, mmr_before | `OnGameStart` |
| `hero_choice` / `hero_reroll` | card_ids[], dbf_ids[] | ヒーロー選択中の `OnUpdate`（2 秒間隔） |
| `hero_selected` | card_id, name, dbf_id | ターン 1 開始 |
| `turn_start` | tier, health, armor | `OnTurnStart(Player)` |
| `buy` / `play` / `spell` | card_id, name, gold_after | ショップ中の差分検出（推定） |
| `sell` | card_id, name（売ったミニオン。1.5.0。取れなければ null）, value（1）, gold_after | 同上。戻ったゴールド（`RESOURCES_USED` の減少 + `TEMP_RESOURCES` の増加 + 払った累計 `NUM_RESOURCES_SPENT_THIS_GAME` の増加。0.9.3）と「盤面から消えて手札に行っていないミニオン」を 3 tick まで待って突き合わせる。1.6.0 から対応が付いたものだけ（件数は `actions.sells` と揃う）。1.5.x は対応が付かない減少も card_id = null の `sell` で出していた（ほぼ全部がゴールド獲得）。1.4.x 以前は value に個数、card_id は常に null |
| `gold_gain` | value（1）, gold_after | 1.6.0。ゴールドが戻ったのに 3 tick 以内に盤面から消えたミニオンが無い（酒場のコイン等）。ショップ終了時に待っているものも出す。件数は `actions.gold_gained` と揃える |
| `shop` | trigger（`turn_start` / `reroll` / `refill` / `added`）, cards[]（card_id。酒場の並び順） | 1.5.0。`turns[].shop_offers` と同じタイミング |
| `triple` | value（個数）, gold_after | 同上 |
| `reroll` | gold_after | 同上 |
| `hero_power` | gold_after。発見型のヒーローパワー（ゴミを宝に 等）で選んだカードが同じ tick で手札に来たときは card_id, name, source=`hero_power`, offered[]（3 択の card_id） | 同上 |
| `dark_gift` | card_id, name（選んだミニオン）, gold_after, source=`dark_gift`, offered[]（3 択。観測できなければ null） | 1.1.0。手札に現れた Entity の **直接の** 作成元（DISPLAYED_CREATOR か CREATOR）がボタン `BG36_Button_DarkGift` / 発見スペル `BG36_MidGameEffect_010`。作成元を何段も辿らない（得たミニオンが生成したカードや悪夢の恵みが作るコピーを除外） |
| `discover` | card_id, name, gold_after, source（`hero_power` / `triple`）, offered[] | 1.1.0。ヒーローパワー（EXHAUSTED と別 tick になったとき）やトリプル報酬の発見で選んだカード。**3 択に含まれていたカードだけ**（Barov の Tavern Coin のような生成物は記録しない） |
| `tier_up` | value（新ティア）, gold_after | 同上 |
| `shop_end` | tier, gold_available, gold_spent, board[], next_opponent_player_id。神祇があれば deity_attack, deity_health（1.2.0） | `OnTurnStart(Opponent)` |
| `combat_start` | opponent_player_id, opponent_hero_card_id, opponent_health, opponent_armor, opponent_tavern_tier（1.5.0）, opponent_board[] | 戦闘フェーズ開始 |
| `combat_end` | result, damage_dealt, damage_taken（再接続中に終わった戦闘は推定値で `inferred: true`。1.6.2）。神祇があれば deity_attack_after, deity_health_after, deity_awakened, deity_golden、相手の Sigil が読めれば opponent_deity_attack, opponent_deity_health, opponent_deity_awakened, opponent_deity_golden（1.2.0。golden は 1.3.0） | 次ターン開始時（最終ターンはゲーム終了時） |
| `trinket` | card_id, name, dbf_id | 獲得を検出したとき |
| `player_eliminated` | player_id, hero_card_id, eliminated_turn, place | ターン開始時のロビー更新 |
| `game_end` | placement, total_turns, status | `OnGameEnd` |
| `mmr_after` | mmr_after, mmr_delta | MMR 後値の確定時 |
| `warning` | message | `notes[]` に追記したとき |
| `reconnect` | game_handle, hdt_game_id（HDT が付け直した GameStats.GameId）, interrupted_combat_turn, interrupted_shop_turn（見られなかった戦闘 / 落ちたショップのターン。無ければ null） | 1.6.2。同じサーバーのゲームで `OnGameStart` が出し直されたとき（上の「再接続」節） |

`freeze` は未実装。取れないイベント種別があっても構わない。主ログの `turns[].actions` は同じ差分検出の集計値なので、events.jsonl と一致する。
書き込みはキュー経由でバックグラウンド行われ、ゲーム終了時と MMR 後値の確定時にフラッシュされる。

## 補助ファイル 2: `<name>.power.log.gz`（任意。`power_log_gzip: false` なら `<name>.power.log`）

該当ゲームの Power.log 行をそのまま書き出したもの。**HDT が保持する `Core.Game.PowerLog`（ゲーム単位の行リスト）を `OnGameEnd` で書く**。
再接続したゲーム（1.6.2）は、HDT が再接続時に `PowerLog` を空にするので、プラグインがターン開始ごとにコピーしておいた再接続前の行を前につなげる。
実測で 1 ゲーム（14 ターン、29 分）約 20 万行 / 29 MB あるため、既定では gzip（約 3 MB）。Python は `gzip.open(path, "rt", encoding="utf-8")` で読める。
HDT の Replays（`.hdtreplay`）機能は BG では動作しないので使わない（hdt-plugin-hsbg-kansousen の docs/hdt-research.md §3.10）。
HDT が読み込んだ時点で日本語カード名は文字化けしているが `CardId` と数値は無傷なので、再抽出は `CardId` ベースで行う。
AI に「生ログから戦闘の詳細を読み解かせる」用途と、将来スキーマを拡張したときの **再抽出用**。

再抽出の例: `hsbg backfill-deity`（`analysis/hsbg/powerlog.py`）は 1.2.0 より前のログに `deity` / `opponent_deity` を補う。
GameEntity の `TURN` はターン n のショップで 2n-1、戦闘で 2n なので、`TURN` が 2n になった時点の自分の Sigil をショップ終了時の値、
2n+1（最終ターンはファイル末尾）になった時点を戦闘後の値とする。元の JSON は `<logs>\.backup\deity-<日時>\` に退避し、
`schema_version` を 1.3.0 にして `notes[]` に `deity backfilled from power.log` を追記する。power.log の無いゲーム（2026-09-25 19:26 より前）は補完できない。
すでに神祇の値があって `golden` が無いログは、プラグイン（0.6.0）が書いたものなら値を残して `golden` だけ足し（note `deity golden backfilled from power.log`）、
以前の補完が書いたものは作り直す（1.2.0 の補完は相手のカードを後片付け後に読んでいて、ヤシャラージュ戦の相手がクトゥーンになっていた）。

## 分析側での正規化テーブル（Analysis CLI 内部。参考）

| テーブル | 主キー | 主な列 |
|---|---|---|
| `games` | game_id | started_at, hero_card_id, hero_base_card_id（スキン正規化後）, placement, mmr_before, mmr_after, mmr_delta, total_turns, final_tier, duration_sec, status, minion_types, anomaly_card_id |
| `turns` | game_id, turn | tavern_tier, health, armor, gold_available, gold_spent, buys, sells, gold_gained（1.6.0）, rerolls, tier_ups |
| `combats` | game_id, turn | opponent_player_id, opponent_hero, opponent_tavern_tier（1.5.0）, result, damage_dealt, damage_taken, bb_win, bb_tie, bb_loss, bb_avg_damage |
| `board_minions` | game_id, turn, position | card_id, tier, attack, health, golden, keywords, divine_shields（1.3.x 以前は keywords から 0/1）, minion_types |
| `opponents` | game_id, player_id | hero_card_id, placement, estimated_placement, eliminated_turn, final_tavern_tier |
| `hand` | game_id, turn, position | card_id, name, card_type, tier, attack, health, golden（1.5.0。1.4.x 以前の手札は card_id, name だけ） |
| `shop_offers` | game_id, turn, offer, position | trigger, card_id, name, card_type, tier, attack, health, golden（1.5.0） |
| `lobby` | game_id, turn, player_id | tavern_tier, health, armor, leaderboard_place, eliminated（1.5.0） |
| `sells` | game_id, turn | card_id, name（events.jsonl の `sell`。1.4.x 以前は card_id が null） |
