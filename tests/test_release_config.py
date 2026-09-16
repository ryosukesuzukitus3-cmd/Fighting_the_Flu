from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pyinstaller_analysis_explicitly_uses_production_optimization() -> None:
    tree = ast.parse((ROOT / "game.spec").read_text(encoding="utf-8"))
    analysis_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Analysis"
    ]

    assert len(analysis_calls) == 1
    optimize = next(
        (keyword.value for keyword in analysis_calls[0].keywords if keyword.arg == "optimize"),
        None,
    )
    assert isinstance(optimize, ast.Constant)
    assert optimize.value == 1


def test_release_workflow_guards_production_optimization() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "Assert production optimization" in workflow
    assert "optimize=1" in workflow
