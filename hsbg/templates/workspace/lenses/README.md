# lenses/

レンズ = 毎回見たい「分析の筋」。1 フォルダ 1 レンズ。

```
lenses/<名前>/
├── lens.toml    # 表示名、説明、状態（active / retired）、api
├── lens.md      # AI への指示: 問い、見る表、判断の基準（分析スキルが毎回読む）
└── metrics.py   # 任意: @lens_table の関数（表を返す）。hsbg.lens だけを import する
```

- 作る: `hsbg lens new <名前>`（例を含む雛形ができる。名前は小文字・数字・`-`・`_`）
- 確かめる: `hsbg lens check`（自分のログで全部の表を動かし、問題を出す）
- 一覧: `hsbg lens list`
- 表は `hsbg stats` の末尾（`## Lens: ...`）とダッシュボードの「マイ分析」に出る
- 使わなくなったレンズは消さずに `status = "retired"` にすると、記録として残り表示されなくなる
- `metrics.py` はあなた自身の Python コードとして実行される。自分で書いた・中身を確かめたコードだけを置く
