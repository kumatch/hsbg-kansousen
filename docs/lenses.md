# レンズの書き方

レンズ = 毎回見たい「分析の筋」。ふつうは AI（`hsbg-lens` スキル）と相談して作りますが、ここではその中身と公開 API をまとめます。

```
<workspace>/lenses/<名前>/      # 名前は小文字・数字・- ・_
├── lens.toml    # label, description, status (active / retired), api
├── lens.md      # AI への指示（分析スキルが毎回読む）
├── metrics.py   # 任意: @lens_table の関数（表を返す）。hsbg.lens だけを import する
└── test_*.py    # 任意: hsbg lens check が pytest で走らせる
```

- 作る: `hsbg lens new <名前>`（動く例が入った雛形）
- 確かめる: `hsbg lens check [名前]`（自分のログで全部の表を動かし、問題を出す。終了コード 1 = 問題あり）
- 使わなくなったら消さずに `status = "retired"`（記録として残り、表示されなくなる）

## lens.toml

```toml
label = "下位回避"                 # stats の見出しとダッシュボードに出る名前
description = "..."               # 説明（stats とダッシュボード）
status = "active"                 # active / retired
api = 1                           # 書いた時点の hsbg.lens.LENS_API
```

## lens.md

分析スキルが毎回読む指示です。決まった書式は無いですが、次を書いておくと分析が安定します。

- **問い**: このレンズで何を確かめるか（1〜3 個）
- **表**: どの表をどう読むか
- **判断の基準**: どれだけの差・ゲーム数で結論にするか、原因と症状の区別、運と選択の区別
- **持ち越すリスト**: 傾向分析の Standing summary に毎回持ち越すリストの名前と書式（例: `candidate` / `confirmed` / `dropped`）
- **1 ゲームの分析で**: 1 ゲームのときに確かめること
- **表の変え方**: 表は分析の提案（`## Proposed lens changes`）に利用者が同意したときだけ変える

## metrics.py（公開 API `hsbg.lens`）

```python
import pandas as pd

from hsbg.lens import Tables, compare_groups, early_game_features, lens_table


@lens_table(
    "top4_vs_bottom4",  # 名前（レンズ内で一意）
    "Top 4 vs bottom 4: early game",  # label: stats の見出し（AI が読む。英語で短く）
    chart="bar",
    x="feature",
    y="diff",  # グラフ: table / bar / barh / line
    description="diff = bottom-4 median − top-4 median",
    title="上位 4 と下位 4: 序盤の中央値",  # ダッシュボードの見出し（無ければ label）
    note="差 = 下位 − 上位",  # ダッシュボードの説明（無ければ description）
    columns={"feature": "項目", "diff": "差"},  # ダッシュボードの列名
)
def top4_vs_bottom4(t: Tables) -> pd.DataFrame:
    return compare_groups(early_game_features(t), {"tier4_turn": "Tier 4 turn", "hp_t8": "HP T8"})
```

- 関数は、今のフィルタのゲームの正規化テーブル `t` を受け取って DataFrame を返す。空のときは列だけの DataFrame を返す
- **`hsbg stats`（AI の入力）には返した DataFrame がそのまま出る**。列名・値・label・description は英語で短く
- **ダッシュボードは利用者の言語で**: `title` / `note`、`display`（返した表 → 見せる表。値の日本語化や時刻の書式。数値は数値のまま）、`columns`
- グラフは hsbg が描く。`x` = カテゴリ / ターン、`y` = 値、`color` = 系列を分ける列（任意）。レンズから plotly を呼ばない
- 表示用に丸める（`round(1)` など）。% の列は 0〜100 で返す
- 閾値は名前付きの定数にし、決めた日・そのときの数字・利用者の同意を注釈に残す

### `hsbg.lens` が出すもの（LENS_API 1）

| 名前 | 内容 |
|---|---|
| `Tables` | 正規化テーブル: `games`, `turns`, `combats`, `board_minions`, `opponents`, `discovers`, `hand`, `shop_offers`, `lobby`, `sells`（列は `hsbg export` で見られる。元のフィールドは docs/log-schema.md） |
| `lens_table(...)` | 表の登録（上の例） |
| `early_game_features(t)` | 1 ゲーム 1 行の序盤の特徴量（`placement`, `group`, `tier3_turn`〜`tier5_turn`, `board_t3`, `board_total_t3`, `hp_t6`, `hp_t8`, `board_diff_t8` / `t10`, `losses_t3_7`, `damage_t3_8`, `rerolls_t1_8`, `buys_t1_8`, `sells_t1_8`, `dark_gifts_t1_8`, `unspent_gold_t1_8` など） |
| `compare_groups(features, {列: ラベル})` | 下位 4 と上位 4 の中央値と差、ゲーム数 |
| `placement_group(placement)` | `"top4"` / `"bottom4"` |
| `card_tiers(t)` | 盤面に出たカードのタヴァーンティア（金色版は元のカードに寄せる） |
| `minion_type_name(token)` / `result_name(token)` | 種族名・勝敗の日本語（`display` 用） |
| `apply_filter(t, LogFilter(...))` | 期間・ヒーロー・MMR での絞り込み |
| `CHART_KINDS`, `LENS_API`, `TableSpec`, `table_spec` | 定数と内部表現 |

API を壊す変更をするときは `LENS_API` を上げます。古い / 新しい `api` のレンズには警告が出ます（動かせる範囲で動く）。

## テスト

ロジックが単純な集計でなければ、`test_<名前>.py` に小さな合成ログでテストを書きます（`hsbg lens check` が pytest で走らせる。
`uv tool install ... --with pytest` で入れておく）。

```python
import metrics as lens  # 同じフォルダの metrics.py
from hsbg import normalize


def test_counts() -> None:
    tables = normalize.normalize(
        [{"status": "complete", "game": {...}, "result": {...}, "turns": [...]}]
    )
    assert lens.my_table(tables)["games"].sum() == 1
```
