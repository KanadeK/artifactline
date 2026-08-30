from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[1]


def run(*args: str, expected: int = 0) -> None:
    print("$", " ".join(args), flush=True)
    completed = subprocess.run(args, cwd=ROOT, check=False)
    if completed.returncode != expected:
        raise RuntimeError(
            f"command exited {completed.returncode}; expected {expected}: {' '.join(args)}"
        )


def inspect_packages(dist: Path) -> None:
    wheel = next(dist.glob("artifactline-*.whl"))
    source = next(dist.glob("artifactline-*.tar.gz"))
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = set(archive.namelist())
    required_modules = {
        "artifactline/__init__.py",
        "artifactline/__main__.py",
        "artifactline/analyze.py",
        "artifactline/cli.py",
        "artifactline/model.py",
        "artifactline/parser.py",
        "artifactline/render.py",
    }
    missing = required_modules - wheel_names
    if missing:
        raise RuntimeError(f"wheel is missing modules: {sorted(missing)}")
    if any(name.startswith("tests/") for name in wheel_names):
        raise RuntimeError("wheel unexpectedly contains tests")
    with tarfile.open(source, "r:gz") as archive:
        source_names = set(archive.getnames())
    if not any(name.endswith("/SPEC.md") for name in source_names):
        raise RuntimeError("source distribution is missing SPEC.md")


def verify_json_report(report_path: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rule_ids = {
        finding["rule_id"] for workflow in report["workflows"] for finding in workflow["findings"]
    }
    expected = {"AFL001", "AFL002", "AFL004", "AFL005", "AFL006", "AFL007", "AFL008"}
    if not expected <= rule_ids:
        raise RuntimeError(f"broken example is missing rules: {sorted(expected - rule_ids)}")
    if report["summary"]["errors"] < 5:
        raise RuntimeError("broken example must demonstrate at least five blocking findings")


def main() -> int:
    temp_root = ROOT / ".tmp"
    temp_root.mkdir(exist_ok=True)
    gate_root = Path(tempfile.mkdtemp(prefix="gate-", dir=temp_root))
    run(
        sys.executable,
        "-m",
        "coverage",
        "run",
        "--branch",
        "-m",
        "pytest",
        f"--basetemp={gate_root / 'pytest'}",
        "-p",
        "no:cacheprovider",
    )
    run(sys.executable, "-m", "coverage", "report", "--fail-under=90")
    run(sys.executable, "-m", "ruff", "check", "src", "tests", "scripts")
    run(sys.executable, "-m", "ruff", "format", "--check", "src", "tests", "scripts")
    run(sys.executable, "-m", "mypy", "src")
    run(sys.executable, "-m", "pip_audit", "--skip-editable")
    run(sys.executable, "-m", "artifactline", "audit", ".github/workflows", "--strict")

    run(sys.executable, "-m", "artifactline", "audit", "examples/healthy.yml")
    broken_report = gate_root / "broken.json"
    run(
        sys.executable,
        "-m",
        "artifactline",
        "audit",
        "examples/broken.yml",
        "--format",
        "json",
        "--output",
        str(broken_report),
        expected=1,
    )
    verify_json_report(broken_report)

    invalid = gate_root / "invalid.yml"
    invalid.write_text("jobs: [invalid]\n", encoding="utf-8", newline="\n")
    run(sys.executable, "-m", "artifactline", "audit", str(invalid), expected=2)

    dist = ROOT / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    run(sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir", str(dist))
    inspect_packages(dist)

    package_venv = gate_root / "package-venv"
    run(sys.executable, "-m", "venv", str(package_venv))
    package_python = package_venv / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    wheel = next(dist.glob("artifactline-*.whl"))
    run(str(package_python), "-m", "pip", "install", str(wheel))
    run(str(package_python), "-m", "artifactline", "audit", "examples/healthy.yml")
    run(
        str(package_python),
        "-m",
        "artifactline",
        "audit",
        "examples/broken.yml",
        expected=1,
    )
    print("ARTIFACTLINE_RELEASE_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
