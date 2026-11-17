"""GRPO training with trl's ``GRPOTrainer`` on a LoRA adapter (US7.1, AC7.1.2, AC7.1.3; ADR-005).

One problem per step: the model samples ``grpo_generations`` answers to a training problem, each is
rewarded (right final number 1, plus 0.1 for a ``#### <number>`` line) and the model moves toward the
answers that scored above their group's mean. A KL term (beta 0.04) keeps it near the reference, which
for a peft model is the model with the adapter switched off (the base model). Training problems come
only from the train part of the fixed split, through the same guard as SFT. The shared metrics callback
streams ``loss``, ``reward``, ``kl`` and ``answer_length`` to ``metrics.jsonl``.

Heavy libraries (torch, transformers, peft, trl) are imported inside the functions.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from gsm8k.run_config import RunConfig
from gsm8k.training import sft
from gsm8k.training.loop import LoopClock, MetricsWriter, gpu_peak_gb, make_metrics_callback
from gsm8k.training.sft import TrainingData, TrainResult

BETA = 0.04
TEMPERATURE = 0.7
DEFAULT_GENERATIONS = 4
# C2 metrics field -> the key trl's trainer logs it under.
LOG_FIELDS = {"reward": "reward", "kl": "kl", "answer_length": "completions/mean_length"}


class GrpoStartError(ValueError):
    """The adapter to start from does not exist."""


def check_start_path(cfg: RunConfig) -> None:
    """Raise GrpoStartError naming the path when ``adapter_path`` is given but is not a folder."""
    if cfg.adapter_path is not None and not Path(cfg.adapter_path).is_dir():
        raise GrpoStartError(f"Adapter to start from not found: {cfg.adapter_path}")


def generations_for(cfg: RunConfig) -> int:
    return cfg.grpo_generations or DEFAULT_GENERATIONS


def python_headers_available() -> bool:
    """Whether ``Python.h`` exists in the interpreter's include folder or in the project's kept headers
    (AC7.1.6); Triton's C helper cannot compile without it."""
    import sysconfig

    from gsm8k import _env

    places = [Path(sysconfig.get_paths()["include"]), _env.python_header_dirs()[0]]
    return any((place / "Python.h").is_file() for place in places)


def steps_for(cfg: RunConfig, max_steps: int | None = None) -> int:
    """``grpo_steps`` when set, else the step plan for the model's saved timings; capped by ``max_steps``."""
    steps = cfg.grpo_steps
    if steps is None:
        from gsm8k.estimates import CAP_SECONDS
        from gsm8k.training.grpo_plan import closing_dev_reserve_s, plan_grpo_steps

        budget = CAP_SECONDS - closing_dev_reserve_s(cfg.model)
        steps = plan_grpo_steps(cfg.model, generations_for(cfg), budget_s=budget).steps
    return min(steps, max_steps) if max_steps is not None else steps


def stop_at_answer_end(model: Any, tokenizer: Any) -> None:
    """Make the model's ``generate`` stop each sequence at the evaluation stop rule (BR3.5: the first
    ``#### <number>`` line or a new ``Question:``). The base model rarely writes an end-of-text token,
    and trl's ``generate`` call has no stopping hook, so the criterion is added to the call here."""
    from transformers import StoppingCriteriaList

    from gsm8k import evaluation

    original = model.generate

    def generate(*args: Any, **kwargs: Any) -> Any:
        ids = kwargs.get("input_ids")
        if ids is not None and "stopping_criteria" not in kwargs:
            stop = evaluation._stop_criterion(tokenizer, ids.shape[1])
            kwargs["stopping_criteria"] = StoppingCriteriaList([stop])
        return original(*args, **kwargs)

    model.generate = generate


def train_grpo(
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
    """Run GRPO from the base model (fresh LoRA of the run's rank) or from ``cfg.adapter_path``
    (trainable) and save the adapter to ``adapter_dir``."""
    check_start_path(cfg)  # before any loader call
    import torch
    from datasets import Dataset
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import PrinterCallback, set_seed
    from trl import GRPOConfig, GRPOTrainer

    from gsm8k import train_cmd
    from gsm8k.training.grpo_rewards import total_rewards

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if data is None:
        data = sft.load_training_data(cfg)
    if model is None or tokenizer is None:
        model, tokenizer = train_cmd.load_for_config(cfg)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    if not data.train:
        raise ValueError("No training problems for GRPO")
    generations = generations_for(cfg)
    total_steps = steps_for(cfg, max_steps)
    if total_steps < 1:
        raise ValueError(f"max_steps must be at least 1, got {max_steps}")

    use_cuda = torch.cuda.is_available()
    if use_cuda:
        torch.cuda.reset_peak_memory_stats()
    set_seed(cfg.seed)
    if cfg.adapter_path is not None:
        peft_model = PeftModel.from_pretrained(model, str(cfg.adapter_path), is_trainable=True)
    else:
        lora = LoraConfig(
            r=cfg.lora_rank,
            lora_alpha=cfg.lora_alpha,
            lora_dropout=sft.LORA_DROPOUT,
            target_modules=list(sft.LORA_TARGETS),
            bias="none",
            task_type="CAUSAL_LM",
        )
        peft_model = get_peft_model(model, lora)
    peft_model.print_trainable_parameters()
    stop_at_answer_end(peft_model, tokenizer)

    dataset = Dataset.from_list([{"prompt": data.prompt_for(p), "gold": str(p.gold)} for p in data.train])

    def dev_eval(target: Any) -> float:
        target = target if target is not None else peft_model
        was_training = target.training
        target.eval()
        try:
            return sft.score_on_dev(target, tokenizer, cfg, data).accuracy
        finally:
            if was_training:
                target.train()

    clock = LoopClock()
    callback = make_metrics_callback(
        MetricsWriter(run_dir),
        clock,
        total_steps,
        dev_eval=dev_eval,
        eval_every=eval_every,
        log_fields=LOG_FIELDS,
    )
    args = GRPOConfig(
        output_dir=str(run_dir),  # nothing is saved there (save_strategy "no"); it stays in outputs/
        per_device_train_batch_size=generations,  # one problem per step: its generations are the batch
        gradient_accumulation_steps=1,
        num_generations=generations,
        max_completion_length=cfg.max_new_tokens,
        beta=BETA,
        temperature=TEMPERATURE,
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
        gradient_checkpointing=use_cuda,
        disable_tqdm=True,
        dataloader_num_workers=0,
        use_vllm=False,
    )
    trainer = GRPOTrainer(
        model=peft_model,
        reward_funcs=total_rewards,
        args=args,
        train_dataset=dataset,
        processing_class=tokenizer,
        callbacks=[callback],
    )
    trainer.remove_callback(PrinterCallback)  # the metrics callback prints its own progress lines
    trainer.train()

    peft_model.eval()
    sft.save_adapter(peft_model, adapter_dir)
    return TrainResult(
        steps=clock.steps or total_steps,
        seconds_per_step=clock.seconds_per_step(),
        peak_gpu_memory_gb=max(clock.peak_gpu_memory_gb, gpu_peak_gb()),
        model=peft_model,
        tokenizer=tokenizer,
    )
