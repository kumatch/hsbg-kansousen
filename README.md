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
4. **ワークスペースのフォルダで** Claude Code を起動し、セットアップを頼む（以後の分析も、いつもこのフォルダで Claude Code を起動します）
   ```powershell
   cd $env:USERPROFILE\hsbg-kansousen-workspace
   claude
   ```
   Claude Code が開いたら、たとえば次のように頼みます。

   > セットアップして。主に MMR 6000 前後で遊んでいて、1 位を取るより 5〜8 位を減らしたい。分析は日本語で、カード名も日本語がいい

   AI（`hsbg-setup` スキル）が対話で次を進めます。答えにくい質問は飛ばしてかまいません。
   - `hsbg config` / `hsbg validate` で、プラグインのログが見つかるか（保存先を変えている場合は `hsbg.toml` を直す）
   - カード名の言語（`locale`）と、分析の文章の言語
   - 知識庫（`knowledge/`）の用意と、ワークスペースを git で管理すること
   - 目標・優先度・助言の前に確かめてほしいことの聞き取り → `profile.md` を書いて見せる

   `profile.md` は後からいつでも「目標を変えたい。〜」と頼めば直してくれます（直接編集してもよい）。
5. ゲームを遊んだら、同じフォルダで Claude Code を開いて「さっきのゲームを分析して」と頼みます。次の「ワークスペースでの使いかた」を参照

hsbg を更新したら、`uv tool upgrade hsbg` のあとワークスペースで `hsbg skills update` を実行してください（スキルが新しくなります）。

## ワークスペースでの使いかた

いつも **ワークスペースのフォルダで** Claude Code を起動して、ふつうの言葉で頼みます（`hsbg` のコマンドは AI が実行します）。
以下の「」は頼み方の例です。言い回しは自由です。

### ゲームの後に: 1 ゲームの分析

```powershell
cd $env:USERPROFILE\hsbg-kansousen-workspace
claude
```

- 「さっきのゲームを分析して」
- 「昨日の最後のゲームを分析して」「今日 6 位だったゲームを見て」
- 「T7 で Tier 4 に上げたのは早すぎた？」のように、気になった場面を添えてもよい

AI（`hsbg-analysis` スキル）は次の順に進めます。

1. `hsbg summarize` でそのゲームの要約（ターンごとの HP・ティア・ゴールド・盤面・戦闘、ショップの提示、手札）を作る
2. `profile.md`、有効なレンズ、前回までの分析の「次に試すこと」、そのゲームの時点で有効だったパッチ（知識庫）を読む
3. ターン番号と数値を挙げて、敗因・勝因の仮説、前回の助言を守れたか、**次に試すこと（1〜3 個）** を書く
4. `analysis\<開始時刻>_<ゲーム ID>_game.md` に保存し、同じ内容を画面に出す

次のゲームの前に「次に試すこと」を読み返すと効果的です。Hearthstone のクラッシュや切断から再接続したゲームは、
見られなかったターンがあるので、分析に含めるかを AI が確認します。

### 何ゲームか遊んだら: 傾向の分析

- 「前回の傾向分析から後のゲームの傾向を見て」（期間を言わなければ、前回の傾向分析の続きから）
- 「直近 30 ゲームの傾向を見て」「10 月 1 日以降」「MMR 7400 以上のゲームだけで」

`hsbg stats` の集計表（ヒーロー、ティアの到達、ターンごとの戦闘勝率、HP の推移、種族、対戦相手、レンズの表）をもとに、
確立したパターン、助言の台帳（守れたか・効いたか）、次の 10 ゲームで試すことを `analysis\trend-<日時>_....md` に保存します。
最後の **Standing summary** が次の傾向分析に引き継がれるので、分析を重ねるほど結論が積み上がります。
期間の途中にパッチがあれば、AI は知識庫を見て期間をパッチの前後に分けて比べます（次の「知識庫の準備と更新」）。

### 毎回見たい観点ができたら: レンズ

分析を重ねるうちに、同じ観点を毎回確かめたくなったら、レンズにします。

- 「2 連敗した直後に Tier を上げたターンの成績を、毎回の傾向分析で見たい。レンズにして」
- 「T8 の盤面が相手より小さかったゲームの順位を表にしたい」

AI（`hsbg-lens` スキル）が、問い・判断の基準・表の列を相談してから、`lenses\<名前>\` に `lens.md` と表のコードを書き、
`hsbg lens check` で確かめます。以後は傾向分析の表とダッシュボードの「マイ分析」に出ます。分析の最後に AI が「レンズをこう変えては」と
提案することがあり、同意したときだけ変わります。書き方の詳細は [docs/lenses.md](docs/lenses.md)。

### 知識庫の準備と更新（パッチが来たら）

`knowledge\` は、ゲームそのものの事実（シーズンの仕組み、ミニオンのティアと数値、パッチごとの変更）の資料庫です。
分析は、カードの事実を推測せずにここで確かめ、**ゲームがどのパッチの下で遊ばれたか** で期間を分けます。
BG はシーズンの開始やパッチ・ホットフィックスで数値や仕組みがよく変わるので、記録が無いと、変更の前と後のゲームを混ぜて比べてしまいます。

**はじめに**（セットアップの後に一度）: 今のシーズンの仕組みを記録します。

- 「今のシーズンの BG の仕組みを knowledge に記録したい。公式のパッチノートはこれ: <URL>」
- 「HDT のカードデータからミニオンプールのスナップショットを作って」（`knowledge\tools\pool.py`）

**パッチやホットフィックスが来たら**:

1. HDT を一度起動する（HDT がカードデータ `CardDefs` を新しくする）
2. ワークスペースで Claude Code を開いて、パッチノートを渡して記録を頼む
   - 「BG のパッチ 37.2 が来た。パッチノートはこれ: <URL>。knowledge に記録して、ミニオンプールのスナップショットを作り直して前回と比べて」
   - パッチノートの本文を貼り付けて「これを knowledge に記録して」でもよい。ゲーム内で気づいた変更は「ゲーム内の表示で〜が Tier 3 になっていた」と伝える
3. AI が `knowledge\patches\<日付>_<版>.md` を作り、`season\current.md` を更新し、カードデータとの食い違いや、確かめ直しが必要になった記述を挙げます
4. 内容を確かめて「knowledge の変更をコミットして」と頼む（分析は知識庫のどのコミットを読んだかを記録し、次の傾向分析でそこからの変更を確かめるため、
   **コミットまでして完了** です）

記述の誤りに気づいたら「knowledge の 37.0 の適用日時が間違っていた。正しくは〜」と頼みます（直したことが分かるコミットになり、次の分析が過去の結論を見直します）。
知識庫はあなた専用で、他の人と共有しません。規約は `knowledge\CLAUDE.md`。

### ダッシュボード: 普段の振り返りに

```powershell
cd $env:USERPROFILE\hsbg-kansousen-workspace
hsbg serve
```

ブラウザで http://127.0.0.1:8501 が開きます（自分の PC の中だけで動きます。終了はターミナルで Ctrl+C）。
AI の分析が「なぜ」を言葉で考える場所なら、ダッシュボードは数字とグラフを眺めて、自分の状態をつかむ場所です。
左のサイドバーで期間（今日、直近 7 日、直近 30 日、全期間、日付の指定）とヒーローを絞れます。

| ページ | 見られるもの | こんなときに |
|---|---|---|
| 概要 | 平均順位・Top 4 率などの指標、MMR の推移、順位の移動平均、順位の分布、直近のゲーム | 遊んだ日の終わりに、調子を確かめる |
| ヒーロー | ヒーローごとの成績と、そのヒーローのティア到達・最終盤面の種族 | ヒーロー選択で迷ったとき |
| 種族 | 出現した種族と成績、最終盤面の主軸種族と順位、ゲーム内の種族の移り変わり、種族の相性 | どの種族で勝てているか |
| プレイ傾向 | ティア到達ターン、ターンごとの戦闘勝率、上位・下位のゲームの HP の推移、リロールと順位 | 序盤・中盤のどこで崩れているか |
| 対戦相手 | 相手ヒーロー別の戦闘成績、負けた戦闘の相手盤面の種族 | 苦手な相手を知る |
| ゲーム一覧 / ゲーム詳細 | 1 ゲームの HP とティアの推移、ターンごとの自分と相手の盤面・手札、ロビー、注目ポイント | AI の分析を読みながら、その場面の盤面を見返す |
| マイ分析 | あなたのレンズの表とグラフ | レンズで追っている観点を確かめる |

ゲームのログが増えたら、サイドバーの「ログを再読み込み」で読み直します。デスクトップのショートカットから起動したいときは、
ショートカットの「項目の場所」に次を書きます（`uv tool install` で入れた `hsbg` を使う）。

```text
pwsh.exe -NoExit -Command "cd $env:USERPROFILE\hsbg-kansousen-workspace; hsbg serve"
```

（このリポジトリを clone している場合は `scripts\start-dashboard.ps1 -Workspace <ワークスペース>` も使えます。）
静的な HTML レポート（`hsbg report --last 50 --open`）は、同じグラフを 1 枚のファイルにまとめたものです。

### 分析の履歴を残す

ワークスペースを git で管理していれば、「分析と knowledge の変更をコミットして」と頼むだけで履歴が残ります（push は自分で行うか、頼んだときだけ）。
GitHub などに置くなら **private** リポジトリにしてください（あなたの戦績と分析が入っています）。

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
