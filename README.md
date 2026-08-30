# Artifactline

Audit GitHub Actions artifact handoffs before workflows run.

Artifactline answers a question syntax linters cannot: **will the file a later
job downloads actually be produced, uniquely named, and available when that
job starts?** It reads workflow YAML, builds an artifact producer/consumer
graph, and reports the exact job edge or upload policy that breaks the handoff.

It is local-first and read-only. It never contacts GitHub, evaluates arbitrary
expressions, starts a runner, fetches an action, or executes a `run:` step.

## What it catches

- Two jobs uploading the same immutable artifact name.
- Matrix uploads whose name omits a varying axis.
- Named or patterned downloads with no producer.
- Consumers missing a transitive `needs` edge to their producer.
- Consumed uploads that only warn or ignore when no files exist.
- Repository-wide hidden-file uploads that may include private configuration.
- Download-all steps whose contract silently expands as producers are added.
- Dynamic expressions that prevent a conclusive offline result.

## Install

Python 3.11 or newer is required.

```console
python -m pip install artifactline-0.1.0-py3-none-any.whl
```

Download the wheel from the
[`v0.1.0` GitHub Release](https://github.com/KanadeK/artifactline/releases/tag/v0.1.0),
or install a checkout for development:

```console
git clone https://github.com/KanadeK/artifactline.git
cd artifactline
python -m pip install -e .
```

## Quick start

Audit a repository, its workflow directory, or one workflow file:

```console
artifactline audit .
artifactline audit .github/workflows
artifactline audit .github/workflows/release.yml
```

A healthy handoff is shown as a real data-flow edge:

```text
Artifactline 0.1.0

healthy.yml
  FLOW build -> publish: package

Summary: 0 errors, 0 warnings, 1 flow
```

The deliberately broken example exercises independent failure paths:

```console
artifactline audit examples/broken.yml
# exits 1

artifactline audit examples/broken.yml --format json --output artifacts/broken.json
artifactline audit examples/broken.yml --format sarif --output artifacts/broken.sarif
```

Exit codes are stable:

| Code | Meaning |
| ---: | --- |
| 0 | Analysis completed with no errors |
| 1 | At least one error, or a warning under `--strict` |
| 2 | Input, YAML, arguments, or output could not be processed |

## GitHub Action

After checkout, the composite action runs the same offline engine and can emit
SARIF for code scanning:

```yaml
- uses: actions/checkout@v4
- uses: KanadeK/artifactline@v0.1.0
  with:
    path: .github/workflows
    format: sarif
    output: artifactline.sarif
    strict: "true"
```

The action itself does not upload SARIF or request write permissions. That
choice remains in the consuming workflow.

## Rules and boundaries

Rule IDs and repairs are documented in [`docs/RULES.md`](docs/RULES.md).
Artifactline complements rather than replaces
[actionlint](https://github.com/rhysd/actionlint),
[zizmor](https://github.com/zizmorcore/zizmor), or
[MatrixBeacon](https://github.com/KanadeK/matrixbeacon). It deliberately does
not execute workflows, inspect remote runs, resolve reusable workflows, or
pretend runtime expressions have known values. See
[`docs/RESEARCH.md`](docs/RESEARCH.md) for the competitor boundary.

## Development and acceptance

```console
uv sync --extra dev
uv run python scripts/check.py
```

The release gate runs branch coverage (minimum 90%), Ruff, strict mypy,
dependency audit, acceptance examples, wheel/sdist builds, archive inspection,
and an isolated wheel smoke test. If a command fails, follow the focused repair
map in [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md), then rerun the full
gate once the root cause is fixed.

The executable contract is in [`SPEC.md`](SPEC.md). Artifactline is an alpha:
warnings describe uncertainty or policy risk; absence of a finding is not proof
that a workflow is safe or that its generated paths exist at runtime.

## License

MIT. See [`LICENSE`](LICENSE).
