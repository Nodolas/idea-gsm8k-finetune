"""Reasoning comparison and endpoint, u10-self-taught-cot part C3 (US10.3; C6 `/reasoning`, schema
`Reasoning`; C2 predictions.jsonl, cot_stats.json and the reasoning-lines rule).

Every test builds its own run log (a C1 CSV written directly, so `cotgen` and `selfcot` rows are on
disk whatever the reader's enums) and run folders in temp folders (`tmp_project_dirs`); nothing
touches the project's outputs/, results/runs.csv or results/finalists.json. FastAPI's `TestClient`
binds no port; no model loads; everything runs on the CPU. `gsm8k.reasoning_report` and the service
are imported inside each test, so a missing piece fails each test on its own.

The main fixture (`_scenario`) has 40 dev problems for `Qwen/Qwen3-1.7B-Base`:
- base (latest base dev row q17-base-dev-2, 0.5000): right on problems 0-19;
- sft (q17-sft-dev-1, 0.5250): right on base's 20 plus problem 30; its predictions miss problem 39 and
  hold one extra id that base never scored (wrong), so flips count over 39 common ids;
- selfcot (latest selfcot dev row q17-selfcot-dev-2, 0.7000): broken 17-19, fixed 20-30, its file in
  reverse order; config.json names the generation run q17-cotgen-train-1 (cot_stats kept = 37).
Reasoning lines: base 2 or 3 lines of 3 words (mean 2.5 lines, 7.5 words), sft 1 line of 4 words,
selfcot 4 or 6 lines of 5 words (mean 5.0 lines, 25.0 words); blank lines and text after the
`####` line never count, and an output without a `####` line counts all its non-empty lines.
"""

import csv
import io
import json
import math
import re
from pathlib import Path

import pytest

from gsm8k.reasoning_text import reasoning_lines, reasoning_words
from gsm8k.run_config import RunConfig, to_dict
from gsm8k.run_records.log import COLUMNS

API = "/api/v1"
Q06 = "Qwen/Qwen3-0.6B-Base"
Q17 = "Qwen/Qwen3-1.7B-Base"
N = 40
GEN_RUN = "q17-cotgen-train-1"
BASE_RUN = "q17-base-dev-2"
SFT_RUN = "q17-sft-dev-1"
SELFCOT_RUN = "q17-selfcot-dev-2"
ROLE_KEYS = {
    "role",
    "run_id",
    "accuracy",
    "correct",
    "scored",
    "interval_low",
    "interval_high",
    "trained_on",
    "gain_pts",
    "noise",
    "mean_lines",
    "mean_words",
    "error",
}
TOP_KEYS = {
    "v",
    "model",
    "available",
    "roles",
    "flips",
    "generation",
    "generation_error",
    "examples",
    "summary",
}
COT_STATS = {
    "v": 1,
    "run_id": GEN_RUN,
    "problems": 60,
    "samples_per_problem": 4,
    "solved": 45,
    "kept": 37,
    "kept_fraction": 0.6167,
    "mean_lines_kept": 4.2,
    "mean_words_kept": 31.5,
    "mean_lines_reference": 2.8,
    "mean_words_reference": 19.25,
}


# --- fixture builders ------------------------------------------------------------------------------


def _pid(i: int) -> str:
    return f"gsm8k-train-{10 * i + 3}"


def _gold(i: int) -> str:
    return str(3 * i + 1)


def _output(i: int, *, lines: int, words: int, answer: str | None, tag: str) -> str:
    """An answer with `lines` reasoning lines of `words` words, blank lines between some of them, then
    `#### <answer>` and trailing text that must not count (no `####` line when answer is None)."""
    body: list[str] = []
    for k in range(lines):
        body.append(" ".join(f"{tag}{i}w{k}x{j}" for j in range(words)))
        if k == 0:
            body.append("")
            body.append("   ")
    if answer is None:
        return "\n".join(body) + "\n"
    return "\n".join([*body, f"#### {answer}", "", "Question: this trailing text is not reasoning"])


def _prediction(i: int, output: str, correct: bool) -> dict:
    gold = _gold(i)
    return {
        "problem_id": _pid(i),
        "output": output,
        "predicted": gold if correct else "0",
        "gold": gold,
        "correct": correct,
    }


def _base_predictions(n: int, right: set[int]) -> list[dict]:
    records = []
    for i in range(n):
        correct = i in right
        lines = 2 if i % 2 == 0 else 3
        no_answer_line = (not correct) and i % 5 == 4
        answer = None if no_answer_line else (_gold(i) if correct else "0")
        records.append(_prediction(i, _output(i, lines=lines, words=3, answer=answer, tag="b"), correct))
    return records


def _selfcot_predictions(n: int, right: set[int]) -> list[dict]:
    records = []
    for i in range(n):
        correct = i in right
        lines = 4 if i % 2 == 0 else 6
        answer = _gold(i) if correct else "0"
        records.append(_prediction(i, _output(i, lines=lines, words=5, answer=answer, tag="s"), correct))
    return list(reversed(records))  # file order differs from base order on purpose


def _sft_predictions(ids: list[int], right: set[int]) -> list[dict]:
    records = []
    for i in ids:
        correct = i in right
        answer = _gold(i) if correct else "0"
        records.append(_prediction(i, _output(i, lines=1, words=4, answer=answer, tag="f"), correct))
    extra = _prediction(999, _output(999, lines=1, words=4, answer="0", tag="f"), False)
    return [*records, extra]


def _write_log(path: Path, rows: list[tuple]) -> None:
    """rows: (run_id, model, method, data, metric, value) in file order (= date order)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMNS)
    for k, (run_id, model, method, data, metric, value) in enumerate(rows):
        date = f"2026-11-{1 + k:02d}T10:00:00Z"
        writer.writerow([date, run_id, model, method, data, metric, f"{value:.4f}", "12.5", "0" * 64, ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _config(run_id: str, *, method: str, model: str = Q17, **fields) -> dict:
    data = to_dict(RunConfig(run_id=run_id, model=model, method="sft", split="dev"))
    data["method"] = method
    data.update(fields)
    return data


def _run_folder(outputs: Path, run_id: str, config: dict, predictions: list[dict] | None = None) -> Path:
    folder = outputs / run_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    if predictions is not None:
        text = "".join(json.dumps(record) + "\n" for record in predictions)
        (folder / "predictions.jsonl").write_text(text, encoding="utf-8")
    return folder


def _generation_folder(outputs: Path, kept: int = 37) -> Path:
    config = _config(GEN_RUN, method="cotgen", split="train", cot_problems=60, cot_samples=4)
    folder = _run_folder(outputs, GEN_RUN, config)
    (folder / "cot_stats.json").write_text(json.dumps(COT_STATS, indent=2) + "\n", encoding="utf-8")
    lines = []
    for k in range(kept):
        lines.append(
            json.dumps(
                {
                    "v": 1,
                    "problem_id": f"gsm8k-train-{5000 + k}",
                    "question": f"Question {k}?",
                    "gold": str(k),
                    "solution": f"Step one.\nStep two.\n#### {k}",
                    "correct_samples": 2,
                    "samples": 4,
                }
            )
            + "\n"
        )
    (folder / "cot_data.jsonl").write_text("".join(lines), encoding="utf-8")
    return folder


BASE_RIGHT = set(range(20))
SFT_RIGHT = BASE_RIGHT | {30}
SELFCOT_RIGHT = (BASE_RIGHT - {17, 18, 19}) | set(range(20, 31))
SELFCOT_WITHIN_RIGHT = (BASE_RIGHT - {19}) | {20, 21}


def _scenario(
    dirs,
    *,
    sft: bool = True,
    selfcot: bool = True,
    selfcot_right: set[int] = SELFCOT_RIGHT,
    sft_train_examples="all",
    selfcot_train_examples="all",
) -> None:
    """The run log and run folders described in the module docstring."""
    outputs = dirs.outputs
    rows = [
        ("q17-base-dev-1", Q17, "base", "gsm8k-dev", "accuracy", 0.9),
        ("q17-selfcot-dev-1", Q17, "selfcot", "gsm8k-dev", "accuracy", 0.1) if selfcot else None,
        (SFT_RUN, Q17, "sft", "gsm8k-dev", "accuracy", len(SFT_RIGHT) / N) if sft else None,
        (BASE_RUN, Q17, "base", "gsm8k-dev", "accuracy", len(BASE_RIGHT) / N),
        (GEN_RUN, Q17, "cotgen", "gsm8k-train", "kept_fraction", COT_STATS["kept_fraction"]),
        (SELFCOT_RUN, Q17, "selfcot", "gsm8k-dev", "accuracy", len(selfcot_right) / N) if selfcot else None,
        ("q17-base-test-1", Q17, "base", "gsm8k-test", "accuracy", 0.2),
        ("q06-base-dev-1", Q06, "base", "gsm8k-dev", "accuracy", 0.05),
        ("q06-selfcot-dev-1", Q06, "selfcot", "gsm8k-dev", "accuracy", 0.95),
    ]
    _write_log(dirs.results, [row for row in rows if row is not None])
    _run_folder(outputs, BASE_RUN, _config(BASE_RUN, method="base"), _base_predictions(N, BASE_RIGHT))
    if sft:
        config = _config(SFT_RUN, method="sft", train_examples=sft_train_examples)
        _run_folder(outputs, SFT_RUN, config, _sft_predictions(list(range(N - 1)), SFT_RIGHT))
    _generation_folder(outputs)
    if selfcot:
        config = _config(
            SELFCOT_RUN, method="selfcot", train_examples=selfcot_train_examples, cot_data_run=GEN_RUN
        )
        _run_folder(outputs, SELFCOT_RUN, config, _selfcot_predictions(N, selfcot_right))


def _client(dirs):
    from fastapi.testclient import TestClient

    from gsm8k.service.app import create_app

    finalists = dirs.results.parent / "finalists.json"
    return TestClient(create_app(results=dirs.results, finalists=finalists, outputs=dirs.outputs))


def _reasoning(dirs, model: str = Q17) -> dict:
    with _client(dirs) as client:
        response = client.get(f"{API}/reasoning", params={"model": model})
    assert response.status_code == 200, response.text
    body = response.json()
    assert TOP_KEYS <= set(body), body
    assert [role["role"] for role in body["roles"]] == ["base", "sft", "selfcot"], body["roles"]
    for role in body["roles"]:
        assert ROLE_KEYS <= set(role), role
    return body


def _roles(body: dict) -> dict:
    return {role["role"]: role for role in body["roles"]}


def _flips(body: dict) -> dict:
    by_role = {flip["role"]: flip for flip in body["flips"]}
    assert len(by_role) == len(body["flips"]), body["flips"]
    return by_role


def _interval(p: float, n: int) -> tuple[float, float]:
    half = 1.96 * math.sqrt(p * (1 - p) / n)
    return max(0.0, p - half), min(1.0, p + half)


def _assert_error(response, status: int, error: str) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert body.get("error") == error, body
    assert isinstance(body.get("message"), str) and body["message"], body
    return body


def _has_any(text: str, options: list[str]) -> bool:
    return any(option in text for option in options)


def _has_count(text: str, n: int) -> bool:
    return re.search(rf"(?<![\d.,]){n}(?![\d]|[.,]\d)", text) is not None


def _accuracy_texts(p: float) -> list[str]:
    return [f"{p * 100:.1f}", f"{round(p * 100)}%", f"{p:.4f}", f"{p:.3f}", f"{p:.2f}"]


# --- AC10.3.1 --------------------------------------------------------------------------------------


def test_AC10_3_1_roles_take_the_latest_dev_row_with_counts_interval_and_gain(tmp_project_dirs):
    from gsm8k.reasoning_report import build_reasoning

    _scenario(tmp_project_dirs)
    body = _reasoning(tmp_project_dirs)

    assert body["v"] == 1
    assert body["model"] == Q17
    assert body["available"] is True
    roles = _roles(body)
    expected = {
        "base": (BASE_RUN, 0.5, 20, 40),
        "sft": (SFT_RUN, 0.525, 21, 40),
        "selfcot": (SELFCOT_RUN, 0.7, 28, 40),
    }
    for name, (run_id, accuracy, correct, scored) in expected.items():
        role = roles[name]
        assert role["run_id"] == run_id, role
        assert role["accuracy"] == pytest.approx(accuracy, abs=1e-4), role
        assert role["correct"] == correct, role
        assert role["scored"] == scored, role
        low, high = _interval(accuracy, scored)
        assert role["interval_low"] == pytest.approx(low, abs=1e-3), role
        assert role["interval_high"] == pytest.approx(high, abs=1e-3), role
        assert role["error"] is None, role

    base = roles["base"]
    assert base["trained_on"] is None and base["gain_pts"] is None and base["noise"] is None, base
    assert roles["sft"]["gain_pts"] == 2.5, roles["sft"]
    assert roles["sft"]["noise"] == "within noise"
    assert roles["selfcot"]["gain_pts"] == 20.0, roles["selfcot"]
    assert roles["selfcot"]["noise"] == "outside noise"
    assert roles["sft"]["trained_on"] == 6973
    assert roles["selfcot"]["trained_on"] == 37

    direct = build_reasoning(Q17, tmp_project_dirs.results, tmp_project_dirs.outputs)
    assert json.loads(json.dumps(direct)) == body


def test_AC10_3_1_interval_is_clipped_to_0_and_1(tmp_project_dirs):
    _write_log(
        tmp_project_dirs.results,
        [
            ("q17-base-dev-1", Q17, "base", "gsm8k-dev", "accuracy", 0.75),
            ("q17-selfcot-dev-1", Q17, "selfcot", "gsm8k-dev", "accuracy", 0.25),
        ],
    )
    outputs = tmp_project_dirs.outputs
    _run_folder(
        outputs, "q17-base-dev-1", _config("q17-base-dev-1", method="base"), _base_predictions(4, {0, 1, 2})
    )
    config = _config("q17-selfcot-dev-1", method="selfcot", cot_data_run=GEN_RUN)
    _run_folder(outputs, "q17-selfcot-dev-1", config, _selfcot_predictions(4, {0}))
    _generation_folder(outputs)

    roles = _roles(_reasoning(tmp_project_dirs))

    base, selfcot = roles["base"], roles["selfcot"]
    assert (base["correct"], base["scored"]) == (3, 4)
    assert base["interval_high"] == pytest.approx(1.0, abs=1e-9), base  # 0.75 + 0.424 clipped
    assert base["interval_low"] == pytest.approx(0.75 - 1.96 * math.sqrt(0.75 * 0.25 / 4), abs=1e-3)
    assert selfcot["interval_low"] == pytest.approx(0.0, abs=1e-9), selfcot  # 0.25 - 0.424 clipped
    assert selfcot["interval_high"] == pytest.approx(0.25 + 1.96 * math.sqrt(0.25 * 0.75 / 4), abs=1e-3)
    assert roles["sft"]["run_id"] is None and roles["sft"]["accuracy"] is None


@pytest.mark.parametrize(
    ("sft_train_examples", "selfcot_train_examples", "sft_expected", "selfcot_expected"),
    [("all", "all", 6973, 37), (500, 1000, 500, 37), (500, 25, 500, 25)],
)
def test_AC10_3_1_trained_on_counts_the_training_problems_learned_from(
    tmp_project_dirs, sft_train_examples, selfcot_train_examples, sft_expected, selfcot_expected
):
    _scenario(
        tmp_project_dirs,
        sft_train_examples=sft_train_examples,
        selfcot_train_examples=selfcot_train_examples,
    )

    roles = _roles(_reasoning(tmp_project_dirs))

    assert roles["base"]["trained_on"] is None
    assert roles["sft"]["trained_on"] == sft_expected  # "all" = the 6,973 training problems
    assert roles["selfcot"]["trained_on"] == selfcot_expected  # "all" or more than kept = kept (37)


@pytest.mark.parametrize(
    ("sft_value", "selfcot_value", "sft_gain", "selfcot_gain"),
    [(0.539, 0.540, 3.9, 4.0), (0.461, 0.460, -3.9, -4.0)],
)
def test_AC10_3_1_noise_label_turns_at_4_points_by_size(
    tmp_project_dirs, sft_value, selfcot_value, sft_gain, selfcot_gain
):
    _write_log(
        tmp_project_dirs.results,
        [
            ("q17-base-dev-1", Q17, "base", "gsm8k-dev", "accuracy", 0.5),
            ("q17-sft-dev-1", Q17, "sft", "gsm8k-dev", "accuracy", sft_value),
            ("q17-selfcot-dev-1", Q17, "selfcot", "gsm8k-dev", "accuracy", selfcot_value),
        ],
    )

    roles = _roles(_reasoning(tmp_project_dirs))

    assert roles["sft"]["gain_pts"] == sft_gain, roles["sft"]
    assert roles["sft"]["noise"] == "within noise"
    assert roles["selfcot"]["gain_pts"] == selfcot_gain, roles["selfcot"]
    assert roles["selfcot"]["noise"] == "outside noise"


# --- AC10.3.2 --------------------------------------------------------------------------------------


def test_AC10_3_2_flips_count_over_the_problems_both_runs_scored(tmp_project_dirs):
    _scenario(tmp_project_dirs)

    flips = _flips(_reasoning(tmp_project_dirs))

    assert set(flips) == {"sft", "selfcot"}
    sft = flips["sft"]
    assert (sft["run_id"], sft["against"]) == (SFT_RUN, BASE_RUN)
    # 39 common ids: problem 39 is missing from sft and its extra id is not in base
    assert (sft["fixed"], sft["broken"], sft["both_right"], sft["both_wrong"]) == (1, 0, 20, 18), sft
    selfcot = flips["selfcot"]
    assert (selfcot["run_id"], selfcot["against"]) == (SELFCOT_RUN, BASE_RUN)
    counts = (selfcot["fixed"], selfcot["broken"], selfcot["both_right"], selfcot["both_wrong"])
    assert counts == (11, 3, 17, 9), selfcot


def test_AC10_3_2_mean_reasoning_lines_and_words_follow_the_rule(tmp_project_dirs):
    _scenario(tmp_project_dirs)

    roles = _roles(_reasoning(tmp_project_dirs))

    files = {
        "base": tmp_project_dirs.outputs / BASE_RUN / "predictions.jsonl",
        "sft": tmp_project_dirs.outputs / SFT_RUN / "predictions.jsonl",
        "selfcot": tmp_project_dirs.outputs / SELFCOT_RUN / "predictions.jsonl",
    }
    designed = {"base": (2.5, 7.5), "sft": (1.0, 4.0), "selfcot": (5.0, 25.0)}
    for name, path in files.items():
        outputs = [json.loads(line)["output"] for line in path.read_text(encoding="utf-8").splitlines()]
        rule_lines = sum(len(reasoning_lines(text)) for text in outputs) / len(outputs)
        rule_words = sum(reasoning_words(text) for text in outputs) / len(outputs)
        assert (rule_lines, rule_words) == designed[name]  # the fixture itself follows the rule
        assert roles[name]["mean_lines"] == pytest.approx(rule_lines, abs=0.01), roles[name]
        assert roles[name]["mean_words"] == pytest.approx(rule_words, abs=0.01), roles[name]


# --- AC10.3.3 --------------------------------------------------------------------------------------


def test_AC10_3_3_generation_figures_come_from_the_named_generation_run(tmp_project_dirs):
    _scenario(tmp_project_dirs)

    body = _reasoning(tmp_project_dirs)

    generation = body["generation"]
    assert body["generation_error"] is None
    assert isinstance(generation, dict), body
    assert generation["run_id"] == GEN_RUN
    for key, value in COT_STATS.items():
        if key == "v":
            continue
        assert generation[key] == pytest.approx(value), (key, generation)


def test_AC10_3_3_examples_are_up_to_3_fixed_problems_in_base_order(tmp_project_dirs):
    _scenario(tmp_project_dirs)
    base = {r["problem_id"]: r for r in _base_predictions(N, BASE_RIGHT)}
    selfcot = {r["problem_id"]: r for r in _selfcot_predictions(N, SELFCOT_RIGHT)}

    examples = _reasoning(tmp_project_dirs)["examples"]

    assert [e["problem_id"] for e in examples] == [_pid(20), _pid(21), _pid(22)], examples
    for example in examples:
        pid = example["problem_id"]
        assert example["gold"] == base[pid]["gold"]
        assert example["base_output"] == base[pid]["output"]
        assert example["selfcot_output"] == selfcot[pid]["output"]


def test_AC10_3_3_examples_are_fewer_when_fewer_problems_were_fixed(tmp_project_dirs):
    _scenario(tmp_project_dirs, sft=False, selfcot_right=SELFCOT_WITHIN_RIGHT)

    examples = _reasoning(tmp_project_dirs)["examples"]

    assert [e["problem_id"] for e in examples] == [_pid(20), _pid(21)], examples


def test_AC10_3_3_summary_names_accuracies_gains_training_sizes_and_flips(tmp_project_dirs):
    _scenario(tmp_project_dirs)

    summary = _reasoning(tmp_project_dirs)["summary"]

    assert isinstance(summary, list) and summary, summary
    assert all(isinstance(sentence, str) and sentence.strip() for sentence in summary), summary
    text = " ".join(summary)
    assert _has_any(text, _accuracy_texts(0.7)), text  # self-taught dev accuracy
    assert _has_any(text, _accuracy_texts(0.5)), text  # base accuracy
    assert _has_any(text, ["20.0", "20 point"]), text  # self-taught gain in points
    assert "outside noise" in text, text  # its noise label
    assert "2.5" in text, text  # the reference fine-tune's gain
    assert _has_any(text, ["6973", "6,973"]), text  # sft trained on all training problems
    assert _has_count(text, 37), text  # selfcot trained on the 37 kept solutions
    assert _has_count(text, 11), text  # fixed by selfcot
    assert _has_count(text, 3), text  # broken by selfcot


def test_AC10_3_3_summary_gives_the_self_taught_noise_label(tmp_project_dirs):
    _scenario(tmp_project_dirs, sft=False, selfcot_right=SELFCOT_WITHIN_RIGHT)

    body = _reasoning(tmp_project_dirs)

    assert _roles(body)["selfcot"]["gain_pts"] == 2.5
    text = " ".join(body["summary"])
    assert "within noise" in text, text
    assert "2.5" in text, text


# --- AC10.3.4 --------------------------------------------------------------------------------------


def test_AC10_3_4_no_selfcot_row_answers_available_false_with_base_and_sft(tmp_project_dirs):
    _scenario(tmp_project_dirs, selfcot=False)

    body = _reasoning(tmp_project_dirs)

    assert body["available"] is False
    roles = _roles(body)
    assert roles["base"]["run_id"] == BASE_RUN
    assert roles["base"]["accuracy"] == pytest.approx(0.5, abs=1e-4)
    assert roles["sft"]["run_id"] == SFT_RUN
    assert roles["sft"]["accuracy"] == pytest.approx(0.525, abs=1e-4)
    assert roles["sft"]["gain_pts"] == 2.5
    selfcot = roles["selfcot"]
    for key in ROLE_KEYS - {"role", "error"}:
        assert selfcot[key] is None, (key, selfcot)  # the q06 selfcot row belongs to another model
    assert set(_flips(body)) == {"sft"}
    assert body["generation"] is None
    assert body["examples"] == []


def test_AC10_3_4_unreadable_predictions_null_only_that_role(tmp_project_dirs):
    _scenario(tmp_project_dirs)
    path = tmp_project_dirs.outputs / SFT_RUN / "predictions.jsonl"
    path.write_text('{"problem_id": "gsm8k-train-3", "output": \n{broken\n', encoding="utf-8")

    body = _reasoning(tmp_project_dirs)

    roles = _roles(body)
    sft = roles["sft"]
    assert sft["run_id"] == SFT_RUN
    assert sft["accuracy"] == pytest.approx(0.525, abs=1e-4)  # from the run log, still known
    for key in ("correct", "scored", "interval_low", "interval_high", "mean_lines", "mean_words"):
        assert sft[key] is None, (key, sft)
    assert isinstance(sft["error"], str) and f"{SFT_RUN}/predictions.jsonl" in sft["error"], sft
    assert set(_flips(body)) == {"selfcot"}
    selfcot = roles["selfcot"]
    assert (selfcot["correct"], selfcot["scored"], selfcot["error"]) == (28, 40, None)
    assert roles["base"]["error"] is None
    assert body["available"] is True
    assert body["generation"] is not None
    assert len(body["examples"]) == 3


@pytest.mark.parametrize(
    ("run_id", "filename"),
    [(GEN_RUN, "cot_stats.json"), (SELFCOT_RUN, "config.json")],
)
def test_AC10_3_4_unreadable_generation_file_nulls_only_the_generation(tmp_project_dirs, run_id, filename):
    _scenario(tmp_project_dirs)
    (tmp_project_dirs.outputs / run_id / filename).write_text("{not json", encoding="utf-8")

    body = _reasoning(tmp_project_dirs)

    assert body["generation"] is None
    error = body["generation_error"]
    assert isinstance(error, str) and f"{run_id}/{filename}" in error, body
    roles = _roles(body)
    assert roles["selfcot"]["accuracy"] == pytest.approx(0.7, abs=1e-4)
    assert (roles["selfcot"]["correct"], roles["selfcot"]["scored"]) == (28, 40)
    assert set(_flips(body)) == {"sft", "selfcot"}
    assert len(body["examples"]) == 3


def test_AC10_3_4_unknown_model_is_invalid_dial(tmp_project_dirs):
    from gsm8k.reasoning_report import build_reasoning

    _scenario(tmp_project_dirs)
    with _client(tmp_project_dirs) as client:
        refused = client.get(f"{API}/reasoning", params={"model": "gpt2"})
        default = client.get(f"{API}/reasoning")

    body = _assert_error(refused, 422, "invalid_dial")
    assert body.get("field") == "model", body
    assert default.status_code == 200, default.text
    assert default.json()["model"] == Q17  # the default model
    with pytest.raises(ValueError):
        build_reasoning("gpt2", tmp_project_dirs.results, tmp_project_dirs.outputs)


@pytest.mark.parametrize(
    "dials",
    [
        {"model": Q17, "method": "cotgen", "split": "train"},
        {"model": Q17, "method": "selfcot", "cot_data_run": GEN_RUN},
    ],
    ids=["cotgen", "selfcot"],
)
def test_AC10_3_4_runs_check_refuses_cotgen_and_selfcot(tmp_project_dirs, dials):
    _scenario(tmp_project_dirs)
    with _client(tmp_project_dirs) as client:
        response = client.post(f"{API}/runs/check", json=dials)

    body = _assert_error(response, 422, "invalid_dial")
    assert body.get("field") == "method", body
