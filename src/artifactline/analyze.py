from __future__ import annotations

import re
from collections import defaultdict
from fnmatch import fnmatchcase

from artifactline.model import (
    Analysis,
    ArtifactFlow,
    Download,
    Finding,
    Job,
    Severity,
    Upload,
    Workflow,
)

_EXPRESSION = re.compile(r"\$\{\{.*?\}\}")


def analyze_workflow(workflow: Workflow) -> Analysis:
    findings: list[Finding] = []
    flows: list[ArtifactFlow] = []
    jobs = {job.job_id: job for job in workflow.jobs}
    uploads = tuple(upload for job in workflow.jobs for upload in job.uploads)
    downloads = tuple(download for job in workflow.jobs for download in job.downloads)

    findings.extend(_duplicate_upload_findings(uploads))
    for job in workflow.jobs:
        findings.extend(_matrix_findings(job))
    for upload in uploads:
        hidden_finding = _broad_hidden_upload_finding(upload)
        if hidden_finding is not None:
            findings.append(hidden_finding)

    static_uploads = tuple(upload for upload in uploads if not _has_expression(upload.name))
    dynamic_uploads = tuple(upload for upload in uploads if _has_expression(upload.name))
    for download in downloads:
        if download.external:
            continue
        matches, download_findings = _match_download(download, static_uploads, dynamic_uploads)
        findings.extend(download_findings)
        for upload in matches:
            flows.append(ArtifactFlow(producer=upload, consumer=download))
            availability = _availability_finding(upload, download, jobs)
            if availability is not None:
                findings.append(availability)
            if upload.if_no_files_found != "error":
                findings.append(
                    Finding(
                        rule_id="AFL005",
                        severity=Severity.ERROR,
                        message=(
                            f"Consumed artifact '{upload.name}' may not be created because "
                            f"if-no-files-found is '{upload.if_no_files_found}'."
                        ),
                        location=upload.location,
                        evidence=(f"consumer job: {download.job_id}",),
                        related=(download.location,),
                    )
                )

    return Analysis(
        workflow=workflow,
        findings=_ordered_unique_findings(findings),
        flows=tuple(
            sorted(
                flows,
                key=lambda flow: (
                    flow.producer.job_id,
                    flow.producer.step_index,
                    flow.consumer.job_id,
                    flow.consumer.step_index,
                ),
            )
        ),
    )


def _duplicate_upload_findings(uploads: tuple[Upload, ...]) -> list[Finding]:
    by_name: defaultdict[str, list[Upload]] = defaultdict(list)
    for upload in uploads:
        if not _has_expression(upload.name):
            by_name[upload.name].append(upload)

    findings: list[Finding] = []
    for name, same_name in sorted(by_name.items()):
        if len(same_name) < 2:
            continue
        first, *duplicates = same_name
        for duplicate in duplicates:
            findings.append(
                Finding(
                    rule_id="AFL001",
                    severity=Severity.ERROR,
                    message=(
                        f"Artifact name '{name}' is uploaded more than once; immutable "
                        "artifacts require a unique name per workflow run."
                    ),
                    location=duplicate.location,
                    evidence=(
                        f"first producer job: {first.job_id}",
                        f"duplicate producer job: {duplicate.job_id}",
                    ),
                    related=(first.location,),
                )
            )
    return findings


def _matrix_findings(job: Job) -> list[Finding]:
    findings: list[Finding] = []
    varying_axes = tuple(axis.name for axis in job.matrix if len(axis.values) > 1)
    for upload in job.uploads:
        missing = tuple(
            axis for axis in varying_axes if not _references_matrix_axis(upload.name, axis)
        )
        if missing:
            findings.append(
                Finding(
                    rule_id="AFL002",
                    severity=Severity.ERROR,
                    message=(
                        f"Artifact name '{upload.name}' omits varying matrix "
                        f"axis/axes: {', '.join(missing)}."
                    ),
                    location=upload.location,
                    evidence=(f"matrix job: {job.job_id}",),
                )
            )
        if job.dynamic_matrix or _has_expression(upload.name):
            findings.append(
                Finding(
                    rule_id="AFL008",
                    severity=Severity.WARNING,
                    message=(
                        f"Artifact name '{upload.name}' contains runtime artifact flow "
                        "that cannot be fully resolved offline."
                    ),
                    location=upload.location,
                    evidence=(f"producer job: {job.job_id}",),
                )
            )
    return findings


def _broad_hidden_upload_finding(upload: Upload) -> Finding | None:
    if not upload.include_hidden_files or not any(_is_broad_path(path) for path in upload.paths):
        return None
    return Finding(
        rule_id="AFL006",
        severity=Severity.WARNING,
        message=(
            f"Artifact '{upload.name}' enables hidden files for a repository-wide path; "
            "credentials and private configuration may be included."
        ),
        location=upload.location,
        evidence=tuple(f"path: {path}" for path in upload.paths),
    )


def _match_download(
    download: Download,
    static_uploads: tuple[Upload, ...],
    dynamic_uploads: tuple[Upload, ...],
) -> tuple[tuple[Upload, ...], list[Finding]]:
    if download.name is None and download.pattern is None:
        return static_uploads, [
            Finding(
                rule_id="AFL007",
                severity=Severity.WARNING,
                message=(
                    "Download has no name or pattern and will consume the workflow's "
                    "entire evolving artifact set."
                ),
                location=download.location,
                evidence=(f"consumer job: {download.job_id}",),
            )
        ]

    selector = download.name if download.name is not None else download.pattern
    assert selector is not None
    if _has_expression(selector):
        return (), [_dynamic_download_finding(download, selector)]

    if download.name is not None:
        matches = tuple(upload for upload in static_uploads if upload.name == download.name)
    else:
        matches = tuple(upload for upload in static_uploads if fnmatchcase(upload.name, selector))
    if matches:
        return matches, []
    if dynamic_uploads:
        return (), [_dynamic_download_finding(download, selector)]
    return (), [
        Finding(
            rule_id="AFL003",
            severity=Severity.ERROR,
            message=f"Download selector '{selector}' has no matching local artifact producer.",
            location=download.location,
            evidence=(f"consumer job: {download.job_id}",),
        )
    ]


def _dynamic_download_finding(download: Download, selector: str) -> Finding:
    return Finding(
        rule_id="AFL008",
        severity=Severity.WARNING,
        message=(
            f"Download selector '{selector}' cannot be conclusively matched because the "
            "handoff contains runtime expressions."
        ),
        location=download.location,
        evidence=(f"consumer job: {download.job_id}",),
    )


def _availability_finding(
    upload: Upload,
    download: Download,
    jobs: dict[str, Job],
) -> Finding | None:
    if upload.job_id == download.job_id:
        if upload.step_index < download.step_index:
            return None
        reason = "the upload step occurs after the download step in the same job"
    elif upload.job_id not in _transitive_needs(jobs[download.job_id], jobs):
        reason = f"consumer job '{download.job_id}' does not depend on producer '{upload.job_id}'"
    else:
        return None
    return Finding(
        rule_id="AFL004",
        severity=Severity.ERROR,
        message=f"Artifact '{upload.name}' is unavailable: {reason}.",
        location=download.location,
        evidence=(f"producer job: {upload.job_id}", f"consumer job: {download.job_id}"),
        related=(upload.location,),
    )


def _transitive_needs(job: Job, jobs: dict[str, Job]) -> frozenset[str]:
    seen: set[str] = set()
    pending = list(job.needs)
    while pending:
        dependency = pending.pop()
        if dependency in seen:
            continue
        seen.add(dependency)
        dependency_job = jobs.get(dependency)
        if dependency_job is not None:
            pending.extend(dependency_job.needs)
    return frozenset(seen)


def _references_matrix_axis(template: str, axis: str) -> bool:
    escaped = re.escape(axis)
    return (
        re.search(
            rf"matrix\s*(?:\.\s*{escaped}\b|\[\s*['\"]{escaped}['\"]\s*\])",
            template,
        )
        is not None
    )


def _has_expression(value: str) -> bool:
    return _EXPRESSION.search(value) is not None


def _is_broad_path(value: str) -> bool:
    normalized = value.strip().replace("\\", "/").rstrip("/")
    return normalized in {"", ".", "**", "**/*", "./**", "./**/*"} or normalized.startswith("**/")


def _ordered_unique_findings(findings: list[Finding]) -> tuple[Finding, ...]:
    unique: dict[tuple[str, str, int, str], Finding] = {}
    for finding in findings:
        key = (
            finding.rule_id,
            finding.location.path.as_posix(),
            finding.location.line,
            finding.message,
        )
        unique[key] = finding
    return tuple(
        sorted(
            unique.values(),
            key=lambda finding: (
                finding.location.path.as_posix(),
                finding.location.line,
                finding.rule_id,
                finding.message,
            ),
        )
    )
