"""docs/architecture.md §1: metrics.py / charts.py must not depend on the presentation layers."""

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "hsbg"


def _imports(module: str) -> set[str]:
    tree = ast.parse((PKG / f"{module}.py").read_text("utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names |= {f".{a.name}" for a in node.names if node.level}
    return names


def test_metrics_has_no_presentation_or_plotly_imports() -> None:
    names = _imports("metrics")
    assert not any(n.startswith("plotly") for n in names)
    assert not names & {".report", ".charts", ".summarize", ".cli", ".dashboard"}


def test_charts_only_depends_on_pandas_and_plotly() -> None:
    names = _imports("charts")
    assert not names & {
        ".report",
        ".summarize",
        ".cli",
        ".metrics",
        ".normalize",
        ".loader",
        ".lens",
        ".lenses",
    }


def test_lens_layer_has_no_presentation_or_plotly_imports() -> None:
    """Lenses compute tables like metrics.py; drawing them is charts.py's job (docs/lenses.md)."""
    for module in ("lens", "lenses"):
        names = _imports(module)
        assert not any(n.startswith(("plotly", "streamlit")) for n in names), module
        assert not names & {".report", ".charts", ".summarize", ".cli", ".dashboard", ".markdown"}
