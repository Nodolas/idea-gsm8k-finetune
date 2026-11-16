"""Model-design inspection for the learning course: ``gsm8k course inspect`` (US12.2, contract C9).

For every Course Models row it reads only the configuration and the tokenizer at the pinned revision,
counts the weights on the ``meta`` device (nothing is downloaded or allocated) and writes
``<outputs>/course/architectures.json`` atomically. It never touches ``results/runs.csv``, the run lock
or the queue.

This module imports no torch or transformers at module level. The three seams ``load_config``,
``load_tokenizer`` and ``load_sample_problem`` are module attributes read at call time, so tests replace
them and nothing is downloaded.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
FIRST_TOKENS = 20
PARTS = ("embeddings", "attention", "mlp", "norms", "head")
BYTES_PER_WEIGHT_BF16 = 2.0
BYTES_PER_WEIGHT_INT4 = 0.5
GB = 1e9


class InspectError(Exception):
    """A model (or the sample problem) could not be read; ``str()`` names it."""


def course_models() -> list[tuple[str, str, str]]:
    """The Course Models rows in table order as (id, revision, licence), read at call time."""
    from gsm8k.course import steps

    return [(m.id, m.revision, m.licence) for m in steps.COURSE_MODELS]


# ----------------------------------------------------------------------------------------- seams


def load_config(model: str, revision: str):
    """The model's configuration at the pinned revision: config files only, never weights."""
    from transformers import AutoConfig

    return AutoConfig.from_pretrained(model, revision=revision, trust_remote_code=False, token=False)


def load_tokenizer(model: str, revision: str):
    """The model's tokenizer at the pinned revision: tokenizer files only, never weights."""
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model, revision=revision, trust_remote_code=False, token=False)


def load_sample_problem() -> tuple[str, str, str]:
    """(problem id, question, 4-shot prompt) of the first scored dev problem of the fixed split (FR1.2)."""
    from gsm8k.datasets_prompts import hub, prompt, split

    problems = hub.load_gsm8k(hub.DATASET_REVISION)
    train_ids = [p.id for p in problems["train"]]
    data_split = split.load_or_build_split(train_ids, split_seed=split.SPLIT_SEED)
    exemplar_ids = prompt.choose_exemplars(data_split.dev_ids, split.SPLIT_SEED)
    by_id = {p.id: p for p in problems["train"]}
    exemplars = [by_id[i] for i in exemplar_ids]
    first = prompt.problems_to_score("dev", data_split, problems, exemplar_ids, 1)[0]
    return first.id, first.question, prompt.build_prompt(exemplars, first.question)


# ------------------------------------------------------------------------------------ weight counts


def _part_of(name: str) -> str:
    """Which part a parameter belongs to; raises for a name it cannot place, so the parts always sum."""
    if any(key in name for key in ("embed_tokens", "embed_in", "wte", "wpe", "embed_positions")):
        return "embeddings"
    if any(key in name for key in ("lm_head", "embed_out")):
        return "head"
    if ".mlp." in name:
        return "mlp"
    if any(key in name for key in (".self_attn.", ".attention.", ".attn.")):
        return "attention"
    if "norm" in name or "ln_" in name:
        return "norms"
    raise ValueError(f"cannot place the parameter {name} in a part")


def count_weights(config: Any) -> tuple[int, dict[str, int], bool]:
    """(total, weights by part, gated MLP) of the model built from ``config`` on the meta device.

    A tied output head shares the input embedding's tensor, which ``named_parameters`` lists once, so
    its part ``head`` is 0.
    """
    import torch
    from transformers import AutoModelForCausalLM

    with torch.device("meta"):
        model = AutoModelForCausalLM.from_config(config)
    parts = dict.fromkeys(PARTS, 0)
    gated = False
    for name, parameter in model.named_parameters():
        parts[_part_of(name)] += parameter.numel()
        if ".mlp." in name and "gate" in name:
            gated = True
    return sum(parts.values()), parts, gated


# ----------------------------------------------------------------------------------- configuration


def _first(config: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        value = getattr(config, name, None)
        if value is not None:
            return value
    return default


def _is_rotary(config: Any) -> bool:
    if hasattr(config, "rope_theta") or hasattr(config, "rotary_pct"):
        return True
    rope = getattr(config, "rope_parameters", None)  # transformers 5 keeps the rotary settings here
    return isinstance(rope, dict) and ("rope_theta" in rope or "rotary_pct" in rope)


def _gb(weights: int, bytes_per_weight: float) -> float:
    return round(weights * bytes_per_weight / GB, 2)


def _token_text(tokenizer: Any, token_id: int) -> str:
    return tokenizer.decode([token_id])


def inspect_model(model: str, revision: str, licence: str, sample: tuple[str, str, str]) -> dict:
    """One architectures.json entry; any failure raises InspectError naming the model."""
    _, problem_text, prompt_text = sample
    try:
        config = load_config(model, revision)
        tokenizer = load_tokenizer(model, revision)
        total, parts, gated = count_weights(config)
        heads = int(_first(config, "num_attention_heads"))
        width = int(_first(config, "hidden_size"))
        kv_heads = int(_first(config, "num_key_value_heads", default=heads))
        problem_ids = list(tokenizer(problem_text)["input_ids"])
        prompt_ids = list(tokenizer(prompt_text)["input_ids"])
        return {
            "id": model,
            "revision": revision,
            "licence": licence,
            "family": config.model_type,
            "layers": int(_first(config, "num_hidden_layers")),
            "width": width,
            "heads": heads,
            "kv_heads": kv_heads,
            "attention": "multi-head" if kv_heads == heads else "grouped-query",
            "head_size": int(_first(config, "head_dim", default=width // heads)),
            "mlp_width": int(_first(config, "intermediate_size", "n_inner", default=4 * width)),
            "mlp_matrices": 3 if gated else 2,
            "vocab": int(config.vocab_size),
            "context": int(_first(config, "max_position_embeddings")),
            "tied_embeddings": bool(config.tie_word_embeddings),
            "position_encoding": "rotary" if _is_rotary(config) else "learned",
            "activation": str(_first(config, "hidden_act", "activation_function", default="unknown")),
            "weights_total": total,
            "weights_by_part": parts,
            "bf16_gb": _gb(total, BYTES_PER_WEIGHT_BF16),
            "int4_gb": _gb(total, BYTES_PER_WEIGHT_INT4),
            "problem_tokens": len(problem_ids),
            "prompt_tokens": len(prompt_ids),
            "first_tokens": [_token_text(tokenizer, token_id) for token_id in problem_ids[:FIRST_TOKENS]],
        }
    except Exception as exc:
        raise InspectError(f"Could not read the model {model} at {revision}: {exc}") from exc


def inspect_models(outputs: Path | None = None) -> dict:
    """The architectures.json document for every Course Models row (nothing is written here)."""
    try:
        problem_id, problem_text, prompt_text = load_sample_problem()
    except Exception as exc:
        raise InspectError(f"Could not build the sample problem: {exc}") from exc
    sample = (problem_id, problem_text, prompt_text)
    models = [inspect_model(model, revision, licence, sample) for model, revision, licence in course_models()]
    return {
        "v": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sample_problem_id": problem_id,
        "models": models,
    }


def architectures_path(outputs: Path) -> Path:
    return Path(outputs) / "course" / "architectures.json"


def write_architectures(outputs: Path) -> Path:
    """Inspect every model, then write ``<outputs>/course/architectures.json`` atomically.

    Everything is read before anything is created, so a model that fails leaves no file behind and
    an existing architectures.json untouched.
    """
    document = inspect_models(outputs)
    path = architectures_path(outputs)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".architectures-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=1)
            handle.write("\n")
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
    return path
