"""Card names and skin -> base hero mapping from HDT's downloaded CardDefs.

HDT keeps `%APPDATA%\\HearthstoneDeckTracker\\CardDefs\\CardDefs.base.xml` (English names plus tags
such as `BACON_SKIN_PARENT_ID`) and one `CardDefs.<locale>.xml` per card language it has displayed
(for a Japanese client: `CardDefs.jaJP.xml`). HDT refreshes them from hearthstonejson on start, so
new heroes and minions appear there without touching this project.

This module reads only card names (and the skin parent), never writes, and degrades gracefully: when
the files are missing every lookup returns the fallback (the English name stored in the log).
Battlegrounds cards only (ids starting with `BG` / `TB_Bacon`) to keep the tables small.

Folder and language: `HSBG_CARDDEFS` / `HSBG_LOCALE` or `carddefs_dir` / `locale` in hsbg.toml
(config.py; default `jaJP`, `enUS` = English names).
"""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import config

DEFAULT_LOCALE = config.DEFAULT_LOCALE
_KEEP_PREFIXES = ("BG", "TB_Bacon")
_SKIN_RE = re.compile(r"_SKIN_[A-Z0-9]+$")


def base_hero_id(card_id: str | None) -> str | None:
    """Regex fallback: TB_BaconShop_HERO_34_SKIN_C -> TB_BaconShop_HERO_34."""
    if not card_id:
        return None
    return _SKIN_RE.sub("", card_id)


def default_dir() -> Path:
    """$HSBG_CARDDEFS > hsbg.toml `carddefs_dir` > HDT's folder (config.py)."""
    return config.load().carddefs_dir


def default_locale() -> str:
    """$HSBG_LOCALE > hsbg.toml `locale` > jaJP (config.py)."""
    return config.load().locale


@dataclass(frozen=True)
class CardNames:
    locale: str
    names: dict[str, str]  # card_id -> name in `locale` (English when the locale file lacks it)
    parents: dict[str, str]  # skin card_id -> base hero card_id (BACON_SKIN_PARENT_ID)
    sources: tuple[Path, ...]  # files actually read; empty when no CardDefs were found

    @property
    def available(self) -> bool:
        return bool(self.names)

    def name(self, card_id: str | None, fallback: str | None = None) -> str | None:
        if not card_id:
            return fallback
        return self.names.get(card_id) or fallback

    def base_id(self, card_id: str | None) -> str | None:
        """Base hero for a skin (CardDefs parent first, `_SKIN_` regex as fallback)."""
        if not card_id:
            return None
        return self.parents.get(card_id) or base_hero_id(card_id)

    def base_name(self, card_id: str | None, fallback: str | None = None) -> str | None:
        """Localized base hero name; falls back to the skin name, then to `fallback`."""
        base = self.base_id(card_id)
        return self.name(base) or self.name(card_id) or fallback

    def localize(self, log: dict[str, Any]) -> dict[str, Any]:
        """Deep copy of a game log with every `{card_id, name}` object renamed in this locale."""
        out = copy.deepcopy(log)
        if self.names:
            self._walk(out)
        return out

    def _walk(self, node: Any) -> None:
        if isinstance(node, dict):
            if "card_id" in node and "name" in node:
                node["name"] = self.name(node.get("card_id"), node.get("name"))
            for v in node.values():
                self._walk(v)
        elif isinstance(node, list):
            for v in node:
                self._walk(v)

    def signature(self) -> str:
        """Changes when the locale or the CardDefs files change (used by the parquet cache)."""
        parts = [self.locale]
        for p in self.sources:
            try:
                st = p.stat()
                parts.append(f"{p.name}:{st.st_mtime_ns}:{st.st_size}")
            except OSError:
                parts.append(f"{p.name}:missing")
        return "|".join(parts)


EMPTY = CardNames("enUS", {}, {}, ())


def _keep(card_id: str | None) -> bool:
    return bool(card_id) and card_id.startswith(_KEEP_PREFIXES)  # type: ignore[union-attr]


def _parse(path: Path, lang: str) -> tuple[dict[str, str], dict[str, int], dict[str, int]]:
    """(names, dbf ids, parent dbf ids) for kept entities. `lang` = child element of CARDNAME."""
    names: dict[str, str] = {}
    dbf: dict[str, int] = {}
    parents: dict[str, int] = {}
    for _, el in ET.iterparse(path):
        if el.tag != "Entity":
            continue
        card_id = el.get("CardID")
        if _keep(card_id):
            try:
                dbf[card_id] = int(el.get("ID") or 0)  # type: ignore[index]
            except ValueError:
                pass
            for tag in el.iter("Tag"):
                tag_name = tag.get("name")
                if tag_name == "CARDNAME":
                    loc = tag.find(lang)
                    if loc is not None and loc.text:
                        names[card_id] = loc.text.strip()  # type: ignore[index]
                elif tag_name == "BACON_SKIN_PARENT_ID":
                    try:
                        parents[card_id] = int(tag.get("value") or 0)  # type: ignore[index]
                    except ValueError:
                        pass
        el.clear()
    return names, dbf, parents


@lru_cache(maxsize=4)
def load(directory: Path, locale: str) -> CardNames:
    """Read CardDefs.base.xml (+ CardDefs.<locale>.xml) from `directory`; EMPTY when absent."""
    base_path = directory / "CardDefs.base.xml"
    loc_path = directory / f"CardDefs.{locale}.xml"
    names: dict[str, str] = {}
    parents: dict[str, str] = {}
    sources: list[Path] = []
    if base_path.exists():
        try:
            en_names, dbf, parent_dbf = _parse(base_path, "enUS")
        except (ET.ParseError, OSError):
            en_names, dbf, parent_dbf = {}, {}, {}
        else:
            sources.append(base_path)
        by_dbf = {v: k for k, v in dbf.items()}
        parents = {
            cid: by_dbf[p] for cid, p in parent_dbf.items() if p in by_dbf and by_dbf[p] != cid
        }
        names.update(en_names)
    if locale != "enUS" and loc_path.exists():
        try:
            loc_names, _, _ = _parse(loc_path, locale)
        except (ET.ParseError, OSError):
            loc_names = {}
        else:
            sources.append(loc_path)
        names.update(loc_names)
    if not sources:
        return EMPTY
    return CardNames(locale, names, parents, tuple(sources))


def default() -> CardNames:
    """Names for the folder / locale given by the environment (cached per process)."""
    return load(default_dir(), default_locale())
