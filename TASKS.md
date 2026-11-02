# TASKS.md

今どこにいて、次に何をするか。完了したら `[x]` にし、判明したことは docs に追記する。

## 新しいセッションの始め方（Claude Code 向け）

1. `CLAUDE.md` → この `TASKS.md` → 作業に関係する docs の順に読む
2. 検証コマンド（`CLAUDE.md`）が緑であることを確かめてから始める
3. 作業の区切りで、変更したファイルと推奨するコミットメッセージを報告して止まる。コミットは許可を得てから

## 現在の状態

- hsbg 0.1.0。読めるログ: schema 1.x（プラグイン 0.2.0 以降。最新 1.7.0）。レンズ API 1
- 公開の準備中（最初のリリース前）

## タスク

- [x] CI（`.github/workflows/ci.yml`）: Windows で ruff + pytest + check_private。プラグインの `schema/game-log.schema.json` と比べる job（取得できなければ警告だけ）
- [x] 甲虫（schema 1.7.0）: turns に `beetle_attack` / `beetle_health` / `beetle_attack_after` / `beetle_health_after`、
      combats に `opponent_beetle_*`（`hsbg export` とレンズから読める）。過去のゲームは `hsbg backfill-beetle` で power.log から補完
- [ ] 甲虫を `summarize`（AI への入力）とダッシュボードのゲーム詳細にも出す（神祇の `## Deity` 表と同じく、盤面の合計と並べる）
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
