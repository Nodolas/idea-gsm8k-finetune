"""u7-grpo part R: GRPO rewards (AC7.1.1) and the step plan (AC7.1.4).

Assumptions (see the test writer's report): reward functions live in ``gsm8k.training.grpo_rewards``
(``correctness_reward``, ``format_reward``, ``total_reward`` on one completion string, and the trl-shaped
``correctness_rewards``, ``format_rewards``, ``total_rewards`` taking ``(completions, gold, **kwargs)``);
the plan lives in ``gsm8k.training.grpo_plan``. Plan results expose ``steps``, ``estimate_s``,
``flagged`` and ``measured`` as attributes (a trailing tuple element is accepted for ``flagged``).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

MODEL = "Qwen/Qwen3-0.6B-Base"
BUDGET = 3 * 3600


def _rewards():
    from gsm8k.training import grpo_rewards

    return grpo_rewards


def _plan_mod():
    from gsm8k.training import grpo_plan

    return grpo_plan


def _get(result, name, index):
    return getattr(result, name) if hasattr(result, name) else result[index]


def _make_run(outputs: Path, name: str, model: str, timings: dict) -> None:
    folder = outputs / name
    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps({"model": model}), encoding="utf-8")
    (folder / "timings.json").write_text(json.dumps(timings), encoding="utf-8")


# ---- AC7.1.1 ----


def test_AC7_1_1_correctness_is_one_for_right_hash_answer():
    r = _rewards()
    assert r.correctness_reward("She has 3 + 4 = 7 apples.\n#### 7", "7") == 1.0
    assert r.correctness_reward("#### 1,250", "1250") == 1.0


def test_AC7_1_1_correctness_uses_last_number_fallback_like_scoring():
    r = _rewards()
    assert r.correctness_reward("So the total is 42 dollars", "42") == 1.0
    assert r.correctness_reward("first 5 then 42", "42") == 1.0
    assert r.correctness_reward("first 42 then 5", "42") == 0.0


def test_AC7_1_1_correctness_is_zero_for_wrong_or_no_number():
    r = _rewards()
    assert r.correctness_reward("#### 8", "7") == 0.0
    assert r.correctness_reward("I do not know", "7") == 0.0
    assert r.correctness_reward("", "7") == 0.0


def test_AC7_1_1_format_reward_only_with_hash_number_line():
    r = _rewards()
    assert r.format_reward("work\n#### 7") == pytest.approx(0.1)
    assert r.format_reward("work\n#### 7\nQuestion: more") == pytest.approx(0.1)
    assert r.format_reward("the answer is 7") == 0.0
    assert r.format_reward("#### no number here") == 0.0
    assert r.format_reward("") == 0.0


def test_AC7_1_1_format_reward_is_given_even_when_answer_is_wrong():
    r = _rewards()
    assert r.format_reward("#### 99") == pytest.approx(0.1)
    assert r.correctness_reward("#### 99", "7") == 0.0


def test_AC7_1_1_total_is_sum_of_correctness_and_format():
    r = _rewards()
    assert r.total_reward("#### 7", "7") == pytest.approx(1.1)
    assert r.total_reward("#### 8", "7") == pytest.approx(0.1)
    assert r.total_reward("it is 7", "7") == pytest.approx(1.0)
    assert r.total_reward("no idea", "7") == 0.0


def test_AC7_1_1_trl_functions_return_one_float_per_completion():
    r = _rewards()
    completions = ["#### 7", "it is 7", "#### 8", "none"]
    gold = ["7", "7", "7", "7"]
    assert r.correctness_rewards(completions, gold) == [1.0, 1.0, 0.0, 0.0]
    assert r.format_rewards(completions, gold) == pytest.approx([0.1, 0.0, 0.1, 0.0])
    assert r.total_rewards(completions, gold) == pytest.approx([1.1, 1.0, 0.1, 0.0])
    out = r.total_rewards(completions, gold, prompts=["p"] * 4, extra=1)
    assert isinstance(out, list) and all(isinstance(x, float) for x in out)


def test_AC7_1_1_trl_functions_accept_message_dict_completions():
    r = _rewards()
    completions = [
        [{"role": "assistant", "content": "work\n#### 7"}],
        [{"role": "assistant", "content": "#### 8"}],
    ]
    assert r.correctness_rewards(completions, ["7", "7"]) == [1.0, 0.0]
    assert r.total_rewards(completions, ["7", "7"]) == pytest.approx([1.1, 0.1])


def test_AC7_1_1_trl_functions_take_gold_as_keyword_and_handle_empty():
    r = _rewards()
    assert r.correctness_rewards(["#### 3"], gold=["3"]) == [1.0]
    assert r.total_rewards([], []) == []


# ---- AC7.1.4 ----


def test_AC7_1_4_steps_sized_from_grpo_seconds_per_step(tmp_path):
    p = _plan_mod()
    _make_run(tmp_path, "g1", MODEL, {"seconds_per_step": 70.0})
    res = p.plan_grpo_steps(MODEL, 4, outputs=tmp_path)
    assert _get(res, "steps", 0) == 154  # floor(10800 / 70)
    assert _get(res, "estimate_s", 1) <= BUDGET
    assert _get(res, "estimate_s", 1) == pytest.approx(154 * 70.0)
    assert _get(res, "flagged", 2) is False
    assert getattr(res, "measured", True) is True


def test_AC7_1_4_steps_sized_from_evaluation_timings_fit_budget(tmp_path):
    p = _plan_mod()
    _make_run(tmp_path, "e1", MODEL, {"seconds_per_problem": 2.0, "seconds_per_step": None})
    few = p.plan_grpo_steps(MODEL, 2, outputs=tmp_path)
    many = p.plan_grpo_steps(MODEL, 8, outputs=tmp_path)
    for res in (few, many):
        assert _get(res, "steps", 0) >= 1
        assert _get(res, "estimate_s", 1) <= BUDGET
        assert _get(res, "flagged", 2) is False
        assert getattr(res, "measured", True) is True
    assert _get(many, "steps", 0) <= _get(few, "steps", 0)


def test_AC7_1_4_budget_argument_changes_step_count(tmp_path):
    p = _plan_mod()
    _make_run(tmp_path, "g1", MODEL, {"seconds_per_step": 60.0})
    res = p.plan_grpo_steps(MODEL, 4, outputs=tmp_path, budget_s=600)
    assert _get(res, "steps", 0) == 10
    assert _get(res, "estimate_s", 1) <= 600


def test_AC7_1_4_other_models_timings_are_ignored(tmp_path):
    p = _plan_mod()
    _make_run(tmp_path, "g1", "Qwen/Qwen3-1.7B-Base", {"seconds_per_step": 10.0})
    res = p.plan_grpo_steps(MODEL, 4, outputs=tmp_path)
    assert getattr(res, "measured", None) is False


def test_AC7_1_4_check_flags_count_over_budget(tmp_path):
    p = _plan_mod()
    _make_run(tmp_path, "g1", MODEL, {"seconds_per_step": 70.0})
    over = p.check_grpo_steps(155, MODEL, 4, outputs=tmp_path)
    assert _get(over, "flagged", -1) is True
    assert _get(over, "estimate_s", 0) == pytest.approx(155 * 70.0) if hasattr(over, "estimate_s") else True


def test_AC7_1_4_check_passes_count_within_budget(tmp_path):
    p = _plan_mod()
    _make_run(tmp_path, "g1", MODEL, {"seconds_per_step": 70.0})
    for requested in (1, 100, 154):
        ok = p.check_grpo_steps(requested, MODEL, 4, outputs=tmp_path)
        assert _get(ok, "flagged", -1) is False


def test_AC7_1_4_check_respects_budget_argument(tmp_path):
    p = _plan_mod()
    _make_run(tmp_path, "g1", MODEL, {"seconds_per_step": 60.0})
    assert _get(p.check_grpo_steps(11, MODEL, 4, outputs=tmp_path, budget_s=600), "flagged", -1) is True
    assert _get(p.check_grpo_steps(10, MODEL, 4, outputs=tmp_path, budget_s=600), "flagged", -1) is False


def test_AC7_1_4_without_saved_timings_plan_uses_fallback_and_says_so(tmp_path):
    p = _plan_mod()
    res = p.plan_grpo_steps(MODEL, 4, outputs=tmp_path)
    assert getattr(res, "measured", None) is False
    assert _get(res, "steps", 0) >= 1
    assert _get(res, "estimate_s", 1) <= BUDGET
    assert _get(res, "flagged", 2) is False


def test_AC7_1_4_plan_with_missing_outputs_folder_uses_fallback(tmp_path):
    p = _plan_mod()
    res = p.plan_grpo_steps(MODEL, 4, outputs=tmp_path / "nope")
    assert getattr(res, "measured", None) is False
    assert _get(res, "steps", 0) >= 1


def test_AC7_1_4_plan_default_outputs_uses_project_outputs(tmp_project_dirs):
    p = _plan_mod()
    _make_run(tmp_project_dirs.outputs, "g1", MODEL, {"seconds_per_step": 100.0})
    res = p.plan_grpo_steps(MODEL, 4)
    assert _get(res, "steps", 0) == 108


def test_AC7_1_4_grpo_plan_imports_no_torch():
    code = (
        "import sys; import gsm8k.training.grpo_plan, gsm8k.training.grpo_rewards; "
        "bad = [m for m in ('torch', 'trl', 'transformers') if m in sys.modules]; "
        "sys.exit(1 if bad else 0)"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
