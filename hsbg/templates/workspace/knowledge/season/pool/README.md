# season/pool/

CardDefs から生成したミニオンプールのスナップショットを置く。**手で編集しない**（作り直すと上書きされる）。
生成スクリプトは `tools/pool.py`（Python 3.12、標準ライブラリのみ）。

**言語**: 英語（`CardDefs.base.xml`）は常に出す。HDT は Hearthstone クライアントの言語のカードデータ（日本語なら `CardDefs.jaJP.xml`）も
取得するので、それがあればその言語の名前と効果も出す（既定はフォルダにある言語版。`--locale jaJP` / `--locale enUS`（英語だけ）で選べる）。
以下は日本語クライアントの例（キーの `ja` / `jaJP` は言語によって変わる）。日時は PC のタイムゾーンで書く。

ミニオンの一覧・Tier・数値・効果テキストは、手書きのファイルに書き写さずにここのスナップショットへリンクする。
スナップショット同士の差分がパッチ記録の裏付けになる。

## ファイル

- `<日付>_build<build>.md` — 人が読む表（Tier ごと）
- `<日付>_build<build>.json` — 機械可読。分析（hsbg-analysis スキル）はこちらを読む
- 日付は CardDefs の更新日（base と言語版の新しい方）。生成した日ではない
- base と言語版の build が違うときは `<日付>_build<base>_ja<jaJP>` になる（英語だけなら付かない）

先頭（JSON は `meta`）に次を書く:

| 項目 | JSON のキー | 内容 |
|---|---|---|
| build | `build_base` / `build_jaJP` | CardDefs のルート要素の `build` 属性。数値・英語は base、日本語は jaJP から取る。英語だけなら `build_base` だけ |
| CardDefs の更新日時 | `carddefs_base_mtime` / `carddefs_jaJP_mtime` | ファイルの更新日時。HDT が取り直した時刻で、パッチの適用時刻ではない |
| 生成日時 | `generated_at` | |
| 対応するパッチ | `patch` / `patch_rule` | 既定は推定: base の更新日以前に適用された最新の `patches/` のファイル。`--patch` で指定もできる |
| 警告 | `warnings` | build の不一致、パッチ記録との日付の開き、同日の適用など。**警告があれば「対応するパッチ」を鵜呑みにしない** |

## 列（JSON のキー）

| 列 | キー | 出どころ |
|---|---|---|
| CardID | `card_id`（`dbf_id` も） | `Entity` の `CardID` / `ID` |
| 日本語名 / 英語名 | `name_ja` / `name_en` | `CARDNAME`（jaJP / enUS）。英語だけなら `name_en` だけ |
| Tier | `tier` | `TECH_LEVEL` |
| 種族 | `races`（HearthDb の enum 名）/ `races_ja`（日本語のときだけ） | `CARDRACE` と、2 つ目の種族のタグ（下記） |
| 攻/体 | `attack` / `health` | `ATK` / `HEALTH` |
| 異形 | `aberration` | `BACON_SUBSET_ABERRATION`=1 |
| デュオ専用 | `duos_only` | `IS_BACON_DUOS_EXCLUSIVE`=1 |
| 効果 | `text_ja` / `text_ja_alt`（`text_en` / `text_en_alt` は JSON のみ） | `CARDTEXT`。変換規則は下記 |
| 金色版 | `golden_card_id` | `BACON_TRIPLE_UPGRADE_MINION_ID`（dbf ID）を CardID に引いたもの |

並びは Tier → 種族 → CardID。

### 種族

- `CARDRACE` の数値 ↔ 名前は HearthDb の `HearthDb.Enums.Race`。2 つ目の種族は CARDRACE ではなく種族ごとのタグ（例: enumID 2523 = ドラゴン）が 1 になっていて、
  その対応は `HearthDb.Enums.RaceUtils.TagRaceMap`。どちらも HearthDb 37.0.0（HDT 1.59.3 同梱の `HearthDb.dll`）から 2026-10-17 に読んで `tools/pool.py` に転記した。
  新しい種族が出たら `RACE_ENUM` / `TAG_RACE` に足す（未知の値は `RACE_<n>` と警告になる）
- `ALL`（26）は「全種族」。種族なしは空（表では「なし」）
- 日本語の種族名は hsbg の `labels.py` に揃えた。クライアントの表記との照合は要確認。ほかの言語では表に enum 名を出す
- 言語の違うスナップショット同士の `diff` は英語の名前・効果と enum 名の種族だけで比べる

### 効果テキストの変換規則

- `[x]`（改行の指示）、`<b>` `<i>` を消す。日本語は改行と `_`（字下げ用の空白）を消し、英語は空白にする
- `{n}` は `TAG_SCRIPT_DATA_NUM_<n+1>` の値に置き換える。タグが無いときは 0（ゲームの既定値）。
  「あと{0}ゴールド！」のような残り回数は、試合中の値ではなく CardDefs の初期値になる
- `A@B` は状態で切り替わる 2 つの文。A を `text_*`、B を `text_*_alt` に入れる（表では「〔別表示: …〕」）。
  区切りでない単独の `@`（「グレード@の」）は数値の差し込みで、`TAG_SCRIPT_DATA_NUM_1` で置き換える
- 英語の `|4(turn, turns)` は直前の数で単数・複数を選ぶ

### 注意

- `IS_BACON_POOL_MINION`=1 は「BG のプールに入りうるカード」。ローテーションで外れた種族（2026-10-17 時点のナーガ）も 1 のまま残る。
  そのロビーに出るかは種族の組み合わせで決まるので、このフラグだけでは分からない
- 禁止中のカードはフラグが外れていることがある（例: 優しいランプの精 `BGS_121`。build 255130 で確認）。禁止は `season/current.md` の「禁止」を見る
- CardDefs はパッチより古いことがある（HDT が取り直すまで更新されない）。メタデータの更新日時とパッチの適用日時を比べる

## 使い方

PowerShell で、知識庫のフォルダ（ワークスペースの `knowledge\`。`hsbg config` の knowledge_dir）から実行する。

```powershell
# スナップショットを作る（HDT の CardDefs を読む）
python tools\pool.py snapshot

# 対応するパッチを指定して作る（推定が外れているとき）
python tools\pool.py snapshot --patch patches/2026-10-02_36.6.3.md

# season\pool の最新 2 つを比べる。--refs で手書きの .md のうち差分のカードに触れている行も出す
python tools\pool.py diff --refs -o $env:TEMP\pool-diff.md

# ファイルを指定して比べる
python tools\pool.py diff season\pool\<古い方>.json season\pool\<新しい方>.json
```

`diff` が出すもの: 追加・削除されたミニオン、既存のミニオンの Tier・攻/体・種族・異形・デュオ専用・効果テキスト（日本語・英語、別表示も）・名前・金色版の変更。
同じ build を作り直すと `generated_at` だけが変わる。

## パッチが来たときの手順

1. HDT を起動して CardDefs を更新させる。`Get-ChildItem "$env:APPDATA\HearthstoneDeckTracker\CardDefs"` で更新日時がパッチの適用より後か確かめる
   （前ならまだ作らない）
2. `patches/` にパッチの記録を作る（`patches/README.md`）。先に作っておくと、スナップショットの「対応するパッチ」がそのファイルになる
3. 作り直す: `python tools\pool.py snapshot`。警告を読む
4. 前回と比べる: `python tools\pool.py diff --refs -o $env:TEMP\pool-diff.md`
   - 差分をパッチノートと突き合わせる。一致・不一致をパッチ記録の「CardDefs との照合」に書く（食い違いはパッチノートが正。`CLAUDE.md`）
   - ノートに無い変更（無告知の変更、CardDefs 側の都合）も記録に書く
5. 差分のカードに触れている手書きの記述（`--refs` の「今を表す手書きの記述」。`season/current.md`、`basics/` など）に
   「要再確認（<バージョン>）」を付ける。例: `要再確認（37.0）`。確かめ直したら外し、確認したビルド / パッチを書き換える。
   `patches/` の過去の記録は書き換えない
6. `season/current.md` の「ミニオンプール」のリンクを新しいスナップショットに替える
7. コミットはパッチの記録と同じ `patch: <バージョン>` に入れてよい（ユーザーの許可を得てから）

※ 例の値（ナーガ、優しいランプの精、build 255130、HearthDb 37.0.0 など）は、このツールを作った 2026-10 時点の確認結果。今のシーズンの事実は自分の `season/` と `patches/` に記録する。
