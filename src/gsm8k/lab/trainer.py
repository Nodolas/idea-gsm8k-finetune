"""The lab's training loop: a plain PyTorch fine-tune of a very small model on the CPU (US11.2, C8).

Seams read at call time: ``load_lab_model(cfg)`` and ``load_lab_problems(cfg)`` (tests replace both).
Tokenization is done once before the first step (``tokenize_examples`` of the SFT module), batches are
padded on the right, and the loss counts the answer tokens unless ``loss_on`` is ``all``.
"""

from __future__ import annotations

import dataclasses
import json
import math
import random
import re
import resource
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gsm8k import evaluation
from gsm8k.datasets_prompts import guard, hub, prompt, split
from gsm8k.datasets_prompts.hub import Problem
from gsm8k.lab.config import LabConfig
from gsm8k.training.sft import tokenize_examples
from gsm8k.training.targets import training_prompt

IGNORE_INDEX = -100
CLIP_NORM = 1.0
DEV_BATCH = 16
CHUNK_BATCHES = 16
SPLIT_SEED = split.SPLIT_SEED
_FORMAT_LINE = re.compile(r"^[ \t]*####[ \t]*[-$]?[ \t]*[\d,]*\d", re.MULTILINE)


class Stopped(Exception):
    """The run was asked to stop (SIGTERM); raised between steps, never in the middle of one."""


# ------------------------------------------------------------------ seams


def load_lab_model(cfg: LabConfig) -> tuple[Any, Any]:
    """The pinned lab model on the CPU in float32 and its tokenizer (pad token = eos when missing)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        cfg.model, revision=cfg.model_revision, trust_remote_code=False, token=False
    )
    model = AutoModelForCausalLM.from_pretrained(
        cfg.model,
        revision=cfg.model_revision,
        dtype=torch.float32,
        use_safetensors=True,
        trust_remote_code=False,
        token=False,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return model.to(torch.device("cpu")), tokenizer


def load_lab_problems(cfg: LabConfig) -> tuple[list[Problem], list[Problem]]:
    """(training problems, dev problems): the first ``train_examples`` of the split's training part by
    index and the first ``dev_problems`` of the 496 scored dev problems. The test split is only used to
    refuse a leak."""
    problems = hub.load_gsm8k(hub.DATASET_REVISION)
    train_ids = [p.id for p in problems["train"]]
    data_split = split.load_or_build_split(train_ids, split_seed=SPLIT_SEED)
    by_id = {p.id: p for p in problems["train"]}
    exemplar_ids = prompt.choose_exemplars(data_split.dev_ids, SPLIT_SEED)
    chosen = split.sort_by_index(list(data_split.train_ids))[: cfg.train_examples]
    forbidden = set(data_split.dev_ids) | {p.id for p in problems["test"]}
    leaked = [i for i in chosen if i in forbidden or not i.startswith(split.TRAIN_PREFIX)]
    if leaked:
        raise ValueError(f"Training data holds dev or test problems: {leaked[:3]}")
    train = [by_id[i] for i in chosen]
    guard.check_training_problems(train, data_split.dev_ids)
    dev = prompt.problems_to_score("dev", data_split, problems, exemplar_ids, cfg.dev_problems)
    return train, dev


# ------------------------------------------------------------------ helpers


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _learning_rate(cfg: LabConfig, step: int, total: int) -> float:
    """The rate used for step ``step`` (1-based): warm-up to the peak, then linear decay or flat."""
    warm = math.ceil(round(cfg.warmup_ratio * total, 9))
    if warm > 0 and step <= warm:
        return cfg.learning_rate * step / warm
    if cfg.schedule == "constant":
        return cfg.learning_rate
    return cfg.learning_rate * (total - step + 1) / (total - warm + 1)


def _dev_steps(total: int) -> list[int]:
    return sorted({0} | {max(1, -(-k * total // 10)) for k in range(1, 11)})


def _batches(order_lengths: list[int], cfg: LabConfig, epochs_rng: random.Random, order_rng: random.Random):
    """One epoch's batches as lists of example indexes (BR: seeded shuffle, optional length grouping)."""
    n = len(order_lengths)
    order = list(range(n))
    epochs_rng.shuffle(order)
    size = cfg.batch_size
    if cfg.batching == "random":
        return [order[i : i + size] for i in range(0, n, size)]
    batches: list[list[int]] = []
    chunk = size * CHUNK_BATCHES
    for start in range(0, n, chunk):
        part = sorted(order[start : start + chunk], key=lambda i: order_lengths[i])
        batches.extend(part[i : i + size] for i in range(0, len(part), size))
    order_rng.shuffle(batches)
    return batches


def _pad(examples: list[dict], pad_id: int, loss_on: str):
    import torch

    width = max(len(e["input_ids"]) for e in examples)
    ids, labels, attention = [], [], []
    for e in examples:
        gap = width - len(e["input_ids"])
        ids.append(e["input_ids"] + [pad_id] * gap)
        own = e["labels"] if loss_on == "answer" else e["input_ids"]
        labels.append(own + [IGNORE_INDEX] * gap)
        attention.append([1] * len(e["input_ids"]) + [0] * gap)
    return (
        torch.tensor(ids, dtype=torch.long),
        torch.tensor(labels, dtype=torch.long),
        torch.tensor(attention, dtype=torch.long),
        width * len(examples) - sum(len(e["input_ids"]) for e in examples),
        width * len(examples),
    )


def _dev_loss(model: Any, examples: list[dict], pad_id: int, stop_check: Callable[[], None]) -> float:
    """Token-weighted mean loss over the answer tokens, whatever ``loss_on`` is."""
    import torch
    import torch.nn.functional as F

    model.eval()
    total, count = 0.0, 0
    with torch.no_grad():
        for start in range(0, len(examples), DEV_BATCH):
            stop_check()
            ids, labels, attention, _, _ = _pad(examples[start : start + DEV_BATCH], pad_id, "answer")
            logits = model(input_ids=ids, attention_mask=attention).logits[:, :-1].float()
            target = labels[:, 1:]
            total += F.cross_entropy(
                logits.reshape(-1, logits.size(-1)),
                target.reshape(-1),
                ignore_index=IGNORE_INDEX,
                reduction="sum",
            ).item()
            count += int((target != IGNORE_INDEX).sum())
    return total / count if count else float("nan")


def _add_lora(model: Any, cfg: LabConfig) -> Any:
    import torch
    from peft import LoraConfig, get_peft_model

    linear_ids = {id(m) for m in model.get_decoder().layers.modules() if isinstance(m, torch.nn.Linear)}
    names = [name for name, module in model.named_modules() if id(module) in linear_ids]
    config = LoraConfig(
        r=cfg.lora_rank,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=0.0,
        target_modules=names,
        bias="none",
        task_type="CAUSAL_LM",
    )
    return get_peft_model(model, config)


def _score(model, tokenizer, dev, cfg, stop_check) -> tuple[float, float, list[str]]:
    """(accuracy, format rate, answers) on the dev problems with the zero-shot training frame."""
    model.eval()
    outputs: list[str] = []

    def prompt_for(problem: Problem) -> str:
        stop_check()
        return training_prompt(problem.question)

    result = evaluation.evaluate(
        model,
        tokenizer,
        dev,
        prompt_for,
        batch_size=16,
        max_new_tokens=cfg.max_new_tokens,
        on_prediction=lambda row: outputs.append(row["output"]),
    )
    with_format = sum(1 for text in outputs if _FORMAT_LINE.search(text))
    rate = with_format / len(outputs) if outputs else 0.0
    return round(result.accuracy, 4), round(rate, 4), outputs


class _MetricsFile:
    def __init__(self, path: Path, total: int, t0: float):
        self.path, self.total, self.t0 = path, total, t0

    def write(self, step: int, *, loss=None, lr=None, grad=None, dev=None) -> None:
        line = {
            "v": 1,
            "step": step,
            "total_steps": self.total,
            "loss": _finite(loss),
            "learning_rate": _finite(lr),
            "grad_norm": _finite(grad),
            "elapsed_s": round(time.perf_counter() - self.t0, 4),
            "dev_loss": _finite(dev),
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")
            fh.flush()


# ------------------------------------------------------------------ one variant


def run_variant(
    lesson_id: str,
    variant_name: str,
    label: str,
    cfg: LabConfig,
    variant_dir: Path,
    stop_check: Callable[[], None],
) -> dict:
    """Train and score one variant; writes ``metrics.jsonl`` and returns the ``summary.json`` content."""
    import torch

    variant_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = variant_dir / "metrics.jsonl"
    metrics_path.write_text("", encoding="utf-8")

    train, dev = load_lab_problems(cfg)
    stop_check()
    torch.manual_seed(cfg.seed)
    model, tokenizer = load_lab_model(cfg)
    model.to(torch.device("cpu"))
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id

    # Tokenize once, before the first step.
    t_tok = time.perf_counter()
    kept: list[tuple[Problem, dict]] = []
    for problem in train:
        for example in tokenize_examples(tokenizer, [problem], cfg.answer_format, cfg.max_seq_len):
            kept.append((problem, example))
    tokenize_seconds = time.perf_counter() - t_tok
    if not kept:
        raise ValueError(
            f"No training example is left: every one is cut at {cfg.max_seq_len} tokens before its answer. "
            "Raise max_seq_len."
        )
    examples = [example for _, example in kept]
    dev_examples = tokenize_examples(tokenizer, dev, cfg.answer_format, cfg.max_seq_len)
    if not dev_examples:
        raise ValueError("No dev example is left after the cut at max_seq_len.")
    lengths = [len(e["input_ids"]) for e in examples]

    if cfg.method == "lora":
        for param in model.parameters():
            param.requires_grad_(False)
        model = _add_lora(model, cfg)
    else:
        for param in model.parameters():
            param.requires_grad_(True)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())

    steps_per_epoch = math.ceil(len(examples) / cfg.batch_size)
    total = steps_per_epoch * cfg.epochs
    dev_at = set(_dev_steps(total))
    t0 = time.perf_counter()
    metrics = _MetricsFile(metrics_path, total, t0)

    dev_losses: list[tuple[int, float]] = []

    def dev_line(step: int) -> None:
        value = _dev_loss(model, dev_examples, pad_id, stop_check)
        dev_losses.append((step, value))
        metrics.write(step, dev=value)

    dev_line(0)
    accuracy_before, format_before, outputs_before = _score(model, tokenizer, dev, cfg, stop_check)

    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=cfg.learning_rate, weight_decay=0.0
    )
    shuffle_rng, order_rng = random.Random(cfg.seed), random.Random(cfg.seed)
    step_losses: list[float | None] = []
    pad_tokens = all_tokens = 0
    step_seconds = 0.0
    retok_seconds = 0.0
    step = 0
    model.train()
    for _ in range(cfg.epochs):
        for batch in _batches(lengths, cfg, shuffle_rng, order_rng):
            started = time.perf_counter()
            if cfg.retokenize:
                t_re = time.perf_counter()
                rows = []
                for i in batch:
                    rows.extend(
                        tokenize_examples(tokenizer, [kept[i][0]], cfg.answer_format, cfg.max_seq_len)
                    )
                retok_seconds += time.perf_counter() - t_re
            else:
                rows = [examples[i] for i in batch]
            ids, labels, attention, pads, cells = _pad(rows, pad_id, cfg.loss_on)
            pad_tokens += pads
            all_tokens += cells
            step += 1
            lr = _learning_rate(cfg, step, total)
            for group in optimizer.param_groups:
                group["lr"] = lr
            optimizer.zero_grad(set_to_none=True)
            loss = model(input_ids=ids, attention_mask=attention, labels=labels).loss
            loss.backward()
            grad = torch.nn.utils.clip_grad_norm_(
                [p for p in model.parameters() if p.requires_grad], CLIP_NORM
            )
            optimizer.step()
            step_seconds += time.perf_counter() - started
            step_losses.append(_finite(loss.item()))
            metrics.write(step, loss=loss.item(), lr=lr, grad=float(grad))
            if step in dev_at:
                dev_line(step)
                model.train()
            stop_check()

    accuracy_after, format_after, outputs_after = _score(model, tokenizer, dev, cfg, stop_check)

    last = step_losses[-10:]
    train_last = None if any(v is None for v in last) else sum(last) / len(last)
    finite_dev = [(s, v) for s, v in dev_losses if _finite(v) is not None]
    best = min(finite_dev, key=lambda item: item[1]) if finite_dev else None
    samples = [
        {"question": p.question, "gold": p.gold, "before": outputs_before[i], "after": outputs_after[i]}
        for i, p in enumerate(dev[: cfg.sample_problems])
    ]
    return {
        "v": 1,
        "lesson": lesson_id,
        "variant": variant_name,
        "label": label,
        "config": dataclasses.asdict(cfg),
        "trainable_params": trainable,
        "total_params": total_params,
        "steps": step,
        "seconds": step_seconds,
        "seconds_per_step": step_seconds / step if step else 0.0,
        "tokenize_seconds": float(tokenize_seconds),
        "retokenize_seconds_per_step": retok_seconds / step if cfg.retokenize and step else None,
        "padding_fraction": pad_tokens / all_tokens if all_tokens else 0.0,
        "peak_memory_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "train_loss_first": step_losses[0] if step_losses else None,
        "train_loss_last": train_last,
        "dev_loss_before": _finite(dev_losses[0][1]),
        "dev_loss_after": _finite(dev_losses[-1][1]),
        "dev_loss_best": best[1] if best else None,
        "dev_loss_best_step": best[0] if best else None,
        "accuracy_before": accuracy_before,
        "accuracy_after": accuracy_after,
        "format_rate_before": format_before,
        "format_rate_after": format_after,
        "samples": samples,
    }
