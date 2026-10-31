# システム設計（分析）

## 1. 全体像

```
ログのフォルダ（hdt-plugin-hsbg-kansousen が書く。docs/log-schema.md）
        │ 読むだけ
        ▼
┌───────────────────────────────────────────────────────┐
│ hsbg 共通層: loader → normalize → metrics               │  ← 集計はここだけ
│              （+ 利用者のレンズ lenses/<名前>/metrics.py）│
└──────┬──────────────┬──────────────┬──────────────┬─────┘
       ▼              ▼              ▼              ▼
 hsbg summarize   hsbg stats     hsbg report    hsbg serve
 1 ゲームの要約   集計の表       静的 HTML      ローカルダッシュボード
 （AI の入力）    （AI の入力）                 （127.0.0.1）
       └──────┬───────┘
              ▼
   Claude Code のスキル（ワークスペースの .claude/skills/）
   hsbg-analysis / hsbg-lens / hsbg-setup
   ── profile.md と各レンズの lens.md に従って分析し、analysis/ に保存
```

**設計原則**: 集計ロジックは `metrics.py`（と利用者のレンズ）にだけあり、静的レポート・ダッシュボード・要約・`stats` はそれを呼ぶ表示層。
同じ指標が画面によって違う値になることを構造で防ぐ。`tests/test_layering.py` が import の向きを検査する。

## 2. 利用者ごとのもの: ワークスペース

利用者の目標、分析の筋、ゲーム知識、保存した分析は、hsbg 本体ではなく各自の **ワークスペース**（`hsbg init <folder>` で作る。private な git リポジトリを推奨）に置く。
利用者どうしで共有しない（共有すると、そのメンテナンスと、誰かの変更が他の人の分析に波及する依存が生まれる）。

```
<workspace>/
├── hsbg.toml            # 設定（§3）
├── CLAUDE.md            # 「ここは hsbg のワークスペース。profile.md とレンズを読む」
├── profile.md           # 目標・優先度・助言の前に確かめること（hsbg-setup スキルが対話で作る）
├── lenses/<名前>/       # レンズ（§4、docs/lenses.md）
├── knowledge/           # ゲームの事実の資料庫（ルールの前提、シーズン、パッチ）。雛形と tools/pool.py を hsbg init が置く
├── analysis/            # 保存された分析（*_game.md, trend-*.md）
├── reports/, export/    # 作り直せる出力（git に入れない）
└── .claude/skills/      # hsbg のスキルの複製（hsbg skills update で更新。利用者は編集しない）
```

## 3. 設定（`hsbg/config.py`）

各値の優先順位は CLI 引数（`--dir`）> 環境変数 > ワークスペースの `hsbg.toml` > 既定値。ワークスペースは `HSBG_WORKSPACE` か、
カレントフォルダから上に `hsbg.toml` を探して見つける。`hsbg config [--json]` が今有効な値と出どころを出す。

| 項目 | 環境変数 | 既定 |
|---|---|---|
| `logs_dir` | `HSBG_LOGS` | `%USERPROFILE%\Documents\HSBG-Logs`（プラグインの既定の出力先） |
| `analysis_dir` / `reports_dir` / `export_dir` | — | ワークスペースの `analysis\` / `reports\` / `export\`（ワークスペースが無ければログフォルダの下） |
| `lenses_dir` | — | ワークスペースの `lenses\`（ワークスペースが無ければレンズ無し） |
| `knowledge_dir` | `HSBG_KNOWLEDGE` | 無し（`hsbg init` が `knowledge` を書く） |
| `carddefs_dir` | `HSBG_CARDDEFS` | `%APPDATA%\HearthstoneDeckTracker\CardDefs` |
| `locale` | `HSBG_LOCALE` | `jaJP`（カード名の言語。英語 `enUS` か、Hearthstone クライアントの言語） |

`%VAR%` はどの OS でも展開し、`hsbg.toml` の相対パスはワークスペース基準。設定の誤りは警告して既定値を使う（落とさない）。
`hsbg serve` は見つけたワークスペースを `HSBG_WORKSPACE` で Streamlit に渡す。

## 4. レンズ（`hsbg/lens.py`、`hsbg/lenses.py`）

レンズ = 利用者が毎回見たい分析の筋。`lenses/<名前>/` に `lens.toml`（表示名、説明、状態 active / retired、api）、`lens.md`（AI への指示）、
任意の `metrics.py`（`@lens_table` の関数が DataFrame を返す）を置く。

- `hsbg stats` は末尾に有効なレンズの表を `## Lens: <label>` として足す（`--no-lenses` で外す）→ AI はコアの表と同じように読む
- ダッシュボードの「マイ分析」ページに有効なレンズの表とグラフを並べる。ダッシュボードだけの見出し・説明・値の表記（日本語化）を指定できる
- `hsbg lens list | new <name> | check [name]`。check は利用者自身のログで全部の表を実行し、問題を報告し、`test_*.py` を pytest で走らせる
- レンズのコードは `hsbg.lens`（公開 API、`LENS_API`）だけを import する。壊れたレンズは警告や表ごとのエラーになり、他の出力は止めない
- レンズは利用者自身の Python として実行される（ワークスペースにあるものだけを読み込む）

書き方は docs/lenses.md。

## 5. スキル（`hsbg/templates/skills/`）

Claude Code のスキルは hsbg に含め、`hsbg init` / `hsbg skills update` がワークスペースの `.claude/skills/` に複製する。スキルは汎用で、
利用者ごとの目標は `profile.md`、分析の筋はレンズが持つ。

| スキル | 役割 |
|---|---|
| `hsbg-analysis` | 1 ゲーム / 傾向の分析と保存。`analyze-game.md`（観点 a〜d + 各レンズのゲーム用チェック）、`analyze-trend.md`（Q1〜Q7 + 各レンズの問い、Standing summary、`## Proposed lens changes`）、`log-caveats.md`（ログの版ごとの注意）を同じフォルダに持つ。知識庫は読んだ時点のコミットを記録し、次の傾向分析でそこからの変更を見る |
| `hsbg-lens` | レンズを利用者と相談して作る・直す・引退させる |
| `hsbg-setup` | 初回の設定確認と、目標の聞き取り → `profile.md` |

## 6. パッケージの構成

```
hsbg/
├── loader.py      # ログの探索・読み込み・スキーマ検証（schema の major が合わないものは読み飛ばして警告）
├── normalize.py   # JSON → pandas DataFrame（games, turns, combats, board_minions, opponents, discovers, hand, shop_offers, lobby, sells）
├── cards.py       # HDT の CardDefs から、ロケール別カード名と スキン → 元ヒーロー（BACON_SKIN_PARENT_ID）。無ければ英語にフォールバック
├── labels.py      # 種族・キーワード・勝敗・状態の日本語表記（表示層専用）
├── metrics.py     # 順位分布、ヒーロー別成績、ティア到達、戦闘勝率、HP 推移、種族、神祇、序盤の特徴量 など
├── charts.py      # plotly の図（表示層はここだけを呼ぶ）
├── markdown.py    # hsbg stats の Markdown
├── summarize.py   # 1 ゲームの Markdown 要約
├── report.py      # 静的 HTML レポート
├── cache.py       # 正規化テーブルの parquet キャッシュ（ログが多いとき）
├── config.py, lens.py, lenses.py, powerlog.py, cli.py
├── dashboard/     # Streamlit アプリ
└── templates/     # ワークスペース・レンズ・スキルの雛形
```

### 6.1 ローカル Web ダッシュボード

| 項目 | 決定 |
|---|---|
| フレームワーク | Streamlit。分析層が Python / pandas なので同じ関数をそのまま呼べる |
| 起動 | `hsbg serve` が内部で `streamlit run` を呼ぶ。Windows のショートカット用に `scripts/start-dashboard.ps1` |
| ネットワーク | `127.0.0.1` 固定（LAN にも公開しない）。Streamlit の利用統計の送信は無効 |
| データ | 起動時とサイドバーの「再読み込み」でログフォルダを走査。数百ゲームを超えたら parquet キャッシュ。DB は使わない |
| 書き込み | ログを**読むだけ** |
| 表示言語 | 画面は日本語。カード名は `locale` |
| ヒーロー | スキンは元ヒーローにまとめて集計・表示 |

初回起動時に Windows Defender ファイアウォールのダイアログが出たら「キャンセル」でよい（127.0.0.1 のみなので許可不要）。
