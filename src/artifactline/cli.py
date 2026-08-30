from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from artifactline import __version__
from artifactline.analyze import analyze_workflow
from artifactline.model import Analysis, Severity
from artifactline.parser import InputError, discover_workflows, parse_workflow_file
from artifactline.render import render_json, render_sarif, render_terminal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="artifactline",
        description="Audit GitHub Actions artifact handoffs before workflows run.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit", help="analyze one workflow or a workflow directory")
    audit.add_argument("path", nargs="?", type=Path, default=Path("."))
    audit.add_argument("--format", choices=("terminal", "json", "sarif"), default="terminal")
    audit.add_argument("--output", type=Path, help="write the selected report to this file")
    audit.add_argument(
        "--strict",
        action="store_true",
        help="return exit 1 for warnings as well as errors",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "audit":
        raise AssertionError(f"unhandled command: {args.command}")
    try:
        analyses = tuple(
            analyze_workflow(parse_workflow_file(path)) for path in discover_workflows(args.path)
        )
        base = args.path.resolve() if args.path.is_dir() else args.path.resolve().parent
        report = _render(args.format, analyses, base)
        if args.output is None:
            print(report)
        else:
            _write_report(args.output, report)
            print(f"Wrote {args.format} report to {args.output}")
    except InputError as exc:
        print(f"artifactline: error: {exc}", file=sys.stderr)
        return 2

    errors = any(
        finding.severity is Severity.ERROR for analysis in analyses for finding in analysis.findings
    )
    warnings = any(
        finding.severity is Severity.WARNING
        for analysis in analyses
        for finding in analysis.findings
    )
    return 1 if errors or (args.strict and warnings) else 0


def _render(format_name: str, analyses: tuple[Analysis, ...], base: Path) -> str:
    if format_name == "json":
        return render_json(analyses, base)
    if format_name == "sarif":
        return render_sarif(analyses, base)
    return render_terminal(analyses, base)


def _write_report(path: Path, report: str) -> None:
    parent = path.resolve().parent
    if not parent.is_dir():
        raise InputError(f"output directory does not exist: {parent}")
    try:
        path.write_text(f"{report}\n", encoding="utf-8", newline="\n")
    except OSError as exc:
        raise InputError(f"cannot write report to {path}: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
