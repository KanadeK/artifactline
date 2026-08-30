from __future__ import annotations

from pathlib import Path

from artifactline.analyze import analyze_workflow
from artifactline.model import Severity
from artifactline.parser import parse_workflow_file


def analyze(tmp_path: Path, body: str):  # type: ignore[no-untyped-def]
    path = tmp_path / "workflow.yml"
    path.write_text(body, encoding="utf-8")
    return analyze_workflow(parse_workflow_file(path))


def rule_ids(result) -> list[str]:  # type: ignore[no-untyped-def]
    return [finding.rule_id for finding in result.findings]


def test_healthy_literal_handoff_builds_flow_without_findings(tmp_path: Path) -> None:
    result = analyze(
        tmp_path,
        """jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with:
          name: packages
          path: dist/*
          if-no-files-found: error
  publish:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with:
          name: packages
""",
    )

    assert result.findings == ()
    assert len(result.flows) == 1
    assert result.flows[0].producer.job_id == "build"
    assert result.flows[0].consumer.job_id == "publish"


def test_duplicate_static_upload_names_are_blocking(tmp_path: Path) -> None:
    result = analyze(
        tmp_path,
        """jobs:
  linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with: {name: dist, path: out/linux}
  windows:
    runs-on: windows-latest
    steps:
      - uses: actions/upload-artifact@v4
        with: {name: dist, path: out/windows}
""",
    )

    finding = next(item for item in result.findings if item.rule_id == "AFL001")
    assert finding.severity is Severity.ERROR
    assert "dist" in finding.message
    assert finding.related[0].line == 5


def test_matrix_name_must_reference_every_varying_axis(tmp_path: Path) -> None:
    result = analyze(
        tmp_path,
        """jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        python: [\"3.12\", \"3.13\"]
        channel: [stable]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/upload-artifact@v4
        with:
          name: dist-${{ matrix.os }}
          path: dist/*
""",
    )

    finding = next(item for item in result.findings if item.rule_id == "AFL002")
    assert "python" in finding.message
    assert "channel" not in finding.message


def test_missing_named_and_pattern_producers_are_reported(tmp_path: Path) -> None:
    result = analyze(
        tmp_path,
        """jobs:
  consume:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with: {name: missing}
      - uses: actions/download-artifact@v5
        with: {pattern: wheel-*}
""",
    )

    assert rule_ids(result).count("AFL003") == 2


def test_consumer_requires_producer_and_producer_must_run_first(tmp_path: Path) -> None:
    result = analyze(
        tmp_path,
        """jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with: {name: package, path: dist/*, if-no-files-found: error}
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with: {name: package}
  backwards:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with: {name: report}
      - uses: actions/upload-artifact@v4
        with: {name: report, path: report.xml, if-no-files-found: error}
""",
    )

    assert rule_ids(result).count("AFL004") == 2


def test_consumed_upload_must_fail_when_no_files_are_found(tmp_path: Path) -> None:
    result = analyze(
        tmp_path,
        """jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with: {name: used, path: dist/*}
      - uses: actions/upload-artifact@v4
        with: {name: unused, path: logs/*}
  publish:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with: {name: used}
""",
    )

    findings = [item for item in result.findings if item.rule_id == "AFL005"]
    assert len(findings) == 1
    assert "used" in findings[0].message


def test_broad_hidden_upload_and_download_all_are_warnings(tmp_path: Path) -> None:
    result = analyze(
        tmp_path,
        """jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with:
          name: workspace
          path: .
          include-hidden-files: true
  consume:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
""",
    )

    warnings = {item.rule_id: item for item in result.findings}
    assert warnings["AFL006"].severity is Severity.WARNING
    assert warnings["AFL007"].severity is Severity.WARNING


def test_dynamic_names_report_uncertainty_instead_of_missing_producer(tmp_path: Path) -> None:
    result = analyze(
        tmp_path,
        """jobs:
  build:
    strategy:
      matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with:
          name: dist-${{ matrix.os }}
          path: dist/*
  consume:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with:
          pattern: dist-*
""",
    )

    assert "AFL008" in rule_ids(result)
    assert "AFL003" not in rule_ids(result)


def test_external_download_is_outside_local_contract(tmp_path: Path) -> None:
    result = analyze(
        tmp_path,
        """jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with:
          name: package
          repository: octo/example
          run-id: 42
""",
    )

    assert result.findings == ()
    assert result.flows == ()
