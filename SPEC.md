# Spec: Artifactline

## Assumptions

1. The first release is an offline Python CLI and composite GitHub Action, not a hosted service.
2. GitHub Actions workflow YAML is untrusted input and must never be executed.
3. Version 0.1 analyzes artifact flow inside one workflow file. Cross-workflow and remote-run downloads are identified as external boundaries, not guessed.
4. Static analysis may report uncertainty for runtime expressions and reusable workflows; it must not invent resolved values.
5. The user delegated product choice and delivery, so this written contract is the approval gate for implementation.

## Objective

Artifactline finds broken and risky data flow through `actions/upload-artifact` and `actions/download-artifact` before a workflow runs. It is for maintainers whose build, test, or release jobs exchange artifacts and who need an explainable answer to four questions:

- Which job produces each artifact?
- Which job consumes it?
- Can the consumer actually run after the producer?
- Can matrix expansion, default names, or broad hidden-file uploads make the handoff fail or leak data?

The first release must turn a workflow into a producer-consumer model, emit stable findings, and return CI-friendly exit codes.

## Tech Stack

- Python 3.11+
- PyYAML 6.x with a safe loader adjusted for GitHub's YAML scalar rules
- Standard-library analysis, rendering, glob matching, JSON, and CLI
- pytest, coverage, Ruff, strict mypy, build, and pip-audit for development gates
- Hatchling for wheel and source-distribution builds

## Commands

```console
uv sync --extra dev
uv run artifactline audit .github/workflows
uv run artifactline audit examples/broken.yml --format json --output artifacts/broken.json
uv run artifactline audit examples/broken.yml --format sarif --output artifacts/broken.sarif
uv run python scripts/check.py
```

Exit codes:

- `0`: analysis completed with no blocking findings
- `1`: at least one error finding, or a warning under `--strict`
- `2`: invalid arguments, unreadable/invalid input, unsupported top-level shape, or output failure

## Project Structure

```text
src/artifactline/       package, parser, model, analyzer, renderers, CLI
tests/                  unit, integration, and command-line tests
examples/               healthy and deliberately broken workflows
docs/                   rule reference, research boundary, troubleshooting
scripts/check.py        release-equivalent local gate
.github/workflows/      cross-platform CI and tag-driven release
tasks/                  implementation plan and completion checklist
```

## Code Style

Use immutable data models, explicit result types, and direct control flow. Boundary validation belongs in the parser; the analyzer consumes validated models.

```python
def analyze_workflow(workflow: Workflow) -> Analysis:
    uploads = tuple(step for job in workflow.jobs for step in job.uploads)
    findings = find_duplicate_upload_names(workflow, uploads)
    return Analysis(workflow=workflow, findings=tuple(sorted(findings)))
```

No framework abstraction, plugin system, network client, auto-fix engine, or expression evaluator belongs in version 0.1.

## Testing Strategy

- Unit tests: GitHub YAML parsing, `needs` closure, matrix-axis references, artifact matching, and stable rule ordering.
- Integration tests: healthy/broken workflow analysis and terminal/JSON/SARIF rendering.
- CLI tests: exit `0`, `1`, and `2`; strict warning behavior; output-file handling.
- Release gate: branch coverage at least 90%, Ruff, strict mypy, dependency audit, build, archive inspection, and isolated wheel execution.
- CI: Windows and Ubuntu across supported Python versions.

Tests assert outcomes and rule IDs, never internal call order. Every behavioral slice starts with a failing test.

## Threat Model

Trust boundary: local workflow YAML and command-line paths are attacker-controlled data.

- YAML is parsed with a safe loader; tags cannot instantiate Python objects.
- Input files are capped at 2 MiB and repository scans at 200 workflow files to bound resource use.
- Workflow `run:` commands and referenced actions are never executed or fetched.
- Artifact names, paths, and expressions are rendered as text, never passed to a shell or interpreted as markup.
- Output is written only to the explicit path supplied by the user.
- The program stores no credentials, contacts no service, and records no telemetry.

Primary abuse cases are YAML object construction, alias/resource bombs, path confusion, terminal escape injection, and accidental leakage caused by `include-hidden-files: true` with a broad upload path. Tests must cover the applicable boundaries.

## Boundaries

- Always: validate external input once, fail fast on malformed workflow structure, preserve deterministic output, test error paths, and keep analysis read-only.
- Ask first: expanding scope to remote GitHub API access, workflow execution, automatic edits, or new credential handling.
- Never: execute workflow steps, evaluate arbitrary expressions, silently treat dynamic values as static, commit secrets, weaken tests to pass a gate, or claim that absence of a finding proves a workflow safe.

## Supported Findings

- `AFL001 duplicate-upload-name`: two statically known uploads can create the same immutable artifact name.
- `AFL002 matrix-name-collision`: a matrix upload name omits one or more static matrix axes.
- `AFL003 missing-producer`: a local named/pattern download has no matching upload.
- `AFL004 missing-needs-edge`: a consumer does not transitively depend on the matching producer job.
- `AFL005 producer-may-be-empty`: a consumed upload keeps `if-no-files-found: warn` or `ignore`.
- `AFL006 broad-hidden-upload`: hidden files are enabled for a repository-wide or recursive path.
- `AFL007 ambiguous-download-all`: a download without `name` or `pattern` can consume an evolving artifact set.
- `AFL008 dynamic-artifact-flow`: a runtime expression prevents a conclusive static handoff result.

## Success Criteria

- Healthy example exits `0`; broken example exits `1` and demonstrates at least five independent failures.
- Invalid YAML and invalid workflow structure exit `2` with actionable repair text and no traceback.
- JSON and SARIF output are deterministic and contain file/line evidence.
- The analyzer never starts a subprocess, contacts a network, or executes workflow content.
- Full local gate and Windows/Linux CI pass without skipped tests and with at least 90% branch coverage.
- Wheel and source distribution install and run in an isolated environment.
- Public `v0.1.0` GitHub Release contains the wheel, source distribution, and checksum manifest, and a downloaded wheel passes a fresh-install smoke test.
- Only the intended GitHub account appears in contributor evidence, then a Gmail completion notice is sent to the account owner.

## Open Questions

None block version 0.1. Runtime matrix values, reusable workflows, cross-workflow artifacts, and automatic fixes are explicit non-goals rather than deferred hidden behavior.
