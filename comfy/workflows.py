"""Load and parameterise ComfyUI API-format workflow JSON.

ComfyUI's API format is a dict keyed by node id; each value has ``class_type``
and ``inputs``. Our workflow files ship with placeholder string values like
``{{POSITIVE_PROMPT}}`` so Python can substitute parameters at run time
without having to know node ids.
"""

from __future__ import annotations

import copy
import json
import random
import re
from pathlib import Path
from typing import Any

_WORKFLOW_DIR = Path(__file__).parent / "workflows"
_PLACEHOLDER_RE = re.compile(r"^\{\{(\w+)\}\}$")


def load(name: str) -> dict[str, Any]:
    """Load a workflow JSON by name (without the .json extension)."""
    path = _WORKFLOW_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Workflow template not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def substitute(workflow: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of ``workflow`` with ``{{NAME}}`` placeholders
    replaced by the matching value from ``values``.

    Strings that are *exactly* ``{{NAME}}`` are replaced with the raw value
    (preserving type, so an int placeholder becomes an int). Other strings
    have ``{{NAME}}`` fragments interpolated with ``str(value)``.
    """
    wf = copy.deepcopy(workflow)

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk(v) for v in obj]
        if isinstance(obj, str):
            exact = _PLACEHOLDER_RE.match(obj)
            if exact:
                key = exact.group(1)
                if key in values:
                    return values[key]
                return obj
            # Partial interpolation for strings with embedded placeholders.
            def _replace(match: re.Match) -> str:
                key = match.group(1)
                return str(values[key]) if key in values else match.group(0)
            return re.sub(r"\{\{(\w+)\}\}", _replace, obj)
        return obj

    return _walk(wf)


def random_seed() -> int:
    """Seed in the range ComfyUI's KSampler accepts."""
    return random.randint(0, 2**63 - 1)
