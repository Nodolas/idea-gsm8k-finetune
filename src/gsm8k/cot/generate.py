"""SelfTaughtCoT, generation: sample the model's own step-by-step solutions and keep the correct ones
(US10.1, FR10.1; contract C2 ``cot_data.jsonl`` and ``cot_stats.json``).

Each training problem gets the fixed 4-shot prompt and ``cot_samples`` samples at ``cot_temperature``
(seeded once with the run's seed); every sample is cut at its BR3.5 stop point. A sample is kept only
if it ends with a ``#### <number>`` line holding the right answer and at least one reasoning line comes
before that line; at most one sample is kept per problem, the first in sample order.

Heavy libraries (torch, transformers) are imported inside the functions. ``generate_cot`` reaches the
sampler through this module's ``sample`` attribute at call time, so tests can hand in a scripted one.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from gsm8k import evaluation, scoring
from gsm8k.reasoning_text import reasoning_lines, reasoning_words

SCHEMA_VERSION = 1
# Sequences (problems times samples) generated together, sized for 8 GB (NFR1); not a dial, not hashed.
SEQUENCES_PER_BATCH = {"Qwen/Qwen3-0.6B-Base": 16, "Qwen/Qwen3-1.7B-Base": 8}
DEFAULT_SEQUENCES_PER_BATCH = 16


@dataclass
class CotResult:
    """The kept records (``cot_data.jsonl`` lines, problem order) and the ``cot_stats.json`` figures."""

    records: list[dict] = field(default_factory=list)
    problems: int = 0
    samples_per_problem: int = 0
    solved: int = 0
    kept: int = 0
    kept_fraction: float = 0.0
    mean_lines_kept: float | None = None
    mean_words_kept: float | None = None
    mean_lines_reference: float | None = None
    mean_words_reference: float | None = None
    seconds_per_generated_problem: float = 0.0
    peak_gpu_memory_gb: float = 0.0

    def stats(self, run_id: str) -> dict:
        """The C2 ``cot_stats.json`` object."""
        return {
            "v": SCHEMA_VERSION,
            "run_id": run_id,
            "problems": self.problems,
            "samples_per_problem": self.samples_per_problem,
            "solved": self.solved,
            "kept": self.kept,
            "kept_fraction": self.kept_fraction,
            "mean_lines_kept": self.mean_lines_kept,
            "mean_words_kept": self.mean_words_kept,
            "mean_lines_reference": self.mean_lines_reference,
            "mean_words_reference": self.mean_words_reference,
        }


def problems_per_batch(model_id: str, samples: int) -> int:
    """How many problems go into one sampling call: the model's sequence budget over the samples."""
    budget = SEQUENCES_PER_BATCH.get(model_id, DEFAULT_SEQUENCES_PER_BATCH)
    return max(1, budget // max(1, samples))


def _final_line(text: str) -> str | None:
    """The first stripped line that starts with ``####`` (where reasoning lines end), or None."""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("####"):
            return line
    return None


def is_correct_sample(output: str, gold: str) -> bool:
    """The sample's answer (BR3.1-BR3.4, after the BR3.5 cut) equals the gold answer."""
    return scoring.score(output, gold)[1]


def keep_sample(output: str, gold: str) -> bool:
    """The keep rule (AC10.1.2): the sample has a ``#### <number>`` line whose number is the gold
    answer, and at least one non-empty reasoning line comes before it."""
    text = scoring.cut_output(output)
    final = _final_line(text)
    if final is None or not is_correct_sample(text, gold):
        return False
    if not scoring.is_correct(scoring.extract_answer(final), gold):
        return False
    return bool(reasoning_lines(text))


def choose_kept(outputs: list[str], gold: str) -> str | None:
    """The first kept sample in sample order, or None when no sample qualifies."""
    for output in outputs:
        if keep_sample(output, gold):
            return output
    return None


def sample(
    model: Any,
    tokenizer: Any,
    prompts: list[str],
    *,
    samples: int,
    temperature: float,
    max_new_tokens: int,
) -> list[list[str]]:
    """``samples`` sampled answers per prompt (plain temperature sampling, no top-k or top-p cut),
    each stopped per sequence at its BR3.5 stop point and cut there. Seed before calling for
    reproducible draws."""
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
    enc = {k: v.to(evaluation._model_device(model)) for k, v in enc.items()}
    prompt_len = enc["input_ids"].shape[1]
    stop = evaluation._stop_criterion(tokenizer, prompt_len)
    with torch.inference_mode():
        out = model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=float(temperature),
            top_k=0,
            top_p=1.0,
            num_beams=1,
            num_return_sequences=samples,
            stopping_criteria=StoppingCriteriaList([stop]),
            pad_token_id=tokenizer.pad_token_id,
        )
    texts = [
        scoring.cut_output(t) for t in tokenizer.batch_decode(out[:, prompt_len:], skip_special_tokens=True)
    ]
    return [texts[i * samples : (i + 1) * samples] for i in range(len(prompts))]


def _mean(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def generate_cot(
    model: Any,
    tokenizer: Any,
    problems: list[Any],
    prompt_for: Callable[[Any], str],
    cfg: Any,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> CotResult:
    """Sample every problem (in the given order), apply the keep rule and gather the C2 figures.

    ``on_progress(done, total)`` is called after each sampling call. The seed is set once, with
    ``transformers.set_seed(cfg.seed)``, before the first sample.
    """
    import torch
    import transformers

    from gsm8k.datasets_prompts.prompt import strip_calculator_notes

    use_cuda = getattr(evaluation._model_device(model), "type", "cpu") == "cuda"
    if use_cuda:
        torch.cuda.reset_peak_memory_stats()
    transformers.set_seed(cfg.seed)
    total = len(problems)
    per_batch = problems_per_batch(cfg.model, cfg.cot_samples)
    result = CotResult(problems=total, samples_per_problem=cfg.cot_samples)
    lines_kept: list[int] = []
    words_kept: list[int] = []
    lines_ref: list[int] = []
    words_ref: list[int] = []
    gen_seconds = 0.0
    done = 0
    for start in range(0, total, per_batch):
        batch = problems[start : start + per_batch]
        t0 = time.perf_counter()
        outputs = sample(
            model,
            tokenizer,
            [prompt_for(p) for p in batch],
            samples=cfg.cot_samples,
            temperature=cfg.cot_temperature,
            max_new_tokens=cfg.max_new_tokens,
        )
        gen_seconds += time.perf_counter() - t0
        if len(outputs) != len(batch):
            raise RuntimeError(f"The sampler returned {len(outputs)} answer lists for {len(batch)} problems")
        for problem, samples in zip(batch, outputs, strict=True):
            correct = sum(1 for s in samples if is_correct_sample(s, problem.gold))
            result.solved += int(correct > 0)
            kept = choose_kept(samples, problem.gold)
            if kept is None:
                continue
            result.records.append(
                {
                    "v": SCHEMA_VERSION,
                    "problem_id": problem.id,
                    "question": problem.question,
                    "gold": problem.gold,
                    "solution": kept,
                    "correct_samples": correct,
                    "samples": len(samples),
                }
            )
            reference = strip_calculator_notes(problem.answer)
            lines_kept.append(len(reasoning_lines(kept)))
            words_kept.append(reasoning_words(kept))
            lines_ref.append(len(reasoning_lines(reference)))
            words_ref.append(reasoning_words(reference))
        done += len(batch)
        if on_progress is not None:
            on_progress(done, total)
    result.kept = len(result.records)
    result.kept_fraction = round(result.kept / total, 4) if total else 0.0
    result.mean_lines_kept = _mean(lines_kept)
    result.mean_words_kept = _mean(words_kept)
    result.mean_lines_reference = _mean(lines_ref)
    result.mean_words_reference = _mean(words_ref)
    result.seconds_per_generated_problem = gen_seconds / total if total else 0.0
    result.peak_gpu_memory_gb = evaluation.peak_gpu_memory_gb(model)
    return result
