# リリースの手順

hsbg は記録アプリ（hsbg-kifu。2026-11-30 までは HDT プラグイン hdt-plugin-hsbg-kansousen）と別に版を付ける。
両者の対応はログの版（`schema_version`）で決まり、README の「記録アプリと hsbg の版」の表に書く。

## 版の付け方

- `pyproject.toml` の `version`。タグは `v<version>`（例 `v0.2.0`）
- 読めるログの版が増えた（`hsbg/loader.py` の `KNOWN_SCHEMA_VERSION` が上がった）ときは、少なくとも minor を上げる
- 記録アプリと番号はそろえない（片方だけ直したときに、もう片方を出さずにすむように）

## 互換の考え方

- 古いログ → 新しい hsbg: 読める。minor で増えるキーはどれも任意なので、無いものは空欄になる。過去のログは `hsbg backfill-*` で power.log から補える
- 新しいログ → 古い hsbg: 同じ major で `KNOWN_SCHEMA_VERSION` より新しいログは、知らないキーを許す検査で読み、知らないキーは使わない。
  `LoadResult.newer` に入り、`hsbg validate` とダッシュボードが hsbg の更新を勧める。major が違うログは読まない
  （hsbg 0.1.0 はこの仕組みの前なので、新しいログをスキーマ違反として読み飛ばす）

## 手順

ログの版が変わったリリースでは、**hsbg を先に**出す（記録アプリだけが新しい期間を作らない）。
ただし main の push は **hsbg-kifu を先に**する。CI の `schema` ジョブは hsbg-kifu の main と写しを比べるので、hsbg を先に push すると古い main と比べて失敗する
（タグとリリースの順番は hsbg が先のまま）。

1. `KNOWN_SCHEMA_VERSION` が hsbg-kifu の `GameLog.CurrentSchemaVersion` と同じこと
   （hsbg-kifu 側の `python scripts\check_cli_sync.py --strict` が確かめる）
2. `pyproject.toml` の `version` を上げ、README の対応表に行を足す。`docs/install.md` にあるタグの zip の URL（`.../archive/refs/tags/v<version>.zip`）の版も上げる
   （デスクトップアプリの利用者は、`docs/install.md` の URL の版を入れる。`tests/test_docs.py` が `version` との食い違いを見つける）。
   検証コマンドと `python scripts\check_private.py` を緑にしてコミットする
3. `git tag -a v<version> -m "hsbg <version>（hsbg-kifu <x.y.z> / schema <a.b.c> まで）"; git push origin main v<version>`
4. GitHub の Releases でタグを選び、リリースノートに次を書く: 読めるログの版、対応する記録アプリの版、変更点、
   版を指定したインストール（`uv tool install https://github.com/kumatch/hsbg-kansousen/archive/refs/tags/v<version>.zip --python 3.12 --with pytest`）、
   更新の手順（デスクトップアプリなら「hsbg を更新して」と頼む。自分でするなら、上の URL で `uv tool install --force`
   → ワークスペースで `hsbg skills update` と `hsbg init .`）
5. その後で hsbg-kifu をリリースし、そのリリースノートに「新しい項目を使うには hsbg <version> 以降」と書く
