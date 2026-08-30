# Contributing

Artifactline changes should preserve its offline, read-only contract and keep
each finding tied to concrete workflow evidence.

## Development

1. Install Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).
2. Run `uv sync --extra dev`.
3. Add a failing test for any behavior change.
4. Make the smallest complete change that fixes the producer/consumer model.
5. Run `uv run python scripts/check.py` before opening a pull request.

New rules need a stable rule ID, focused tests for healthy and broken paths,
terminal/JSON/SARIF output, and an entry in `docs/RULES.md`. Runtime-dependent
cases must report uncertainty instead of guessing a workflow result.

## Scope

Please keep proposals within first-party `actions/upload-artifact` and
`actions/download-artifact` data flow unless an issue first establishes a new
boundary. Artifactline does not execute workflows or replace general syntax and
security analyzers.
