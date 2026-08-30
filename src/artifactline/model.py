from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SourceLocation:
    path: Path
    line: int
    column: int = 1


@dataclass(frozen=True, slots=True)
class MatrixAxis:
    name: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Upload:
    job_id: str
    step_index: int
    action: str
    name: str
    paths: tuple[str, ...]
    if_no_files_found: str
    include_hidden_files: bool
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Download:
    job_id: str
    step_index: int
    action: str
    name: str | None
    pattern: str | None
    merge_multiple: bool
    external: bool
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Job:
    job_id: str
    needs: tuple[str, ...]
    matrix: tuple[MatrixAxis, ...]
    dynamic_matrix: bool
    uploads: tuple[Upload, ...]
    downloads: tuple[Download, ...]

    @property
    def matrix_axes(self) -> tuple[str, ...]:
        return tuple(axis.name for axis in self.matrix)


@dataclass(frozen=True, slots=True)
class Workflow:
    path: Path
    jobs: tuple[Job, ...]


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    severity: Severity
    message: str
    location: SourceLocation
    evidence: tuple[str, ...] = ()
    related: tuple[SourceLocation, ...] = ()


@dataclass(frozen=True, slots=True)
class ArtifactFlow:
    producer: Upload
    consumer: Download


@dataclass(frozen=True, slots=True)
class Analysis:
    workflow: Workflow
    findings: tuple[Finding, ...]
    flows: tuple[ArtifactFlow, ...]
