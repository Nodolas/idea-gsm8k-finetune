"""Evaluation: load a model, generate greedy answers with the stop rule and score them (US1.4, W4 step 6).

Heavy libraries (torch, transformers) are imported inside the functions, so importing this module
never loads them before ``gsm8k._env`` has set the in-folder caches (BR1.1, AC1.1.4).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gsm8k import scoring

# Fixed evaluation batch size per model (security-design.md, NFR1.1); not a dial, not in the hash.
BATCH_SIZES = {"Qwen/Qwen3-0.6B-Base": 8, "Qwen/Qwen3-1.7B-Base": 4}
DEFAULT_BATCH_SIZE = 8
DEFAULT_MAX_NEW_TOKENS = 512

_GIB = 1024**3


@dataclass
class EvalResult:
    accuracy: float
    scored: int
    correct: int
    seconds_per_problem: float
    peak_gpu_memory_gb: float


def batch_size_for(model_id: str) -> int:
    return BATCH_SIZES.get(model_id, DEFAULT_BATCH_SIZE)


def load_model(model_id: str, revision: str, adapter_path: Path | None = None) -> tuple[Any, Any]:
    """Load the pinned model and tokenizer through the hub module: bfloat16 on CUDA, float32 on the CPU."""
    import torch

    from gsm8k.datasets_prompts import hub

    use_cuda = torch.cuda.is_available()
    dtype = torch.bfloat16 if use_cuda else torch.float32
    tokenizer = hub.load_tokenizer(model_id, revision)
    model = hub.load_causal_lm(model_id, revision, dtype)
    if adapter_path is not None:
        try:
            from peft import PeftModel
        except ImportError as exc:  # TRL/PEFT arrive with u3-sft
            raise RuntimeError(
                f"Adapter evaluation arrives with u3-sft (peft is not installed): {adapter_path}"
            ) from exc
        model = PeftModel.from_pretrained(model, str(adapter_path))
    model.to(torch.device("cuda" if use_cuda else "cpu"))
    model.eval()
    return model, tokenizer


def _model_device(model: Any) -> Any:
    device = getattr(model, "device", None)
    if device is None:
        device = next(model.parameters()).device
    return device


def peak_gpu_memory_gb(model: Any) -> float:
    """Peak allocated GPU memory in GiB since the last reset when the model is on CUDA, else 0.0."""
    if getattr(_model_device(model), "type", "cpu") != "cuda":
        return 0.0
    import torch

    return torch.cuda.max_memory_allocated() / _GIB


def _reached_stop(text: str) -> bool:
    """BR3.5: the generated text has passed its stop point (the end of the first ``#### <number>``
    line, or a new ``Question:``) exactly when the scoring cut would shorten it."""
    return scoring.cut_output(text) != text


def _stop_criterion(tokenizer: Any, prompt_len: int) -> Any:
    """A per-sequence stopping criterion for the BR3.5 stop rule."""
    import torch
    from transformers import StoppingCriteria

    class AnswerStop(StoppingCriteria):
        def __init__(self) -> None:
            self.done: torch.Tensor | None = None

        def __call__(self, input_ids: torch.Tensor, scores: torch.Tensor, **kwargs: Any) -> torch.Tensor:
            if self.done is None or self.done.shape[0] != input_ids.shape[0]:
                self.done = torch.zeros(input_ids.shape[0], dtype=torch.bool, device=input_ids.device)
            for i in range(input_ids.shape[0]):
                if self.done[i]:
                    continue
                text = tokenizer.decode(input_ids[i, prompt_len:], skip_special_tokens=True)
                if _reached_stop(text):
                    self.done[i] = True
            return self.done.clone()

    return AnswerStop()


def generate(
    model: Any, tokenizer: Any, prompts: list[str], max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS
) -> list[str]:
    """Greedy generation for a batch of prompts (left padded), cut at the BR3.5 stop point."""
    import torch
    from transformers import StoppingCriteriaList

    if not prompts:
        return []
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    old_side = tokenizer.padding_side
    tokenizer.padding_side = "left"
    try:
        enc = tokenizer(prompts, return_tensors="pt", padding=True)
    finally:
        tokenizer.padding_side = old_side
    enc = {k: v.to(_model_device(model)) for k, v in enc.items()}
    prompt_len = enc["input_ids"].shape[1]
    stop = _stop_criterion(tokenizer, prompt_len)
    with torch.inference_mode():
        out = model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            num_beams=1,
            stopping_criteria=StoppingCriteriaList([stop]),
            pad_token_id=tokenizer.pad_token_id,
        )
    texts = tokenizer.batch_decode(out[:, prompt_len:], skip_special_tokens=True)
    return [scoring.cut_output(t) for t in texts]


def evaluate(
    model: Any,
    tokenizer: Any,
    problems: list[Any],
    prompt_for: Callable[[Any], str],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    on_prediction: Callable[[dict], None] | None = None,
) -> EvalResult:
    """Score every problem; each prediction is handed to ``on_prediction`` as soon as it is scored."""
    import torch

    use_cuda = getattr(_model_device(model), "type", "cpu") == "cuda"
    if use_cuda:
        torch.cuda.reset_peak_memory_stats()
    correct = 0
    gen_seconds = 0.0
    for start in range(0, len(problems), batch_size):
        batch = problems[start : start + batch_size]
        t0 = time.perf_counter()
        outputs = generate(model, tokenizer, [prompt_for(p) for p in batch], max_new_tokens)
        gen_seconds += time.perf_counter() - t0
        for problem, output in zip(batch, outputs, strict=True):
            predicted, ok = scoring.score(output, problem.gold)
            correct += int(ok)
            if on_prediction is not None:
                on_prediction(
                    {
                        "problem_id": problem.id,
                        "output": output,
                        "predicted": predicted,
                        "gold": problem.gold,
                        "correct": ok,
                    }
                )
    scored = len(problems)
    peak = peak_gpu_memory_gb(model)
    return EvalResult(
        accuracy=correct / scored if scored else 0.0,
        scored=scored,
        correct=correct,
        seconds_per_problem=gen_seconds / scored if scored else 0.0,
        peak_gpu_memory_gb=peak,
    )
