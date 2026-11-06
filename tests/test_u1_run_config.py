"""AC1.4.5 config_hash (BR4.5, contract C2) and the RunConfig helpers it relies on.

C2 hash rule: sha256 of the canonical JSON (sorted keys, compact separators; u1 tech-stack-decisions.md)
of {model, method} plus every other field whose value differs from its documented default, without
run_id and v. No model, no GPU; files only under pytest's tmp_path.
"""

import dataclasses
import hashlib
import json

import pytest

from gsm8k.datasets_prompts.hub import DATASET_REVISION, MODEL_REVISIONS
from gsm8k.run_config import (
    ConfigError,
    RunConfig,
    config_hash,
    from_dict,
    read_config,
    to_dict,
    validate,
)

RUN_ID = "q06-base-dev-1"
MODEL_06 = "Qwen/Qwen3-0.6B-Base"
MODEL_17 = "Qwen/Qwen3-1.7B-Base"

C2_FIELDS = {
    "v",
    "run_id",
    "model",
    "method",
    "split",
    "adapter_path",
    "learning_rate",
    "epochs",
    "lora_rank",
    "lora_alpha",
    "max_seq_len",
    "train_examples",
    "batch_size",
    "warmup_ratio",
    "seed",
    "split_seed",
    "model_revision",
    "dataset_revision",
    "answer_format",
    "limit",
    "vote_samples",
    "calculator",
    "max_new_tokens",
    "grpo_steps",
    "grpo_generations",
}

# One non-default value for every C2 field that enters the hash (all but run_id and v).
CHANGED_VALUES = {
    "model": MODEL_17,
    "method": "sft",
    "split": "test",
    "adapter_path": "checkpoints/q06-sft-dev-1",
    "learning_rate": 1e-4,
    "epochs": 2,
    "lora_rank": 8,
    "lora_alpha": 16,
    "max_seq_len": 256,
    "train_examples": 100,
    "batch_size": 8,
    "warmup_ratio": 0.1,
    "seed": 7,
    "split_seed": 43,
    "model_revision": "0" * 40,
    "dataset_revision": "1" * 40,
    "answer_format": "terse",
    "limit": 3,
    "vote_samples": 5,
    "calculator": True,
    "max_new_tokens": 256,
    "grpo_steps": 10,
    "grpo_generations": 4,
}


def _expected_hash(fields: dict) -> str:
    text = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_AC1_4_5_defaults_match_documented_values():
    cfg = RunConfig(run_id=RUN_ID)
    assert set(to_dict(cfg)) == C2_FIELDS
    assert cfg.v == 1
    assert cfg.run_id == RUN_ID
    assert cfg.model == MODEL_06
    assert cfg.method == "base"
    assert cfg.split == "dev"
    assert cfg.adapter_path is None
    assert cfg.learning_rate == pytest.approx(2e-4)
    assert cfg.epochs == 1
    assert cfg.lora_rank == 16
    assert cfg.lora_alpha == 32
    assert cfg.max_seq_len == 512
    assert cfg.train_examples == "all"
    assert cfg.batch_size == 4
    assert cfg.warmup_ratio == pytest.approx(0.03)
    assert cfg.seed == 42
    assert cfg.split_seed == 42
    assert cfg.model_revision == MODEL_REVISIONS[MODEL_06]
    assert cfg.dataset_revision == DATASET_REVISION
    assert cfg.answer_format == "step-by-step"
    assert cfg.limit is None
    assert cfg.vote_samples == 1
    assert cfg.calculator is False
    assert cfg.max_new_tokens == 512
    assert cfg.grpo_steps is None
    assert cfg.grpo_generations is None


def test_AC1_4_5_same_config_and_seed_give_same_hash():
    first = RunConfig(run_id=RUN_ID, seed=7, limit=3)
    second = RunConfig(run_id=RUN_ID, seed=7, limit=3)
    assert config_hash(first) == config_hash(second)
    digest = config_hash(first)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_AC1_4_5_run_id_and_v_do_not_change_hash():
    base = RunConfig(run_id=RUN_ID)
    assert config_hash(base) == config_hash(dataclasses.replace(base, run_id="q06-base-dev-2"))
    assert config_hash(base) == config_hash(dataclasses.replace(base, run_id="adhoc-20261101-201530"))
    assert config_hash(base) == config_hash(dataclasses.replace(base, v=2))


@pytest.mark.parametrize("field", sorted(CHANGED_VALUES))
def test_AC1_4_5_any_dial_changed_changes_hash(field):
    base = RunConfig(run_id=RUN_ID)
    changed_value = CHANGED_VALUES[field]
    assert getattr(base, field) != changed_value, f"{field}: test value equals the default"
    changed = dataclasses.replace(base, **{field: changed_value})
    assert config_hash(changed) != config_hash(base)


def test_AC1_4_5_different_values_of_one_dial_give_different_hashes():
    hashes = {config_hash(RunConfig(run_id=RUN_ID, seed=s)) for s in (0, 1, 7, 42, 2**31 - 1)}
    assert len(hashes) == 5


def test_AC1_4_5_default_config_hashes_only_model_and_method():
    cfg = RunConfig(run_id=RUN_ID)
    assert config_hash(cfg) == _expected_hash({"model": MODEL_06, "method": "base"})


def test_AC1_4_5_non_default_fields_join_the_hash_input():
    cfg = RunConfig(run_id=RUN_ID, seed=7, limit=3, max_new_tokens=256)
    expected = _expected_hash(
        {"model": MODEL_06, "method": "base", "seed": 7, "limit": 3, "max_new_tokens": 256}
    )
    assert config_hash(cfg) == expected


def test_AC1_4_5_field_at_default_hashes_like_one_without_it():
    without = from_dict({"run_id": RUN_ID})
    with_defaults = from_dict({"run_id": RUN_ID, "seed": 42, "max_new_tokens": 512, "limit": None})
    assert config_hash(without) == config_hash(with_defaults)
    assert config_hash(without) == config_hash(RunConfig(run_id=RUN_ID))


def test_AC1_4_5_to_dict_from_dict_round_trip_keeps_hash():
    cfg = RunConfig(run_id=RUN_ID, seed=7, limit=3, max_new_tokens=256, split="test")
    data = to_dict(cfg)
    assert data["v"] == 1
    assert data["run_id"] == RUN_ID
    assert data["max_new_tokens"] == 256
    json.dumps(data)  # JSON-serialisable as written to config.json
    again = from_dict(data)
    assert again == cfg
    assert config_hash(again) == config_hash(cfg)


def test_AC1_4_5_from_dict_ignores_unknown_keys():
    data = to_dict(RunConfig(run_id=RUN_ID, seed=7))
    data["a_field_added_later"] = "whatever"
    cfg = from_dict(data)
    assert cfg.seed == 7
    assert config_hash(cfg) == config_hash(RunConfig(run_id=RUN_ID, seed=7))


def test_AC1_4_5_read_config_reads_written_file(tmp_path):
    cfg = RunConfig(run_id=RUN_ID, limit=3, max_new_tokens=256)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(to_dict(cfg)), encoding="utf-8")
    loaded = read_config(path)
    assert loaded == cfg
    assert config_hash(loaded) == config_hash(cfg)


def test_AC1_4_5_validate_accepts_defaults_and_names_a_bad_dial():
    validate(RunConfig(run_id=RUN_ID))
    validate(RunConfig(run_id=RUN_ID, limit=3, max_new_tokens=256, seed=0))
    with pytest.raises(ConfigError) as bad_rate:
        validate(RunConfig(run_id=RUN_ID, learning_rate=1.0))
    assert "learning" in str(bad_rate.value).lower()
    with pytest.raises(ConfigError) as bad_model:
        validate(RunConfig(run_id=RUN_ID, model="gpt2"))
    assert "model" in str(bad_model.value).lower()
    with pytest.raises(ConfigError) as bad_rank:
        validate(RunConfig(run_id=RUN_ID, lora_rank=7))
    assert "rank" in str(bad_rank.value).lower()
