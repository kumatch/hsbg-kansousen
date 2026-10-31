# hsbg-kansousen

Hearthstone Battlegrounds（BG）の自分のゲームを、AI エージェント（Claude Code）と一緒に振り返る **感想戦** の道具です。
HDT プラグイン [hdt-plugin-hsbg-kansousen](https://github.com/kumatch/hdt-plugin-hsbg-kansousen) が 1 ゲームごとに保存した記録を読み、
集計（`hsbg` コマンド）、ローカルのダッシュボード、AI による分析をします。何をどう分析するかは利用者ごとに違うので、
**自分の目標と分析の筋（レンズ）を AI と相談しながら作っていく** 形になっています。

> English: analysis tools for your own Hearthstone Battlegrounds games — CLI tables, a local dashboard
> and Claude Code skills — reading the logs of hdt-plugin-hsbg-kansousen. You keep your goals,
> your analysis angles ("lenses") and your game knowledge in your own private workspace.

- 動作環境: Windows（プラグインと同じ PC）、Python 3.12、[uv](https://docs.astral.sh/uv/)、AI 分析には [Claude Code](https://claude.com/claude-code)
- ログは読むだけで書き換えません。外部へは何も送りません（ダッシュボードは 127.0.0.1 だけで開きます）
- 非公式のファンメイドツールです。Blizzard Entertainment、HearthSim とは関係ありません

## しくみ

```
hdt-plugin-hsbg-kansousen ──書く──▶ ログのフォルダ（Documents\HSBG-Logs\YYYY\MM\*.json）
                                          │ 読む
                                          ▼
        hsbg（このリポジトリ）: hsbg stats / summarize / report / serve、Claude Code のスキル
                                          ▲ 読む                     │ 書く
                                          │                          ▼
        あなたのワークスペース（private）: hsbg.toml, profile.md, lenses/, knowledge/, analysis/
```

| ワークスペースの中身 | 役割 |
|---|---|
| `profile.md` | あなたの目標と優先度（例: 「1 位より 5〜8 位を避けたい」）。AI が分析のたびに最初に読む |
| `lenses/` | 毎回見たい分析の筋。AI への指示（`lens.md`）と、必要なら表を作るコード（`metrics.py`）。`hsbg stats` とダッシュボードの「マイ分析」に出る |
| `knowledge/` | ゲームそのものの事実（ルールの前提、シーズン、パッチ）。あなた専用で、他の人とは共有しない。パッチノートを AI に渡して育てる |
| `analysis/` | 保存された AI の分析。次の分析が前回の「次に試すこと」や傾向のまとめを引き継ぐ |

## はじめかた

1. プラグインを入れて、BG を何ゲームか遊ぶ（[プラグインの README](https://github.com/kumatch/hdt-plugin-hsbg-kansousen)）
2. uv を入れて、`hsbg` をインストールする
   ```powershell
   winget install astral-sh.uv
   uv tool install git+https://github.com/kumatch/hsbg-kansousen --with pytest
   ```
   （`hsbg` が見つからないと言われたら `uv tool update-shell` を実行して、ターミナルを開き直す）
3. ワークスペースを作る（git の private リポジトリにしておくと、分析と知識の履歴が残ります）
   ```powershell
   hsbg init $env:USERPROFILE\hsbg-kansousen-workspace
   cd $env:USERPROFILE\hsbg-kansousen-workspace
   git init
   ```
4. そのフォルダで Claude Code を起動し、「セットアップして」と頼む。ログの場所の確認と、目標の聞き取り（`profile.md` の作成）を AI が進めます
   ```powershell
   claude
   ```
5. あとは「さっきのゲームを分析して」「直近 20 ゲームの傾向を見て」と頼むだけです。分析は `analysis\` に保存されます。
   同じ観点を毎回見たくなったら「この観点をレンズにして」と頼むと、AI が相談しながらレンズを作ります

hsbg を更新したら、`uv tool upgrade hsbg` のあとワークスペースで `hsbg skills update` を実行してください（スキルが新しくなります）。

## 言語

- **カード名・ヒーロー名**: 英語か、**Hearthstone クライアントの言語**のどちらか（HDT がクライアントの言語のカードデータだけを取得するため）。
  `hsbg.toml` の `locale`（既定 `jaJP`、英語は `enUS`）。その言語のデータが無ければ英語になります
- **分析の文章**: 何語でもよい（`profile.md` に書いておく）
- **ダッシュボード・レポートの画面**: 今は日本語だけ

## コマンド

| コマンド | 内容 |
|---|---|
| `hsbg config` | 今有効なフォルダ（ログ、分析、レポート、知識庫、カードデータ）と言語、その出どころ |
| `hsbg validate` | ログの検証と、不完全なゲームの一覧 |
| `hsbg summarize latest` | 1 ゲームの要約（AI の入力） |
| `hsbg stats --last 20` | 集計の表（AI の傾向分析の入力）。最後にあなたのレンズの表 |
| `hsbg report --last 50 --open` | 静的 HTML レポート |
| `hsbg serve` | ローカルダッシュボード（http://127.0.0.1:8501） |
| `hsbg export --format csv` | 正規化したテーブルの書き出し |
| `hsbg init <folder>` | ワークスペースの雛形（既存のファイルは触らない） |
| `hsbg lens list / new <name> / check` | レンズの一覧・雛形の作成・自分のログでの検査 |
| `hsbg skills update` | ワークスペースのスキルを、入っている hsbg のものに更新 |

フォルダや言語は、ワークスペースの `hsbg.toml`（`hsbg init` が全項目をコメントで説明した雛形を書きます）か、環境変数
`HSBG_LOGS` / `HSBG_KNOWLEDGE` / `HSBG_CARDDEFS` / `HSBG_LOCALE` で変えられます。

## 文書

| 文書 | 内容 |
|---|---|
| [docs/architecture.md](docs/architecture.md) | 設計（集計の層、設定、ワークスペース、レンズ、スキル） |
| [docs/lenses.md](docs/lenses.md) | レンズの書き方（`hsbg.lens` の公開 API） |
| [docs/analysis-and-visualization.md](docs/analysis-and-visualization.md) | 指標、ダッシュボードの画面、AI 分析の作法 |
| [docs/log-schema.md](docs/log-schema.md) | ログの仕様（プラグインのリポジトリが正本） |

## 開発

```powershell
git clone https://github.com/kumatch/hsbg-kansousen
cd hsbg-kansousen
uv sync
uv run ruff format .; uv run ruff check .; uv run pytest -q
```

開発中のコードで `hsbg` を使うには `uv tool install --editable . --with pytest`。規約は `CLAUDE.md`。

## ライセンス

MIT（[LICENSE](LICENSE)）。
