from __future__ import annotations

from pathlib import Path

import pytest

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
