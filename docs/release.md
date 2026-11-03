# リリースの手順

hsbg はプラグイン（hdt-plugin-hsbg-kansousen）と別に版を付ける。両者の対応はログの版（`schema_version`）で決まり、
README の「プラグインと hsbg の版」の表に書く。

## 版の付け方

- `pyproject.toml` の `version`。タグは `v<version>`（例 `v0.2.0`）
- 読めるログの版が増えた（`hsbg/loader.py` の `KNOWN_SCHEMA_VERSION` が上がった）ときは、少なくとも minor を上げる
- プラグインと番号はそろえない（片方だけ直したときに、もう片方を出さずにすむように）

## 互換の考え方

- 古いログ → 新しい hsbg: 読める。minor で増えるキーはどれも任意なので、無いものは空欄になる。過去のログは `hsbg backfill-*` で power.log から補える
- 新しいログ → 古い hsbg: 同じ major で `KNOWN_SCHEMA_VERSION` より新しいログは、知らないキーを許す検査で読み、知らないキーは使わない。
  `LoadResult.newer` に入り、`hsbg validate` とダッシュボードが hsbg の更新を勧める。major が違うログは読まない
  （hsbg 0.1.0 はこの仕組みの前なので、新しいログをスキーマ違反として読み飛ばす）

## 手順

ログの版が変わったリリースでは、**hsbg を先に**出す（プラグインだけが新しい期間を作らない）。

1. `KNOWN_SCHEMA_VERSION` がプラグインの `GameLog.CurrentSchemaVersion` と同じこと
   （プラグイン側の `python scripts\check_cli_sync.py --strict` が確かめる）
2. `pyproject.toml` の `version` を上げ、README の対応表に行を足す。検証コマンドと `python scripts\check_private.py` を緑にしてコミットする
3. `git tag -a v<version> -m "hsbg <version>（プラグイン <x.y.z> / schema <a.b.c> まで）"; git push origin main v<version>`
4. GitHub の Releases でタグを選び、リリースノートに次を書く: 読めるログの版、対応するプラグインの版、変更点、
   版を指定したインストール（`uv tool install git+https://github.com/kumatch/hsbg-kansousen@v<version> --with pytest`）、
   更新の手順（`uv tool upgrade hsbg` → ワークスペースで `hsbg skills update`）
5. その後でプラグインをリリースし、そのリリースノートに「新しい項目を使うには hsbg <version> 以降」と書く
