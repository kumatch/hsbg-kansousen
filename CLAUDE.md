# CLAUDE.md — hsbg-kansousen

Claude Code がこのリポジトリ（hsbg 本体）の開発セッションで読む規約です。詳細は `docs/`。ここには「毎回守ること」だけを書きます。
（自分のゲームを分析するときは、このリポジトリではなく `hsbg init` で作ったワークスペースで Claude Code を起動します。）

## このリポジトリは何か

HDT プラグイン hdt-plugin-hsbg-kansousen（別リポジトリ）が書いた BG のゲームログを読み、集計・可視化・AI 分析をする道具（Python パッケージ `hsbg`）。
利用者ごとの目標・分析の筋・ゲーム知識は、各自の private なワークスペース（`profile.md`、`lenses/`、`knowledge/`）が持つ。
**このリポジトリには、特定のプレイヤーの目標・分析の筋・戦績・結論を入れない**（雛形と汎用の部品だけ）。

## 必ず読むドキュメント

- `docs/architecture.md` — 設計（層、設定、ワークスペース、レンズ、スキル）
- `docs/log-schema.md` — ログ仕様（プラグインのリポジトリが正本。`hsbg/game-log.schema.json` はそのコピー）
- `docs/lenses.md` — レンズの公開 API（`hsbg.lens`）
- `TASKS.md` — 今やるべきタスク

## 構成

```
pyproject.toml, uv.lock, .streamlit/config.toml
hsbg/
├── loader, normalize, metrics, charts, report, summarize, markdown（stats）, cache, cli
├── cards（HDT の CardDefs からカード名とスキン → 元ヒーロー）, labels（種族・キーワード等の日本語）, powerlog
├── config（フォルダと言語: CLI > 環境変数 > ワークスペースの hsbg.toml > 既定）
├── lens（レンズのコードが使う公開 API）, lenses（ワークスペースの lenses/ の発見・実行）
├── game-log.schema.json（プラグインのリポジトリの schema/ のコピー）
├── dashboard/（app, data, filters, components, views/）
└── templates/
    ├── workspace/（hsbg init: hsbg.toml, CLAUDE.md, README, lenses/README, knowledge/ の雛形と tools/pool.py）
    ├── lens/（hsbg lens new）
    └── skills/（Claude Code スキル hsbg-analysis（+ analyze-game / analyze-trend / log-caveats）・hsbg-lens・hsbg-setup。
                 hsbg init / hsbg skills update がワークスペースの .claude/skills/ に複製する）
tests/（fixtures/ は scripts/anonymize_log.py で匿名化したログと小さな CardDefs）
scripts/（start-dashboard.ps1, anonymize_log.py, check_private.py）
```

## コーディング規約

- Python 3.12、パッケージ管理は `uv`。`ruff` でフォーマット・lint。型ヒント必須
- 入力は docs/log-schema.md の JSON。スキーマ違反は警告して読み飛ばす（落とさない）。設定やレンズの誤りも警告にして続ける
- pandas DataFrame への正規化は `normalize.py` の 1 か所
- **集計は `metrics.py`、図は `charts.py` にだけ書く**。`report.py`（静的 HTML）と `dashboard/`（Streamlit）は呼ぶだけの表示層。
  利用者のレンズ（ワークスペースの `lenses/<名前>/metrics.py`）も同じで、`hsbg.lens` だけを import して DataFrame を返し、図は `charts.lens_figure` が描く
- **`hsbg.lens` は公開 API**。変えるときは互換を保つか `LENS_API` を上げる（古いレンズには警告を出し、落とさない）
- ダッシュボードは `127.0.0.1` にのみ bind し、ログファイルを読むだけで書き換えない。外部へ送信しない
- 表示は日本語（ダッシュボード、静的レポート、グラフ）。カード名は `cards.py` が HDT の `CardDefs.<locale>.xml` から引く（無ければログの英語名）。
  `summarize` / `stats`（AI 入力）の見出しは英語のまま
- テストは `tests/fixtures/carddefs/` の小さな CardDefs を使う（`conftest.py` が環境変数を設定。実機の HDT フォルダやワークスペースには依存しない）
- スキルやワークスペースの雛形（`hsbg/templates/`）に、特定の人のパス・戦績・分析の筋を書かない（`tests/test_config.py` が検査する）
- テキストは BOM なし UTF-8、改行 LF。`.ps1` は BOM 付き UTF-8（Windows PowerShell 5.1 が日本語を読めるように）
- Markdown の編集は Edit / Write ツールで（Bash の Python ヒアドキュメントにバックスラッシュ付きのパスを書くと制御文字に化けることがある）

## 検証コマンド（変更後は必ず緑にする）

- `uv run ruff format .; uv run ruff check .; uv run pytest -q`
- ダッシュボード（`hsbg serve`）起動中は `.venv\Scripts\hsbg.exe` がロックされ `uv sync` が失敗する。その間は `uv run --no-sync ...`
- 公開前: `python scripts\check_private.py`（個人の情報が入っていないか。deny list は各自がリポジトリの外に置く）
- スキルを変えたら、手元のワークスペースで `hsbg skills update` して実際に分析を 1 回試す

## 作業の進め方

- `TASKS.md` の順に進める。コミットはユーザーの許可を得てから
- ログ仕様に関わる変更は、先にプラグインのリポジトリで docs/log-schema.md と schema を変えてから、こちらのコピーと読み込みを合わせる

## やらないこと

- データベースの導入（ファイルシステムのみ）
- 外部サーバへのアップロード、外部公開される Web ダッシュボード
- 利用者の目標や分析の筋をこのリポジトリのコードに固定すること（それはワークスペースの profile.md とレンズの役目）
