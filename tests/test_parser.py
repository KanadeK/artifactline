from __future__ import annotations

from pathlib import Path

import pytest

import artifactline.parser as parser_module
from artifactline.parser import InputError, discover_workflows, parse_workflow_file


def write_workflow(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_discovers_repo_workflows_in_stable_order(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    second = write_workflow(workflows / "z-release.yaml", "jobs: {}\n")
    first = write_workflow(workflows / "a-ci.yml", "jobs: {}\n")
    write_workflow(workflows / "notes.txt", "not a workflow\n")

    assert discover_workflows(tmp_path) == (first.resolve(), second.resolve())


def test_parses_github_on_key_jobs_matrix_and_artifact_steps(tmp_path: Path) -> None:
    workflow_path = write_workflow(
        tmp_path / "ci.yml",
        """name: CI
on: [push]
jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        python: [\"3.12\", \"3.13\"]
        include:
          - os: ubuntu-latest
            python: \"3.13\"
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/upload-artifact@v4
        with:
          name: dist-${{ matrix.os }}
          path: |
            dist/*.whl
            dist/*.tar.gz
          include-hidden-files: false
  publish:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with:
          pattern: dist-*
          merge-multiple: true
""",
    )

    workflow = parse_workflow_file(workflow_path)

    assert workflow.path == workflow_path.resolve()
    assert tuple(job.job_id for job in workflow.jobs) == ("build", "publish")
    build, publish = workflow.jobs
    assert build.matrix_axes == ("os", "python")
    assert build.dynamic_matrix is False
    assert build.uploads[0].name == "dist-${{ matrix.os }}"
    assert build.uploads[0].paths == ("dist/*.whl", "dist/*.tar.gz")
    assert build.uploads[0].include_hidden_files is False
    assert build.uploads[0].location.line == 14
    assert publish.needs == ("build",)
    assert publish.downloads[0].pattern == "dist-*"
    assert publish.downloads[0].merge_multiple is True
    assert publish.downloads[0].location.line == 25


def test_marks_runtime_matrix_and_external_download_boundary(tmp_path: Path) -> None:
    workflow_path = write_workflow(
        tmp_path / "dynamic.yml",
        """jobs:
  build:
    strategy:
      matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}
    runs-on: ubuntu-latest
    steps: []
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v5
        with:
          name: dist
          repository: octo/example
          run-id: ${{ inputs.run_id }}
""",
    )

    workflow = parse_workflow_file(workflow_path)

    assert workflow.jobs[0].dynamic_matrix is True
    assert workflow.jobs[0].matrix_axes == ()
    assert workflow.jobs[1].downloads[0].external is True


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("jobs: [not-a-map]\n", "'jobs' must be a mapping"),
        ("jobs:\n  build:\n    steps: nope\n", "steps must be a list"),
        ("jobs: {\n", "invalid YAML"),
    ],
)
def test_rejects_malformed_workflow(tmp_path: Path, body: str, message: str) -> None:
    workflow_path = write_workflow(tmp_path / "bad.yml", body)

    with pytest.raises(InputError, match=message):
        parse_workflow_file(workflow_path)


def test_rejects_workflow_larger_than_boundary(tmp_path: Path) -> None:
    workflow_path = write_workflow(tmp_path / "huge.yml", "#" + ("x" * (2 * 1024 * 1024)))

    with pytest.raises(InputError, match="exceeds the 2 MiB limit"):
        parse_workflow_file(workflow_path)


def test_discovery_reports_missing_empty_and_over_limit_inputs(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(InputError, match="input does not exist"):
        discover_workflows(tmp_path / "missing")
    with pytest.raises(InputError, match="no .yml or .yaml"):
        discover_workflows(tmp_path)

    write_workflow(tmp_path / "a.yml", "jobs: {}\n")
    write_workflow(tmp_path / "b.yml", "jobs: {}\n")
    monkeypatch.setattr(parser_module, "MAX_WORKFLOW_FILES", 1)
    with pytest.raises(InputError, match="scan limit is 1"):
        discover_workflows(tmp_path)


def test_rejects_non_utf8_and_nul_bytes(tmp_path: Path) -> None:
    non_utf8 = tmp_path / "bytes.yml"
    non_utf8.write_bytes(b"jobs: {}\n\xff")
    with pytest.raises(InputError, match="as UTF-8"):
        parse_workflow_file(non_utf8)

    nul = tmp_path / "nul.yml"
    nul.write_bytes(b"jobs: {}\n\x00")
    with pytest.raises(InputError, match="contains a NUL byte"):
        parse_workflow_file(nul)


def test_empty_document_and_non_action_step_are_valid(tmp_path: Path) -> None:
    empty = write_workflow(tmp_path / "empty.yml", "")
    assert parse_workflow_file(empty).jobs == ()

    run_only = write_workflow(
        tmp_path / "run.yml",
        """jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
""",
    )
    job = parse_workflow_file(run_only).jobs[0]
    assert job.uploads == ()
    assert job.downloads == ()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("jobs:\n  1: {}\n", "workflow 'jobs' keys must be strings"),
        ("jobs:\n  test:\n    steps: [not-a-map]\n", "step 1 must be a mapping"),
        ("jobs:\n  test:\n    needs: [build, 3]\n", "needs must be a string or list"),
        ("jobs:\n  test:\n    strategy: dynamic\n", "strategy must be a mapping"),
    ],
)
def test_rejects_invalid_job_boundaries(tmp_path: Path, body: str, message: str) -> None:
    workflow = write_workflow(tmp_path / "invalid-job.yml", body)
    with pytest.raises(InputError, match=message):
        parse_workflow_file(workflow)


def test_parses_scalar_inputs_and_marks_dynamic_axis(tmp_path: Path) -> None:
    workflow = write_workflow(
        tmp_path / "scalars.yml",
        """jobs:
  build:
    strategy:
      matrix:
        os: ${{ fromJSON(inputs.os) }}
        flavor: [true, 3]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with:
          name: 7
          include-hidden-files: "true"
""",
    )

    job = parse_workflow_file(workflow).jobs[0]
    assert job.dynamic_matrix is True
    assert job.matrix[0].values == ("true", "3")
    assert job.uploads[0].name == "7"
    assert job.uploads[0].paths == ()
    assert job.uploads[0].include_hidden_files is True


def test_action_location_supports_named_steps(tmp_path: Path) -> None:
    workflow = write_workflow(
        tmp_path / "named-step.yml",
        """jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Upload package
        uses: actions/upload-artifact@v4
        with:
          name: package
""",
    )

    upload = parse_workflow_file(workflow).jobs[0].uploads[0]

    assert upload.location.line == 6


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            """jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with: {include-hidden-files: yes}
""",
            "must be true or false",
        ),
        (
            """jobs:
  build:
    strategy:
      matrix:
        os: [{name: ubuntu}]
    runs-on: ubuntu-latest
    steps: []
""",
            "matrix values must be scalar",
        ),
    ],
)
def test_rejects_invalid_action_and_matrix_scalars(tmp_path: Path, body: str, message: str) -> None:
    workflow = write_workflow(tmp_path / "invalid-scalar.yml", body)
    with pytest.raises(InputError, match=message):
        parse_workflow_file(workflow)
