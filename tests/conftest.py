"""Shared test fixtures (lead-owned). Tests run on the CPU and never touch the project's
outputs/, checkpoints/ or results/runs.csv (CLAUDE.md, Learning runs; stories.md Conventions)."""

from dataclasses import dataclass
from pathlib import Path

import pytest

import gsm8k  # noqa: F401  (sets the in-folder caches before torch or transformers load)

TINY_MODEL_BASE = "Qwen/Qwen3-0.6B-Base"


@dataclass
class ProjectDirs:
    outputs: Path
    checkpoints: Path
    results: Path


@pytest.fixture
def tmp_project_dirs(tmp_path, monkeypatch) -> ProjectDirs:
    """Point outputs/ and checkpoints/ at temp folders; `results` is a temp run log path (not created)."""
    dirs = ProjectDirs(tmp_path / "outputs", tmp_path / "checkpoints", tmp_path / "results" / "runs.csv")
    dirs.outputs.mkdir()
    dirs.checkpoints.mkdir()
    dirs.results.parent.mkdir()
    monkeypatch.setenv("GSM8K_OUTPUTS_DIR", str(dirs.outputs))
    monkeypatch.setenv("GSM8K_CHECKPOINTS_DIR", str(dirs.checkpoints))
    return dirs


@pytest.fixture(scope="session")
def tiny_model():
    """A tiny Qwen3-architecture model with random weights and the real 0.6B tokenizer (stories.md
    Conventions, tiny model fixture). Returns (model, tokenizer); never loads real model weights."""
    import torch
    from transformers import AutoTokenizer, Qwen3Config, Qwen3ForCausalLM

    from gsm8k.datasets_prompts.hub import MODEL_REVISIONS

    tokenizer = AutoTokenizer.from_pretrained(
        TINY_MODEL_BASE, revision=MODEL_REVISIONS[TINY_MODEL_BASE], trust_remote_code=False
    )
    config = Qwen3Config(
        vocab_size=len(tokenizer),
        hidden_size=64,
        intermediate_size=128,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=2,
        head_dim=16,
        max_position_embeddings=4096,
        tie_word_embeddings=True,
    )
    torch.manual_seed(0)
    model = Qwen3ForCausalLM(config).eval()
    return model, tokenizer


@pytest.fixture(autouse=True)
def gpu_free_for_the_worker(monkeypatch):
    """The worker's GPU check (AC3.7.7) reads this PC's processes and nvidia-smi; every test starts from a
    free GPU, and the AC3.7.7 tests point `worker.gpu_check` at their own stub."""
    try:
        from gsm8k.run_control import worker
    except ImportError:
        return
    monkeypatch.setattr(worker, "gpu_check", lambda: (0, ""), raising=False)
