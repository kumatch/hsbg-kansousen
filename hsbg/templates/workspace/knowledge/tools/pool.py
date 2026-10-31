"""ミニオンプールのスナップショットを CardDefs から作り、2 つのスナップショットを比べる。

hsbg の知識庫の雛形に含まれるツール。英語（CardDefs.base.xml）は常に、クライアントの言語のカードデータ
（HDT が取得する CardDefs.<言語>.xml。日本語なら jaJP）があればその言語も出す。--locale で言語を選べる。
日時は PC のタイムゾーンで書く。

使い方（知識庫のフォルダで。詳しくは season/pool/README.md）:

    python tools/pool.py snapshot            # season/pool/<日付>_build<build>.md / .json を作る
    python tools/pool.py diff                # season/pool の最新 2 つを比べる
    python tools/pool.py diff OLD.json NEW.json --refs -o diff.md

Python 3.12、標準ライブラリのみ。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

SCHEMA = 1
REPO = Path(__file__).resolve().parent.parent
POOL_DIR = REPO / "season" / "pool"
PATCH_DIR = REPO / "patches"

# CARDRACE の値 → HearthDb の Race enum 名。
# 確認: HearthDb 37.0.0（HDT 1.59.3 同梱の HearthDb.dll）の HearthDb.Enums.Race をリフレクションで読んだもの（2026-10-17）
RACE_ENUM = {
    11: "UNDEAD", 14: "MURLOC", 15: "DEMON", 17: "MECHANICAL", 18: "ELEMENTAL", 20: "PET",
    21: "TOTEM", 23: "PIRATE", 24: "DRAGON", 26: "ALL", 43: "QUILBOAR", 92: "NAGA",
    93: "OLDGOD", 126: "ABERRATION",
}
# 2 つ目以降の種族は「種族ごとのタグ = 1」で入る（CARDRACE は 1 つしか持てない）。
# タグの enumID → Race。確認: 同じ HearthDb 37.0.0 の HearthDb.Enums.RaceUtils.TagRaceMap（BG に関係する分だけ）
TAG_RACE = {
    2522: "PIRATE", 2523: "DRAGON", 2534: "UNDEAD", 2536: "MURLOC", 2537: "DEMON",
    2539: "MECHANICAL", 2540: "ELEMENTAL", 2542: "PET", 2543: "TOTEM", 2546: "QUILBOAR",
    2553: "NAGA", 2554: "OLDGOD", 4756: "ABERRATION",
}
# 日本語の種族名。hsbg の labels.py（MINION_TYPES）に揃えた。クライアント表記との照合は要確認
RACE_JA = {
    "UNDEAD": "アンデッド", "MURLOC": "マーロック", "DEMON": "悪魔", "MECHANICAL": "メカ",
    "ELEMENTAL": "エレメンタル", "PET": "獣", "TOTEM": "トーテム", "PIRATE": "海賊",
    "DRAGON": "ドラゴン", "ALL": "全種族", "QUILBOAR": "キルボア", "NAGA": "ナーガ",
    "OLDGOD": "古き神", "ABERRATION": "異形",
}

LANG_LABEL = {"jaJP": "日本語"}  # 表の見出しに使う言語の名前（無い言語はロケール名のまま）


def lang_key(locale: str) -> str:
    """JSON のキーに使う短い言語名（jaJP → ja）。"""
    return locale[:2]


def lang_label(locale: str) -> str:
    return LANG_LABEL.get(locale, locale)


def snapshot_locale(meta: dict) -> str | None:
    """スナップショットの言語（meta の build_<ロケール>）。英語だけなら None。"""
    for key in meta:
        if key.startswith("build_") and key != "build_base":
            return key.removeprefix("build_")
    return None


def diff_fields(locale: str | None) -> list[tuple[str, str]]:
    """差分で比べる項目（JSON のキー → 表示名）。"""
    if locale:
        k, label = lang_key(locale), lang_label(locale)
        local = [(f"name_{k}", f"{label}名")]
        local_text = [(f"text_{k}", f"効果（{label}）"), (f"text_{k}_alt", f"効果・別表示（{label}）")]
    else:
        local, local_text = [], []
    return [
        *local, ("name_en", "英語名"), ("tier", "Tier"), ("stats", "攻/体"),
        ("races", "種族"), ("aberration", "異形"), ("duos_only", "デュオ専用"),
        *local_text,
        ("text_en", "効果（英語）"), ("text_en_alt", "効果・別表示（英語）"),
        ("golden_card_id", "金色版"),
    ]


# ---------------------------------------------------------------- CardDefs

def default_carddefs_dir() -> Path:
    return Path(os.environ.get("APPDATA", "")) / "HearthstoneDeckTracker" / "CardDefs"


def load_xml(path: Path) -> tuple[str, dict[str, ET.Element]]:
    root = ET.parse(path).getroot()
    return root.get("build", ""), {e.get("CardID"): e for e in root.iter("Entity")}


def int_tags(entity: ET.Element) -> dict[str, int]:
    """名前 → 値（Int / Bool のタグ）。名前の無いタグは enumID を "#<enumID>" のキーにする。"""
    out: dict[str, int] = {}
    for t in entity.findall("Tag"):
        v = t.get("value")
        if v is None:
            continue
        name = t.get("name") or ""
        key = name if name and not name.isdigit() else f"#{t.get('enumID')}"
        out[key] = int(v)
        out[f"#{t.get('enumID')}"] = int(v)
    return out


def loc_text(entity: ET.Element | None, tag: str, lang: str) -> str:
    if entity is None:
        return ""
    node = entity.find(f"Tag[@name='{tag}']/{lang}")
    return (node.text or "") if node is not None else ""


# ---------------------------------------------------------------- 効果テキスト

_ALT_START = re.compile(r"(?:<b>)?\[x\]")


def _plain(s: str) -> str:
    return re.sub(r"\[x\]|</?[bi]>|[_\s]", "", s)


def split_alt(text: str) -> tuple[str, str]:
    """`A@B` を本文 A と別表示 B に分ける。

    `@` には 2 つの意味がある: 状態によって切り替わる別の文（区切り）と、数値の差し込み（「グレード@の」）。
    `@` の直後が `[x]` で始まる、または前後の文の書き出しが同じなら区切りとみなす。
    """
    for i, ch in enumerate(text):
        if ch != "@":
            continue
        before, after = text[:i], text[i + 1:]
        head = _plain(before)[:8]
        if _ALT_START.match(after) or (head and _plain(after).startswith(head)):
            return before, after
    return text, ""


def render(text: str, nums: dict[int, int], lang: str) -> str:
    """CardDefs の CARDTEXT を読める形にする（規則は season/pool/README.md）。"""
    s = text.replace("[x]", "")
    s = re.sub(r"</?[bi]>", "", s)
    s = re.sub(r"\{(\d+)\}", lambda m: str(nums.get(int(m.group(1)) + 1, 0)), s)
    s = s.replace("@", str(nums.get(1, 0)))
    # 英語の複数形 `|4(turn, turns)`
    s = re.sub(r"(\d+)(\s*)\|4\(([^,()]*),\s*([^()]*)\)",
               lambda m: m.group(1) + m.group(2) + (m.group(3) if m.group(1) == "1" else m.group(4)), s)
    if lang == "jaJP":
        s = s.replace("_", "").replace("\n", "")
    else:
        s = re.sub(r"\s+", " ", s.replace("_", " "))
    return s.strip()


def card_texts(base_e: ET.Element, loc_e: ET.Element | None, locale: str | None,
               tags: dict[str, int]) -> dict[str, str]:
    nums = {n: tags[f"TAG_SCRIPT_DATA_NUM_{n}"] for n in range(1, 10) if f"TAG_SCRIPT_DATA_NUM_{n}" in tags}
    out = {}
    langs = [(lang_key(locale), loc_e, locale)] if locale else []
    for key, entity, lang in (*langs, ("en", base_e, "enUS")):
        main, alt = split_alt(loc_text(entity, "CARDTEXT", lang))
        out[f"text_{key}"] = render(main, nums, lang)
        out[f"text_{key}_alt"] = render(alt, nums, lang) if alt else ""
    return out


# ---------------------------------------------------------------- パッチの対応

def patch_files() -> list[tuple[str, str]]:
    """(日付, リポジトリからの相対パス) を日付順に。"""
    out = []
    for p in PATCH_DIR.glob("*.md"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})_", p.name)
        if m:
            out.append((m.group(1), p.relative_to(REPO).as_posix()))
    return sorted(out)


def patch_for(date: str, patches: list[tuple[str, str]]) -> tuple[str, str]:
    """date 以前に適用された最新のパッチ。(パス, 適用日)。無ければ ("", "")"""
    cand = [p for p in patches if p[0] <= date]
    return (cand[-1][1], cand[-1][0]) if cand else ("", "")


# ---------------------------------------------------------------- snapshot

def mtime_local(path: Path) -> datetime:
    """ファイルの更新日時（PC のタイムゾーン）。"""
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().replace(microsecond=0)


def find_locale(cd_dir: Path, wanted: str | None) -> str | None:
    """使う言語。指定があればそれ（ファイルが無ければエラー）、無ければフォルダにある言語版
    （HDT はクライアントの言語のものを取得する。複数あれば新しい方）、無ければ None（英語だけ）。"""
    if wanted:
        if wanted == "enUS":
            return None
        if not (cd_dir / f"CardDefs.{wanted}.xml").is_file():
            raise SystemExit(f"{cd_dir / f'CardDefs.{wanted}.xml'} が無い（HDT は Hearthstone クライアントの言語のものだけを取得する）")
        return wanted
    found = [p for p in cd_dir.glob("CardDefs.*.xml") if p.name != "CardDefs.base.xml"]
    if not found:
        return None
    newest = max(found, key=lambda p: p.stat().st_mtime)
    return newest.name.removeprefix("CardDefs.").removesuffix(".xml")


def build_snapshot(cd_dir: Path, patch_override: str | None, wanted_locale: str | None = None) -> dict:
    base_path = cd_dir / "CardDefs.base.xml"
    build_base, base = load_xml(base_path)
    base_mtime = mtime_local(base_path)
    locale = find_locale(cd_dir, wanted_locale)
    if locale:
        loc_path = cd_dir / f"CardDefs.{locale}.xml"
        build_loc, loc = load_xml(loc_path)
        loc_mtime = mtime_local(loc_path)
        k = lang_key(locale)
    else:
        build_loc, loc, loc_mtime, k = "", {}, None, ""
    warnings: list[str] = []

    dbf_to_card = {int(e.get("ID")): cid for cid, e in base.items() if e.get("ID")}
    minions = []
    for cid, e in base.items():
        tags = int_tags(e)
        if tags.get("IS_BACON_POOL_MINION") != 1:
            continue
        loc_e = loc.get(cid)
        if locale and loc_e is None:
            warnings.append(f"{cid}: {locale} に無い")
        races = []
        primary = tags.get("CARDRACE", 0)
        if primary:
            races.append(RACE_ENUM.get(primary, f"RACE_{primary}"))
            if primary not in RACE_ENUM:
                warnings.append(f"{cid}: 未知の CARDRACE {primary}")
        for enum_id, race in TAG_RACE.items():
            if tags.get(f"#{enum_id}") == 1 and race not in races:
                races.append(race)
        golden = tags.get("BACON_TRIPLE_UPGRADE_MINION_ID")
        minion: dict = {"card_id": cid, "dbf_id": int(e.get("ID"))}
        if locale:
            minion[f"name_{k}"] = loc_text(loc_e, "CARDNAME", locale)
        minion.update({
            "name_en": loc_text(e, "CARDNAME", "enUS"),
            "tier": tags.get("TECH_LEVEL"),
            "attack": tags.get("ATK", 0),
            "health": tags.get("HEALTH", 0),
            "races": races,
        })
        if locale == "jaJP":  # 種族名の対応表は日本語だけ
            minion["races_ja"] = [RACE_JA.get(r, r) for r in races]
        minion.update({
            "aberration": tags.get("BACON_SUBSET_ABERRATION") == 1,
            "duos_only": tags.get("IS_BACON_DUOS_EXCLUSIVE") == 1,
            **card_texts(e, loc_e, locale, tags),
            "golden_card_id": dbf_to_card.get(golden, f"dbf:{golden}") if golden else "",
        })
        minions.append(minion)
    minions.sort(key=lambda m: (m["tier"] or 0, "・".join(race_names(m)) or "~", m["card_id"]))

    patches = patch_files()
    date_base = base_mtime.date().isoformat()
    if patch_override:
        patch, patch_date, rule = patch_override, "", "指定（--patch）"
    else:
        patch, patch_date = patch_for(date_base, patches)
        rule = "推定: CardDefs.base.xml の更新日以前に適用された最新のパッチ記録"
        if loc_mtime is not None:
            patch_loc, _ = patch_for(loc_mtime.date().isoformat(), patches)
            if patch_loc != patch:
                warnings.append(f"base と {locale} で対応するパッチが違う（base: {patch} / {locale}: {patch_loc}）。数値は base、テキストは {locale} から取っている")
        if patch_date == date_base:
            warnings.append(f"CardDefs の更新日がパッチ {patch} の適用日と同じ。取得がパッチの前か後かは時刻で確かめる")
        if patches and patches[-1][0] == patch_date:
            gap = (base_mtime.date() - datetime.fromisoformat(patch_date).date()).days
            if gap > 7:
                warnings.append(f"CardDefs の更新日が最新のパッチ記録（{patch}）の {gap} 日後。記録されていないパッチがある可能性")
    if locale and build_base != build_loc:
        warnings.append(f"base と {locale} の build が違う（base {build_base} / {locale} {build_loc}）")

    meta: dict = {"build_base": build_base}
    if locale:
        meta[f"build_{locale}"] = build_loc
    meta["carddefs_base_mtime"] = base_mtime.isoformat()
    if loc_mtime is not None:
        meta[f"carddefs_{locale}_mtime"] = loc_mtime.isoformat()
    return {
        "schema": SCHEMA,
        "meta": {
            **meta,
            "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
            "patch": patch,
            "patch_rule": rule,
            "source": "HDT CardDefs（%APPDATA%\\HearthstoneDeckTracker\\CardDefs）、IS_BACON_POOL_MINION=1",
            "race_enum": "HearthDb 37.0.0 の Race / RaceUtils.TagRaceMap（tools/pool.py に転記）",
            "count": len(minions),
            "warnings": warnings,
        },
        "minions": minions,
    }


def race_names(m: dict) -> list[str]:
    """表に出す種族名: 日本語の対応があればそれ、無ければ HearthDb の enum 名。"""
    return m["races_ja"] if "races_ja" in m else m["races"]


def snapshot_stem(meta: dict) -> str:
    locale = snapshot_locale(meta)
    dates = [meta["carddefs_base_mtime"]] + ([meta[f"carddefs_{locale}_mtime"]] if locale else [])
    stem = f"{max(dates)[:10]}_build{meta['build_base']}"
    if locale and meta[f"build_{locale}"] != meta["build_base"]:
        stem += f"_{lang_key(locale)}{meta[f'build_{locale}']}"
    return stem


def md_cell(s: object) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def snapshot_markdown(snap: dict) -> str:
    meta, minions = snap["meta"], snap["minions"]
    locale = snapshot_locale(meta)
    lines = [
        f"# ミニオンプール（CardDefs build {meta['build_base']}）",
        "",
        "`tools/pool.py snapshot` で生成。**手で編集しない**。列と変換規則は `season/pool/README.md`。",
        "",
        "| 項目 | 値 |",
        "|---|---|",
        f"| build（base） | {meta['build_base']} |",
    ]
    if locale:
        lines.append(f"| build（{locale}） | {meta[f'build_{locale}']} |")
    lines.append(f"| CardDefs.base.xml の更新日時 | {meta['carddefs_base_mtime']} |")
    if locale:
        lines.append(f"| CardDefs.{locale}.xml の更新日時 | {meta[f'carddefs_{locale}_mtime']} |")
    lines += [
        f"| 生成日時 | {meta['generated_at']} |",
        f"| 対応するパッチ | `{meta['patch']}`（{meta['patch_rule']}） |",
        f"| 件数 | {meta['count']}（`IS_BACON_POOL_MINION`=1） |",
    ]
    for w in meta["warnings"]:
        lines.append(f"| 警告 | {md_cell(w)} |")
    lines.append("")
    k = lang_key(locale) if locale else "en"
    name_cols = [f"{lang_label(locale)}名", "英語名"] if locale else ["英語名"]
    tiers = sorted({m["tier"] or 0 for m in minions})
    for tier in tiers:
        rows = [m for m in minions if (m["tier"] or 0) == tier]
        head = ["CardID", *name_cols, "種族", "攻/体", "異形", "デュオ専用", "効果", "金色版"]
        lines += [
            f"## Tier {tier}（{len(rows)}）",
            "",
            "| " + " | ".join(head) + " |",
            "|" + "|".join("---" for _ in head) + "|",
        ]
        for m in rows:
            text = m[f"text_{k}"] + (f"〔別表示: {m[f'text_{k}_alt']}〕" if m[f"text_{k}_alt"] else "")
            names = [m[f"name_{k}"], m["name_en"]] if locale else [m["name_en"]]
            lines.append("| " + " | ".join(md_cell(x) for x in (
                f"`{m['card_id']}`", *names, "・".join(race_names(m)) or "なし",
                f"{m['attack']}/{m['health']}", "○" if m["aberration"] else "", "○" if m["duos_only"] else "",
                text, f"`{m['golden_card_id']}`" if m["golden_card_id"] else "")) + " |")
        lines.append("")
    return "\n".join(lines)


def cmd_snapshot(args: argparse.Namespace) -> int:
    snap = build_snapshot(Path(args.carddefs), args.patch, args.locale)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = snapshot_stem(snap["meta"])
    (out_dir / f"{stem}.json").write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (out_dir / f"{stem}.md").write_text(snapshot_markdown(snap) + "\n", encoding="utf-8", newline="\n")
    print(f"{out_dir / stem}.json / .md: {snap['meta']['count']} 体、パッチ {snap['meta']['patch']}")
    for w in snap["meta"]["warnings"]:
        print(f"警告: {w}")
    return 0


# ---------------------------------------------------------------- diff

def latest_snapshots(n: int = 2) -> list[Path]:
    return sorted(POOL_DIR.glob("*_build*.json"))[-n:]


def field_value(m: dict, key: str, local: bool = True) -> str:
    """local=False: 種族は言語に依らない enum 名で（言語の違うスナップショット同士を比べるとき）。"""
    if key == "stats":
        return f"{m['attack']}/{m['health']}"
    if key == "races":
        return "・".join(race_names(m) if local else m["races"]) or "なし"
    v = m.get(key, "")
    if isinstance(v, bool):
        return "○" if v else "×"
    return "" if v is None else str(v)


def find_refs(card_ids: list[str]) -> dict[str, list[str]]:
    """手書きの .md（season/pool を除く）で CardID に触れている行。"""
    pats = {cid: re.compile(rf"(?<![\w]){re.escape(cid)}(?![\w])") for cid in card_ids}
    refs: dict[str, list[str]] = {cid: [] for cid in card_ids}
    for path in sorted(REPO.rglob("*.md")):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith("season/pool/") or rel.startswith("."):
            continue
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for cid, pat in pats.items():
                if pat.search(line):
                    refs[cid].append(f"{rel}:{no}")
    return refs


def diff_markdown(old: dict, new: dict, old_name: str, new_name: str, with_refs: bool) -> str:
    om = {m["card_id"]: m for m in old["minions"]}
    nm = {m["card_id"]: m for m in new["minions"]}
    added = [nm[c] for c in nm if c not in om]
    removed = [om[c] for c in om if c not in nm]
    locale = snapshot_locale(new["meta"])
    same_lang = snapshot_locale(old["meta"]) == locale
    if not same_lang:
        locale = None  # 言語が違うスナップショット同士は英語だけで比べる
    k = lang_key(locale) if locale else "en"
    changes = []
    for cid in nm:
        if cid in om:
            for key, label in diff_fields(locale):
                a, b = field_value(om[cid], key, same_lang), field_value(nm[cid], key, same_lang)
                if a != b:
                    changes.append((nm[cid], label, a, b))

    def meta_line(name: str, snap: dict) -> str:
        m = snap["meta"]
        loc = snapshot_locale(m)
        builds = f"base {m['build_base']}" + (f" / {loc} {m[f'build_{loc}']}" if loc else "")
        return f"`{name}`（{builds}、CardDefs {m['carddefs_base_mtime'][:16]}、パッチ `{m['patch']}`）"

    lines = [
        "# ミニオンプールの差分",
        "",
        f"- 旧: {meta_line(old_name, old)}",
        f"- 新: {meta_line(new_name, new)}",
        f"- 追加 {len(added)} / 削除 {len(removed)} / 変更 {len(changes)} 項目（{len({c[0]['card_id'] for c in changes})} 体）",
    ]
    if locale and old["meta"][f"build_{locale}"] != new["meta"][f"build_{locale}"]:
        label = lang_label(locale)
        lines.append(f"- {locale} の build が違うので、{label}テキストだけの変更は翻訳の修正のことがある（英語テキストと見比べる）")
    lines.append("")
    name_cols = [f"{lang_label(locale)}名", "英語名"] if locale else ["英語名"]

    def names(m: dict) -> list[str]:
        return [m[f"name_{k}"], m["name_en"]] if locale else [m["name_en"]]

    def row_table(title: str, rows: list[dict]) -> None:
        lines.extend([f"## {title}（{len(rows)}）", ""])
        if not rows:
            lines.extend(["なし", ""])
            return
        head = ["CardID", *name_cols, "Tier", "種族", "攻/体", "効果"]
        lines.extend(["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"])
        for m in rows:
            lines.append("| " + " | ".join(md_cell(x) for x in (
                f"`{m['card_id']}`", *names(m), m["tier"], field_value(m, "races"),
                field_value(m, "stats"), m[f"text_{k}"])) + " |")
        lines.append("")

    row_table("追加", added)
    row_table("削除", removed)
    lines.extend([f"## 変更（{len(changes)}）", ""])
    if changes:
        head = ["CardID", *name_cols, "項目", "変更前", "変更後"]
        lines.extend(["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"])
        for m, label, a, b in changes:
            lines.append("| " + " | ".join(md_cell(x) for x in (
                f"`{m['card_id']}`", *names(m), label, a, b)) + " |")
    else:
        lines.append("なし")
    lines.append("")

    if with_refs:
        ids = [m["card_id"] for m in added + removed] + sorted({c[0]["card_id"] for c in changes})
        refs = find_refs(ids)
        # patches/ は過去の記録なので書き換えない。照合の参考に別に出す
        for title, keep in (("「今」を表す手書きの記述（要再確認を付ける候補）", lambda r: not r.startswith("patches/")),
                            ("過去のパッチ記録（書き換えない。照合の参考）", lambda r: r.startswith("patches/"))):
            lines.extend([f"## {title}", ""])
            hit = False
            for cid in ids:
                rs = [r for r in refs[cid] if keep(r)]
                if rs:
                    hit = True
                    lines.append(f"- `{cid}`: " + ", ".join(rs))
            if not hit:
                lines.append("なし")
            lines.append("")
    return "\n".join(lines)


def cmd_diff(args: argparse.Namespace) -> int:
    if args.old and args.new:
        paths = [Path(args.old), Path(args.new)]
    elif args.old or args.new:
        print("OLD と NEW は両方指定するか、両方省略する", file=sys.stderr)
        return 2
    else:
        paths = latest_snapshots()
        if len(paths) < 2:
            print(f"{POOL_DIR} にスナップショットが 2 つない", file=sys.stderr)
            return 2
    old, new = (json.loads(p.read_text(encoding="utf-8")) for p in paths)
    text = diff_markdown(old, new, paths[0].name, paths[1].name, args.refs)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"{args.output} に書いた")
    else:
        print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot", help="CardDefs からスナップショットを作る")
    s.add_argument("--carddefs", default=str(default_carddefs_dir()), help="CardDefs のフォルダ（既定: HDT の場所）")
    s.add_argument("--out", default=str(POOL_DIR), help="出力先（既定: season/pool）")
    s.add_argument("--patch", help="対応するパッチを推定せずに指定する（例: patches/2026-10-02_36.6.3.md）")
    s.add_argument("--locale", help="英語以外に出す言語（例: jaJP。enUS = 英語だけ。既定: CardDefs フォルダにある言語版）")
    s.set_defaults(func=cmd_snapshot)
    d = sub.add_parser("diff", help="2 つのスナップショット（.json）を比べる")
    d.add_argument("old", nargs="?", help="古い方の .json（省略時は season/pool の最新 2 つ）")
    d.add_argument("new", nargs="?", help="新しい方の .json")
    d.add_argument("--refs", action="store_true", help="差分のカードに触れている手書きの .md の行を一覧にする")
    d.add_argument("-o", "--output", help="書き出すファイル（省略時は標準出力）")
    d.set_defaults(func=cmd_diff)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
