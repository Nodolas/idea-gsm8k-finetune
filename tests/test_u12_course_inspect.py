"""u12-learning-course, US12.2: `gsm8k course inspect` on the CPU (contract C9).

The configuration and tokenizer reads go through the seams `gsm8k.course.inspect.load_config(model,
revision)` and `load_tokenizer(model, revision)`, the sample problem through
`gsm8k.course.inspect.load_sample_problem() -> (problem_id, problem_text, prompt_text)`; the tests replace
all three, so nothing is downloaded. The configurations are tiny fixtures built from transformers config
classes (GPT-NeoX, Llama, Qwen2, Qwen3), the tokenizer is a small byte-level BPE trained offline in the
test, and the expected weight counts are worked out here on the `meta` device, by part, independently of
the code under test. Outputs go to a temporary folder only.
"""

import builtins
import io
import json
import os
from datetime import datetime
from pathlib import Path

import pytest
import torch
from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers
from torch.overrides import TorchFunctionMode
from transformers import (
    AutoModelForCausalLM,
    GPT2Config,
    GPTNeoXConfig,
    LlamaConfig,
    PreTrainedTokenizerFast,
    Qwen2Config,
    Qwen3Config,
)

from gsm8k import cli
from gsm8k.datasets_prompts.hub import MODEL_REVISIONS

ROOT = Path(__file__).resolve().parents[1]

# The Course Models table of stories.md (section 12), in order: (id, revision).
COURSE_MODELS = [
    ("EleutherAI/pythia-31m", "e556ace21b489575e94e9d50b6dad2fcc7419679"),
    ("HuggingFaceTB/SmolLM2-360M", "f8027fd0eaeea54caa13c31d31b9fdc459c38b49"),
    ("Qwen/Qwen2.5-0.5B", "060db6499f32faf8b98477b0a26969ef7d8b9987"),
    ("Qwen/Qwen3-0.6B-Base", MODEL_REVISIONS["Qwen/Qwen3-0.6B-Base"]),
    ("Qwen/Qwen3-1.7B-Base", MODEL_REVISIONS["Qwen/Qwen3-1.7B-Base"]),
]
IDS = [model for model, _ in COURSE_MODELS]
PYTHIA, SMOLLM2, QWEN25, QWEN3_06, QWEN3_17 = IDS

MODEL_FIELDS = {
    "id",
    "revision",
    "licence",
    "family",
    "layers",
    "width",
    "heads",
    "kv_heads",
    "attention",
    "head_size",
    "mlp_width",
    "mlp_matrices",
    "vocab",
    "context",
    "tied_embeddings",
    "position_encoding",
    "activation",
    "weights_total",
    "weights_by_part",
    "bf16_gb",
    "int4_gb",
    "problem_tokens",
    "prompt_tokens",
    "first_tokens",
}
PARTS = ("embeddings", "attention", "mlp", "norms", "head")

PROBLEM_ID = "gsm8k-train-0042"
PROBLEM_TEXT = (
    "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. "
    "How many clips did Natalia sell altogether in April and May? Show every step of the work."
)
PROMPT_TEXT = (
    "Question: There are 15 trees in the grove. Grove workers will plant trees in the grove today. After "
    "they are done, there will be 21 trees. How many trees did the grove workers plant today?\n"
    "Answer: There are 15 trees originally. Then there were 21 trees after some more were planted. So "
    "there must have been 21 - 15 = 6. The answer is 6.\n\n"
    "Question: If there are 3 cars in the parking lot and 2 more cars arrive, how many cars are in the "
    "parking lot?\nAnswer: There are originally 3 cars. 2 more cars arrive. 3 + 2 = 5. The answer is 5.\n\n"
    f"Question: {PROBLEM_TEXT}\nAnswer:"
)


# ---------------------------------------------------------------------------------------------------
# Fixtures: a tokenizer, tiny configurations (and large ones for the memory figures), the seams.
# ---------------------------------------------------------------------------------------------------


def _train_tokenizer() -> PreTrainedTokenizerFast:
    tokenizer = Tokenizer(models.BPE())
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder = decoders.ByteLevel()
    trainer = trainers.BpeTrainer(
        vocab_size=512,
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
        special_tokens=["<|endoftext|>"],
        show_progress=False,
    )
    tokenizer.train_from_iterator([PROMPT_TEXT, PROBLEM_TEXT] * 4, trainer)
    return PreTrainedTokenizerFast(tokenizer_object=tokenizer, eos_token="<|endoftext|>")


@pytest.fixture(scope="module")
def tokenizer():
    tok = _train_tokenizer()
    assert len(tok.encode(PROBLEM_TEXT)) > 25  # first_tokens must be cut at 20
    return tok


def tiny_configs(vocab: int) -> dict:
    """One tiny configuration per course model: 2 or 3 layers, width 64, a few heads."""
    return {
        PYTHIA: GPTNeoXConfig(
            vocab_size=vocab,
            hidden_size=64,
            intermediate_size=256,
            num_hidden_layers=2,
            num_attention_heads=4,
            rotary_pct=0.25,
            max_position_embeddings=128,
            hidden_act="gelu",
        ),
        SMOLLM2: LlamaConfig(
            vocab_size=vocab,
            hidden_size=64,
            intermediate_size=192,
            num_hidden_layers=3,
            num_attention_heads=4,
            num_key_value_heads=2,
            max_position_embeddings=256,
            hidden_act="silu",
            tie_word_embeddings=True,
        ),
        QWEN25: Qwen2Config(
            vocab_size=vocab,
            hidden_size=64,
            intermediate_size=160,
            num_hidden_layers=2,
            num_attention_heads=4,
            num_key_value_heads=2,
            max_position_embeddings=512,
            hidden_act="silu",
            tie_word_embeddings=True,
        ),
        QWEN3_06: Qwen3Config(
            vocab_size=vocab,
            hidden_size=64,
            intermediate_size=128,
            num_hidden_layers=2,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=32,
            max_position_embeddings=1024,
            hidden_act="silu",
            tie_word_embeddings=True,
        ),
        QWEN3_17: Qwen3Config(
            vocab_size=vocab,
            hidden_size=64,
            intermediate_size=224,
            num_hidden_layers=3,
            num_attention_heads=4,
            num_key_value_heads=2,
            head_dim=16,
            max_position_embeddings=2048,
            hidden_act="silu",
            tie_word_embeddings=False,
        ),
    }


def big_configs(vocab: int) -> dict:
    """Large configurations (about 0.5 to 1.5 billion weights): only ever built on the meta device."""
    configs = tiny_configs(vocab)
    configs[PYTHIA] = GPTNeoXConfig(
        vocab_size=vocab,
        hidden_size=2048,
        intermediate_size=8192,
        num_hidden_layers=16,
        num_attention_heads=16,
        rotary_pct=0.25,
        max_position_embeddings=2048,
    )
    configs[SMOLLM2] = LlamaConfig(
        vocab_size=vocab,
        hidden_size=2048,
        intermediate_size=6144,
        num_hidden_layers=12,
        num_attention_heads=16,
        num_key_value_heads=4,
        tie_word_embeddings=True,
    )
    configs[QWEN25] = Qwen2Config(
        vocab_size=vocab,
        hidden_size=2048,
        intermediate_size=5632,
        num_hidden_layers=12,
        num_attention_heads=16,
        num_key_value_heads=4,
        tie_word_embeddings=True,
    )
    configs[QWEN3_06] = Qwen3Config(
        vocab_size=vocab,
        hidden_size=1024,
        intermediate_size=3072,
        num_hidden_layers=14,
        num_attention_heads=16,
        num_key_value_heads=8,
        head_dim=128,
        tie_word_embeddings=True,
    )
    configs[QWEN3_17] = Qwen3Config(
        vocab_size=vocab,
        hidden_size=2048,
        intermediate_size=6144,
        num_hidden_layers=16,
        num_attention_heads=16,
        num_key_value_heads=8,
        head_dim=128,
        tie_word_embeddings=False,
    )
    return configs


# What the tiny configurations must come out as, per model (the table of the Course Models rows).
EXPECTED = {
    PYTHIA: dict(
        family="gpt_neox", layers=2, width=64, heads=4, kv_heads=4, attention="multi-head", head_size=16,
        mlp_width=256, mlp_matrices=2, context=128, tied_embeddings=False, activation="gelu",
    ),
    SMOLLM2: dict(
        family="llama", layers=3, width=64, heads=4, kv_heads=2, attention="grouped-query", head_size=16,
        mlp_width=192, mlp_matrices=3, context=256, tied_embeddings=True, activation="silu",
    ),
    QWEN25: dict(
        family="qwen2", layers=2, width=64, heads=4, kv_heads=2, attention="grouped-query", head_size=16,
        mlp_width=160, mlp_matrices=3, context=512, tied_embeddings=True, activation="silu",
    ),
    QWEN3_06: dict(
        family="qwen3", layers=2, width=64, heads=4, kv_heads=2, attention="grouped-query", head_size=32,
        mlp_width=128, mlp_matrices=3, context=1024, tied_embeddings=True, activation="silu",
    ),
    QWEN3_17: dict(
        family="qwen3", layers=3, width=64, heads=4, kv_heads=2, attention="grouped-query", head_size=16,
        mlp_width=224, mlp_matrices=3, context=2048, tied_embeddings=False, activation="silu",
    ),
}  # fmt: skip


def build_meta(config):
    with torch.device("meta"):
        return AutoModelForCausalLM.from_config(config)


def classify(name: str) -> str:
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
    raise AssertionError(f"test helper cannot classify parameter {name}")


def expected_weights(config) -> tuple[int, dict]:
    """Total and by-part weight counts of the model built from `config` on the meta device."""
    model = build_meta(config)
    parts = dict.fromkeys(PARTS, 0)
    for name, parameter in model.named_parameters():  # tied weights are listed once
        parts[classify(name)] += parameter.numel()
    total = sum(parameter.numel() for parameter in model.parameters())
    assert sum(parts.values()) == total
    return total, parts


class Seams:
    """Replaces the three seams of gsm8k.course.inspect and records how they were called."""

    def __init__(self, monkeypatch, tokenizer, configs, problem=(PROBLEM_ID, PROBLEM_TEXT, PROMPT_TEXT)):
        self.configs = configs
        self.tokenizer = tokenizer
        self.config_calls: list[tuple[str, str]] = []
        self.tokenizer_calls: list[tuple[str, str]] = []
        self.cuda_seen: list[str | None] = []
        self.fail: dict[tuple[str, str], Exception] = {}
        monkeypatch.setattr("gsm8k.course.inspect.load_config", self.load_config)
        monkeypatch.setattr("gsm8k.course.inspect.load_tokenizer", self.load_tokenizer)
        monkeypatch.setattr("gsm8k.course.inspect.load_sample_problem", lambda: problem)

    def load_config(self, model, revision):
        self.config_calls.append((model, revision))
        self.cuda_seen.append(os.environ.get("CUDA_VISIBLE_DEVICES"))
        if ("load_config", model) in self.fail:
            raise self.fail[("load_config", model)]
        return self.configs[model]

    def load_tokenizer(self, model, revision):
        self.tokenizer_calls.append((model, revision))
        self.cuda_seen.append(os.environ.get("CUDA_VISIBLE_DEVICES"))
        if ("load_tokenizer", model) in self.fail:
            raise self.fail[("load_tokenizer", model)]
        return self.tokenizer


@pytest.fixture
def seams(monkeypatch, tokenizer):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")  # so the handler's change is visible, and undone
    return Seams(monkeypatch, tokenizer, tiny_configs(len(tokenizer)))


def run_inspect(outputs: Path | None, *extra: str) -> int:
    args = ["course", "inspect"]
    if outputs is not None:
        args += ["--outputs", str(outputs)]
    return cli.main([*args, *extra])


def architectures_path(outputs: Path) -> Path:
    return outputs / "course" / "architectures.json"


@pytest.fixture
def inspected(seams, tmp_project_dirs):
    """Runs the command once on the tiny configurations; returns (exit code, parsed file, seams)."""
    code = run_inspect(tmp_project_dirs.outputs)
    path = architectures_path(tmp_project_dirs.outputs)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return code, data, seams


def entry(data: dict, model: str) -> dict:
    return next(item for item in data["models"] if item["id"] == model)


# ---------------------------------------------------------------------------------------------------
# AC12.2.1
# ---------------------------------------------------------------------------------------------------


def test_AC12_2_1_writes_architectures_json_with_one_entry_per_course_model_in_table_order(inspected):
    code, data, _ = inspected
    assert code == 0
    assert data is not None
    assert data["v"] == 1
    assert data["sample_problem_id"] == PROBLEM_ID
    assert datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
    assert [item["id"] for item in data["models"]] == IDS
    assert [item["revision"] for item in data["models"]] == [revision for _, revision in COURSE_MODELS]


def test_AC12_2_1_every_entry_has_every_c9_field(inspected):
    _, data, _ = inspected
    for item in data["models"]:
        assert MODEL_FIELDS <= set(item), (item["id"], MODEL_FIELDS - set(item))
        assert set(item["weights_by_part"]) == set(PARTS)
        assert len(item["first_tokens"]) <= 20


def test_AC12_2_1_reads_each_model_at_its_pinned_revision_and_takes_the_licence_from_the_table(inspected):
    _, data, seams = inspected
    assert sorted(seams.config_calls) == sorted(COURSE_MODELS)
    assert sorted(seams.tokenizer_calls) == sorted(COURSE_MODELS)
    assert [item["licence"] for item in data["models"]] == ["Apache-2.0"] * 5


def test_AC12_2_1_configuration_fields_come_from_each_models_configuration(inspected):
    _, data, _ = inspected
    for model, wanted in EXPECTED.items():
        item = entry(data, model)
        for key, value in wanted.items():
            assert item[key] == value, (model, key, item[key], value)
        assert item["vocab"] == len(inspected[2].tokenizer)


def test_AC12_2_1_attention_kind_is_multi_head_when_kv_heads_equal_heads_else_grouped_query(inspected):
    _, data, _ = inspected
    for item in data["models"]:
        wanted = "multi-head" if item["kv_heads"] == item["heads"] else "grouped-query"
        assert item["attention"] == wanted, item["id"]
    assert entry(data, PYTHIA)["attention"] == "multi-head"
    assert entry(data, SMOLLM2)["attention"] == "grouped-query"
    assert entry(data, QWEN3_06)["attention"] == "grouped-query"


def test_AC12_2_1_mlp_matrices_are_three_for_gated_mlps_and_two_for_gpt_neox(inspected):
    _, data, _ = inspected
    assert entry(data, PYTHIA)["mlp_matrices"] == 2
    for model in (SMOLLM2, QWEN25, QWEN3_06, QWEN3_17):
        assert entry(data, model)["mlp_matrices"] == 3, model


def test_AC12_2_1_position_encoding_is_rotary_for_rope_configurations(inspected):
    # In the installed transformers the rotary settings of a configuration live in `rope_parameters`
    # (`rope_theta`, `partial_rotary_factor`), so they are not always attributes of their own.
    _, data, _ = inspected
    for item in data["models"]:
        assert item["position_encoding"] == "rotary", item["id"]


def test_AC12_2_1_position_encoding_is_learned_without_rotary_settings(seams, tmp_project_dirs):
    config = GPT2Config(
        vocab_size=len(seams.tokenizer), n_positions=128, n_embd=64, n_layer=2, n_head=4, n_inner=256
    )
    seams.configs[PYTHIA] = config
    assert run_inspect(tmp_project_dirs.outputs) == 0
    data = json.loads(architectures_path(tmp_project_dirs.outputs).read_text(encoding="utf-8"))
    item = entry(data, PYTHIA)
    total, parts = expected_weights(config)
    assert item["position_encoding"] == "learned"
    assert item["weights_by_part"]["embeddings"] == parts["embeddings"]  # token plus position embeddings
    assert item["weights_total"] == total
    assert entry(data, QWEN3_06)["position_encoding"] == "rotary"


def test_AC12_2_1_weights_by_part_sum_to_weights_total(inspected):
    _, data, _ = inspected
    for item in data["models"]:
        parts = item["weights_by_part"]
        assert all(isinstance(value, int) and value >= 0 for value in parts.values()), item["id"]
        assert sum(parts.values()) == item["weights_total"], item["id"]


def test_AC12_2_1_weights_total_and_parts_equal_those_of_a_model_built_from_the_same_configuration(inspected):
    _, data, seams = inspected
    for model, config in seams.configs.items():
        total, parts = expected_weights(config)
        item = entry(data, model)
        assert item["weights_total"] == total, model
        assert item["weights_by_part"] == parts, model


def test_AC12_2_1_head_is_zero_when_embeddings_are_tied_and_counted_when_they_are_not(inspected):
    _, data, seams = inspected
    for model, config in seams.configs.items():
        item = entry(data, model)
        assert item["tied_embeddings"] is bool(config.tie_word_embeddings)
        if item["tied_embeddings"]:
            assert item["weights_by_part"]["head"] == 0, model
        else:
            assert item["weights_by_part"]["head"] == len(seams.tokenizer) * 64, model
    assert entry(data, QWEN3_06)["weights_by_part"]["head"] == 0
    assert entry(data, QWEN3_17)["weights_by_part"]["head"] > 0


def test_AC12_2_1_memory_of_the_weights_is_given_in_gb_with_two_decimals(
    monkeypatch, tokenizer, tmp_project_dirs
):
    # Large configurations (built on the meta device only) so that two decimals say something.
    configs = big_configs(len(tokenizer))
    Seams(monkeypatch, tokenizer, configs)
    assert run_inspect(tmp_project_dirs.outputs) == 0
    data = json.loads(architectures_path(tmp_project_dirs.outputs).read_text(encoding="utf-8"))
    for model, config in configs.items():
        total, _ = expected_weights(config)
        item = entry(data, model)
        assert item["weights_total"] == total
        for key in ("bf16_gb", "int4_gb"):
            assert isinstance(item[key], float), (model, key)
            assert round(item[key], 2) == item[key], (model, key)
        # bf16 is 2 bytes a weight; GB is 10^9 or 2^30 bytes.
        bf16 = [round(total * 2 / unit, 2) for unit in (1e9, 2**30)]
        assert any(abs(item["bf16_gb"] - wanted) <= 0.011 for wanted in bf16), (model, item["bf16_gb"], bf16)
        # 4-bit is 0.5 bytes a weight (0.55 with the quantization constants).
        int4 = [round(total * bytes_ / unit, 2) for unit in (1e9, 2**30) for bytes_ in (0.5, 0.55)]
        assert any(abs(item["int4_gb"] - wanted) <= 0.011 for wanted in int4), (model, item["int4_gb"], int4)
        assert 0 < item["int4_gb"] < item["bf16_gb"]


def test_AC12_2_1_sample_problem_token_counts_and_first_twenty_tokens(inspected):
    _, data, seams = inspected
    tokenizer = seams.tokenizer
    problem_tokens = len(tokenizer(PROBLEM_TEXT)["input_ids"])
    prompt_tokens = len(tokenizer(PROMPT_TEXT)["input_ids"])
    assert problem_tokens > 20
    for item in data["models"]:
        assert item["problem_tokens"] == problem_tokens, item["id"]
        assert item["prompt_tokens"] == prompt_tokens, item["id"]
        assert item["prompt_tokens"] > item["problem_tokens"]
        assert len(item["first_tokens"]) == 20
        assert all(isinstance(token, str) for token in item["first_tokens"])


def test_AC12_2_1_first_tokens_are_fewer_than_twenty_when_the_problem_is_shorter(
    monkeypatch, tokenizer, tmp_project_dirs
):
    short = "What is 3 plus 4?"
    Seams(monkeypatch, tokenizer, tiny_configs(len(tokenizer)), problem=("gsm8k-train-0007", short, short))
    assert run_inspect(tmp_project_dirs.outputs) == 0
    data = json.loads(architectures_path(tmp_project_dirs.outputs).read_text(encoding="utf-8"))
    count = len(tokenizer(short)["input_ids"])
    assert 0 < count < 20
    for item in data["models"]:
        assert item["problem_tokens"] == count
        assert len(item["first_tokens"]) == count
        assert all(isinstance(token, str) for token in item["first_tokens"])


def test_AC12_2_1_exits_zero_and_writes_to_the_default_outputs_folder_without_the_option(
    seams, tmp_project_dirs
):
    # GSM8K_OUTPUTS_DIR (tmp_project_dirs) is the default outputs folder.
    assert run_inspect(None) == 0
    data = json.loads(architectures_path(tmp_project_dirs.outputs).read_text(encoding="utf-8"))
    assert [item["id"] for item in data["models"]] == IDS


def test_AC12_2_1_a_second_run_replaces_the_file_and_leaves_no_temporary_files(seams, tmp_project_dirs):
    course = tmp_project_dirs.outputs / "course"
    course.mkdir()
    architectures_path(tmp_project_dirs.outputs).write_text('{"v": 1, "models": []}', encoding="utf-8")
    assert run_inspect(tmp_project_dirs.outputs) == 0
    data = json.loads(architectures_path(tmp_project_dirs.outputs).read_text(encoding="utf-8"))
    assert len(data["models"]) == 5
    assert [path.name for path in course.iterdir()] == ["architectures.json"]


# ---------------------------------------------------------------------------------------------------
# AC12.2.2
# ---------------------------------------------------------------------------------------------------


def test_AC12_2_2_the_handler_hides_the_gpu_before_it_reads_any_model(inspected):
    code, _, seams = inspected
    assert code == 0
    assert seams.cuda_seen  # the seams were reached
    assert set(seams.cuda_seen) == {""}
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""


class _NoRealTensors(TorchFunctionMode):
    """Fails the first time a large tensor is created off the meta device."""

    def __init__(self):
        super().__init__()
        self.big: list[tuple[str, int]] = []

    def __torch_function__(self, func, types, args=(), kwargs=None):
        result = func(*args, **(kwargs or {}))
        if isinstance(result, torch.Tensor) and result.device.type != "meta" and result.numel() > 1_000_000:
            self.big.append((str(func), result.numel()))
            raise AssertionError(f"a real tensor of {result.numel()} values was created")
        return result


def test_AC12_2_2_counts_the_weights_on_the_meta_device_without_loading_them(
    monkeypatch, tokenizer, tmp_project_dirs
):
    def refuse(*args, **kwargs):
        raise AssertionError("the weights must not be loaded")

    for target in (
        "transformers.AutoModelForCausalLM.from_pretrained",
        "transformers.PreTrainedModel.from_pretrained",
        "huggingface_hub.snapshot_download",
        "huggingface_hub.hf_hub_download",
    ):
        monkeypatch.setattr(target, refuse)
    monkeypatch.setattr("safetensors.torch.load_file", refuse)
    Seams(monkeypatch, tokenizer, big_configs(len(tokenizer)))
    guard = _NoRealTensors()
    with guard:
        code = run_inspect(tmp_project_dirs.outputs)
    assert guard.big == []
    assert code == 0
    data = json.loads(architectures_path(tmp_project_dirs.outputs).read_text(encoding="utf-8"))
    assert entry(data, QWEN3_17)["weights_total"] > 500_000_000


class _OpenSpy:
    def __init__(self, monkeypatch):
        self.paths: list[str] = []
        real = builtins.open

        def spy(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                self.paths.append(os.fsdecode(file))
            return real(file, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", spy)
        monkeypatch.setattr(io, "open", spy)


def test_AC12_2_2_never_reads_or_writes_the_run_log_the_run_lock_or_the_queue(
    seams, tmp_project_dirs, monkeypatch
):
    results = ROOT / "results" / "runs.csv"
    before = results.read_bytes() if results.exists() else None
    spy = _OpenSpy(monkeypatch)
    assert run_inspect(tmp_project_dirs.outputs) == 0
    assert (results.read_bytes() if results.exists() else None) == before
    outputs = tmp_project_dirs.outputs
    assert not (outputs / "run.lock").exists()
    assert not (outputs / "queue").exists()
    assert not tmp_project_dirs.results.exists()  # the fixture's temporary run log path
    assert sorted(path.name for path in outputs.iterdir()) == ["course"]
    for opened in spy.paths:
        parts = Path(opened).parts
        assert Path(opened).name not in {"runs.csv", "run.lock"}, opened
        assert "queue" not in parts, opened
        assert str(ROOT / "results") not in opened, opened


def test_AC12_2_2_the_handler_sets_cuda_visible_devices_to_empty(seams):
    # The test setup had the GPU visible ("0"), so the empty value comes from the command's handler.
    assert os.environ["CUDA_VISIBLE_DEVICES"] == "0"
    assert run_inspect(None) == 0
    assert os.environ["CUDA_VISIBLE_DEVICES"] == ""


@pytest.mark.parametrize(
    ("seam", "model", "error"),
    [
        ("load_config", PYTHIA, OSError("config.json could not be read")),
        ("load_config", QWEN25, ValueError("not a configuration")),
        ("load_config", QWEN3_17, OSError("offline")),
        ("load_tokenizer", SMOLLM2, OSError("tokenizer files could not be read")),
        ("load_tokenizer", QWEN3_06, ValueError("bad tokenizer")),
        ("load_tokenizer", QWEN3_17, OSError("offline")),
    ],
)
def test_AC12_2_2_a_model_that_cannot_be_read_ends_with_exit_1_naming_it_and_writes_nothing(
    seams, tmp_project_dirs, capsys, seam, model, error
):
    seams.fail[(seam, model)] = error
    code = run_inspect(tmp_project_dirs.outputs)
    out = capsys.readouterr()
    assert code == 1
    assert model in out.out + out.err
    assert [path for path in tmp_project_dirs.outputs.rglob("*") if path.is_file()] == []


def test_AC12_2_2_a_failed_run_does_not_replace_an_existing_architectures_json(
    seams, tmp_project_dirs, capsys
):
    course = tmp_project_dirs.outputs / "course"
    course.mkdir()
    old = '{"v": 1, "generated_at": "2026-11-01T00:00:00Z", "sample_problem_id": "x", "models": []}'
    architectures_path(tmp_project_dirs.outputs).write_text(old, encoding="utf-8")
    seams.fail[("load_tokenizer", QWEN3_17)] = OSError("offline")  # the last model: nothing partial
    code = run_inspect(tmp_project_dirs.outputs)
    out = capsys.readouterr()
    assert code == 1
    assert QWEN3_17 in out.out + out.err
    assert architectures_path(tmp_project_dirs.outputs).read_text(encoding="utf-8") == old
    assert [path.name for path in course.iterdir()] == ["architectures.json"]
