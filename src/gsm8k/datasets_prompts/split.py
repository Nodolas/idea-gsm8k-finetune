"""The fixed dev/train split of the GSM8K training problems (BR1.3-BR1.6, BR5.4; NFR7.1, NFR8.1).

The split is a pure function of the fixed split seed, never of a training seed. It is saved to
``outputs/splits/gsm8k-split<split_seed>.json``; a missing file is rebuilt, an unreadable or
invalid one stops the run.
"""

import json
import os
import random
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

SPLIT_SEED = 42
DEV_SIZE = 500

TRAIN_PREFIX = "gsm8k-train-"
TEST_PREFIX = "gsm8k-test-"
_ID_PATTERN = re.compile(r"^gsm8k-(train|test)-(\d+)$")


@dataclass
class Split:
    dev_ids: list[str]
    train_ids: list[str]
    split_seed: int


class SplitFileError(Exception):
    """The split file exists but cannot be parsed or fails BR1.4/BR1.5."""

    def __init__(self, path: Path):
        self.path = Path(path)
        super().__init__(f"Split file could not be read: {path}")


def index_of(problem_id: str) -> int:
    """The numeric row index of a problem id such as ``gsm8k-train-17``."""
    match = _ID_PATTERN.match(problem_id) if isinstance(problem_id, str) else None
    if not match:
        raise ValueError(f"Not a GSM8K problem id: {problem_id!r}")
    return int(match.group(2))


def sort_by_index(ids: list[str]) -> list[str]:
    return sorted(ids, key=index_of)


def build_split(train_ids: list[str], split_seed: int = SPLIT_SEED) -> Split:
    """BR1.3: sort by index, shuffle with ``random.Random(split_seed)``, first 500 are dev."""
    if len(set(train_ids)) != len(train_ids):
        raise ValueError("Training ids contain duplicates")
    for problem_id in train_ids:
        if not problem_id.startswith(TRAIN_PREFIX):
            index_of(problem_id)  # malformed ids raise here
            raise ValueError(f"Not a training problem id: {problem_id}")
    order = sort_by_index(list(train_ids))
    random.Random(split_seed).shuffle(order)
    return Split(
        dev_ids=sort_by_index(order[:DEV_SIZE]),
        train_ids=sort_by_index(order[DEV_SIZE:]),
        split_seed=split_seed,
    )


def validate_split(split: Split, all_train_ids: list[str]) -> None:
    """BR1.4 and BR1.5; raises ``ValueError`` when the split is invalid."""
    dev, train = list(split.dev_ids), list(split.train_ids)
    if any(not isinstance(i, str) for i in dev + train):
        raise ValueError("Split ids must be strings")
    tainted = [i for i in dev + train if i.startswith(TEST_PREFIX)]
    if tainted:
        raise ValueError(f"Split holds test problems: {tainted[:3]}")
    if len(set(dev)) != len(dev) or len(set(train)) != len(train):
        raise ValueError("Split lists contain duplicate ids")
    overlap = set(dev) & set(train)
    if overlap:
        raise ValueError(f"Dev and train overlap: {sorted(overlap, key=index_of)[:3]}")
    if set(dev) | set(train) != set(all_train_ids):
        raise ValueError("Dev and train together are not exactly the training problems")


def split_path(split_seed: int = SPLIT_SEED) -> Path:
    # Imported here so this module stays importable on its own (run_records is another block).
    from gsm8k.run_records.paths import outputs_root

    return outputs_root() / "splits" / f"gsm8k-split{split_seed}.json"


def _atomic_write_text(path: Path, text: str) -> None:
    """BR5.4: write to a temporary name in the same folder, then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _read_split(path: Path, all_train_ids: list[str], split_seed: int) -> Split:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or doc.get("split_seed") != split_seed:
            raise ValueError("wrong document or split seed")
        dev, train = doc["dev_ids"], doc["train_ids"]
        if not isinstance(dev, list) or not isinstance(train, list):
            raise ValueError("id lists missing")
        split = Split(dev_ids=dev, train_ids=train, split_seed=split_seed)
        validate_split(split, all_train_ids)
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise SplitFileError(path) from exc
    return split


def load_or_build_split(
    train_ids: list[str], path: Path | None = None, split_seed: int = SPLIT_SEED
) -> Split:
    """BR1.6: read the saved split, or build and save it atomically when the file is missing.

    An existing file that cannot be parsed or fails BR1.4/BR1.5 raises ``SplitFileError`` and is
    left as it is.
    """
    path = Path(path) if path is not None else split_path(split_seed)
    if path.exists():
        return _read_split(path, train_ids, split_seed)
    split = build_split(train_ids, split_seed)
    validate_split(split, train_ids)
    doc = {"split_seed": split.split_seed, "dev_ids": split.dev_ids, "train_ids": split.train_ids}
    _atomic_write_text(path, json.dumps(doc, indent=1) + "\n")
    return split
