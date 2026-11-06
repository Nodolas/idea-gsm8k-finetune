"""Supervised fine-tuning with LoRA (US2.2, FR2.1, FR2.3, FR2.4; ADR-005).

LoRA adapters go on every linear layer of the decoder blocks (the q/k/v/o attention projections
and the gate/up/down MLP projections, never the output head) with the configuration's
rank and alpha. Training examples come from the train part of the fixed split only, never from dev
or test (NFR8); the loss counts the answer tokens only. On CUDA the model trains in bfloat16
autocast with gradient checkpointing, so the 1.7B model fits 8 GB (NFR1).

Heavy libraries (torch, transformers, peft) are imported inside the functions.
"""

from __future__ import annotations

import math
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gsm8k import evaluation
from gsm8k.datasets_prompts.hub import Problem
from gsm8k.run_config import RunConfig
from gsm8k.training.loop import LoopClock, MetricsWriter, gpu_peak_gb, make_metrics_callback
from gsm8k.training.targets import training_text

IGNORE_INDEX = -100
LORA_DROPOUT = 0.05
# Every linear layer of a Qwen3 decoder block (what peft's "all-linear" picks, written out so the
# adapter config names them plainly); the output head is never adapted.
LORA_TARGETS = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")


@dataclass
class TrainResult:
    steps: int
    seconds_per_step: float
    peak_gpu_memory_gb: float
    model: Any
    tokenizer: Any


@dataclass
class TrainingData:
    """The training problems (train part of the split), the dev problems to score and the four
    exemplars of the fixed prompt (taken from dev, BR2.1)."""

    train: list[Problem]
    dev: list[Problem]
    exemplars: list[Problem]

    def prompt_for(self, problem: Problem) -> str:
        from gsm8k.datasets_prompts import prompt

        return prompt.build_prompt(self.exemplars, problem.question)


def load_training_data(cfg: RunConfig) -> TrainingData:
    """Load GSM8K and the fixed split; ``train_examples`` takes the first N training problems by index.

    The dev problems to score are limited by ``cfg.limit``. Raises ValueError if a training problem
    were a dev or test problem (NFR8.1).
    """
    from gsm8k.datasets_prompts import hub, prompt, split

    problems = hub.load_gsm8k(cfg.dataset_revision)
    train_ids = [p.id for p in problems["train"]]
    data_split = split.load_or_build_split(train_ids, split_seed=cfg.split_seed)
    by_id = {p.id: p for p in problems["train"]}
    exemplar_ids = prompt.choose_exemplars(data_split.dev_ids, cfg.split_seed)
    chosen = split.sort_by_index(list(data_split.train_ids))
    if cfg.train_examples != "all":
        chosen = chosen[: int(cfg.train_examples)]
    forbidden = set(data_split.dev_ids) | {p.id for p in problems["test"]}
    leaked = [i for i in chosen if i in forbidden or not i.startswith(split.TRAIN_PREFIX)]
    if leaked:
        raise ValueError(f"Training data holds dev or test problems: {leaked[:3]}")
    dev = prompt.problems_to_score("dev", data_split, problems, exemplar_ids, cfg.limit)
    return TrainingData(
        train=[by_id[i] for i in chosen],
        dev=dev,
        exemplars=[by_id[i] for i in exemplar_ids],
    )


def total_steps_for(n_examples: int, batch_size: int, epochs: int, max_steps: int | None = None) -> int:
    """Optimizer steps of a run: whole batches per epoch (the last one may be short) times epochs,
    capped by ``max_steps``."""
    steps = math.ceil(n_examples / batch_size) * epochs
    if max_steps is not None:
        steps = min(steps, max_steps)
    return max(steps, 0)


def planned_examples(cfg: RunConfig) -> int:
    """How many training problems a configuration asks for (before tokenization)."""
    from gsm8k.run_config import TRAIN_SPLIT_SIZE

    return TRAIN_SPLIT_SIZE if cfg.train_examples == "all" else int(cfg.train_examples)


def score_on_dev(
    model: Any,
    tokenizer: Any,
    cfg: RunConfig,
    data: TrainingData,
    *,
    on_prediction: Callable[[dict], None] | None = None,
) -> evaluation.EvalResult:
    """Score the model on the dev problems with the fixed 4-shot prompt and the BR3.5 stop rule."""
    return evaluation.evaluate(
        model,
        tokenizer,
        data.dev,
        data.prompt_for,
        batch_size=evaluation.batch_size_for(cfg.model),
        max_new_tokens=cfg.max_new_tokens,
        on_prediction=on_prediction,
    )


def tokenize_examples(
    tokenizer: Any, problems: list[Problem], answer_format: str, max_seq_len: int
) -> list[dict]:
    """input_ids and labels per problem; prompt tokens are masked from the loss, the target ends
    with the end-of-text token, and the whole example is cut at ``max_seq_len`` tokens. An example
    with no target token left after the cut is dropped."""
    eos = tokenizer.eos_token_id
    examples = []
    for problem in problems:
        prompt, target = training_text(problem, answer_format)
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        target_ids = tokenizer(target, add_special_tokens=False)["input_ids"]
        if eos is not None:
            target_ids = [*target_ids, eos]
        input_ids = (prompt_ids + target_ids)[:max_seq_len]
        labels = ([IGNORE_INDEX] * len(prompt_ids) + target_ids)[:max_seq_len]
        if all(label == IGNORE_INDEX for label in labels):
            continue
        examples.append({"input_ids": input_ids, "labels": labels})
    return examples


class PadCollator:
    """Right-pads a batch to its longest example; padding is masked from attention and loss."""

    def __init__(self, pad_token_id: int):
        self.pad_token_id = pad_token_id

    def __call__(self, batch: list[dict]) -> dict:
        import torch

        width = max(len(item["input_ids"]) for item in batch)
        input_ids, labels, attention = [], [], []
        for item in batch:
            pad = width - len(item["input_ids"])
            input_ids.append(item["input_ids"] + [self.pad_token_id] * pad)
            labels.append(item["labels"] + [IGNORE_INDEX] * pad)
            attention.append([1] * len(item["input_ids"]) + [0] * pad)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
            "attention_mask": torch.tensor(attention, dtype=torch.long),
        }


def save_adapter(model: Any, adapter_dir: Path) -> None:
    """Save the adapter to a temporary folder next to ``adapter_dir`` and rename it into place, so a
    failure (a CUDA out-of-memory error, a stop) never leaves a half-saved adapter at that path."""
    adapter_dir = Path(adapter_dir)
    adapter_dir.parent.mkdir(parents=True, exist_ok=True)
    if adapter_dir.exists():
        raise FileExistsError(f"Adapter folder already exists: {adapter_dir}")
    tmp = Path(tempfile.mkdtemp(prefix=f".{adapter_dir.name}.partial-", dir=adapter_dir.parent))
    try:
        model.save_pretrained(str(tmp))
        os.chmod(tmp, 0o755)
        os.rename(tmp, adapter_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def train_sft(
    cfg: RunConfig,
    run_dir: Path,
    adapter_dir: Path,
    *,
    model: Any = None,
    tokenizer: Any = None,
    eval_every: int | None = None,
    max_steps: int | None = None,
    data: TrainingData | None = None,
) -> TrainResult:
    """Fine-tune ``cfg.model`` with LoRA on the training problems and save the adapter to ``adapter_dir``.

    Streams one metrics line per step to ``<run_dir>/metrics.jsonl`` and, with ``eval_every``, a
    dev-accuracy line every that many steps. ``model``/``tokenizer`` are injectable (tests); else the
    pinned model is loaded. ``max_steps`` caps the steps (tests). ``data`` avoids a second load.
    """
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import PrinterCallback, Trainer, TrainingArguments, set_seed

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if model is None or tokenizer is None:
        model, tokenizer = evaluation.load_model(cfg.model, cfg.model_revision)
    if data is None:
        data = load_training_data(cfg)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    examples = tokenize_examples(tokenizer, data.train, cfg.answer_format, cfg.max_seq_len)
    if not examples:
        raise ValueError("No training example fits the maximum sequence length")
    total_steps = total_steps_for(len(examples), cfg.batch_size, cfg.epochs, max_steps)
    if total_steps < 1:
        raise ValueError(f"max_steps must be at least 1, got {max_steps}")

    use_cuda = torch.cuda.is_available()
    if use_cuda:
        torch.cuda.reset_peak_memory_stats()
    set_seed(cfg.seed)
    lora = LoraConfig(
        r=cfg.lora_rank,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=LORA_DROPOUT,
        target_modules=list(LORA_TARGETS),
        bias="none",
        task_type="CAUSAL_LM",
    )
    peft_model = get_peft_model(model, lora)
    peft_model.print_trainable_parameters()

    def dev_eval(target: Any) -> float:
        target = target if target is not None else peft_model
        was_training = target.training
        target.eval()
        try:
            return score_on_dev(target, tokenizer, cfg, data).accuracy
        finally:
            if was_training:
                target.train()

    clock = LoopClock()
    callback = make_metrics_callback(
        MetricsWriter(run_dir), clock, total_steps, dev_eval=dev_eval, eval_every=eval_every
    )
    args = TrainingArguments(
        output_dir=str(run_dir),  # nothing is saved there (save_strategy "no"); it stays in outputs/
        per_device_train_batch_size=cfg.batch_size,
        gradient_accumulation_steps=1,
        learning_rate=cfg.learning_rate,
        max_steps=total_steps,
        warmup_steps=math.ceil(cfg.warmup_ratio * total_steps),
        lr_scheduler_type="linear",
        weight_decay=0.0,
        max_grad_norm=1.0,
        logging_strategy="steps",
        logging_steps=1,
        save_strategy="no",
        eval_strategy="no",
        report_to="none",
        seed=cfg.seed,
        data_seed=cfg.seed,
        bf16=use_cuda,
        use_cpu=not use_cuda,
        optim="adamw_torch_fused" if use_cuda else "adamw_torch",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        disable_tqdm=True,
        dataloader_num_workers=0,
        dataloader_pin_memory=use_cuda,
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=peft_model,
        args=args,
        train_dataset=examples,
        data_collator=PadCollator(tokenizer.pad_token_id),
        callbacks=[callback],
    )
    trainer.remove_callback(PrinterCallback)  # the metrics callback prints its own progress lines
    trainer.train()

    peft_model.eval()
    save_adapter(peft_model, adapter_dir)
    peak = max(clock.peak_gpu_memory_gb, gpu_peak_gb())
    return TrainResult(
        steps=clock.steps or total_steps,
        seconds_per_step=clock.seconds_per_step(),
        peak_gpu_memory_gb=peak,
        model=peft_model,
        tokenizer=tokenizer,
    )
