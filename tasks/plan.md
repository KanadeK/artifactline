# Implementation Plan: Artifactline v0.1.0

## Overview

Build a read-only Python CLI and composite GitHub Action that statically models artifact uploads/downloads inside GitHub Actions workflows, detects broken handoffs and risky upload policies, and emits terminal, JSON, and SARIF reports.

## Architecture Decisions

- Parse once at the system boundary into immutable typed models; analysis never consumes raw YAML.
- Recognize only first-party upload/download actions and explicit supported inputs.
- Treat runtime expressions as uncertainty and emit `AFL008` instead of guessing.
- Model transitive `needs` reachability because artifact availability is a graph property.
- Keep v0.1 offline and read-only; no API, runner, shell, or auto-fix path.

## Dependency Graph

```text
safe YAML parser
    -> typed workflow/jobs/steps
        -> producer/consumer graph
            -> rule findings
                -> terminal / JSON / SARIF
                    -> CLI exit policy
```

## Phase 1: Foundation

- Task 1: Initialize packaging, immutable models, and safe workflow discovery.
- Task 2: Parse jobs, needs, static matrix axes, and artifact action inputs.

Checkpoint: parser tests, lint, and strict types pass.

## Phase 2: Core analysis

- Task 3: Build producer/consumer graph and duplicate/matrix collision rules.
- Task 4: Add missing producer, missing needs, consumed-empty, hidden upload, download-all, and dynamic-flow rules.

Checkpoint: healthy/broken examples prove the complete input -> analysis path.

## Phase 3: Delivery

- Task 5: Add deterministic terminal, JSON, and SARIF renderers plus CLI exit behavior.
- Task 6: Add documentation, composite action, cross-platform CI, release workflow, and release-equivalent gate.
- Task 7: Independent five-axis review, repair findings, package, publish, verify, and notify.

Checkpoint: all success criteria in `SPEC.md` pass.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| GitHub expressions cannot be fully resolved offline | False certainty | Emit `AFL008`; do not guess |
| YAML 1.1 parses `on` as boolean | Broken workflow structure | GitHub-compatible scalar resolver and regression test |
| Matrix analysis drifts into MatrixBeacon scope | Product duplication | Inspect only declared axis names needed for artifact uniqueness |
| Findings become noisy | Users ignore the tool | Block only provable errors; keep uncertainty and broad policies as warnings |
| Malicious YAML consumes resources or emits terminal controls | Local denial/leak | File/count caps, safe loader, output sanitization |
| Release succeeds remotely after a local timeout | Duplicate writes | Inspect tag/release/assets before retrying creation |

## Open Questions

None for v0.1.0.
