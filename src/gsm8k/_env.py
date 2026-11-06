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


def setup_env() -> None:
    for name, rel in CACHE_DIRS.items():
        os.environ[name] = str(ROOT / rel)
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    for name in TOKEN_VARS:
        os.environ.pop(name, None)
