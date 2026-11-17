"""Keep every cache inside the project folder (BR1.1, NFR5) and run without a Hub token (NFR6.2).

Imported by ``gsm8k/__init__.py`` before anything else, so torch, transformers and datasets
always see these values, whichever ``gsm8k`` module a script imports first.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CACHE_DIRS = {
    "HF_HOME": ".cache/huggingface",
    "PIP_CACHE_DIR": ".cache/pip",
    "XDG_CACHE_HOME": ".cache",
    "TRITON_CACHE_DIR": ".cache/triton",
    "TORCHINDUCTOR_CACHE_DIR": ".cache/torchinductor",
    "TORCH_HOME": ".cache/torch",
}

TOKEN_VARS = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")

# Python's C headers kept in the project folder (AC7.1.6), unpacked by scripts/fetch-python-headers.sh.
PYTHON_HEADERS = ".tools/python-headers/usr/include"


def python_header_dirs() -> list[Path]:
    """The two include folders (``python3.12`` and its parent) that Triton's C helper needs."""
    return [ROOT / PYTHON_HEADERS / "python3.12", ROOT / PYTHON_HEADERS]


def _cpath_value() -> str:
    """``CPATH`` with the header folders first, the old entries after them, no duplicates, no empty entry."""
    first = [str(path) for path in python_header_dirs()]
    old = [entry for entry in os.environ.get("CPATH", "").split(os.pathsep) if entry and entry not in first]
    return os.pathsep.join([*first, *old])


def setup_env() -> None:
    for name, rel in CACHE_DIRS.items():
        os.environ[name] = str(ROOT / rel)
    os.environ["CPATH"] = _cpath_value()
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    for name in TOKEN_VARS:
        os.environ.pop(name, None)
