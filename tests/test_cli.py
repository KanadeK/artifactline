from __future__ import annotations

import json
from pathlib import Path

from artifactline.cli import main


def write_workflow(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


HEALTHY = """jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with: {name: package, path: dist/*, if-no-files-found: error}
  publish:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with: {name: package}
"""

BROKEN = """jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with: {name: package, path: dist/*}
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with: {name: package}
"""


def test_terminal_report_and_exit_zero_for_healthy_flow(
    tmp_path: Path, capsys, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    workflow = write_workflow(tmp_path / "ci.yml", HEALTHY)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["audit", str(workflow)])

    output = capsys.readouterr()
    assert exit_code == 0
    assert "FLOW build -> publish: package" in output.out
    assert "Summary: 0 errors, 0 warnings, 1 flow" in output.out
    assert output.err == ""


def test_blocking_findings_exit_one(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workflow = write_workflow(tmp_path / "broken.yml", BROKEN)

    exit_code = main(["audit", str(workflow)])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "ERROR AFL004" in output.out
    assert "ERROR AFL005" in output.out


def test_strict_mode_promotes_warning_to_exit_one(tmp_path: Path) -> None:
    workflow = write_workflow(
        tmp_path / "warning.yml",
        """jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with: {repository: octo/example, run-id: 42}
      - uses: actions/upload-artifact@v4
        with: {name: workspace, path: ., include-hidden-files: true}
""",
    )

    assert main(["audit", str(workflow)]) == 0
    assert main(["audit", str(workflow), "--strict"]) == 1


def test_json_report_is_deterministic_and_has_evidence(tmp_path: Path, capsys, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    workflow = write_workflow(tmp_path / "broken.yml", BROKEN)
    monkeypatch.chdir(tmp_path)

    assert main(["audit", str(workflow), "--format", "json"]) == 1
    first = capsys.readouterr().out
    assert main(["audit", str(workflow), "--format", "json"]) == 1
    second = capsys.readouterr().out

    assert first == second
    report = json.loads(first)
    assert report["schema_version"] == "1.0"
    assert report["summary"]["errors"] == 2
    assert report["workflows"][0]["path"] == "broken.yml"
    assert report["workflows"][0]["findings"][0]["location"]["line"] > 0


def test_sarif_report_contains_rules_and_locations(tmp_path: Path, capsys, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    workflow = write_workflow(tmp_path / "broken.yml", BROKEN)
    monkeypatch.chdir(tmp_path)

    assert main(["audit", str(workflow), "--format", "sarif"]) == 1

    report = json.loads(capsys.readouterr().out)
    run = report["runs"][0]
    assert report["version"] == "2.1.0"
    assert {result["ruleId"] for result in run["results"]} == {"AFL004", "AFL005"}
    assert (
        run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        == "broken.yml"
    )


def test_output_file_receives_report(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workflow = write_workflow(tmp_path / "ci.yml", HEALTHY)
    output_path = tmp_path / "report.json"

    assert main(["audit", str(workflow), "--format", "json", "--output", str(output_path)]) == 0

    assert json.loads(output_path.read_text(encoding="utf-8"))["summary"]["flows"] == 1
    assert "Wrote json report" in capsys.readouterr().out


def test_invalid_input_exits_two_without_traceback(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workflow = write_workflow(tmp_path / "bad.yml", "jobs: [broken]\n")

    exit_code = main(["audit", str(workflow)])

    output = capsys.readouterr()
    assert exit_code == 2
    assert "artifactline: error:" in output.err
    assert "'jobs' must be a mapping" in output.err
    assert "Traceback" not in output.err


def test_terminal_escapes_control_characters(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workflow = write_workflow(
        tmp_path / "control.yml",
        """jobs:
  first:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with: {name: "bad\\e[31m", path: one}
  second:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with: {name: "bad\\e[31m", path: two}
""",
    )

    assert main(["audit", str(workflow)]) == 1

    output = capsys.readouterr().out
    assert "\x1b" not in output
    assert "\\x1b[31m" in output
