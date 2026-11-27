"""The install instructions point at the version being released (docs/release.md)."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG_ZIP = re.compile(r"hsbg-kansousen/archive/refs/tags/v([0-9][0-9A-Za-z.\-]*)\.zip")
INSTALL_DOC_URL = "https://github.com/kumatch/hsbg-kansousen/blob/main/docs/install.md"


def _version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_tag_zip_urls_match_the_package_version() -> None:
    version = _version()
    assert TAG_ZIP.search((ROOT / "docs" / "install.md").read_text(encoding="utf-8"))
    for name in ["README.md", "docs/install.md", "docs/desktop-app.md"]:
        found = set(TAG_ZIP.findall((ROOT / name).read_text(encoding="utf-8")))
        assert found <= {version}, f"{name}: {sorted(found)} != {version}"


def test_user_docs_do_not_ask_for_git() -> None:
    """git is the player's own choice: the setup and the workspace never need or suggest it."""
    names = ["docs/install.md", "docs/desktop-app.md"] + [
        str(p.relative_to(ROOT)) for p in (ROOT / "hsbg" / "templates" / "workspace").rglob("*.md")
    ]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    texts = {"README.md": readme.split("## 開発")[0]}  # the developer section may clone
    texts |= {name: (ROOT / name).read_text(encoding="utf-8") for name in names}
    for name, text in texts.items():
        for word in ["git+https", "git init", "git clone", "git は"]:
            assert word not in text, f"{name}: {word}"


def test_desktop_app_prompt_points_at_the_install_doc() -> None:
    assert (ROOT / "docs" / "install.md").is_file()
    for name in ["README.md", "docs/desktop-app.md"]:
        assert INSTALL_DOC_URL in (ROOT / name).read_text(encoding="utf-8"), name
