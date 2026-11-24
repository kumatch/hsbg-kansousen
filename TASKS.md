# TASKS.md

今どこにいて、次に何をするか。完了したら `[x]` にし、判明したことは docs に追記する。

## 新しいセッションの始め方（Claude Code 向け）

1. `CLAUDE.md` → この `TASKS.md` → 作業に関係する docs の順に読む
2. 検証コマンド（`CLAUDE.md`）が緑であることを確かめてから始める
3. 作業の区切りで、変更したファイルと推奨するコミットメッセージを報告して止まる。コミットは許可を得てから

## 現在の状態

- hsbg 0.5.0（2026-11-23 リリース。0.1.0 はプラグイン 0.11.0 に合わせて `62d7034` にタグを打ってリリース）。読めるログ: schema 1.x（プラグイン 0.2.0 以降）。
  すべての項目を読むのは 1.11.0 まで（`loader.KNOWN_SCHEMA_VERSION`。0.5.0 で上げた）、それより新しい 1.x は既知の項目だけで読む。レンズ API 1
- 公開の準備中。GitHub Releases に v0.1.0、v0.2.0、v0.3.0、v0.4.0、v0.5.0 を置いた

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
- [ ] 持っているヒーローパワーと時渡り（schema 1.12.0、hsbg-kifu の M10・M11。同じ版で一緒にリリースする）:
  - [x] ヒーローパワー（M10）: `turns` の列 `hero_power_card_id` / `hero_power_name` / `additional_hero_power_card_id` / `additional_hero_power_name`
        （`CACHE_FORMAT` 15）、要約の「## Hero powers」（変わったターンだけ）、log-caveats。要約の選択肢は、後から得たヒーローパワー
        （ゲンの発見、時渡りの「○○の力」、グエンの選んだもの）による選択を「Hero power (X)」と書く（最初のヒーローパワーの別の形 = カード ID が
        最初のもので始まるもの、ゲイルウィングの行き先などは今までどおり「Hero power → X」）
  - [ ] 時渡り（M11）: hsbg-kifu の M11 に合わせる
  - [ ] リリース（hsbg-kifu より先に。版を上げる）
- [ ] CI を Ubuntu でも（テストに Windows のパスを前提にしたものがあるので、直してから）
- [ ] 別の Windows ユーザーで README の手順だけを見て、インストール → `hsbg init` → セットアップ → 分析まで通す
- [ ] Issue テンプレート: hsbg の版、`hsbg config` と `hsbg validate` の出力。ログを添えるときは `scripts/anonymize_log.py` を通した `.json` だけ
      （Power.log やワークスペースの分析・profile.md は貼らない）
- [ ] 公開: リポジトリを public にする（プラグインの最初のリリースと、README の手順の確認の後）
- [ ] ダッシュボード・レポートの画面の英語化（今は日本語だけ）
- [ ] ワークスペースの雛形の英語版（`hsbg init --lang en` など）
- [ ] Hearthstone クライアントと違う言語のカード名（HDT が取得しない言語の CardDefs を hsbg が取得する。外部通信が増えるので要検討）

## 判明したこと・決めたこと

- 利用者ごとのもの（目標、分析の筋、ゲーム知識、保存した分析）はワークスペースに置き、利用者どうしで共有しない（共有すると、そのメンテナンスと、
  誰かの変更が他の人の分析に波及する依存が生まれるため）。知識庫は使うことを勧め、`hsbg init` が空の雛形を用意する
