# Research and differentiation

Research was performed on 2026-08-30 before implementation.

## Problem evidence

GitHub documents artifact handoffs as a job data-flow mechanism and says consumers should depend on producers through `needs`. The upload action also documents that artifact names are immutable, matrix jobs need unique names, hidden-file uploads can expose sensitive content, and missing paths warn by default.

- [GitHub: store and share data with workflow artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data)
- [actions/upload-artifact](https://github.com/actions/upload-artifact)
- [actions/download-artifact](https://github.com/actions/download-artifact)

These constraints interact across jobs and matrix dimensions, but official documentation presents them as configuration rules and examples rather than one pre-run artifact-flow audit.

## Adjacent tools

- [actionlint](https://github.com/rhysd/actionlint) validates GitHub Actions syntax, expressions, and embedded scripts. Its usage documentation does not describe producer-consumer artifact modeling.
- [zizmor](https://github.com/zizmorcore/zizmor) audits GitHub Actions security. Its artifact references appear in broader credential and permissions rules rather than an artifact dependency graph.
- [MatrixBeacon](https://github.com/KanadeK/matrixbeacon) expands and audits static matrices. Artifactline does not duplicate its general matrix coverage checks; it only reads declared axis names to prove whether an artifact name distinguishes matrix variants.

Repository and code searches combined terms such as `upload-artifact`, `download-artifact`, `needs`, `matrix collision`, `artifact contract`, and `artifact graph`. No representative open-source project found in that pass combined immutable-name collision checks, producer/consumer dependency validation, missing-file policy, and broad hidden-upload checks into one offline CLI. This is evidence of differentiation, not proof that no similar repository exists anywhere.

## Product boundary

Artifactline is intentionally narrow:

```text
workflow YAML -> artifact producer/consumer graph -> explainable findings + CI reports
```

It does not run Actions locally, replace actionlint or zizmor, inspect remote workflow runs, or promise complete GitHub expression evaluation.
