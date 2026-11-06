"""Where run files live: outputs/, checkpoints/, the run log, run folders; run id and adapter checks.

``GSM8K_OUTPUTS_DIR`` and ``GSM8K_CHECKPOINTS_DIR`` move outputs/ and checkpoints/ (tests point them at
temp folders); both are read at call time.
"""

import os
import re
from pathlib import Path

from gsm8k._env import ROOT

DEFAULT_RESULTS: Path = ROOT / "results" / "runs.csv"

# C1 attempt ids ("<base id>-<n>", e.g. q06-sft-dev-2) and ad-hoc ids for runs without --run-id
# ("adhoc-<UTC yyyymmdd-HHMMSS>").
RUN_ID_PATTERN = re.compile(r"(?:(?:q06|q17)-[a-z0-9]+-[a-z0-9]+-[0-9]+|adhoc-[0-9]{8}-[0-9]{6})")


def outputs_root() -> Path:
    value = os.environ.get("GSM8K_OUTPUTS_DIR")
    return Path(value) if value else ROOT / "outputs"


def checkpoints_root() -> Path:
    value = os.environ.get("GSM8K_CHECKPOINTS_DIR")
    return Path(value) if value else ROOT / "checkpoints"


def check_run_id(run_id: str) -> None:
    """Raise ValueError unless run_id is a C1 attempt id or an ad-hoc id (so it is a safe folder name)."""
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(
            f"Invalid run id: {run_id!r} (expected e.g. q06-base-dev-1 or adhoc-20261101-201530)"
        )


def run_dir(run_id: str) -> Path:
    """The run's folder ``outputs/<run_id>/`` (not created)."""
    check_run_id(run_id)
    return outputs_root() / run_id


def resolve_adapter(path: str) -> Path:
    """The adapter folder as an absolute path; it must exist and lie inside checkpoints/.

    A relative path is read from the project folder. Raises ``FileNotFoundError("Adapter not found:
    <path>")`` when it is missing and ``ValueError`` when it resolves outside checkpoints/ (also
    through a symlink).
    """
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    if not candidate.exists():
        raise FileNotFoundError(f"Adapter not found: {path}")
    resolved = candidate.resolve()
    root = checkpoints_root().resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError(f"Adapter must be inside {root}: {path}")
    return resolved
