# AI 分析と戦績可視化の設計

## 1. 分析の問い（何を知りたいか）

ログ設計と指標はこの問いに答えられることを基準にする。

| # | 問い | 必要なデータ | 指標 |
|---|---|---|---|
| Q1 | 全体の成績は上向いているか | placement, mmr, started_at | MMR 推移、移動平均順位（直近 20） |
| Q2 | どのヒーローで勝てて、どれで負けているか | hero, placement | ヒーロー別 平均順位 / Top4 率 / 1 位率 / 試行回数 |
| Q3 | ティアアップのタイミングは適切か | turns[].tavern_tier, placement | ティア到達ターンの分布と順位の相関（例: T3 到達が 5 ターン目以前 vs 以後） |
| Q4 | どのターン帯で負け始めるか | combats[].result, damage_taken, health | ターン帯別 戦闘勝率、HP 推移の中央値 |
| Q5 | リロールしすぎ / しなさすぎか | actions.rerolls, gold_spent, placement | リロール数と順位の関係 |
| Q6 | 苦手な相手ヒーロー・構成 | combat.opponent_hero, opponent_board | 相手ヒーロー別戦闘勝率、負け戦闘の相手盤面のタイプ分布 |
| Q7 | 種族: どの種族で勝てて / 負けているか。ゲーム内で主軸種族はどう移るか。相性は | game.minion_types（出現 5 種）、各ターンの board / opponent_board、combat.result | 出現時 vs 使用時の平均順位・採用率、最終主軸種族別の順位 / 主軸を固めたターン / 方針転換回数、序盤→最終の遷移、自分の主軸 × 相手の主軸の戦闘勝率（§1.1） |
| Q8 | 敗退の直接原因は何か（1 ゲーム） | 全ターン詳細 + events | AI による定性分析 |

### 1.1 種族の分析軸（2026-09-25 細部調整 P-6）

ゲームごとにランダムに 5 種族が出現するので、ヒーローと同じ粒度で「種族ごとの内訳・傾向・次戦のレコメンド」を出す。
`metrics.py` の定義:

- **主軸種族**（main type）= そのターンのショップ終了時の盤面で最も数が多い種族。複数種族のミニオンは両方に数え、
  全種族（`all`）ミニオンは勝った種族に加算、種族なしは盤面数にだけ数える。同数なら合計スタッツ（攻撃 + 体力）が大きい方、
  それも同じなら種族名順。`dominant_type`（1 盤面、純 Python）と `main_type_by_turn`（全盤面、pandas）が同じ規則を実装し、
  テストで一致を検査する
- **出現 vs 使用**（`type_availability_stats`）: 種族ごとに「出現したゲーム」（`game.minion_types`）の成績と、
  その種族を最終盤面の主軸にした「使ったゲーム」の成績、採用率、使わなかったときの平均順位。
  → 使ったときの方が良い種族は次に出たら狙う候補、採用率が高いのに順位が悪い種族は癖
- **最終主軸種族と順位**（`minion_type_stats`）: ゲーム数、平均順位、Top4 率、1 位率、盤面に占める割合、
  **主軸を固めたターン**（最終主軸が最後まで主軸であり続けた最初のターン）の中央値、**方針転換**（T4 以降に主軸が入れ替わった回数）の平均
- **フェーズ別の主軸**（`type_phases`）: ゲームごとに序盤（T1〜5）・中盤（T6〜10）・終盤（T11〜）それぞれの最後のターンの主軸と最終主軸、
  固めたターン、方針転換。`type_transitions` で序盤→最終の遷移を集計。`type_timeline` はターン × ゲームの主軸（タイムライン図）
- **相性**（`type_matchups` / `opponent_type_stats`）: 自分の主軸 × 相手の主軸の戦闘勝率、相手主軸種族別の戦闘成績
- 制約: 盤面は Phase 3（プラグイン v0.2）以降のログにしかないので、それ以前のゲームは種族の集計に入らない。
  異形は 36.6.1〜36.6.3（2026-10-02）の間は毎ゲーム出現したため、その期間は出現の有無での比較は他の種族だけに意味がある。
  36.6.3 以降は約半数のロビーに出る通常の種族になった。
  種族の組み合わせ（どの 5 種が揃ったとき）の分析はサンプルが 1 ゲーム単位で割れるので保留（§7）

## 2. 戦績サマリーレポート（静的 HTML）の構成

`hsbg report` が生成する単一 HTML（plotly を inline、オフラインで開ける）。
**用途**: 生成時点のスナップショット。月次の振り返り、保存・共有、Claude に読ませる入力。
日常的な閲覧と掘り下げはダッシュボード（§3）で行う。

1. **ヘッダー**: 対象期間、ゲーム数、除外した incomplete 数
2. **KPI カード**: 平均順位、Top4 率、1 位率、MMR 変化（期間合計）、平均ゲーム時間
3. **MMR 推移**: 折れ線（x: ゲーム順 / 日付、y: mmr_after）。欠損は補間しない
4. **順位分布**: 1〜8 位のヒストグラム
5. **ヒーロー別成績**: 表（ヒーロー、n、平均順位、Top4 率、1 位率）+ 横棒グラフ。n < 3 は薄く表示
5b. **種族**（§1.1）: 出現 vs 使用の表とグラフ、最終主軸種族の表と横棒グラフ、主軸種族のタイムライン、相性ヒートマップ
6. **ティア到達ターン**: 箱ひげ（T2〜T6 それぞれの到達ターン）、色分けで Top4 / Bottom4
7. **ターン帯別 戦闘勝率**: 折れ線（x: ターン、y: 勝率）
8. **HP 推移**: ターン毎の HP の中央値と四分位（Top4 と Bottom4 で分けて重ねる）
9. **相手ヒーロー別 戦闘成績**: 表
10. **直近ゲーム一覧**: 日時、ヒーロー、順位、MMR Δ、最終ティア、ログファイルへのリンク

## 3. ローカル Web ダッシュボード（`hsbg serve`）の構成

§2 のグラフは `charts.py` の同じ関数で描画する。ダッシュボード固有なのは「フィルタ」と「掘り下げ」。

表示は日本語（2026-09-25 の細部調整で英語 UI から置き換え）。カード名・ヒーロー名・ミニオン名は HDT が持つ日本語カード定義
（`%APPDATA%\HearthstoneDeckTracker\CardDefs\CardDefs.jaJP.xml`）から `cards.py` が引き、種族・キーワード・勝敗などの語は `labels.py` で訳す。
ヒーローはスキン名ではなく元ヒーロー名で集計・表示する（例: 「弾嵐のアラキア」→「アラキア」。ゲーム詳細ではスキン名も併記）。
`summarize` / `stats` の Markdown（AI 入力）は見出しを英語のままにし、カード名だけ日本語になる。

### 共通サイドバー
- 期間（プリセット: 今日 / 直近 7 日 / 直近 30 日 / 今シーズン / 全期間、または日付範囲）
- ヒーロー（複数選択）
- incomplete を含める（既定 OFF）
- 再読み込みボタン、最終読み込み時刻、対象ゲーム数

### ページ
| ページ | 内容 |
|---|---|
| 1. 概要 | KPI カード、MMR 推移、順位分布、直近 10 ゲーム。§2 の 1〜4 に相当 |
| 2. ヒーロー | ヒーロー別成績表（ソート可）。行を選ぶとそのヒーローの順位分布・ティア到達ターン・最終盤面の傾向を表示 |
| 2b. 種族 | §1.1 の 4 節: 出現した種族と成績（出現 vs 使用）、最終盤面の主軸種族と順位（固めたターン・方針転換）、ゲーム内の主軸種族の推移（タイムライン、フェーズ別の表、固めたターン / 方針転換 × 順位の散布図、序盤→最終の遷移）、種族の相性（ヒートマップ、相手主軸別成績） |
| 3. プレイ傾向 | ティア到達ターン、ターン帯別戦闘勝率、HP 推移、リロール数と順位（Q3〜Q5） |
| 4. 対戦相手 | 相手ヒーロー別戦闘成績、負け戦闘の相手盤面の種族分布（Q6） |
| 5. ゲーム一覧 | 全ゲームの表（日時、ヒーロー、順位、MMR Δ、最終ティア、ターン数）。行選択で 6 へ |
| 6. ゲーム詳細 | 1 ゲームのヘッダー（§4 と同じ情報）、HP/ティアのターン推移グラフ、主軸種族の推移（T1〜4 メカ → T5〜 アンデッド のような 1 行）、ターンを選ぶとその時の自盤面と相手盤面をカード風に並べて表示、戦闘結果、行動集計。「AI 分析用に要約をコピー」ボタン |

### セッション振り返りの使い方（想定）
その日のプレイ後に「今日」フィルタで概要ページを開き、順位が悪かったゲームをゲーム一覧から選んで詳細を見る。
気になったゲームは要約をコピーして Claude に渡す。

## 4. 1 ゲーム要約（`hsbg summarize`）の形式

AI 入力用。1 ゲームを 1〜2 千トークン程度に収める。

```markdown
# Game 2026-09-15 21:30 — Hero: <name> — Placement: 5/8 — MMR 6120 → 6098 (-22)
Anomaly: <name or none> / Trinkets: <...> / Duration: 27m / Turns: 12

## Lobby
<hero list with eliminated_turn / placement>

## Turn-by-turn
| T | Tier | HP | Gold spent | Buys/Sells/Rerolls/TierUp | Opponent | Result | Dmg | Board (end of shop) |
|---|------|----|------------|---------------------------|----------|--------|-----|---------------------|
| 1 | 1 | 30+5 | 3 | 1/0/0/0 | HeroX | win | +4 | Minion A 3/3 |
...

## Key moments (auto-detected)
- T4: tier up to 3 (early relative to your median T5)
- T7: lost combat, took 12 (largest single hit)
- T9: 3 rerolls, no buy
- T12: eliminated by HeroY (board: ...)

## Final board
<7 minions with stats/keywords>
```

「Key moments」は `metrics.py` のルール（自分の過去中央値との比較、最大被ダメ、リロール多用ターン等）で機械的に抽出する。
AI に渡す前に人間が読んでも意味が分かることを重視する。

## 5. AI 分析プロンプトの設計方針

- **根拠の強制**: 「必ずターン番号と数値を引用して述べる」を指示。ログにない情報（相手の手札等）を推測で断定させない
- **視点を分ける**: (a) ティア戦略 (b) 経済（ゴールド使途） (c) 盤面構築 (d) 戦闘のマッチアップ の 4 視点で評価させる
- **仮説として出す**: 「敗因の仮説を確度順に 3 つ」。断定させない
- **傾向分析は統計を先に渡す**: `metrics.py` の数値表を与えてから解釈させる（LLM に集計させない）
- **比較対象**: 自分の過去中央値（`hsbg summarize` の Key moments、`hsbg stats` の表）を渡すと「自分にとって早い/遅い」が言える
- **保存と振り返り**: 分析結果はワークスペースの分析フォルダ（`hsbg config` の analysis_dir）に Markdown で保存する。次の分析では直近の「次に試すこと」を読み、実行できたか・効いたかを `Follow-up on previous advice` で振り返る
- **累積サマリー**: 傾向分析が読む過去ファイルは最新の `trend-*.md` 1 件だけなので、各トレンド分析の末尾に `## Standing summary`（確立したパターン + レコメンド台帳）を必ず置き、前回分を引き継いで更新する。最新 1 件だけで分析の下地が分かる状態を保つ。プレイヤーが過去ファイルを指定する必要はない

## 6. Claude Code スキルの骨子

**2026-10-31 から**（docs/architecture.md §5）: スキルは `analysis/hsbg/templates/skills/` に置き、`hsbg init` / `hsbg skills update` が利用者のワークスペースの
`.claude/skills/` に複製する。利用者はワークスペースで Claude Code を起動して分析する。スキルは汎用で、利用者ごとの目標はワークスペースの `profile.md`、
分析の筋はレンズ（`lenses/<名前>/lens.md` と表）が持つ。

- `hsbg-analysis` — 1 ゲーム / 傾向の分析と保存。`analyze-game.md`（観点 a〜d + 各レンズのゲーム用チェック）、`analyze-trend.md`（Q1〜Q7 + 各レンズの問い、
  Standing summary にレンズごとのリスト、`## Proposed lens changes`）、`log-caveats.md`（ログの版ごとの注意）を同じフォルダに持つ
- `hsbg-lens` — レンズを利用者と相談して作る・直す・引退させる（`hsbg lens new / check`）
- `hsbg-setup` — 初回の設定確認と、目標のインタビュー → `profile.md`

以下は 2026-09-25 の当初の骨子（記録として残す。当時はリポジトリの `.claude/skills/hsbg-analysis/` と `analysis/prompts/` にあった）:

```markdown
---
name: hsbg-analysis
description: Analyze Hearthstone Battlegrounds game logs in Documents\HSBG-Logs using the hsbg CLI. Use when the user asks about their BG results, a specific game, hero performance, or trends.
---
1. Locate logs: default %USERPROFILE%\Documents\HSBG-Logs. "latest game" = newest *.json with status complete.
2. For one game: run `uv run hsbg summarize <path>` (cwd: analysis/), then apply prompts/analyze-game.md.
3. For trends: run `uv run hsbg export --format csv --last N` and `uv run hsbg report --last N`; apply prompts/analyze-trend.md.
4. Always cite turn numbers and values from the summary. Never invent information not in the log.
5. At the end, mention the HTML report path, and that `uv run hsbg serve` opens the interactive dashboard.
```

## 7. 将来の拡張
- ダッシュボードから Claude API を呼んで 1 ゲーム分析を画面内に表示（API キーの扱いを別途設計）
- Tier7 のメタ統計（ヒーロー tier、平均順位）を手動転記した CSV を `analysis/reference/` に置き、自分の成績との差分を出す
- Bob's Buddy 予測と実結果の乖離（「勝率 70% の戦闘で負けた回数」）を指標化
- 最終盤面のクラスタリング（種族タイプ + キーワード構成）
- 種族の組み合わせ（出現した 5 種の組）ごとの成績、ヒーロー × 種族の相性（サンプルが 50 ゲームを超えてから）
