"""Part A data (u1-eval-skeleton): GSM8K loading, the fixed dev split and the 4-shot prompt.

Criteria AC1.1.1, AC1.1.2, AC1.1.3, AC1.1.5 (US1.1) and AC1.2.1, AC1.2.2, AC1.2.3 (US1.2) in
stories.md; rules BR1.2-BR1.6 and BR2.1-BR2.3 in the u1 functional design rules.md. Split files
go to the temp outputs folder of `tmp_project_dirs`, never the project's outputs/.
"""

import json
import os
import random
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from gsm8k._env import ROOT
from gsm8k.datasets_prompts.hub import DATASET_CONFIG, DATASET_ID, Problem, load_gsm8k
from gsm8k.datasets_prompts.prompt import (
    build_prompt,
    choose_exemplars,
    problems_to_score,
    strip_calculator_notes,
)
from gsm8k.datasets_prompts.split import (
    DEV_SIZE,
    SPLIT_SEED,
    Split,
    SplitFileError,
    build_split,
    load_or_build_split,
    split_path,
    validate_split,
)

N_TRAIN = 7473
N_TEST = 1319
N_DEV = 500
N_EXEMPLARS = 4


def index_of(problem_id: str) -> int:
    return int(problem_id.rsplit("-", 1)[1])


def by_index(ids: list[str]) -> list[str]:
    return sorted(ids, key=index_of)


@pytest.fixture(scope="session")
def gsm8k_data() -> dict[str, list[Problem]]:
    """The real GSM8K splits, loaded once (downloaded into the project's .cache/ if missing)."""
    return load_gsm8k()


@pytest.fixture(scope="session")
def train_ids(gsm8k_data) -> list[str]:
    return [p.id for p in gsm8k_data["train"]]


@pytest.fixture(scope="session")
def gsm8k_test_ids(gsm8k_data) -> list[str]:
    return [p.id for p in gsm8k_data["test"]]


def _make_problem(i: int, split: str = "train") -> Problem:
    return Problem(
        id=f"gsm8k-{split}-{i}",
        question=f"Sam has {i} apples and buys 2 more. How many apples does he have?",
        answer=f"Sam has {i} + 2 = <<{i}+2={i + 2}>>{i + 2} apples.\n#### {i + 2}",
        gold=str(i + 2),
    )


def _add_to_string_lists(node, value: str):
    """Append `value` to every list of strings in a parsed JSON document (format-agnostic tamper)."""
    if isinstance(node, dict):
        for v in node.values():
            _add_to_string_lists(v, value)
    elif isinstance(node, list):
        if node and all(isinstance(x, str) for x in node):
            node.append(value)
        else:
            for v in node:
                _add_to_string_lists(v, value)


# ---------------------------------------------------------------- AC1.1.1 (BR1.2)


def test_AC1_1_1_loads_without_token_into_project_cache(tmp_path):
    """openai/gsm8k config main loads with no login or token, and every cache lies under ROOT/.cache."""
    assert DATASET_ID == "openai/gsm8k"
    assert DATASET_CONFIG == "main"
    env = {k: v for k, v in os.environ.items() if k not in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")}
    env["HF_TOKEN"] = "hf_this_token_must_be_removed"  # setup_env must drop it (NFR6.2)
    env["HF_TOKEN_PATH"] = str(tmp_path / "no-token-here" / "token")  # no stored token either
    script = (
        "import json\n"
        "import gsm8k\n"
        "import datasets\n"
        "import huggingface_hub\n"
        "from huggingface_hub import constants\n"
        "from gsm8k.datasets_prompts.hub import load_gsm8k\n"
        "data = load_gsm8k()\n"
        "print(json.dumps({'token': huggingface_hub.get_token(),"
        " 'hub_cache': str(constants.HF_HUB_CACHE),"
        " 'datasets_cache': str(datasets.config.HF_DATASETS_CACHE),"
        " 'hf_home': str(constants.HF_HOME),"
        " 'train': len(data['train']), 'test': len(data['test'])}))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr
    info = json.loads(proc.stdout.strip().splitlines()[-1])
    assert info["token"] is None
    assert (info["train"], info["test"]) == (N_TRAIN, N_TEST)
    cache_root = (ROOT / ".cache").resolve()
    for key in ("hub_cache", "datasets_cache", "hf_home"):
        assert Path(info[key]).resolve().is_relative_to(cache_root), (key, info[key])
    found = [p for p in (ROOT / ".cache" / "huggingface").rglob("*gsm8k*")]
    assert found, "no gsm8k files under the project's .cache/huggingface"
    assert all(p.resolve().is_relative_to(cache_root) for p in found)


def test_AC1_1_1_problems_have_ids_and_gold(gsm8k_data):
    """Ids follow row order (gsm8k-train-<i>, gsm8k-test-<i>); gold is the number after ####."""
    assert set(gsm8k_data) == {"train", "test"}
    train, test = gsm8k_data["train"], gsm8k_data["test"]
    assert len(train) == N_TRAIN
    assert len(test) == N_TEST
    assert [p.id for p in train] == [f"gsm8k-train-{i}" for i in range(N_TRAIN)]
    assert [p.id for p in test] == [f"gsm8k-test-{i}" for i in range(N_TEST)]
    for p in train[:50] + test[:50]:
        assert p.question
        assert "####" in p.answer
        assert p.gold == p.answer.split("####")[-1].strip()
    with pytest.raises(FrozenInstanceError):
        train[0].gold = "0"  # type: ignore[misc]


# ---------------------------------------------------------------- AC1.1.2 (BR1.3, BR1.4)


def test_AC1_1_2_split_is_same_twice_disjoint_and_complete(train_ids):
    assert SPLIT_SEED == 42
    assert DEV_SIZE == N_DEV
    a = build_split(train_ids, 42)
    b = build_split(list(train_ids), 42)
    assert isinstance(a, Split)
    assert a.split_seed == 42
    assert a.dev_ids == b.dev_ids
    assert a.train_ids == b.train_ids
    assert len(a.dev_ids) == N_DEV
    assert len(a.train_ids) == N_TRAIN - N_DEV == 6973
    assert len(set(a.dev_ids)) == N_DEV
    assert len(set(a.train_ids)) == 6973
    assert not set(a.dev_ids) & set(a.train_ids)
    assert set(a.dev_ids) | set(a.train_ids) == set(train_ids)
    validate_split(a, train_ids)


def test_AC1_1_2_split_follows_seeded_shuffle_rule(train_ids):
    """BR1.3: sort by index, shuffle with random.Random(split_seed), first 500 dev; lists sorted by index."""
    order = by_index(train_ids)
    random.Random(42).shuffle(order)
    expected_dev = by_index(order[:N_DEV])
    expected_train = by_index(order[N_DEV:])
    shuffled_input = list(train_ids)
    random.Random(7).shuffle(shuffled_input)
    split = build_split(shuffled_input, 42)
    assert split.dev_ids == expected_dev
    assert split.train_ids == expected_train
    assert build_split(train_ids).dev_ids == expected_dev  # default seed is 42


def test_AC1_1_2_other_seed_gives_other_split(train_ids):
    assert build_split(train_ids, 43).dev_ids != build_split(train_ids, 42).dev_ids


def test_AC1_1_2_validate_rejects_overlap_and_gaps(train_ids):
    good = build_split(train_ids, 42)
    overlap = Split(dev_ids=good.dev_ids, train_ids=good.train_ids + [good.dev_ids[0]], split_seed=42)
    with pytest.raises(ValueError):
        validate_split(overlap, train_ids)
    gap = Split(dev_ids=good.dev_ids, train_ids=good.train_ids[1:], split_seed=42)
    with pytest.raises(ValueError):
        validate_split(gap, train_ids)


# ---------------------------------------------------------------- AC1.1.3 (BR1.5)


def test_AC1_1_3_no_test_problem_in_dev_or_train(train_ids, gsm8k_test_ids):
    split = build_split(train_ids, 42)
    assert len(gsm8k_test_ids) == N_TEST
    tests = set(gsm8k_test_ids)
    assert not tests & set(split.dev_ids)
    assert not tests & set(split.train_ids)
    assert not any(i.startswith("gsm8k-test-") for i in split.dev_ids + split.train_ids)
    tainted = Split(dev_ids=split.dev_ids + ["gsm8k-test-0"], train_ids=split.train_ids, split_seed=42)
    with pytest.raises(ValueError):
        validate_split(tainted, train_ids)


# ---------------------------------------------------------------- AC1.1.5 (BR1.6)


def test_AC1_1_5_missing_split_file_is_rebuilt_with_same_ids(tmp_project_dirs, train_ids):
    path = split_path()
    assert path == tmp_project_dirs.outputs / "splits" / "gsm8k-split42.json"
    assert not path.exists()
    first = load_or_build_split(train_ids)
    assert path.is_file()
    assert sorted(p.name for p in path.parent.iterdir()) == [path.name]  # atomic save, no temp left
    expected = build_split(train_ids, 42)
    assert (first.dev_ids, first.train_ids) == (expected.dev_ids, expected.train_ids)
    again = load_or_build_split(train_ids)  # read back from the file
    assert (again.dev_ids, again.train_ids) == (expected.dev_ids, expected.train_ids)
    path.unlink()
    rebuilt = load_or_build_split(train_ids)
    assert path.is_file()
    assert (rebuilt.dev_ids, rebuilt.train_ids) == (expected.dev_ids, expected.train_ids)


def test_AC1_1_5_corrupt_split_file_stops_naming_the_file(tmp_project_dirs, train_ids):
    path = split_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{this is not json", encoding="utf-8")
    with pytest.raises(SplitFileError) as err:
        load_or_build_split(train_ids)
    assert str(err.value) == f"Split file could not be read: {path}"
    assert path.read_text(encoding="utf-8") == "{this is not json"  # not silently replaced


def test_AC1_1_5_invalid_split_file_counts_as_unreadable(tmp_project_dirs, train_ids):
    """A parsable file that fails BR1.4/BR1.5 (here: a test id added) stops the run too."""
    path = tmp_project_dirs.outputs / "custom" / "split.json"
    load_or_build_split(train_ids, path=path)
    assert path.is_file()
    doc = json.loads(path.read_text(encoding="utf-8"))
    _add_to_string_lists(doc, "gsm8k-test-0")
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SplitFileError) as err:
        load_or_build_split(train_ids, path=path)
    assert str(path) in str(err.value)


# ---------------------------------------------------------------- AC1.2.1 (BR2.1)


def test_AC1_2_1_exemplars_deterministic_from_seed(train_ids):
    split = build_split(train_ids, 42)
    a = choose_exemplars(split.dev_ids, 42)
    b = choose_exemplars(list(split.dev_ids), 42)
    assert a == b
    assert len(a) == N_EXEMPLARS
    assert len(set(a)) == N_EXEMPLARS
    assert set(a) <= set(split.dev_ids)
    expected = random.Random(42).sample(by_index(split.dev_ids), N_EXEMPLARS)
    assert a == expected  # seeded sample of the index-sorted dev ids, sampled order kept
    shuffled = list(split.dev_ids)
    random.Random(3).shuffle(shuffled)
    assert choose_exemplars(shuffled) == expected  # default seed 42, input order irrelevant


# ---------------------------------------------------------------- AC1.2.2 (BR2.2)


def test_AC1_2_2_dev_scoring_leaves_out_exemplars(gsm8k_data, train_ids):
    split = build_split(train_ids, 42)
    exemplars = choose_exemplars(split.dev_ids, 42)
    dev = problems_to_score("dev", split, gsm8k_data, exemplars)
    ids = [p.id for p in dev]
    assert len(ids) == 496
    assert not set(ids) & set(exemplars)
    assert set(ids) == set(split.dev_ids) - set(exemplars)
    assert ids == by_index(ids)
    assert all(isinstance(p, Problem) for p in dev)
    limited = problems_to_score("dev", split, gsm8k_data, exemplars, limit=3)
    assert [p.id for p in limited] == ids[:3]


def test_AC1_2_2_test_scoring_uses_all_test_problems(gsm8k_data, train_ids):
    split = build_split(train_ids, 42)
    exemplars = choose_exemplars(split.dev_ids, 42)
    test = problems_to_score("test", split, gsm8k_data, exemplars)
    assert [p.id for p in test] == [f"gsm8k-test-{i}" for i in range(N_TEST)]
    limited = problems_to_score("test", split, gsm8k_data, exemplars, limit=5)
    assert [p.id for p in limited] == [f"gsm8k-test-{i}" for i in range(5)]


# ---------------------------------------------------------------- AC1.2.3 (BR2.3)


def test_AC1_2_3_strip_calculator_notes():
    assert strip_calculator_notes("She pays 48/2 = <<48/2=24>>24 dollars.") == "She pays 48/2 = 24 dollars."
    assert strip_calculator_notes("a <<1+1=2>>2 and b <<2*3=6>>6\n#### 6") == "a 2 and b 6\n#### 6"
    assert strip_calculator_notes("no notes here\n#### 5") == "no notes here\n#### 5"


def test_AC1_2_3_prompt_text_is_fixed_and_byte_identical():
    exemplars = [_make_problem(i) for i in (3, 1, 4, 5)]
    target = "Ann reads 10 pages a day. How many pages does she read in 3 days?"
    blocks = [
        f"Question: {p.question}\nAnswer: Sam has {i} + 2 = {i + 2} apples.\n#### {i + 2}"
        for p, i in zip(exemplars, (3, 1, 4, 5), strict=True)
    ]
    expected = "\n\n".join(blocks) + f"\n\nQuestion: {target}\nAnswer:"
    first = build_prompt(exemplars, target)
    second = build_prompt(list(exemplars), target)
    assert first == expected
    assert first.encode("utf-8") == second.encode("utf-8")
    assert "<<" not in first and ">>" not in first
    assert first.endswith("Answer:")


def test_AC1_2_3_real_prompt_holds_exemplars_then_target(gsm8k_data, train_ids):
    split = build_split(train_ids, 42)
    exemplar_ids = choose_exemplars(split.dev_ids, 42)
    by_id = {p.id: p for p in gsm8k_data["train"]}
    exemplars = [by_id[i] for i in exemplar_ids]
    target = gsm8k_data["train"][index_of(split.dev_ids[0])]
    prompt = build_prompt(exemplars, target.question)
    assert prompt == build_prompt(exemplars, target.question)
    assert "<<" not in prompt
    position = 0
    for p in exemplars:
        block = f"Question: {p.question}\nAnswer: {strip_calculator_notes(p.answer)}"
        assert block.endswith(f"#### {p.gold}")
        found = prompt.find(block, position)
        assert found >= position, p.id  # each exemplar in order, its answer right after its question
        position = found + len(block)
    assert prompt.endswith(f"\n\nQuestion: {target.question}\nAnswer:")
    assert prompt.rfind("Question: ") == len(prompt) - len(f"Question: {target.question}\nAnswer:")
