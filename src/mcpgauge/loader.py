from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from mcpgauge.schema import Suite


class SuiteLoadError(Exception):
    """Raised when a suite YAML file cannot be loaded or validated."""


def load_suite(path: Path | str) -> Suite:
    """Load and validate a Suite from a YAML file.

    Raises SuiteLoadError with a human-readable message on any problem.
    """
    path = Path(path).resolve()

    if not path.exists():
        raise SuiteLoadError(f"Suite file not found: {path}")

    try:
        with path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise SuiteLoadError(f"Invalid YAML in {path.name}: {exc}") from exc

    if not isinstance(data, dict):
        raise SuiteLoadError(
            f"Suite file must be a YAML mapping, got {type(data).__name__}: {path.name}"
        )

    try:
        return Suite.model_validate(data)
    except ValidationError as exc:
        lines = [f"Suite validation failed for {path}:"]
        for err in exc.errors():
            loc = " -> ".join(str(part) for part in err["loc"])
            lines.append(f"  - {loc}: {err['msg']}")
        raise SuiteLoadError("\n".join(lines)) from exc
