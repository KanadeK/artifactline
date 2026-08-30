from __future__ import annotations

import copy
import re
from collections import defaultdict, deque
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypeAlias

import yaml

from artifactline.model import Download, Job, MatrixAxis, SourceLocation, Upload, Workflow

MAX_WORKFLOW_BYTES = 2 * 1024 * 1024
MAX_WORKFLOW_FILES = 200
MAX_JOBS = 256
MAX_STEPS_PER_JOB = 512

YamlMapping: TypeAlias = Mapping[str, Any]


class InputError(ValueError):
    """The supplied workflow input cannot be analyzed."""


class GitHubLoader(yaml.SafeLoader):
    """Safe YAML loader whose booleans match GitHub's YAML 1.2 behavior."""


GitHubLoader.yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for initial, resolvers in GitHubLoader.yaml_implicit_resolvers.items():
    GitHubLoader.yaml_implicit_resolvers[initial] = [
        resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:bool"
    ]
GitHubLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)

_USES_LINE = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^'\"\s#]+)", re.MULTILINE)
_UPLOAD_ACTION = re.compile(r"^actions/upload-artifact@", re.IGNORECASE)
_DOWNLOAD_ACTION = re.compile(r"^actions/download-artifact@", re.IGNORECASE)


def discover_workflows(target: Path) -> tuple[Path, ...]:
    resolved = target.resolve()
    if not resolved.exists():
        raise InputError(f"input does not exist: {resolved}")
    if resolved.is_file():
        return (resolved,)

    repository_workflows = resolved / ".github" / "workflows"
    workflow_dir = repository_workflows if repository_workflows.is_dir() else resolved
    files = sorted(
        (*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")),
        key=lambda path: path.name.casefold(),
    )
    if not files:
        raise InputError(f"no .yml or .yaml workflow files found in {workflow_dir}")
    if len(files) > MAX_WORKFLOW_FILES:
        raise InputError(
            f"found {len(files)} workflow files; the scan limit is {MAX_WORKFLOW_FILES}"
        )
    return tuple(path.resolve() for path in files)


def parse_workflow_file(path: Path) -> Workflow:
    resolved = path.resolve()
    try:
        size = resolved.stat().st_size
    except OSError as exc:
        raise InputError(f"cannot read workflow metadata for {resolved}: {exc}") from exc
    if size > MAX_WORKFLOW_BYTES:
        raise InputError(f"workflow {resolved} exceeds the 2 MiB limit")

    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InputError(f"cannot read workflow {resolved} as UTF-8: {exc}") from exc
    if "\x00" in text:
        raise InputError(f"workflow {resolved} contains a NUL byte")

    try:
        document = yaml.load(text, Loader=GitHubLoader)
    except yaml.YAMLError as exc:
        raise InputError(f"invalid YAML in {resolved}: {_yaml_error(exc)}") from exc
    if document is None:
        document = {}
    root = _mapping(document, "workflow document")
    jobs_value = root.get("jobs", {})
    jobs_data = _mapping(jobs_value, "workflow 'jobs'")
    if len(jobs_data) > MAX_JOBS:
        raise InputError(f"workflow has {len(jobs_data)} jobs; the limit is {MAX_JOBS}")

    action_lines = _action_line_queues(text)
    jobs: list[Job] = []
    for job_id_value, job_value in jobs_data.items():
        jobs.append(_parse_job(resolved, job_id_value, job_value, action_lines))
    return Workflow(path=resolved, jobs=tuple(jobs))


def _parse_job(
    path: Path,
    job_id: str,
    value: object,
    action_lines: Mapping[str, deque[int]],
) -> Job:
    data = _mapping(value, f"job '{job_id}'")
    needs = _parse_needs(data.get("needs"), job_id)
    matrix, dynamic_matrix = _parse_matrix(data.get("strategy"), job_id)
    steps_value = data.get("steps", [])
    if not isinstance(steps_value, list):
        raise InputError(f"job '{job_id}' steps must be a list")
    if len(steps_value) > MAX_STEPS_PER_JOB:
        raise InputError(
            f"job '{job_id}' has {len(steps_value)} steps; the limit is {MAX_STEPS_PER_JOB}"
        )

    uploads: list[Upload] = []
    downloads: list[Download] = []
    for step_index, step_value in enumerate(steps_value):
        if not isinstance(step_value, Mapping):
            raise InputError(f"job '{job_id}' step {step_index + 1} must be a mapping")
        uses_value = step_value.get("uses")
        if not isinstance(uses_value, str):
            continue
        uses = uses_value.strip()
        with_data = _optional_mapping(step_value.get("with"), f"job '{job_id}' step 'with'")
        line = _take_action_line(action_lines, uses)
        location = SourceLocation(path=path, line=line)
        if _UPLOAD_ACTION.match(uses):
            uploads.append(_parse_upload(job_id, step_index, uses, with_data, location))
        elif _DOWNLOAD_ACTION.match(uses):
            downloads.append(_parse_download(job_id, step_index, uses, with_data, location))

    return Job(
        job_id=job_id,
        needs=needs,
        matrix=matrix,
        dynamic_matrix=dynamic_matrix,
        uploads=tuple(uploads),
        downloads=tuple(downloads),
    )


def _parse_needs(value: object, job_id: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise InputError(f"job '{job_id}' needs must be a string or list of strings")


def _parse_matrix(strategy_value: object, job_id: str) -> tuple[tuple[MatrixAxis, ...], bool]:
    if strategy_value is None:
        return (), False
    strategy = _mapping(strategy_value, f"job '{job_id}' strategy")
    matrix_value = strategy.get("matrix")
    if matrix_value is None:
        return (), False
    if not isinstance(matrix_value, Mapping):
        return (), True

    axes: list[MatrixAxis] = []
    dynamic = False
    for name_value, values_value in matrix_value.items():
        if name_value in {"include", "exclude"}:
            continue
        if not isinstance(name_value, str):
            raise InputError(f"job '{job_id}' matrix axis names must be strings")
        if not isinstance(values_value, list):
            dynamic = True
            continue
        axes.append(
            MatrixAxis(
                name=name_value,
                values=tuple(_scalar_text(item) for item in values_value),
            )
        )
    return tuple(axes), dynamic


def _parse_upload(
    job_id: str,
    step_index: int,
    uses: str,
    data: YamlMapping,
    location: SourceLocation,
) -> Upload:
    return Upload(
        job_id=job_id,
        step_index=step_index,
        action=uses,
        name=_input_text(data, "name", "artifact"),
        paths=_path_lines(data.get("path")),
        if_no_files_found=_input_text(data, "if-no-files-found", "warn").lower(),
        include_hidden_files=_input_bool(data, "include-hidden-files", False),
        location=location,
    )


def _parse_download(
    job_id: str,
    step_index: int,
    uses: str,
    data: YamlMapping,
    location: SourceLocation,
) -> Download:
    return Download(
        job_id=job_id,
        step_index=step_index,
        action=uses,
        name=_optional_input_text(data, "name"),
        pattern=_optional_input_text(data, "pattern"),
        merge_multiple=_input_bool(data, "merge-multiple", False),
        external="repository" in data or "run-id" in data,
        location=location,
    )


def _action_line_queues(text: str) -> Mapping[str, deque[int]]:
    queues: defaultdict[str, deque[int]] = defaultdict(deque)
    for match in _USES_LINE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        queues[match.group(1).casefold()].append(line)
    return queues


def _take_action_line(action_lines: Mapping[str, deque[int]], uses: str) -> int:
    queue = action_lines.get(uses.casefold())
    return queue.popleft() if queue else 1


def _mapping(value: object, context: str) -> YamlMapping:
    if not isinstance(value, Mapping):
        raise InputError(f"{context} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise InputError(f"{context} keys must be strings")
    return value


def _optional_mapping(value: object, context: str) -> YamlMapping:
    if value is None:
        return {}
    return _mapping(value, context)


def _scalar_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    raise InputError("matrix values must be scalar")


def _input_text(data: YamlMapping, key: str, default: str) -> str:
    value = data.get(key)
    return default if value is None else _scalar_text(value)


def _optional_input_text(data: YamlMapping, key: str) -> str | None:
    value = data.get(key)
    return None if value is None else _scalar_text(value)


def _input_bool(data: YamlMapping, key: str, default: bool) -> bool:
    value = data.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.casefold() in {"true", "false"}:
        return value.casefold() == "true"
    raise InputError(f"action input '{key}' must be true or false")


def _path_lines(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    text = _scalar_text(value)
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def _yaml_error(exc: yaml.YAMLError) -> str:
    problem = getattr(exc, "problem", None)
    mark = getattr(exc, "problem_mark", None)
    if problem and mark:
        return f"line {mark.line + 1}, column {mark.column + 1}: {problem}"
    return str(exc).splitlines()[0]
