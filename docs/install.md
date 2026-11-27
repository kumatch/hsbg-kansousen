# hsbg-kansousen のセットアップ手順（Claude が実行する）

この文書は、利用者に「この手順に従ってセットアップして」と頼まれた Claude（Claude デスクトップアプリのコードタブ、または Claude Code）が、
上から順に実行する手順です。人が読んでも、何が行われるかが分かるように書いています（人向けの案内は [desktop-app.md](desktop-app.md)）。

- 対象: Windows 10 / 11
- **このフォルダ** = セッションで開いているフォルダ。ここが利用者のワークスペース（分析・目標・知識庫を置く場所）になります
- 利用者とは利用者の言語で話し、各段階の終わりに何をしたか・何が分かったかを短く伝えます

## 1. 始める前に、利用者に説明して了承を得る

次を短く説明し、始めてよいかを聞いてください。了承を得るまで、何もインストールしません。

- 入れるもの（どちらも利用者のユーザーにだけ。管理者の権限は使わない）
  - **uv**: Python のツールを入れる道具。`winget` で入れる（すでにあれば入れない）
  - **hsbg**: このツール本体。uv が GitHub から取得して `%USERPROFILE%\.local\bin\hsbg.exe` に置く。Python 3.12 が無ければ uv が取得する
- このフォルダに作るもの: `hsbg.toml`（設定）、`CLAUDE.md`、`README.md`、`analysis\`、`lenses\`、`knowledge\`、`.claude\`（Claude 用のスキル）。
  すでにあるファイルは書き換えない
- ゲームのログ（記録アプリ hsbg-kifu が書く `Documents\HSBG-Logs`）は読むだけ。分析の内容や戦績をどこかへ送ることはない（インターネットはダウンロードにだけ使う）
- コマンドを実行するたびに、アプリが許可を求めるので、内容を見て許可してほしいこと

このフォルダが空でないときは、次のように扱います。

- `hsbg.toml` がある: すでにワークスペース。3〜4 で足りないものだけを入れ、5 は足りないファイルを足すだけになる
- 他のファイルがある: ここをワークスペースにしてよいかを確かめる

## 2. コマンドの実行のしかた

- PowerShell で実行します。**各コマンドの前に PATH を読み直してください**（インストールした直後は、起動中のアプリに新しい PATH が反映されないため）:

  ```powershell
  $env:Path = [Environment]::GetEnvironmentVariable('Path','User') + ';' + [Environment]::GetEnvironmentVariable('Path','Machine')
  ```

- Bash しか使えないときは、PowerShell のコマンドを `powershell.exe -NoProfile -Command "..."` で包んで実行します
- コマンドが失敗したら、出力を利用者に見せて止まり、どうするかを相談します（別のインストール方法を勝手に試さない）

## 3. uv を入れる

1. `uv --version`。表示されれば 4 へ
2. 無ければ `winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements`
   - `winget` が無いときは、Microsoft Store の「アプリ インストーラー」を入れてもらってから、もう一度
3. PATH を読み直して `uv --version` で確かめる

## 4. hsbg を入れる

1. `hsbg config`。最初の行に `hsbg <版>` が表示されれば、入っている版を伝えて 5 へ。**入れ直しや更新はしない**（頼まれたときだけ。下の「更新するとき」）
2. 無ければ、次で入れる（タグの zip を uv が GitHub から取得する）:

   ```powershell
   uv tool install https://github.com/kumatch/hsbg-kansousen/archive/refs/tags/v0.5.0.zip --with pytest
   ```

3. `uv tool update-shell`（次にアプリを開いたときから `hsbg` が見つかるように、PATH に `%USERPROFILE%\.local\bin` を足す）
4. PATH を読み直して `hsbg config` で確かめる（最初の行が `hsbg <版>`）。見つからなければ `& "$env:USERPROFILE\.local\bin\hsbg.exe" config`
   （このセッションの残りはこのフルパスで呼んでよい）

## 5. ワークスペースを作る

1. このフォルダで `hsbg init .`（すでにあるファイルはそのまま。作ったものの一覧が出る）
2. `.claude\skills\` に hsbg のスキル（`hsbg-setup`、`hsbg-analysis`、`hsbg-lens`）が入る。このセッションでもそのまま使える。
   `hsbg-setup` が使えないときは、`.claude\skills\hsbg-setup\SKILL.md` を読んで、その手順に従う

## 6. 設定と目標（hsbg-setup スキル）

`hsbg-setup` スキルの手順で進めます: 記録アプリ hsbg-kifu のログが見つかるか（`hsbg config` / `hsbg validate`）、カード名と分析の言語、
知識庫の説明、目標の聞き取りと `profile.md` の作成。答えにくい質問は飛ばしてよいと伝えてください。

## 7. 終わりに利用者に伝えること

- **アプリを一度終了して、開き直してほしい**（`hsbg` がそのまま見つかるようになる）
- 次からも、**このフォルダを選んで**コードタブのセッションを始める（最近使ったフォルダから選べる）
- 頼み方の例: 「さっきのゲームを分析して」「直近 30 ゲームの傾向を見て」「ダッシュボードを開いて」「今のシーズンの BG の仕組みを knowledge に記録したい」
- 案内: https://github.com/kumatch/hsbg-kansousen/blob/main/docs/desktop-app.md

## 更新するとき（「hsbg を更新して」と頼まれたら）

1. 入っている版を `hsbg config` の最初の行で、最新の版を https://github.com/kumatch/hsbg-kansousen/releases で確かめる。同じなら何もしない
2. どう入っているかを `Get-Content "$(uv tool dir)\hsbg\uv-receipt.toml"` で確かめる。`url = "https://github.com/kumatch/hsbg-kansousen/archive/refs/tags/..."`
   なら次へ。それ以外（`editable` やローカルのパスなど）なら、利用者が自分で入れたもの（開発者など）なので置き換えず、利用者に任せる
3. `uv tool install --force https://github.com/kumatch/hsbg-kansousen/archive/refs/tags/v<最新の版>.zip --with pytest`
   （`uv tool upgrade` は、zip で入れたものには効かない）
4. ワークスペースで `hsbg skills update`（スキルを新しくする）と `hsbg init .`（新しい版で増えたファイルだけを足す）
5. 記録アプリ hsbg-kifu の版との対応は README の「記録アプリと hsbg の版」
