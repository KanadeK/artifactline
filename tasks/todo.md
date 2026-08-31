# Artifactline v0.1.0 task list

## Task 1: Package and boundary models

- [x] Add package metadata, immutable models, and workflow discovery.
- Acceptance: files/directories resolve deterministically; unsafe size/count inputs fail.
- Verify: focused model/discovery tests.
- Files: `pyproject.toml`, `src/artifactline/model.py`, `src/artifactline/parser.py`, `tests/test_parser.py`.

## Task 2: Parse artifact actions

- [x] Parse jobs, transitive inputs, needs, static matrix axis names, action inputs, and source lines.
- Acceptance: GitHub `on:` remains a string key; dynamic values are explicit.
- Verify: parser tests cover healthy, malformed, matrix, and dynamic workflows.
- Files: `src/artifactline/parser.py`, `tests/test_parser.py`, `examples/healthy.yml`, `examples/broken.yml`.

## Task 3: Core graph and collision rules

- [x] Build artifact producer/consumer graph and implement `AFL001` to `AFL004`.
- Acceptance: duplicate names, incomplete matrix names, missing producers, and missing needs edges are proven from models.
- Verify: focused analysis tests start red and finish green.
- Files: `src/artifactline/analyze.py`, `src/artifactline/model.py`, `tests/test_analyze.py`.

## Task 4: Policy and uncertainty rules

- [x] Implement `AFL005` to `AFL008`.
- Acceptance: consumed warn/ignore uploads, broad hidden paths, download-all, and dynamic flows are distinguished by severity.
- Verify: focused tests cover each rule and false-positive boundary.
- Files: `src/artifactline/analyze.py`, `tests/test_analyze.py`, `docs/RULES.md`.

## Task 5: Reports and CLI

- [x] Add terminal, JSON, SARIF, output files, strict mode, and stable exit codes.
- Acceptance: healthy=`0`, findings=`1`, invalid input=`2`; reports are deterministic and line-addressable.
- Verify: integration/CLI tests and example commands.
- Files: `src/artifactline/render.py`, `src/artifactline/cli.py`, `src/artifactline/__main__.py`, `tests/test_cli.py`.

## Task 6: Release engineering

- [x] Add README, troubleshooting, CI, composite action, release workflow, changelog, and gate script.
- Acceptance: cross-platform CI and local release gate include coverage, lint, types, audit, build, archive inspection, and isolated install.
- Verify: `uv run python scripts/check.py`.
- Files are split into documentation and automation increments of no more than five files each.

## Task 7: Publish and notify

- [x] Review all changes across correctness, simplicity, architecture, security, and performance.
- [x] Create public repository, push `main`, wait for CI, tag `v0.1.0`, and verify non-draft Release assets.
- [x] Download the public wheel, install in a fresh environment, run healthy/broken smoke tests, and verify contributors.
- [x] Send the owner a Gmail completion notice with repository, release, verification, and failure-repair commands.
