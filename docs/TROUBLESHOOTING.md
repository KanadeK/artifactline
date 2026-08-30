# Troubleshooting and repair flow

Start with the failing command. Fix its root cause, rerun that focused command,
then run the full release gate once.

## Exit 2: input or YAML failure

Run the smallest failing target:

```console
artifactline audit .github/workflows/ci.yml
```

The message includes the path and, for YAML syntax failures, the parser line
and column. Confirm the target exists, is UTF-8, has a mapping at `jobs:`, and
uses a list for each job's `steps:`. Artifactline does not accept files larger
than 2 MiB or scans above 200 workflow files.

## Exit 1: artifact contract failure

Read the stable `AFLnnn` ID and use [`RULES.md`](RULES.md). Repair the producer,
selector, policy, or job dependency; do not silence the finding by deleting the
test or weakening `--strict` without changing the intended contract.

For machine-readable evidence:

```console
artifactline audit .github/workflows/ci.yml --format json
artifactline audit .github/workflows/ci.yml --format sarif
```

## Windows uv cache error 183

Use a repository-local cache rather than the conflicting default cache:

```powershell
uv --cache-dir .uv-cache-artifactline sync --extra dev
uv --cache-dir .uv-cache-artifactline run python scripts/check.py
```

## Dependency audit cannot reach PyPI or OSV

Do not skip the audit or mark it green. Confirm the lockfile is unchanged, run
the same gate in a network-enabled environment, and keep the audit in CI. A
socket or DNS failure means the audit is unavailable, not that dependencies
are safe.

## Coverage, Ruff, or mypy fails

Run only the reported gate while repairing:

```console
uv run coverage run --branch -m pytest
uv run coverage report --fail-under=90
uv run ruff check src tests scripts
uv run mypy src
```

Add behavior tests for uncovered failure paths. Do not lower the 90% branch
threshold, disable a rule, add a broad type ignore, or skip a failing test to
cross the gate.

## Build or isolated wheel smoke fails

Remove only generated `dist/` and `.tmp/package-venv/`, rebuild, inspect the
archive contents, and install the wheel into a new virtual environment. The
source checkout passing is not evidence that the published package works.
