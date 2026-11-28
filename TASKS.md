# TASKS.md

今どこにいて、次に何をするか。完了したら `[x]` にし、判明したことは docs に追記する。

## 新しいセッションの始め方（Claude Code 向け）

1. `CLAUDE.md` → この `TASKS.md` → 作業に関係する docs の順に読む
2. 検証コマンド（`CLAUDE.md`）が緑であることを確かめてから始める
3. 作業の区切りで、変更したファイルと推奨するコミットメッセージを報告して止まる。コミットは許可を得てから

## 現在の状態

- hsbg 0.6.0（2026-11-28 リリース。Claude デスクトップアプリから始められるように。0.1.0 はプラグイン 0.11.0 に合わせて `62d7034` にタグを打ってリリース）。読めるログ: schema 1.x（プラグイン 0.2.0 以降と hsbg-kifu）。
  すべての項目を読むのは 1.11.0 まで（`loader.KNOWN_SCHEMA_VERSION`。0.5.0 で上げた）、それより新しい 1.x は既知の項目だけで読む。レンズ API 1
- リポジトリは公開済み（https://github.com/kumatch/hsbg-kansousen）。GitHub Releases に v0.1.0〜v0.6.0 を置いた
- 記録アプリは hsbg-kifu。HDT プラグインは HDT のプラグイン廃止（2026-11-30）で動かなくなるが、その記録は読み続ける

## タスク

- [x] CI（`.github/workflows/ci.yml`）: Windows で ruff + pytest + check_private。プラグインの `schema/game-log.schema.json` と比べる job（取得できなければ警告だけ）
- [x] 甲虫（schema 1.7.0）: turns に `beetle_attack` / `beetle_health` / `beetle_attack_after` / `beetle_health_after`、
      combats に `opponent_beetle_*`（`hsbg export` とレンズから読める）
- [x] この対戦中の強化（schema 1.8.0）: `blood_gem_*` / `tavern_spell_*` / `tavern_minion_*` / `tavern_elemental_*` と `opponent_*` の列。
      過去のゲームは `hsbg backfill-buffs` で power.log から補完（`backfill-beetle` は置き換えた）
- [x] この対戦中の強化を `summarize`（`## This-game buffs (not on the board)` の表。盤面の合計と並べる）とダッシュボードのゲーム詳細
      （強化のグラフ、ターンごとの自分・相手の値、全ターンの表で神祇の列の隣）に出す。プラグイン 0.13.0 の実機確認のゲーム（2026-11-03 22:50）で確認。
      強化は 1 体・1 個あたりの量で盤面の合計より桁が小さいので、グラフは神祇・盤面のグラフとは別にした（同じ軸だと底に張り付く）
- [x] プラグインとの版の食い違い対策: 新しいプラグインのログも既知の項目だけで読み、`hsbg validate` とダッシュボードで更新を勧める。
      版はそろえず、README の対応表とリリースノートで対応を書く（`docs/release.md`）。`hsbg config` に版を出す
- [x] リリース: v0.1.0（プラグイン 0.11.0 に対応）と v0.2.0（0.13.0 に対応）のタグと GitHub Release。その後でプラグイン v0.13.0 をリリースした（2026-11-04）
- [x] 血の宝石の雨（schema 1.9.0）: `blood_gem_barrage_*` と `opponent_blood_gem_barrage_*` の列、summarize とダッシュボードの表示、
      `hsbg backfill-buffs` での補完（power.log から。試しに数えると 65 件。まだ実行していない）
- [x] リリース: v0.3.0（2026-11-06。プラグイン 0.14.0 の実機確認の後、プラグインより先に）
- [x] ログの仕様の正本が hsbg-kifu に移った（2026-11-21。schema 1.9.0 のまま）: CI の `schema` ジョブの比較先、CLAUDE.md、`docs/release.md`、
      README の版の節を hsbg-kifu に向けた。`log-caveats.md` に hsbg-kifu の記録の違い（`shop_offers` がバフ込み、行動の回数が正確）を書いた。
      README の「はじめかた」は hsbg-kifu の最初のリリース（2026-11-22）に合わせて書き換えた
- [x] アイスブロック（schema 1.10.0、hsbg-kifu 0.2.0）: combats の列 `ice_block` / `opponent_ice_block`（`CACHE_FORMAT` 13）、
      要約の戦闘の列の「(my Ice Block)」「(opp. Ice Block)」、Key moments、`log-caveats.md`。保存済みのログを power.log から補う backfill はまだ無い
- [x] リリース: v0.4.0（2026-11-22。schema 1.10.0 まで読む。hsbg-kifu 0.2.0 より先に）
- [x] すべての選択肢（schema 1.11.0、hsbg-kifu 0.3.0）: `choices`（選択肢 1 回ずつ）と `choice_offers`（候補 1 枚ずつ）の表（`CACHE_FORMAT` 14）、
      `discovers` に `source_card_id`、要約の「## Choices」、log-caveats（選択肢の読み方と、hsbg-kifu 0.1.0〜0.2.0 で発見の行が抜けていること）。
      要約では、ヒーローパワーが前に作ったカードによる選択を「Hero power → <カード>」と書き、候補にミニオンがあれば discover、無ければ pick と書き分ける
      （0.3.0 の実機確認のゲイルウィング: 行き先の選択と、着いたときの発見が同じ hero_power で見分けにくかった）
- [x] リリース: v0.5.0（2026-11-23。schema 1.11.0 まで読む。hsbg-kifu 0.3.0 より先に。push は hsbg-kifu の main が先で、CI は最初の実行で緑）
- [x] 古い表記: スキル・雛形の記録アプリを HDT プラグインから hsbg-kifu に（2026-11-28）
- Claude デスクトップアプリ（コードタブ）から使えるようにする。ターミナルを使わない人が「セットアップして」「ダッシュボードを開いて」と頼むだけで使える形。
  中身（hsbg のコマンドとスキル）はターミナル版と同じで、違うのは Claude がコマンドを打つことだけ。アプリ版は git を使わずに完結させる
  - [x] 0. 実機での確認（2026-11-28。結果は「判明したこと」。git が無い PC でアプリが git を求めないかは 5 で）: タグのソース zip での `uv tool install`（git が PATH に無い状態で。`UV_TOOL_DIR` / `UV_TOOL_BIN_DIR` を一時フォルダに向け、
        手元の hsbg に触れない）、インストール直後の PATH、`.claude/launch.json` で `hsbg serve` がアプリのブラウザペインに出るか、
        `.claude/settings.json` の許可ルールの書式（PowerShell）、`hsbg init` で置いたスキルが同じセッションで使えるか
  - [x] 1. git を任意にする（2026-11-28）: README・ワークスペースの README / CLAUDE.md・hsbg-setup・hsbg-lens の「git を勧める」を任意に。
        知識庫に `knowledge/CHANGELOG.md`（変更のたびに日時・種類 patch / fix / season・ファイルを 1 行。git を使う人も書く）。
        分析の `Knowledge:` 行は git があればハッシュ、無ければ CHANGELOG の最後の日時。次の傾向分析は git log / diff か、その日時より後の CHANGELOG の行で変更を見る
  - [x] 2. git の要らないインストール（2026-11-28。README 冒頭に、アプリに送る最初の依頼文。`tests/test_docs.py` が URL の版を検査）: `uv tool install https://github.com/kumatch/hsbg-kansousen/archive/refs/tags/v<版>.zip`。
        AI が上から実行する手順書 `docs/install.md`（uv → hsbg → `hsbg init .` → hsbg-setup へ引き継ぎ → アプリの再起動）。
        `docs/release.md` に「README と install.md の URL の版を上げる」。`git+https` はターミナル版に残す
  - [x] 3. アプリとの連携（2026-11-28。雛形はパッケージの中では `claude/` に置き、`hsbg init` が `.claude/` に写す）: `hsbg init` が `.claude/launch.json`（`hsbg serve --no-open`、autoVerify なし）と `.claude/settings.json`
        （読むだけの hsbg コマンドを許可、ログのフォルダを additionalDirectories）を置く。ワークスペースの CLAUDE.md に「ダッシュボードを開いて / 止めて」
  - [x] 4. 人向けの文書（2026-11-28。README の「はじめかた」をデスクトップアプリと Claude Code（CLI）の 2 つに分け、自分で打つコマンドは install.md に集約）: `docs/desktop-app.md`（アプリの入れ方、フォルダの作り方、コードタブ、承認の読み方、最初の依頼文、ふだんの頼み方、更新、困ったとき）、
        README の入口をアプリ版とターミナル版に分ける、`docs/architecture.md`
  - [x] 5. 通しの確認（2026-11-28。2 回目で通った。結果は「判明したこと」）: git の入っていない別の Windows ユーザーで、アプリだけでインストール → セットアップ → 分析 → ダッシュボードまで通す
  - [x] 6. リリース: v0.6.0（2026-11-28。ログの読み込みは 0.5.0 と同じ）
  - [ ] 7. ターミナル版（README の「Claude Code（CLI）を使う」）も、git の無い別のユーザーで通す
- [ ] 持っているヒーローパワーと時渡り（schema 1.12.0、hsbg-kifu の M10・M11。同じ版で一緒にリリースする）:
  - [x] ヒーローパワー（M10）: `turns` の列 `hero_power_card_id` / `hero_power_name` / `additional_hero_power_card_id` / `additional_hero_power_name`
        （`CACHE_FORMAT` 15）、要約の「## Hero powers」（変わったターンだけ）、log-caveats。要約の選択肢は、後から得たヒーローパワー
        （ゲンの発見、時渡りの「○○の力」、グエンの選んだもの）による選択を「Hero power (X)」と書く（最初のヒーローパワーの別の形 = カード ID が
        最初のもので始まるもの、ゲイルウィングの行き先などは今までどおり「Hero power → X」）
  - [x] 時渡り（M11）: `timewarp_offers` の表（時渡りの候補 1 枚ずつ。値段・買ったか・買った順。`CACHE_FORMAT` 16）、要約の「## Timewarp」、
        選択肢の `timewarp` の表示、log-caveats、`hsbg export` の説明に表の名前を足した
  - [ ] リリース: v0.7.0（hsbg-kifu 0.5.0 より先に。読めるログの版が上がるので minor を上げる）
- [ ] CI を Ubuntu でも（テストに Windows のパスを前提にしたものがあるので、直してから）
- [ ] Issue テンプレート: hsbg の版、`hsbg config` と `hsbg validate` の出力。ログを添えるときは `scripts/anonymize_log.py` を通した `.json` だけ
      （Power.log やワークスペースの分析・profile.md は貼らない）
- [x] 公開: リポジトリを public にした
- [ ] ダッシュボード・レポートの画面の英語化（今は日本語だけ）
- [ ] ワークスペースの雛形の英語版（`hsbg init --lang en` など）
- [ ] Hearthstone クライアントと違う言語のカード名（HDT が取得しない言語の CardDefs を hsbg が取得する。外部通信が増えるので要検討）

## 判明したこと・決めたこと

- 利用者ごとのもの（目標、分析の筋、ゲーム知識、保存した分析）はワークスペースに置き、利用者どうしで共有しない（共有すると、そのメンテナンスと、
  誰かの変更が他の人の分析に波及する依存が生まれるため）。知識庫は使うことを勧め、`hsbg init` が空の雛形を用意する
- git は前提にしない（2026-11-28）。インストール（タグの zip）も、ワークスペースの履歴（分析のファイルと `knowledge/CHANGELOG.md`）も git 無しで完結させ、
  README・案内・雛形では git に触れない（`tests/test_docs.py` が検査）。使うかは利用者に任せ、スキルは、利用者が git で管理していればそれに合わせるだけ
- `uv tool install git+https://...` は git 本体が要る。タグのソース zip（`.../archive/refs/tags/v<版>.zip`）なら git が PATH に無くても入る
  （2026-11-28、uv 0.12.14 で確認）。zip で入れたものは `uv tool upgrade hsbg` が「Nothing to upgrade」になるので、更新は新しい版の URL で
  `uv tool install --force <URL>`。uv のツールの置き場は既定で `%USERPROFILE%\.local\bin`。winget の uv はパッケージのフォルダをユーザーの PATH に足すだけなので、
  入れた直後の同じセッションでは見えない（PATH を読み直すか、アプリを再起動する）
- Claude Code の許可ルールは PowerShell でも Bash と同じ形（`PowerShell(hsbg stats *)`）。プロジェクトの `.claude/settings.json` の allow と
  `additionalDirectories` は、フォルダを信頼した後で効く。`additionalDirectories` で `%USERPROFILE%` が展開されるかは文書に無い。
  プロジェクトの `.claude/skills/` はセッション中に足しても読み込まれる（出なければ `/reload-skills`）
- デスクトップアプリのコードタブで `.claude/launch.json`（`runtimeExecutable: "hsbg"`、`runtimeArgs: ["serve", "--no-open", "--port", "8501"]`、
  `port: 8501`、`autoVerify: false`）が動いた（2026-11-28）。ブラウザペインのヘッダーの Dev servers メニューは、セッションで最初のメッセージを送った後に出る。
  起動ボタンでダッシュボードが開き、表示と操作もできた。8501 が使用中だったときは、アプリが引数を `--server.port 8502` にして空いているポートで起動した
  プロジェクトの `.claude/settings.json` の `PowerShell(hsbg config *)` で、フォルダを信頼した後は承認なしで実行された。`hsbg init` が置いたスキル 3 つも `/` の一覧に出た
- 通しの確認の 1 回目（2026-11-28、別の Windows ユーザー、アプリ 6.28899.6.0、uv 0.13.10）: git は求められず、インストールの前の説明と了承も出た。
  `uv tool install` が Python 3.15.2 を入れたところで `Missing expected target directory for Python minor version link` で失敗した。
  `%APPDATA%\uv\python` の中身がアプリのパッケージの `LocalCache\Roaming\uv\python` にもあった。アプリのマニフェストは AppData への書き込みを振り替える設定
  （`FileSystemWriteVirtualization`。レジストリは振り替えない `RegistryWriteVirtualization disabled`）なので、uv の置き場所を
  ユーザーの環境変数で `%USERPROFILE%\.local\share\uv` と `%USERPROFILE%\.cache\uv` にし、`--python 3.12` を付けることにした。
  開発用のユーザーでは、`Invoke-CommandInDesktopPackage` でパッケージの中から実行しても振り替えは起きず、uv 0.13.10 と Python 3.15 でも失敗を再現できなかった
- 通しの確認の 2 回目（2026-11-28、同じ別ユーザーで最初から）: インストール、分析、ダッシュボードの表示までアプリの中で完結した。
  アプリの外の PowerShell と、アプリを開き直した後の `hsbg config` も動いた。セットアップの終わりの案内に、知識庫を始めることが無く、
  ダッシュボードの案内が埋もれていたので、hsbg-setup の最後を「次にできること」の番号付きの一覧（分析したいこと、ゲームの分析、知識庫、ダッシュボード）にし、
  最後のメッセージの最後に置くようにした
