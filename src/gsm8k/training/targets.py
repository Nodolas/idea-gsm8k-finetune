"""Training targets: the prompt and the answer a fine-tune learns, per answer format (FR2.1, BR2.3).

The prompt is the zero-shot frame of the fixed evaluation prompt (``Question: <q>`` newline
``Answer:``), so a fine-tuned model sees at training time the same frame it is scored with. The
target starts with a space (it continues ``Answer:``) and ends with the ``#### <gold>`` line.
"""

from gsm8k.datasets_prompts.hub import Problem
from gsm8k.datasets_prompts.prompt import strip_calculator_notes

ANSWER_FORMATS = ("step-by-step", "terse")


def training_prompt(question: str) -> str:
    """The zero-shot ``Question: <q>`` newline ``Answer:`` frame of BR2.3."""
    return f"Question: {question}\nAnswer:"


def training_text(problem: Problem, answer_format: str) -> tuple[str, str]:
    """(prompt, target) for one training problem.

    ``step-by-step``: the worked answer without its ``<<...>>`` calculator notes, ending with
    ``#### <gold>``; ``terse``: only the ``#### <gold>`` line.
    """
    if answer_format not in ANSWER_FORMATS:
        raise ValueError(f"answer_format must be one of {', '.join(ANSWER_FORMATS)}, got {answer_format!r}")
    gold_line = f"#### {problem.gold}"
    if answer_format == "terse":
        return training_prompt(problem.question), " " + gold_line
    worked = strip_calculator_notes(problem.answer)
    steps = worked.rsplit("####", 1)[0].strip() if "####" in worked else worked.strip()
    target = f"{steps}\n{gold_line}" if steps else gold_line
    return training_prompt(problem.question), " " + target
