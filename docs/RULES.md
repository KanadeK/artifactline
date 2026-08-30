# Artifactline rules

Errors exit `1`. Warnings exit `0` unless `--strict` is enabled. Every result
contains a stable rule ID, source line, and evidence fields suitable for CI.

## AFL001

### Duplicate upload name

Two statically known uploads use the same artifact name. Modern
`actions/upload-artifact` artifacts are immutable within a workflow run, so
the later upload conflicts instead of appending safely.

Repair: add the distinguishing platform, job, or variant to each name and use
the same exact name or pattern in its consumers.

## AFL002

### Matrix name collision

An upload runs in a matrix but its name omits at least one axis with multiple
values. Jobs that differ only on the omitted axis can upload the same name.

Repair: include every varying axis, for example
`package-${{ matrix.os }}-${{ matrix.python }}`. A single-valued axis is not
required because it cannot create a collision in that workflow definition.

## AFL003

### Missing producer

A local named or patterned download has no statically matching upload.

Repair: correct the selector or add the intended producer. If the artifact
comes from another run or repository, declare the official `repository` and
`run-id` inputs so Artifactline treats it as an external boundary.

## AFL004

### Missing needs edge

A consumer job does not transitively depend on its producer, or a same-job
download appears before the upload step.

Repair: add the producer to `needs` (directly or through a valid dependency
chain), or reorder same-job steps so upload precedes download.

## AFL005

### Producer may be empty

A downstream job consumes an upload whose `if-no-files-found` policy is the
default `warn` or explicit `ignore`. The producer can succeed without creating
the artifact, leaving the consumer to fail later with less context.

Repair: set `if-no-files-found: error` on every upload that is a required input
to another job.

## AFL006

### Broad hidden upload

`include-hidden-files: true` is combined with `.` or a repository-wide glob.
This can package hidden configuration, credentials, or tool state.

Repair: upload a narrow generated directory or explicit file list. Keep hidden
files disabled unless the artifact contract names and reviews them.

## AFL007

### Ambiguous download all

A download has neither `name` nor `pattern`, so every artifact in the run is
part of its contract. Adding an unrelated producer silently changes the files
the consumer receives.

Repair: use an exact `name` or a deliberate `pattern`; set `merge-multiple`
explicitly when matching more than one artifact.

## AFL008

### Dynamic artifact flow

A runtime expression or dynamic matrix prevents a conclusive offline match.
Artifactline reports uncertainty instead of inventing values.

Repair: when practical, keep artifact names and selectors derived from the
same visible matrix axes. Otherwise review the runtime producer/consumer
contract and use `--strict` if unresolved flow must block CI.
