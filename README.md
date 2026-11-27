# hsbg-kansousen

Hearthstone Battlegrounds（BG）の自分のゲームを、AI エージェント（Claude Code）と一緒に振り返る **感想戦** の道具です。
記録アプリ [hsbg-kifu](https://github.com/kumatch/hsbg-kifu) が 1 ゲームごとに保存した記録を読み、
集計（`hsbg` コマンド）、ローカルのダッシュボード、AI による分析をします。何をどう分析するかは利用者ごとに違うので、
**自分の目標と分析の筋（レンズ）を AI と相談しながら作っていく** 形になっています。

> English: analysis tools for your own Hearthstone Battlegrounds games — CLI tables, a local dashboard
> and Claude Code skills — reading the game logs written by hsbg-kifu. You keep your goals,
> your analysis angles ("lenses") and your game knowledge in your own private workspace.

- 動作環境: Windows（記録アプリと同じ PC）、AI 分析には Claude（[デスクトップアプリ](https://claude.ai/download)の「コード」タブ、または [Claude Code](https://claude.com/claude-code)）。
  Python 3.12 と [uv](https://docs.astral.sh/uv/) はセットアップで入ります
- ログは読むだけで書き換えません。外部へは何も送りません（ダッシュボードは 127.0.0.1 だけで開きます）
- 非公式のファンメイドツールです。Blizzard Entertainment、HearthSim とは関係ありません

## しくみ

```
hsbg-kifu（記録アプリ）──書く──▶ ログのフォルダ（Documents\HSBG-Logs\YYYY\MM\*.json）
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

Claude に次の文を送ると、Claude がセットアップを進めます（インストール、ワークスペースの作成、記録のフォルダの確認、あなたの目標の聞き取り）。
コマンドは Claude が実行し、あなたは内容を見て許可します。Claude デスクトップアプリと Claude Code（CLI）のどちらでも同じ文です。

> hsbg-kansousen を使い始めたい。https://github.com/kumatch/hsbg-kansousen/blob/main/docs/install.md の手順に従って、このフォルダにセットアップして

どちらの場合も、先に記録アプリ hsbg-kifu を入れて、BG を何ゲームか遊んでおきます（[hsbg-kifu の README](https://github.com/kumatch/hsbg-kifu)。HDT と一緒に使います）。
HDT プラグイン [hdt-plugin-hsbg-kansousen](https://github.com/kumatch/hdt-plugin-hsbg-kansousen) の記録も、同じフォルダにあればそのまま読めます
（プラグインは、HDT がプラグインを廃止する 2026-11-30 以降は動きません）。

### Claude デスクトップアプリを使う

ターミナルの操作は要りません。

1. [Claude デスクトップアプリ](https://claude.ai/download)を入れる（「コード」タブを使うので、Claude の Pro 以上のプランが要ります）
2. ワークスペース（あなた専用の分析のフォルダ）にする空のフォルダを作る（例: 「ドキュメント」の中の `hsbg-workspace`）
3. アプリの「コード」タブで、そのフォルダを選んでセッションを始める（フォルダを信頼するかを聞かれたら、信頼する）
4. 上の文をそのままコピーして送る。Claude の説明を読み、許可を求められたら内容を見て許可し、質問に答える（答えにくい質問は飛ばしてかまいません）
5. 終わったら、アプリを一度終了して開き直す
6. 次からも同じフォルダを選んで、「さっきのゲームを分析して」「ダッシュボードを開いて」のように頼む（次の「ワークスペースでの使いかた」）

画面の操作や困ったときのことは [docs/desktop-app.md](docs/desktop-app.md) にあります。

### Claude Code（CLI）を使う

1. [Claude Code](https://code.claude.com/docs/en/setup) を入れる（Claude の Pro 以上のプラン、または API キーが要ります）
2. ワークスペースにする空のフォルダを作り、そのフォルダでターミナルを開いて `claude` を起動する
   （エクスプローラーでフォルダを右クリック →「ターミナルで開く」。フォルダを信頼するかを聞かれたら、信頼する）
   ```powershell
   mkdir $env:USERPROFILE\hsbg-workspace
   cd $env:USERPROFILE\hsbg-workspace
   claude
   ```
3. 上の文をそのままコピーして送る。Claude の説明を読み、許可を求められたら内容を見て許可し、質問に答える
4. 終わったら、ターミナルを一度閉じて開き直す
5. 次からも同じフォルダで `claude` を起動して頼む（次の「ワークスペースでの使いかた」）

Claude が実行するコマンドは、すべて [docs/install.md](docs/install.md) に書いてあります。Claude に任せずに自分で入れるときも、この手順書のコマンドを順に実行します。

hsbg の更新は、どちらの場合も「hsbg を更新して」と頼みます（手順は docs/install.md の「更新するとき」）。

### 記録アプリと hsbg の版

記録アプリ（HDT プラグイン、またはその後継の [hsbg-kifu](https://github.com/kumatch/hsbg-kifu)）を新しくしたら、hsbg も対応する版以降にしてください。
対応はログの版（`schema_version`）で決まります。

| hsbg | すべての項目を読めるログ | 対応する記録アプリ |
|---|---|---|
| [0.5.0](https://github.com/kumatch/hsbg-kansousen/releases/tag/v0.5.0) | schema 1.11.0 まで | hsbg-kifu [0.3.0](https://github.com/kumatch/hsbg-kifu/releases/tag/v0.3.0) まで（すべての選択肢と候補） |
| [0.4.0](https://github.com/kumatch/hsbg-kansousen/releases/tag/v0.4.0) | schema 1.10.0 まで | hsbg-kifu [0.2.0](https://github.com/kumatch/hsbg-kifu/releases/tag/v0.2.0) まで（アイスブロック） |
| [0.3.0](https://github.com/kumatch/hsbg-kansousen/releases/tag/v0.3.0) | schema 1.9.0 まで | プラグイン [0.14.0](https://github.com/kumatch/hdt-plugin-hsbg-kansousen/releases/tag/v0.14.0) まで、hsbg-kifu [0.1.0](https://github.com/kumatch/hsbg-kifu/releases/tag/v0.1.0) |
| [0.2.0](https://github.com/kumatch/hsbg-kansousen/releases/tag/v0.2.0) | schema 1.8.0 まで | プラグイン [0.13.0](https://github.com/kumatch/hdt-plugin-hsbg-kansousen/releases/tag/v0.13.0) まで |
| [0.1.0](https://github.com/kumatch/hsbg-kansousen/releases/tag/v0.1.0) | schema 1.6.2 まで | プラグイン [0.11.0](https://github.com/kumatch/hdt-plugin-hsbg-kansousen/releases/tag/v0.11.0) まで |

- hsbg より新しい記録アプリのログ（同じ schema 1.x）も、0.2.0 以降なら読み込みます。新しい項目は使わず、
  `hsbg validate` とダッシュボードに「hsbg を更新してください」と出ます（0.1.0 はそのログを読み飛ばします）
- 古い記録アプリのログは、新しい hsbg でもそのまま読めます（無い項目は空欄。いくつかは `hsbg backfill-*` で power.log から補えます）
- 版を指定して入れるときは、[docs/install.md](docs/install.md) の `uv tool install` の URL の版（`v<版>.zip` の部分）を変えます

## ワークスペースでの使いかた

いつも **ワークスペースのフォルダで** Claude を開いて、ふつうの言葉で頼みます（`hsbg` のコマンドは AI が実行します）。
デスクトップアプリなら「コード」タブでワークスペースのフォルダを選んでセッションを始め、ターミナルならそのフォルダで `claude` を起動します。
以下の「」は頼み方の例です。言い回しは自由です。

### ゲームの後に: 1 ゲームの分析

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
4. AI は変更を `knowledge\CHANGELOG.md` にも 1 行ずつ記録します。分析は知識庫をどの時点まで読んだかを記録し、次の傾向分析でそこからの変更を確かめます

記述の誤りに気づいたら「knowledge の 37.0 の適用日時が間違っていた。正しくは〜」と頼みます（直したことが `fix:` として記録され、次の分析が過去の結論を見直します）。
知識庫はあなた専用で、他の人と共有しません。規約は `knowledge\CLAUDE.md`。

### ダッシュボード: 普段の振り返りに

Claude に「ダッシュボードを開いて」と頼みます（終わったら「ダッシュボードを止めて」）。自分で起動するときは、次のとおりです。

```powershell
cd $env:USERPROFILE\hsbg-kansousen-workspace
hsbg serve
```

ブラウザで http://127.0.0.1:8501 が開きます（自分の PC の中だけで動きます。ターミナルで起動したときの終了は Ctrl+C）。
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

（hsbg のソースを手元に置いている場合は `scripts\start-dashboard.ps1 -Workspace <ワークスペース>` も使えます。）
静的な HTML レポート（`hsbg report --last 50 --open`）は、同じグラフを 1 枚のファイルにまとめたものです。

### 分析の履歴を残す

特別な準備は要りません。分析は `analysis\` にファイルとして溜まり、知識庫の変更は `knowledge\CHANGELOG.md` に記録されて、次の分析に引き継がれます。
消えると困るものなので、ときどきワークスペースのフォルダごとバックアップを取ってください（`reports\` と `export\` は作り直せるので要りません）。
ワークスペースにはあなたの戦績と分析が入っているので、他の人と共有する場所には置かないでください。

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
| [docs/desktop-app.md](docs/desktop-app.md) | Claude デスクトップアプリでの使いかた（はじめかた、頼み方、困ったとき） |
| [docs/install.md](docs/install.md) | セットアップの手順（Claude が実行する。何が行われるかを人が確かめるのにも） |
| [docs/architecture.md](docs/architecture.md) | 設計（集計の層、設定、ワークスペース、レンズ、スキル） |
| [docs/lenses.md](docs/lenses.md) | レンズの書き方（`hsbg.lens` の公開 API） |
| [docs/analysis-and-visualization.md](docs/analysis-and-visualization.md) | 指標、ダッシュボードの画面、AI 分析の作法 |
| [docs/log-schema.md](docs/log-schema.md) | ログの仕様（hsbg-kifu のリポジトリが正本） |

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
