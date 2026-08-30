# Artifactline

Audit GitHub Actions artifact handoffs before workflows run.

Artifactline builds a read-only producer/consumer model from workflow YAML and
finds immutable artifact-name collisions, missing producers, missing `needs`
edges, consumed uploads that may be empty, broad hidden-file uploads, and
dynamic handoffs that cannot be proven offline.

The project is under active development toward `v0.1.0`. The executable
contract, supported findings, and acceptance criteria are defined in
[`SPEC.md`](SPEC.md).
