from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from artifactline import __version__
from artifactline.model import Analysis, Finding, Severity, SourceLocation

INFORMATION_URI = "https://github.com/KanadeK/artifactline"

RULES: dict[str, tuple[str, str]] = {
    "AFL001": (
        "duplicate-upload-name",
        "A statically known artifact name is uploaded more than once in one workflow run.",
    ),
    "AFL002": (
        "matrix-name-collision",
        "An artifact name omits a varying matrix axis and can collide across matrix jobs.",
    ),
    "AFL003": (
        "missing-producer",
        "A local artifact download has no matching upload in the workflow.",
    ),
    "AFL004": (
        "missing-needs-edge",
        "A consumer cannot wait for its artifact producer through the job dependency graph.",
    ),
    "AFL005": (
        "producer-may-be-empty",
        "A consumed upload does not fail when its path produces no files.",
    ),
    "AFL006": (
        "broad-hidden-upload",
        "A broad upload includes hidden files and may collect private repository content.",
    ),
    "AFL007": (
        "ambiguous-download-all",
        "A download consumes every artifact instead of declaring a stable selector.",
    ),
    "AFL008": (
        "dynamic-artifact-flow",
        "Runtime expressions prevent a conclusive offline artifact handoff result.",
    ),
}


def render_terminal(analyses: tuple[Analysis, ...], base: Path) -> str:
    lines = [f"Artifactline {__version__}"]
    for analysis in analyses:
        lines.append("")
        lines.append(_safe(_display_path(analysis.workflow.path, base)))
        for finding in analysis.findings:
            lines.append(
                f"  {finding.severity.value.upper()} {finding.rule_id} "
                f"line {finding.location.line}: {_safe(finding.message)}"
            )
            for evidence in finding.evidence:
                lines.append(f"    {_safe(evidence)}")
        for flow in analysis.flows:
            lines.append(
                "  FLOW "
                f"{_safe(flow.producer.job_id)} -> {_safe(flow.consumer.job_id)}: "
                f"{_safe(flow.producer.name)}"
            )
    summary = _summary(analyses)
    lines.extend(
        [
            "",
            "Summary: "
            f"{summary['errors']} {_plural(summary['errors'], 'error')}, "
            f"{summary['warnings']} {_plural(summary['warnings'], 'warning')}, "
            f"{summary['flows']} {_plural(summary['flows'], 'flow')}",
        ]
    )
    return "\n".join(lines)


def render_json(analyses: tuple[Analysis, ...], base: Path) -> str:
    report = {
        "schema_version": "1.0",
        "tool": {"name": "artifactline", "version": __version__},
        "summary": _summary(analyses),
        "workflows": [_analysis_json(analysis, base) for analysis in analyses],
    }
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)


def render_sarif(analyses: tuple[Analysis, ...], base: Path) -> str:
    results = [
        _sarif_result(finding, base) for analysis in analyses for finding in analysis.findings
    ]
    report = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Artifactline",
                        "semanticVersion": __version__,
                        "informationUri": INFORMATION_URI,
                        "rules": [_sarif_rule(rule_id) for rule_id in sorted(RULES)],
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)


def _analysis_json(analysis: Analysis, base: Path) -> dict[str, Any]:
    return {
        "path": _display_path(analysis.workflow.path, base),
        "findings": [_finding_json(finding, base) for finding in analysis.findings],
        "flows": [
            {
                "artifact": flow.producer.name,
                "producer": {
                    "job": flow.producer.job_id,
                    "line": flow.producer.location.line,
                },
                "consumer": {
                    "job": flow.consumer.job_id,
                    "line": flow.consumer.location.line,
                },
            }
            for flow in analysis.flows
        ],
    }


def _finding_json(finding: Finding, base: Path) -> dict[str, Any]:
    return {
        "rule_id": finding.rule_id,
        "severity": finding.severity.value,
        "message": finding.message,
        "location": _location_json(finding.location, base),
        "evidence": list(finding.evidence),
        "related": [_location_json(location, base) for location in finding.related],
    }


def _location_json(location: SourceLocation, base: Path) -> dict[str, Any]:
    return {
        "path": _display_path(location.path, base),
        "line": location.line,
        "column": location.column,
    }


def _sarif_rule(rule_id: str) -> dict[str, Any]:
    title, description = RULES[rule_id]
    return {
        "id": rule_id,
        "name": title,
        "shortDescription": {"text": description},
        "helpUri": f"{INFORMATION_URI}/blob/main/docs/RULES.md#{rule_id.lower()}",
    }


def _sarif_result(finding: Finding, base: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ruleId": finding.rule_id,
        "level": "error" if finding.severity is Severity.ERROR else "warning",
        "message": {"text": finding.message},
        "locations": [_sarif_location(finding.location, base)],
    }
    if finding.related:
        result["relatedLocations"] = [
            {"id": index, **_sarif_location(location, base)}
            for index, location in enumerate(finding.related, start=1)
        ]
    return result


def _sarif_location(location: SourceLocation, base: Path) -> dict[str, Any]:
    return {
        "physicalLocation": {
            "artifactLocation": {"uri": _display_path(location.path, base)},
            "region": {"startLine": location.line, "startColumn": location.column},
        }
    }


def _summary(analyses: tuple[Analysis, ...]) -> dict[str, int]:
    findings = tuple(finding for analysis in analyses for finding in analysis.findings)
    return {
        "workflows": len(analyses),
        "errors": sum(finding.severity is Severity.ERROR for finding in findings),
        "warnings": sum(finding.severity is Severity.WARNING for finding in findings),
        "flows": sum(len(analysis.flows) for analysis in analyses),
    }


def _display_path(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _safe(value: str) -> str:
    return "".join(
        f"\\x{ord(character):02x}" if ord(character) < 32 or ord(character) == 127 else character
        for character in value
    )


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"
