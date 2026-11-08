"""ReasoningReport: self-taught chain of thought against base and the reference fine-tune (US10.3).

``build_reasoning`` builds the C6 ``Reasoning`` body for one model from the run log (C1) and the run
folders (C2): for each role (base, sft, selfcot) the model's latest ``gsm8k-dev`` accuracy row, the
correct and scored counts from its ``predictions.jsonl``, the 95% interval (normal approximation,
clipped to 0..1), the training problems a fine-tune learned from, the gain over base in points with its
noise label, and the mean reasoning lines and words of its outputs (``gsm8k.reasoning_text``); the
problem flips of sft and selfcot against base; the generation figures of the selfcot run's
``cot_data_run`` (its ``cot_stats.json``); up to 3 problems selfcot fixed, as examples; and plain
English summary sentences built from those numbers.

It only reads files: an unreadable predictions file nulls that role's derived figures with an error
naming the file, an unreadable ``config.json`` or ``cot_stats.json`` nulls the generation figures with
an error naming the file, and an unreadable run log raises the run log's own ``OSError``. It imports
only RunRecords, ``reasoning_text`` and the standard library, never training or evaluation code
(ADR-006).
"""

import json
import math
from pathlib import Path

from gsm8k.reasoning_text import reasoning_lines, reasoning_words
from gsm8k.run_records import log, paths

VERSION = 1
DEFAULT_MODEL = "Qwen/Qwen3-1.7B-Base"
ROLES = ("base", "sft", "selfcot")
FINE_TUNES = ("sft", "selfcot")
DEV_DATA = "gsm8k-dev"
ACCURACY = "accuracy"
TRAIN_SPLIT_SIZE = 6973  # 7,473 training problems minus the 500 dev problems (C2 train_examples "all")
NOISE_POINTS = 4.0  # a gain under 4 points is within noise (stories.md, AC10.3.1)
Z_95 = 1.96
MAX_EXAMPLES = 3
WITHIN_NOISE = "within noise"
OUTSIDE_NOISE = "outside noise"


class UnknownModel(ValueError):
    """The model is not one of the two allowed models (C6: 422 invalid_dial, field model)."""


class _Unreadable(Exception):
    """A run file that is missing or cannot be parsed; the message names the file."""


# --- reading run files ---------------------------------------------------------------------------------


def _folder(outputs: Path, run_id: str) -> Path:
    if not isinstance(run_id, str) or not paths.RUN_ID_PATTERN.fullmatch(run_id):
        raise _Unreadable(f"Run id is not a valid run folder name: {run_id!r}")
    return outputs / run_id


def _read_json(outputs: Path, run_id: str, name: str, label: str) -> dict:
    path = _folder(outputs, run_id) / name
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise _Unreadable(f"{label} could not be read: {path}") from exc
    if not isinstance(data, dict):
        raise _Unreadable(f"{label} could not be read: {path}")
    return data


def _read_predictions(outputs: Path, run_id: str) -> list[dict]:
    """The C2 predictions records in file order; each needs problem_id, output and a boolean correct."""
    path = _folder(outputs, run_id) / "predictions.jsonl"
    message = f"Predictions could not be read: {path}"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _Unreadable(message) from exc
    records: list[dict] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise _Unreadable(message) from exc
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("problem_id"), str)
            or not isinstance(record.get("output"), str)
            or not isinstance(record.get("correct"), bool)
        ):
            raise _Unreadable(message)
        records.append(record)
    return records


# --- figures -------------------------------------------------------------------------------------------


def _latest_dev_rows(rows: list, model: str) -> dict:
    """The last ``gsm8k-dev`` accuracy row in file order of each role for the model."""
    latest: dict = {}
    for row in rows:
        if row.model == model and row.method in ROLES and row.data == DEV_DATA and row.metric == ACCURACY:
            latest[row.method] = row
    return latest


def _interval(accuracy: float, scored: int | None) -> tuple[float | None, float | None]:
    if not scored:
        return None, None
    p = min(1.0, max(0.0, accuracy))
    half = Z_95 * math.sqrt(p * (1.0 - p) / scored)
    return round(max(0.0, accuracy - half), 4), round(min(1.0, accuracy + half), 4)


def _noise(gain_pts: float) -> str:
    return WITHIN_NOISE if abs(gain_pts) < NOISE_POINTS else OUTSIDE_NOISE


def _empty_role(role: str) -> dict:
    return {
        "role": role,
        "run_id": None,
        "accuracy": None,
        "correct": None,
        "scored": None,
        "interval_low": None,
        "interval_high": None,
        "trained_on": None,
        "gain_pts": None,
        "noise": None,
        "mean_lines": None,
        "mean_words": None,
        "error": None,
    }


def _trained_on(train_examples, available: int | None) -> int | None:
    """train_examples of the run's config.json, ``all`` = what was available, capped at it."""
    if train_examples == "all":
        return available
    if isinstance(train_examples, bool) or not isinstance(train_examples, int):
        return None
    return min(train_examples, available) if available is not None else train_examples


def _flip(role: dict, base: dict, run_preds: list[dict], base_preds: list[dict]) -> dict:
    """Fixed, broken, both right and both wrong over the problem ids both runs scored."""
    base_correct = {record["problem_id"]: record["correct"] for record in base_preds}
    run_correct = {record["problem_id"]: record["correct"] for record in run_preds}
    counts = {"fixed": 0, "broken": 0, "both_right": 0, "both_wrong": 0}
    for problem_id, right in run_correct.items():
        if problem_id not in base_correct:
            continue
        was_right = base_correct[problem_id]
        if right and was_right:
            counts["both_right"] += 1
        elif right:
            counts["fixed"] += 1
        elif was_right:
            counts["broken"] += 1
        else:
            counts["both_wrong"] += 1
    return {"role": role["role"], "run_id": role["run_id"], "against": base["run_id"], **counts}


def _examples(base_preds: list[dict], selfcot_preds: list[dict]) -> list[dict]:
    """Up to 3 problems base got wrong and selfcot right, in base predictions order."""
    selfcot = {record["problem_id"]: record for record in selfcot_preds}
    examples: list[dict] = []
    for record in base_preds:
        other = selfcot.get(record["problem_id"])
        if record["correct"] or other is None or not other["correct"]:
            continue
        examples.append(
            {
                "problem_id": record["problem_id"],
                "gold": str(record.get("gold", "")),
                "base_output": record["output"],
                "selfcot_output": other["output"],
            }
        )
        if len(examples) == MAX_EXAMPLES:
            break
    return examples


def _generation(outputs: Path, selfcot_run: str) -> tuple[dict | None, str | None, int | None, object]:
    """(generation figures, generation error, kept count, selfcot train_examples) of the selfcot run."""
    try:
        config = _read_json(outputs, selfcot_run, "config.json", "Run config")
    except _Unreadable as exc:
        return None, str(exc), None, None
    train_examples = config.get("train_examples", "all")
    cot_run = config.get("cot_data_run")
    if not cot_run:
        path = _folder(outputs, selfcot_run) / "config.json"
        return None, f"Run config names no generation run (cot_data_run): {path}", None, train_examples
    try:
        stats = _read_json(outputs, cot_run, "cot_stats.json", "Generation figures")
    except _Unreadable as exc:
        return None, str(exc), None, train_examples
    generation = {key: value for key, value in stats.items() if key != "v"}
    generation["run_id"] = cot_run
    kept = stats.get("kept")
    kept = kept if isinstance(kept, int) and not isinstance(kept, bool) else None
    return generation, None, kept, train_examples


# --- summary -------------------------------------------------------------------------------------------


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _scored_text(role: dict) -> str:
    if role["correct"] is None or role["scored"] is None:
        return ""
    return f" ({role['correct']} of {role['scored']} problems)"


def _gain_text(role: dict) -> str:
    return f"a gain of {role['gain_pts']:+.1f} points over base, {role['noise']}"


def _summary(model: str, roles: dict, flips: dict) -> list[str]:
    base, sft, selfcot = roles["base"], roles["sft"], roles["selfcot"]
    sentences: list[str] = []
    if selfcot["run_id"] is None:
        sentences.append(f"No self-taught chain-of-thought run has a dev score for {model} yet.")
    else:
        text = (
            f"The self-taught chain-of-thought run {selfcot['run_id']} scored "
            f"{_pct(selfcot['accuracy'])} on the dev split{_scored_text(selfcot)}"
        )
        if base["run_id"] is not None:
            text += f", against {_pct(base['accuracy'])} for the base model ({base['run_id']})"
        sentences.append(text + ".")
        if selfcot["gain_pts"] is not None:
            sentences.append(
                f"That is {_gain_text(selfcot)} (a gain counts as outside noise from "
                f"{NOISE_POINTS:.0f} points)."
            )
    if selfcot["run_id"] is None and base["run_id"] is not None:
        sentences.append(
            f"The base model ({base['run_id']}) scored {_pct(base['accuracy'])} on the dev split"
            f"{_scored_text(base)}."
        )
    if sft["run_id"] is not None:
        text = f"The reference fine-tune {sft['run_id']} scored {_pct(sft['accuracy'])}"
        if sft["gain_pts"] is not None:
            text += f", {_gain_text(sft)}"
        sentences.append(text + ".")
    learned = []
    if sft["trained_on"] is not None:
        learned.append(
            f"the reference fine-tune learned from {sft['trained_on']:,} training problems "
            "with GSM8K's own worked solutions"
        )
    if selfcot["trained_on"] is not None:
        learned.append(
            f"the self-taught run learned from {selfcot['trained_on']:,} solutions the model wrote "
            "itself and got right"
        )
    if learned:
        text = "; ".join(learned)
        sentences.append(text[0].upper() + text[1:] + ".")
    for name, label in (("selfcot", "the self-taught run"), ("sft", "the reference fine-tune")):
        flip = flips.get(name)
        if flip is None:
            continue
        text = (
            f"Against base, {label} fixed {flip['fixed']} problems and broke {flip['broken']} "
            f"({flip['both_right']} both right, {flip['both_wrong']} both wrong)."
        )
        sentences.append(text[0].upper() + text[1:])
    if selfcot["mean_lines"] is not None and base["mean_lines"] is not None:
        sentences.append(
            f"Self-taught answers reason in {selfcot['mean_lines']:.1f} lines and "
            f"{selfcot['mean_words']:.1f} words on average, against {base['mean_lines']:.1f} lines and "
            f"{base['mean_words']:.1f} words for the base model."
        )
    return sentences


# --- the comparison ------------------------------------------------------------------------------------


def build_reasoning(model: str, results: Path, outputs: Path) -> dict:
    """The C6 ``Reasoning`` body for ``model`` from the run log ``results`` and the run folders under
    ``outputs``. Raises ``UnknownModel`` (a ``ValueError``) for a model outside the two allowed, and the
    run log's ``OSError`` when the run log cannot be read."""
    if model not in log.MODELS:
        raise UnknownModel(f"model must be one of {', '.join(log.MODELS)}, got {model!r}")
    outputs = Path(outputs)
    rows, _ = log.read_rows(Path(results))
    latest = _latest_dev_rows(rows, model)

    roles = {name: _empty_role(name) for name in ROLES}
    predictions: dict[str, list[dict]] = {}
    for name in ROLES:
        row = latest.get(name)
        if row is None:
            continue
        role = roles[name]
        role["run_id"] = row.run_id
        role["accuracy"] = row.value
        try:
            records = _read_predictions(outputs, row.run_id)
        except _Unreadable as exc:
            role["error"] = str(exc)
            continue
        predictions[name] = records
        scored = len(records)
        role["correct"] = sum(1 for record in records if record["correct"])
        role["scored"] = scored
        role["interval_low"], role["interval_high"] = _interval(row.value, scored)
        if scored:
            outputs_text = [record["output"] for record in records]
            role["mean_lines"] = round(sum(len(reasoning_lines(t)) for t in outputs_text) / scored, 4)
            role["mean_words"] = round(sum(reasoning_words(t) for t in outputs_text) / scored, 4)

    base = roles["base"]
    for name in FINE_TUNES:
        role = roles[name]
        if role["run_id"] is not None and base["run_id"] is not None:
            role["gain_pts"] = round((role["accuracy"] - base["accuracy"]) * 100, 1)
            role["noise"] = _noise(role["gain_pts"])

    sft = roles["sft"]
    if sft["run_id"] is not None:
        try:
            config = _read_json(outputs, sft["run_id"], "config.json", "Run config")
        except _Unreadable:
            config = None
        if config is not None:
            sft["trained_on"] = _trained_on(config.get("train_examples", "all"), TRAIN_SPLIT_SIZE)

    generation = None
    generation_error = None
    selfcot = roles["selfcot"]
    if selfcot["run_id"] is not None:
        generation, generation_error, kept, train_examples = _generation(outputs, selfcot["run_id"])
        selfcot["trained_on"] = _trained_on(train_examples, kept) if train_examples is not None else None

    flips: dict[str, dict] = {}
    if "base" in predictions:
        for name in FINE_TUNES:
            if name in predictions:
                flips[name] = _flip(roles[name], base, predictions[name], predictions["base"])

    examples = []
    if "base" in predictions and "selfcot" in predictions:
        examples = _examples(predictions["base"], predictions["selfcot"])

    return {
        "v": VERSION,
        "model": model,
        "available": selfcot["run_id"] is not None,
        "roles": [roles[name] for name in ROLES],
        "flips": [flips[name] for name in FINE_TUNES if name in flips],
        "generation": generation,
        "generation_error": generation_error,
        "examples": examples,
        "summary": _summary(model, roles, flips),
    }
