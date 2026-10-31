r"""Find personal data before publishing: user folders, e-mail addresses, BattleTags, account ids,
and the words in your own deny list (your user name, real name, private paths, ...).

The deny list is a text file outside the repository (one word or phrase per line, `#` comments,
case-insensitive): --denylist, else $HSBG_DENYLIST, else %APPDATA%\hsbg-dev\denylist.txt (on other
systems ~/.config/hsbg-dev/denylist.txt). Never commit it.

Usage (Python 3.12, standard library only; run from the repository root):
  python scripts\check_private.py                 # the files git tracks
  python scripts\check_private.py <path> [...]    # these files / folders instead
  python scripts\check_private.py --history       # also every commit's diff and message
Exit code 1 when something is found. A line with `check_private: ok` in it (e.g. a test that needs a
sample user folder) is skipped.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

# Built-in patterns that are personal for anyone. A placeholder (<user>, %USERPROFILE%, $env:...)
# after C:\Users\ is fine.
PATTERNS: dict[str, re.Pattern[str]] = {
    "user folder": re.compile(
        r"[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/)(?!<|%|\$|(?:"
        + r"|".join(["Public", "Default", "me", "user", "username", "you", "example"])
        + r")\b)[^\\/\s\"'`]+",
        re.IGNORECASE,
    ),
    "home folder": re.compile(
        r"(?<![\w.])/(?:Users|home)/(?!<|\$|(?:me|user|username|you|example)\b)[a-z][\w.-]*",
        re.IGNORECASE,
    ),
    "e-mail": re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b", re.IGNORECASE),
    "BattleTag": re.compile(r"(?<![\w#&])[^\W\d_][\w]{2,11}#\d{4,5}\b"),
    "account id": re.compile(r"GameAccountId=\[hi=[1-9]\d{5,} lo=[1-9]\d{3,}\]"),
}
# Addresses that are meant to be public (commit trailers, examples).
ALLOWED_EMAILS = re.compile(
    r"(noreply@anthropic\.com|@users\.noreply\.github\.com|@example\.(com|org)|"
    r"^[\w.+-]+@\d+\.\d+)",  # "pkg@1.2.3" version pins
    re.IGNORECASE,
)
# A line that contains this is an intended example (e.g. a test of a path rule); the deny list
# still applies to the other lines.
ALLOW_MARK = "check_private: ok"
SKIP_SUFFIXES = {".png", ".jpg", ".gif", ".ico", ".zip", ".gz", ".dll", ".exe", ".pdb", ".pyc"}
# build output and environments that are never published (when a folder is given)
SKIP_DIRS = {".git", ".venv", "node_modules", "bin", "obj", "dist", "__pycache__", ".pytest_cache"}
SKIP_DIRS |= {".ruff_cache", ".cache"}


def default_denylist() -> Path:
    if os.environ.get("HSBG_DENYLIST"):
        return Path(os.environ["HSBG_DENYLIST"])
    if os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "hsbg-dev" / "denylist.txt"
    return Path.home() / ".config" / "hsbg-dev" / "denylist.txt"


def read_denylist(path: Path) -> list[str]:
    if not path.is_file():
        return []
    words = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line)
    return words


def findings(text: str, words: list[str]) -> Iterator[tuple[int, str, str]]:
    """(line number, kind, matched text) for every hit in `text`."""
    lowered = [w.lower() for w in words]
    for n, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if ALLOW_MARK in low:
            continue
        for word, w in zip(words, lowered, strict=True):
            if w in low:
                yield n, "deny list", word
        for kind, pattern in PATTERNS.items():
            for m in pattern.finditer(line):
                if kind == "e-mail" and ALLOWED_EMAILS.search(m.group(0)):
                    continue
                yield n, kind, m.group(0)


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True)
    return [Path(p) for p in out.stdout.decode("utf-8").split("\0") if p]


def expand(paths: Iterable[Path]) -> Iterator[Path]:
    for p in paths:
        if p.is_dir():
            yield from (
                f for f in sorted(p.rglob("*")) if f.is_file() and not SKIP_DIRS & set(f.parts)
            )
        elif p.is_file():
            yield p


def read_text(path: Path) -> str | None:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path, help="files / folders (default: git ls-files)")
    ap.add_argument("--denylist", type=Path, default=None)
    ap.add_argument("--history", action="store_true", help="also scan git log -p (all commits)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    deny_path = args.denylist or default_denylist()
    words = read_denylist(deny_path)
    if not words:
        print(f"note: no deny list at {deny_path}; only the built-in patterns are checked")

    hits = 0
    files = list(expand(args.paths)) if args.paths else tracked_files()
    for path in files:
        text = read_text(path)
        if text is None:
            continue
        for n, kind, match in findings(text, words):
            hits += 1
            print(f"{path}:{n}: {kind}: {match}")
    if args.history:
        log = subprocess.run(
            ["git", "log", "-p", "--all", "--format=commit %H%n%an <%ae>%n%B"],
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8", errors="replace")
        for n, kind, match in findings(log, words):
            hits += 1
            print(f"git log -p:{n}: {kind}: {match}")
    print(f"{len(files)} files checked, {hits} findings")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
