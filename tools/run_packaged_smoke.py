"""Run an already-built executable outside the repo and verify its JSON result."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run_packaged_smoke(executable: Path, report_path: Path) -> dict:
    executable = executable.resolve()
    report_path = report_path.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)
    expected_ids = sorted(
        data["stage_id"]
        for path in (ROOT / "data" / "stages").glob("stage*.json")
        if not (data := json.loads(path.read_text(encoding="utf-8"))).get("debug")
    )
    # Remove only this explicitly named old report, so a failed invocation can
    # never be mistaken for a successful earlier smoke run.
    report_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="flu-packaged-cwd-") as directory:
        working_directory = Path(directory).resolve()
        if working_directory.is_relative_to(ROOT):
            raise RuntimeError("temporary smoke cwd must be outside the repository")
        process = subprocess.run(
            [str(executable), "--smoke-test", "--smoke-output", str(report_path)],
            cwd=working_directory, timeout=180,
        )
        if not report_path.is_file():
            raise RuntimeError(f"packaged smoke exited {process.returncode} without a JSON report")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if process.returncode != 0 or report.get("status") != "passed":
            raise RuntimeError(f"packaged smoke failed ({process.returncode}): {report}")
        if report.get("kind") != "packaged_runtime_smoke" or report.get("frozen") is not True:
            raise RuntimeError("smoke result did not come from the packaged entry point")
        if Path(report["cwd"]).resolve() != working_directory:
            raise RuntimeError("smoke did not execute in the requested external directory")
        stages = report.get("stages", [])
        if [stage.get("stage") for stage in stages] != expected_ids:
            raise RuntimeError("packaged smoke did not cover every authored campaign stage")
        for index, stage in enumerate(stages):
            expected_next = expected_ids[index + 1] if index + 1 < len(expected_ids) else None
            if (stage.get("next_stage") != expected_next
                    or stage.get("initialized") is not True or stage.get("drawn") is not True):
                raise RuntimeError(f"incomplete packaged stage check: {stage}")
        if not all(report.get(key) is True for key in ("settings_saved", "highscore_saved", "playlog_saved")):
            raise RuntimeError("packaged smoke did not verify all user-data saves")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=ROOT / "dist" / "InfuruToNoShito" / "InfuruToNoShito.exe")
    parser.add_argument("--report", type=Path, default=ROOT / "build-reports" / "packaged-smoke.json")
    args = parser.parse_args()
    print(json.dumps(run_packaged_smoke(args.exe, args.report), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
