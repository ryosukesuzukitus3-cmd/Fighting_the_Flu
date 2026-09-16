"""Regression checks for optional local development helpers."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_hook(agent: str, filename: str):
    path = ROOT / agent / "hooks" / f"{filename}.py"
    spec = importlib.util.spec_from_file_location(f"{agent[1:]}_{filename}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=[".codex", ".claude"])
def agent(request):
    return request.param


def _result(code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


def test_helpers_use_their_own_worktree(agent, monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "another-project"))
    monkeypatch.chdir(tmp_path)
    for name in ("check_sync", "md_to_html"):
        assert _load_hook(agent, name).PROJECT_DIR == ROOT


def test_git_failure_is_not_an_unchanged_tree(agent, monkeypatch, capsys):
    module = _load_hook(agent, "check_sync")
    calls = []

    def fail(cmd):
        calls.append(cmd)
        return _result(128, stderr="fatal: not a git repository")

    monkeypatch.setattr(module, "_run", fail)
    assert module.main(["--changed-only"]) == 2
    assert len(calls) == 1
    assert "not a git repository" in capsys.readouterr().err


def test_command_launch_failure_is_reported(agent, monkeypatch, capsys):
    module = _load_hook(agent, "check_sync")

    def missing(_cmd):
        raise FileNotFoundError("git executable missing")

    monkeypatch.setattr(module, "_run", missing)
    assert module.main([]) == 2
    assert "git executable missing" in capsys.readouterr().err


def test_no_change_skips_only_when_requested(agent, monkeypatch):
    module = _load_hook(agent, "check_sync")
    calls = []

    def run(cmd):
        calls.append(cmd)
        return _result()

    monkeypatch.setattr(module, "_run", run)
    assert module.main(["--changed-only"]) == 0
    assert len(calls) == 1
    calls.clear()
    assert module.main([]) == 0
    assert len(calls) == 3
    expected_check_option = "docs-check" if agent == ".codex" else "--check"
    assert expected_check_option in calls[1]


def test_regeneration_requires_write_option(agent, monkeypatch):
    module = _load_hook(agent, "check_sync")
    calls = []

    def run(cmd):
        calls.append(cmd)
        return _result(stdout=" M docs/agent_guide_shared.md" if cmd[0] == "git" else "")

    monkeypatch.setattr(module, "_run", run)
    assert module.main(["--write"]) == 0
    if agent == ".codex":
        assert calls[1][-1] == "docs"
    else:
        assert calls[1][-1].endswith("gen_docs.py")


def test_check_failure_preserves_stdout_and_stderr(agent, monkeypatch, capsys):
    module = _load_hook(agent, "check_sync")
    results = iter([
        _result(),
        _result(1, stdout="generated guide differs", stderr="generator detail"),
        _result(1, stdout="missing item definition"),
    ])
    monkeypatch.setattr(module, "_run", lambda _cmd: next(results))
    assert module.main([]) == 2
    err = capsys.readouterr().err
    assert "generated guide differs" in err
    assert "generator detail" in err
    assert "missing item definition" in err


def test_change_detection_includes_guides_and_tests(agent, monkeypatch, tmp_path):
    module = _load_hook(agent, "check_sync")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    monkeypatch.setattr(module, "PROJECT_DIR", tmp_path)
    assert not module._has_changes()
    guide = tmp_path / "AGENTS.md"
    guide.write_text("# Updated rules", encoding="utf-8")
    assert module._has_changes()
    guide.unlink()
    (tmp_path / "captures").mkdir()
    (tmp_path / "captures" / "local.txt").write_text("local evidence", encoding="utf-8")
    assert not module._has_changes()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_example.py").write_text("", encoding="utf-8")
    assert module._has_changes()


def test_checker_python_falls_back_without_a_local_venv(agent, monkeypatch, tmp_path):
    module = _load_hook(agent, "check_sync")
    monkeypatch.setattr(module, "PROJECT_DIR", tmp_path)
    assert module._project_python() == sys.executable


def test_html_without_file_does_not_read_stdin(agent, monkeypatch):
    module = _load_hook(agent, "md_to_html")

    def forbidden(*_args, **_kwargs):
        pytest.fail("Unrequested HTML rendering")

    monkeypatch.setattr(module, "cli_render", forbidden)
    with pytest.raises(SystemExit) as exc:
        module.main([])
    assert exc.value.code == 2


def test_plain_html_stays_local_without_api_or_browser(agent, monkeypatch, tmp_path):
    module = _load_hook(agent, "md_to_html")
    monkeypatch.setattr(module, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(module, "OUTPUT_DIR", tmp_path / ".html")

    def forbidden(*_args, **_kwargs):
        pytest.fail("Unrequested external action")

    monkeypatch.setattr(module, "render_fancy", forbidden)
    monkeypatch.setattr(module.webbrowser, "open", forbidden)
    source = tmp_path / "review.md"
    source.write_text("# Local review\n\n## Result\n\nAll clear.", encoding="utf-8")
    assert module.main(["--file", str(source)]) == 0
    rendered = (tmp_path / ".html" / "review.html").read_text(encoding="utf-8")
    assert "Local review" in rendered
    assert "All clear." in rendered


def test_html_browser_open_requires_explicit_option(agent, monkeypatch, tmp_path):
    module = _load_hook(agent, "md_to_html")
    target = tmp_path / "review.html"
    opened = []
    monkeypatch.setattr(module, "cli_render", lambda *_args: target)
    monkeypatch.setattr(module.webbrowser, "open", lambda uri: opened.append(uri) or True)
    assert module.main(["--file", "review.md", "--open"]) == 0
    assert opened == [target.as_uri()]


def test_html_failure_has_nonzero_result(agent, tmp_path, capsys):
    module = _load_hook(agent, "md_to_html")
    assert module.main(["--file", str(tmp_path / "missing.md")]) == 2
    assert "Markdown file not found" in capsys.readouterr().err


def test_html_cli_errors_are_utf8(agent, tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / agent / "hooks/md_to_html.py"),
         "--file", str(tmp_path / "存在しない台本.md")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 2
    assert "存在しない台本.md" in result.stderr


def test_html_from_another_worktree_is_rejected(agent, monkeypatch, tmp_path, capsys):
    module = _load_hook(agent, "md_to_html")
    own = tmp_path / "own-tree"
    own.mkdir()
    other = tmp_path / "other-tree"
    other.mkdir()
    source = other / "review.md"
    source.write_text("# Other tree", encoding="utf-8")
    monkeypatch.setattr(module, "PROJECT_DIR", own)
    monkeypatch.setattr(module, "OUTPUT_DIR", own / ".html")
    assert module.main(["--file", str(source)]) == 2
    assert "outside this worktree" in capsys.readouterr().err
    assert not (own / ".html").exists()


def test_fancy_does_not_guess_an_api_model(agent, monkeypatch):
    module = _load_hook(agent, "md_to_html")
    monkeypatch.delenv("FLU_HTML_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="FLU_HTML_MODEL"):
        module.render_fancy("# Review", ROOT / "docs/design.md")
