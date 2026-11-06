"""u1-eval-skeleton, part C: the in-folder caches are set before any other import (AC1.1.4, BR1.1, C5)."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "HF_HOME": ROOT / ".cache" / "huggingface",
    "PIP_CACHE_DIR": ROOT / ".cache" / "pip",
    "XDG_CACHE_HOME": ROOT / ".cache",
    "TRITON_CACHE_DIR": ROOT / ".cache" / "triton",
    "TORCHINDUCTOR_CACHE_DIR": ROOT / ".cache" / "torchinductor",
    "TORCH_HOME": ROOT / ".cache" / "torch",
}

HEAVY = ("torch", "transformers", "datasets", "huggingface_hub", "accelerate")

# Records the six variables at the moment the first heavy library is imported, then runs the
# project entry modules. Printed as one JSON line.
PROBE = """
import importlib.abc, json, os, sys
NAMES = {names!r}
HEAVY = {heavy!r}
seen = {{}}

class Probe(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        top = fullname.split(".")[0]
        if top in HEAVY and "first_heavy" not in seen:
            seen["first_heavy"] = top
            seen["env"] = {{k: os.environ.get(k) for k in NAMES}}
        return None

sys.meta_path.insert(0, Probe())
{body}
import torch  # noqa: makes sure a heavy import happened at least once
print(json.dumps(seen))
"""


def _poisoned_env(tmp_path: Path) -> dict[str, str]:
    """An environment where every cache variable points outside the project."""
    env = dict(os.environ)
    elsewhere = tmp_path / "elsewhere"
    for name in EXPECTED:
        env[name] = str(elsewhere / name.lower())
    env["CUDA_VISIBLE_DEVICES"] = ""
    env.pop("PYTHONPATH", None)
    return env


def _run(code: str, tmp_path: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=_poisoned_env(tmp_path),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _assert_project_caches(env: dict[str, str]) -> None:
    for name, expected in EXPECTED.items():
        value = env[name]
        assert value is not None, f"{name} is not set"
        path = Path(value)
        assert path.is_absolute(), f"{name}={value} is not absolute"
        assert path == expected, f"{name}={value}, expected {expected}"
        assert path.resolve().is_relative_to(ROOT.resolve()), f"{name}={value} is outside the project"


def test_AC1_1_4_caches_set_before_any_heavy_import(tmp_path):
    body = "import gsm8k.cli\nimport gsm8k.evaluation\n"
    seen = _run(PROBE.format(names=list(EXPECTED), heavy=list(HEAVY), body=body), tmp_path)
    assert "env" in seen, "no heavy library was imported at all"
    _assert_project_caches(seen["env"])


def test_AC1_1_4_importing_gsm8k_sets_caches_without_loading_torch(tmp_path):
    code = (
        "import json, os, sys\n"
        "import gsm8k\n"
        f"names = {list(EXPECTED)!r}\n"
        f"heavy = {list(HEAVY)!r}\n"
        "print(json.dumps({'env': {k: os.environ.get(k) for k in names},"
        " 'loaded': [m for m in heavy if m in sys.modules]}))\n"
    )
    seen = _run(code, tmp_path)
    _assert_project_caches(seen["env"])
    assert seen["loaded"] == [], f"importing gsm8k loaded {seen['loaded']}"


def test_AC1_1_4_python_m_gsm8k_entry_sets_caches_first(tmp_path):
    body = (
        "import runpy, sys\n"
        "sys.argv = ['gsm8k', '--help']\n"
        "try:\n"
        "    runpy.run_module('gsm8k', run_name='__main__')\n"
        "except SystemExit:\n"
        "    pass\n"
    )
    seen = _run(PROBE.format(names=list(EXPECTED), heavy=list(HEAVY), body=body), tmp_path)
    assert "env" in seen
    _assert_project_caches(seen["env"])
