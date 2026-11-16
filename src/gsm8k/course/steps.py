"""The learning course as data: 24 steps, their runs and the five course models (US12.1; contract C9).

The Course Steps, Course Runs and Course Models tables of stories.md are the structure; the texts of the
steps are the teaching (a "why" read before acting, a body with the numbers to look at, two or three
multiple-choice questions the service checks, an "in your own words" prompt and a model answer).

Pure data. Importing this module stays light: no torch, transformers, peft or bitsandbytes, and no
environment change. The model revisions come from ``gsm8k.datasets_prompts.hub``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from gsm8k.datasets_prompts import hub

COURSE_RESULTS = "outputs/course/runs.csv"
ATTEMPT_ID_PATTERN = re.compile(r"^course-c[0-9]{2}-[a-z0-9-]+-[1-9][0-9]*$")

PYTHIA = "EleutherAI/pythia-31m"
SMOLLM2 = "HuggingFaceTB/SmolLM2-360M"
QWEN25 = "Qwen/Qwen2.5-0.5B"
QWEN3_06 = "Qwen/Qwen3-0.6B-Base"
QWEN3_17 = "Qwen/Qwen3-1.7B-Base"


def course_dir(outputs: Path) -> Path:
    """``<outputs>/course``: the course's shared files (runs.csv, architectures.json, progress.json)."""
    return Path(outputs) / "course"


def model_revision(model: str) -> str:
    """The pinned revision of a course model (project models from ``MODEL_REVISIONS``)."""
    revision = hub.revision_of(model)
    if revision is None:
        raise KeyError(model)
    return revision


@dataclass(frozen=True)
class Question:
    prompt: str
    options: tuple[str, ...]
    right: int
    explanation: str


@dataclass(frozen=True)
class Step:
    id: str
    number: int
    part: int
    part_title: str
    title: str
    kind: str  # gpu | inspect | lab | read
    runs: tuple[str, ...]
    lesson: str
    why: str
    body: str
    questions: tuple[Question, ...]
    own_words_prompt: str
    model_answer: str


@dataclass(frozen=True)
class CourseRunSpec:
    step: str
    run: str
    command: str  # evaluate | train | cot-generate
    model: str
    changes: dict = field(default_factory=dict)
    changes_text: str = ""


@dataclass(frozen=True)
class CourseModel:
    id: str
    revision: str
    weights_label: str
    why: str
    licence: str = "Apache-2.0"


PARTS: tuple[tuple[int, str], ...] = (
    (1, "Scoring a base model"),
    (2, "Model designs"),
    (3, "How fine-tuning works (lab, CPU)"),
    (4, "Fine-tuning approaches"),
    (5, "The training pipeline"),
)
_PART_TITLE = dict(PARTS)


# --- Course Runs and Course Models (stories.md tables) ---


def _run(step: str, run: str, command: str, text: str, **changes: object) -> CourseRunSpec:
    return CourseRunSpec(step, run, command, str(changes["model"]), dict(changes), text)


COURSE_RUNS: tuple[CourseRunSpec, ...] = (
    _run("c01", "base-06", "evaluate", "Scores Qwen3-0.6B-Base as it is", model=QWEN3_06, method="base"),
    _run("c05", "pythia", "evaluate", "Scores Pythia-31M", model=PYTHIA, method="base"),
    _run("c05", "smollm2", "evaluate", "Scores SmolLM2-360M", model=SMOLLM2, method="base"),
    _run("c05", "qwen25", "evaluate", "Scores Qwen2.5-0.5B", model=QWEN25, method="base"),
    _run("c05", "qwen3-17", "evaluate", "Scores Qwen3-1.7B-Base", model=QWEN3_17, method="base"),
    _run(
        "c20",
        "lora",
        "train",
        "LoRA fine-tune on 300 training problems, then scores 100 dev problems",
        model=QWEN3_06,
        method="sft",
        train_examples=300,
    ),
    _run(
        "c20",
        "qlora",
        "train",
        "The same fine-tune with the frozen base model in 4-bit (QLoRA)",
        model=QWEN3_06,
        method="sft",
        train_examples=300,
        quantize="4bit",
    ),
    _run(
        "c21",
        "sft",
        "train",
        "Supervised LoRA fine-tune on 400 training problems, then scores 100 dev problems",
        model=QWEN3_06,
        method="sft",
        train_examples=400,
    ),
    _run(
        "c22",
        "cotgen",
        "cot-generate",
        "Samples 4 solutions for each of 100 training problems and keeps the correct ones",
        model=QWEN3_06,
        method="cotgen",
        split="train",
        cot_problems=100,
        cot_samples=4,
        limit=None,
    ),
    _run(
        "c22",
        "selfcot",
        "train",
        "Fine-tunes on up to 100 of the model's own correct solutions, then scores 100 dev problems",
        model=QWEN3_06,
        method="selfcot",
        train_examples=100,
    ),
    _run(
        "c23",
        "grpo",
        "train",
        "GRPO for 20 steps with 4 answers per problem, from the c21 adapter when there is one",
        model=QWEN3_06,
        method="grpo",
        grpo_steps=20,
        grpo_generations=4,
    ),
)


def runs_of(step_id: str) -> tuple[CourseRunSpec, ...]:
    """The runs of a step in table order (empty for steps without runs and unknown ids)."""
    return tuple(spec for spec in COURSE_RUNS if spec.step == step_id)


_MODEL_ROWS = (
    (PYTHIA, "30.5 M", "the lab's model (group 11): an older GPT-NeoX design, far too small for math"),
    (SMOLLM2, "362 M", "a Llama-style design trained on fewer, more curated tokens"),
    (QWEN25, "494 M", "the previous Qwen generation, the same family a size step below"),
    (QWEN3_06, "0.6 B", "the project's small model"),
    (QWEN3_17, "1.7 B", "the project's main model"),
)
COURSE_MODELS: tuple[CourseModel, ...] = tuple(
    CourseModel(id=model, revision=model_revision(model), weights_label=label, why=why)
    for model, label, why in _MODEL_ROWS
)


# --- the steps ---


def _flow(text: str) -> str:
    """Markdown with each paragraph and each list item on one line (hard-wrapped source lines joined)."""
    lines: list[str] = []
    for raw in text.strip().splitlines():
        line = raw.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
        elif lines and lines[-1] != "" and not line.startswith("- "):
            lines[-1] += " " + line
        else:
            lines.append(line)
    return "\n".join(lines)


def _q(prompt: str, options: list[str], right: int, explanation: str) -> Question:
    return Question(prompt=prompt, options=tuple(options), right=right, explanation=explanation)


def _step(
    number: int,
    part: int,
    title: str,
    kind: str,
    *,
    why: str,
    body: str,
    questions: list[Question],
    own_words_prompt: str,
    model_answer: str,
    lesson: str = "",
) -> Step:
    step_id = f"c{number:02d}"
    return Step(
        id=step_id,
        number=number,
        part=part,
        part_title=_PART_TITLE[part],
        title=title,
        kind=kind,
        runs=tuple(spec.run for spec in runs_of(step_id)),
        lesson=lesson,
        why=why,
        body=_flow(body),
        questions=tuple(questions),
        own_words_prompt=own_words_prompt,
        model_answer=model_answer,
    )


_C01 = _step(
    1,
    1,
    "How a base model is scored",
    "gpu",
    why=(
        "Every number in this course is an accuracy, so you first need to see exactly how one is made. "
        "This step scores the project's small base model on 100 dev problems and gives you the reference "
        "point that every later run is compared with."
    ),
    body="""
A base model has only been trained to continue text. It has never been taught to answer a question, so the
evaluation does the teaching in the prompt: it shows the model four solved GSM8K problems (always the same
four, the 4-shot prompt), then the new problem, and lets the model continue. The solved examples show the
format: a few lines of working, then a last line `#### <number>`.

The model then writes its answer greedily: at every step it picks the single most likely next token, so the
same prompt always gives the same answer. The scorer takes the final number of the answer and compares it
with the right one exactly. The accuracy is the share of problems whose final number matches.

This course scores only the first 100 dev problems so that a run takes minutes. One accuracy from 100
problems is a rough number: its 95 % interval is about 1.96 times the square root of p times (1 minus p)
divided by 100, which is close to plus or minus 10 points when p is near 60 %. The project's own reference
run on 496 dev problems gave 59.7 % for Qwen3-0.6B-Base, with an interval of about plus or minus 4 points.

Run it, and then look at three numbers: the accuracy, its interval and the minutes. The interval is
as important as the accuracy: a difference between two runs smaller than the interval is not a finding.
""",
    questions=[
        _q(
            "Why does the evaluation put four solved problems in front of the question?",
            [
                "They are the training data that the model learns from during the run.",
                "A base model only continues text, so the examples show it the answer format to continue.",
                "They let the model look up the right answer to the new problem.",
                "They make the run slower on purpose so the timing is measurable.",
            ],
            1,
            "Nothing is trained or looked up. The four examples are part of the input, and the model "
            "continues the pattern: working lines, then a last line that starts with ####.",
        ),
        _q(
            "A run scores 60 right out of 100 problems. What can you say?",
            [
                "The true accuracy is exactly 60 %.",
                "The true accuracy is between 59 % and 61 %.",
                "The true accuracy is plausibly anywhere from about 50 % to 70 %.",
            ],
            2,
            "With 100 problems the 95 % interval is about plus or minus 10 points. Another 100 "
            "problems could "
            "easily give 55 or 65.",
        ),
        _q(
            "What does greedy decoding mean for a run?",
            [
                "The model always takes the most likely next token, so the same prompt gives the "
                "same answer.",
                "The model samples at random, so every run gives a different score.",
                "The model tries four answers and keeps the best one.",
            ],
            0,
            "Greedy decoding has no randomness, which is why an evaluation can be repeated and compared.",
        ),
    ],
    own_words_prompt=(
        "In your own words: how does the project turn a base model and 100 problems into one accuracy, and "
        "how sure can you be of it?"
    ),
    model_answer=(
        "The model gets a prompt with four solved examples and the new problem, writes its answer greedily, "
        "and the final number is compared with the right one. The accuracy is the share of problems "
        "matched. With only 100 problems it is only good to about plus or minus 10 points, so small "
        "differences between runs mean nothing."
    ),
)

_C02 = _step(
    2,
    2,
    "Tokens and the prompt",
    "inspect",
    why=(
        "Before you compare model designs you need to know what a model actually reads: tokens, not words. "
        "This step reads the real tokenizers of the five course models, so the differences you see later "
        "start from the same text."
    ),
    body="""
A model never sees letters or words. A tokenizer cuts the text into tokens, pieces of a few letters,
and each token is a number between 0 and the vocabulary size. Qwen3 has a vocabulary of 151,936 tokens,
Pythia 50,304, SmolLM2 49,152. A larger vocabulary has a token for more whole words, so the same text
becomes fewer tokens.

The inspection takes the first scored dev problem and shows its first 20 tokens as separate pieces, then
counts the tokens of the problem and of the whole 4-shot prompt (the four solved examples, then the
problem). Look at where the cuts fall: common words are one token, numbers are cut into digits or short
groups, and a space is part of the token that follows it.

Why it matters: the prompt is read in full before the first answer token is written, and its length counts
against the model's context length. The 4-shot prompt is several times longer than the problem, so most
of the work of an evaluation is reading the prompt, not writing the answer.

The inspection needs only the models' configuration and tokenizer files, so it runs on the CPU in under
a minute and downloads a few megabytes, not the weights.
""",
    questions=[
        _q(
            "What does a language model read?",
            [
                "Words, one at a time.",
                "Single letters.",
                "Tokens: numbered pieces of text from a fixed vocabulary.",
            ],
            2,
            "The tokenizer cuts the text into pieces that are in its vocabulary and the model reads their "
            "numbers.",
        ),
        _q(
            "The same problem text gives different token counts for different models. Why?",
            [
                "Each model has its own tokenizer and vocabulary, so the cuts differ.",
                "The models read the text at different speeds.",
                "Some models skip the numbers in the text.",
            ],
            0,
            "A tokenizer is part of the model's design. A bigger vocabulary usually means fewer "
            "tokens for the "
            "same text.",
        ),
        _q(
            "Why is the 4-shot prompt much more than the problem in token count?",
            [
                "Because the tokenizer adds padding to every prompt.",
                "Because it holds four solved examples as well as the new problem, and all of it is "
                "read first.",
                "Because the answer is already included in it.",
            ],
            1,
            "The solved examples are the cost of teaching the format in the prompt. They are read again for "
            "every problem.",
        ),
    ],
    own_words_prompt=(
        "In your own words: what is a token, and why do different models count different numbers?"
    ),
    model_answer=(
        "A token is a piece of text that is in a model's fixed vocabulary, and the model reads the "
        "numbers of "
        "those pieces. Each model has its own tokenizer, so the same text is cut into more or fewer pieces. "
        "The prompt length matters because it is all read before the first answer token."
    ),
)

_C03 = _step(
    3,
    2,
    "Inside a decoder-only transformer",
    "inspect",
    why=(
        "All five course models are decoder-only transformers, and so are the big models you tune later. "
        "Knowing the parts lets you read the tables in the next step and see where the weights, and so the "
        "memory, actually are."
    ),
    body="""
A decoder-only transformer is a stack of the same block, repeated, between an input and an output.

- **Embeddings.** A table with one row per token. The token's row is a vector of the model's width, 1,024
  numbers for Qwen3-0.6B. With 151,936 tokens that table alone holds 155.6 million weights, about 26 % of
  the model.
- **The residual stream.** One vector per position that runs through the whole stack. Every block reads it
  and adds its result back to it, so the stream collects what each layer found, and an early layer's work
  is never lost.
- **The attention block.** It lets each position look at the positions before it. Qwen3 uses grouped-query
  attention: 16 query heads share 8 key-value heads, each 128 numbers wide, so the stored keys and values
  take half the memory of full multi-head attention and the quality is close.
- **The MLP block.** Two or three large matrices applied to each position alone. In Qwen3 it is gated, with a
  hidden width of 3,072, and it holds about 60 % of every block's weights: this is where most facts
  and skills are stored.
- **Norms.** A normalisation before the attention block and before the MLP block (and one last norm at the
  end) keeps the numbers in the stream at a stable size. They hold very few weights.
- **The output head.** A final matrix turns the last vector into one score for every token in the
  vocabulary; the best-scoring token is the next one. Qwen3-0.6B ties its output head to its embeddings: the
  same table is used to read tokens in and to score tokens out, so it is stored once.

The stack in Qwen3-0.6B is 28 blocks. In the weights-by-part bar of the inspection the embeddings are one
big piece, the attention and MLP parts together hold the rest, norms are a sliver, and the head is zero
because it is tied.
""",
    questions=[
        _q(
            "What is the residual stream?",
            [
                "The vector for each position that runs through all blocks, where each block adds "
                "its result.",
                "The leftover memory after the weights are loaded.",
                "The list of tokens that the model has not read yet.",
                "A second copy of the model that is used while training.",
            ],
            0,
            "Each block reads the stream and adds to it, so information from early layers stays available.",
        ),
        _q(
            "Qwen3-0.6B has 16 query heads and 8 key-value heads. What does grouped-query attention save?",
            [
                "Weights in the MLP block.",
                "Memory for the stored keys and values: half of what 16 key-value heads would need.",
                "Nothing, because the number of heads is the same.",
            ],
            1,
            "Groups of two query heads share one key-value head, so there are half as many keys and "
            "values to "
            "store and read.",
        ),
        _q(
            "What does it mean that Qwen3-0.6B ties its output head to its embeddings?",
            [
                "The output head is trained first and the embeddings after it.",
                "The model has no output head, so it cannot write text.",
                "The same table of weights both reads tokens in and scores tokens out, so it is stored once.",
            ],
            2,
            "The head still exists as a function, but its weights are the embedding table, so 'head' counts "
            "0 weights. This matters in small models, where the table is a large share.",
        ),
    ],
    own_words_prompt=(
        "In your own words: follow one token through a block of the model. Which parts does it pass, and "
        "where does the residual stream come in?"
    ),
    model_answer=(
        "The token becomes a vector from the embeddings. In each block a norm and the attention block let it "
        "look at earlier tokens, its result is added to the residual stream, then a norm and the MLP block "
        "work on it and add their result too. After the last block the output head scores every token in the "
        "vocabulary."
    ),
)

_C04 = _step(
    4,
    2,
    "Five designs side by side",
    "inspect",
    why=(
        "Now that you know the parts, you can compare five real designs and see which numbers differ. The "
        "table is also the input of the memory budget in step c19."
    ),
    body="""
The inspection reads each model's real configuration and builds one table. What each column means:

- **Layers**: how many times the block is repeated. More layers means a deeper stack.
- **Width**: the length of the vector in the residual stream. It sets the size of every matrix.
- **Attention heads**: how many separate looks at the earlier positions each attention block makes.
- **Key-value heads**: how many keys and values are stored. When it equals the heads the attention is
  multi-head. When it is smaller it is grouped-query: Qwen2.5-0.5B has 14 heads and only 2 key-value heads.
- **Head size**: the width of one head.
- **MLP width**: the hidden width of the MLP block. It is usually three to four times the width.
- **MLP matrices**: 3 when the MLP is gated (Qwen, SmolLM) and 2 when it is not (Pythia).
- **Vocabulary**: the number of tokens, and so the rows of the embedding table.
- **Context**: the longest text the model was built to read, in tokens.
- **Tied**: whether the output head reuses the embeddings. Pythia does not tie them and pays for two big
  tables out of 30.5 million weights.
- **Position encoding**: rotary encoding turns the vectors by an angle that depends on the position, so
  attention sees how far apart two tokens are; the old alternative is learned position embeddings.
  Pythia applies rotary to part of each head only.
- **Activation**: the nonlinearity in the MLP: SiLU in the gated models, GELU in Pythia.
- **bf16 and 4-bit GB**: the memory of the weights alone at 2 bytes a weight (bf16) and at 0.5 bytes a
  weight (4-bit). Qwen3-0.6B needs about 1.2 GB in bf16 and 0.3 GB in 4-bit; Qwen3-1.7B 3.4 GB and 0.9 GB.

Look for the pattern: Pythia, SmolLM2 and the two Qwen generations all use the same recipe of norm,
attention, norm, MLP, but they pick different sizes. The small models spend a large share of their weights
on the embedding table: 155.6 million of Qwen3-0.6B's 596 million, and 136 million of Qwen2.5-0.5B's 494
million, which is why they tie it.
""",
    questions=[
        _q(
            "Qwen3-0.6B-Base has 16 attention heads and 8 key-value heads. Which attention kind is that?",
            [
                "Multi-head attention.",
                "Grouped-query attention.",
                "Learned attention.",
                "Tied attention.",
            ],
            1,
            "Multi-head means as many key-value heads as heads. Fewer key-value heads, shared by groups of "
            "heads, is grouped-query.",
        ),
        _q(
            "Why do small models often tie their embeddings?",
            [
                "Tying makes the model read faster.",
                "The embedding table is a large share of a small model's weights and tying stores it once.",
                "Tied embeddings are the only way to use rotary position encoding.",
            ],
            1,
            "With a vocabulary of 150,000 tokens the table is about a quarter of a 0.5-0.6B model. "
            "Not storing "
            "it twice saves that much.",
        ),
        _q(
            "What does the 4-bit column of a model tell you?",
            [
                "The memory the weights alone need at half a byte a weight, without activations or "
                "training state.",
                "The memory needed to train the model in 4-bit.",
                "The accuracy of the model after it is made 4-bit.",
            ],
            0,
            "It is only the stored weights. Training needs gradients and optimizer states on top (step c19).",
        ),
    ],
    own_words_prompt=(
        "In your own words: pick two columns of the table and say what a difference between two models in "
        "that column means."
    ),
    model_answer=(
        "Key-value heads: a model with fewer key-value heads than heads stores less per token when it reads "
        "a long text, at a small cost in quality. Tied: a model that ties its embeddings stores the "
        "vocabulary table once, which saves a lot in a small model."
    ),
)

_C05 = _step(
    5,
    2,
    "Same test, five designs",
    "gpu",
    why=(
        "You have seen how the designs differ on paper. Here they all take the same test, with the same "
        "prompt, decoding and scoring, so the differences in the score come from the models."
    ),
    body="""
This step queues one evaluation per model: Pythia-31M, SmolLM2-360M, Qwen2.5-0.5B and Qwen3-1.7B-Base. (The
fifth, Qwen3-0.6B-Base, is your c01 run.) They run one after another on the GPU, a few minutes each.

What to look at in the results:

- **Pythia-31M should be near 0 %.** It has 31 million weights and was trained on text in general. It can
  continue the format, but it has no way to calculate. This is the floor of the scale.
- **The Qwen3 models are close to the top.** In this project's reference runs on 496 dev problems,
  Qwen3-0.6B-Base got 59.7 % and Qwen3-1.7B-Base 79.0 %. On your 100 problems expect Qwen3-1.7B-Base near
  79 %, give or take 8 points.
- **The models in between** (SmolLM2-360M and Qwen2.5-0.5B) show how much the design and the training data
  matter beyond size: look at how each compares with Qwen3-0.6B-Base, which has only a little more weight.

Read each accuracy with its interval of about plus or minus 10 points. A gap of 5 points between two of
the middle models is within noise; a gap of 30 points is not.
""",
    questions=[
        _q(
            "Pythia-31M scores close to 0 %. What is the best explanation?",
            [
                "The prompt does not work with its tokenizer.",
                "It is far too small (31 million weights) to do the calculation, even though it can copy the "
                "answer format.",
                "It was trained on the test problems and refuses to answer them.",
            ],
            1,
            "It writes text in the right shape, but the numbers are wrong. Size and training data matter "
            "for maths.",
        ),
        _q(
            "Why can the five scores be compared with each other?",
            [
                "Every model is trained for the same number of steps first.",
                "Every model gets the same prompt, the same greedy decoding and the same scoring on the same "
                "100 problems.",
                "All five models have the same design.",
            ],
            1,
            "The test is fixed, so the models are the only thing that changes. The designs are different.",
        ),
        _q(
            "Qwen2.5-0.5B scores 4 points above SmolLM2-360M on your 100 problems. What do you conclude?",
            [
                "Qwen2.5 is the better design.",
                "SmolLM2 has a bug.",
                "Nothing yet: 4 points is well within the plus or minus 10 points of 100 problems.",
            ],
            2,
            "To call two models different you need a gap larger than the intervals, or many more problems.",
        ),
    ],
    own_words_prompt=(
        "In your own words: what did you learn from the five scores, and what can't you conclude from them?"
    ),
    model_answer=(
        "Size and training matter a lot for maths: Pythia is near 0 %, and the larger Qwen3 model is far "
        "ahead of the smaller ones. With only 100 problems the models in the middle cannot be told apart "
        "by a few points, so the ranking among close models is not a result."
    ),
)

_C06 = _step(
    6,
    2,
    "Why Qwen3-1.7B, and why not the others",
    "read",
    why=(
        "The project fine-tunes Qwen3-1.7B-Base, and you can now judge that choice. Choosing a model is the "
        "decision that limits everything afterwards, so the reasons are worth knowing."
    ),
    body="""
**Why Qwen3-1.7B-Base was chosen.** Qwen3-1.7B-Base leaves room to improve: it scores 79.0 % on the
dev split, far from
what a tuned model could reach, so a gain from fine-tuning can show. (The project's own first fine-tune did
not move it, 78.6 %, which is a reminder that room is not the same as an easy gain.) Qwen3-1.7B-Base fits
LoRA training in 8 GB: its weights take 3.4 GB in bf16 and the adapter training peaks at 5.0 GB at batch
size 2. Qwen3-1.7B-Base is released under the Apache-2.0 licence, and it downloads without an account.

**Why not the alternatives.**

- Larger dense models, such as 7B or 8B ones, do not fit in 8 GB, even with LoRA: 7 billion weights alone
  are 14 GB in bf16.
- Mixture-of-experts models hold many expert blocks and use only a few at a time, but all the experts must
  be kept in memory, so a small active size does not mean a small memory.
- Encoder-decoder models, such as T5, are built to turn one text into another, not for few-shot,
  step-by-step answers that continue a prompt.
- Gated models, such as Llama and Gemma, need an account and an accepted licence before the first download,
  which the project does not use (charter rule 4: no accounts).
- Models that already score 85 to 95 % on GSM8K leave little room to improve, and they may have seen the
  GSM8K problems in training, so their score is contaminated: you could not tell learning from memory.

The smaller sibling, Qwen3-0.6B-Base, is the course's training model for exactly the opposite reasons: it is
quick, and a few minutes of GPU show something.
""",
    questions=[
        _q(
            "Why is a 7B dense model not an option on this PC?",
            [
                "It has no Apache licence.",
                "Its weights alone (about 14 GB in bf16) do not fit in 8 GB of GPU memory.",
                "It cannot read the GSM8K prompt.",
                "It is too accurate to improve.",
            ],
            1,
            "Weights alone need 2 bytes each in bf16, so 7 billion weights are about 14 GB, before any "
            "training state.",
        ),
        _q(
            "Why is a mixture-of-experts model with 3 billion active weights still hard to fit?",
            [
                "Only active weights count, so it fits easily.",
                "All the experts have to be held in memory, not only the active ones.",
                "Experts must be trained one at a time.",
            ],
            1,
            "The router can pick any expert for any token, so all of them must be loaded.",
        ),
        _q(
            "A model that scores 92 % on GSM8K is a poor base for this project. Which two reasons?",
            [
                "It is gated and encoder-decoder.",
                "There is little room to improve, and it may have seen GSM8K during training "
                "(contamination).",
                "It needs 4-bit weights and a larger vocabulary.",
            ],
            1,
            "With little room, a gain is hard to see; with contamination, a high score may be memory.",
        ),
    ],
    own_words_prompt="In your own words: why Qwen3-1.7B-Base, and what rules out a larger or a gated model?",
    model_answer=(
        "It scores 79 % so there is room, it fits LoRA training in 8 GB, and its licence and "
        "download need no "
        "account. Larger dense models do not fit in 8 GB, mixture-of-experts models must keep every "
        "expert in "
        "memory, and gated models like Llama need an account that the project may not create."
    ),
)


def _lab(
    number: int,
    title: str,
    *,
    why: str,
    body: str,
    questions: list[Question],
    own_words_prompt: str,
    model_answer: str,
) -> Step:
    return _step(
        number,
        3,
        title,
        "lab",
        why=why,
        body=body,
        questions=questions,
        own_words_prompt=own_words_prompt,
        model_answer=model_answer,
        lesson=f"l{number - 6:02d}",
    )


_C07 = _lab(
    7,
    "What a fine-tune does",
    why=(
        "The next twelve steps run on the CPU, on a model of 31 million weights, in minutes each. The first "
        "one shows what training changes at all, before any dial is turned."
    ),
    body="""
Open lesson 1 in the Lab and run it. A small LoRA fine-tune of Pythia-31M on a few hundred worked answers
runs, and the page shows the dev loss before and after, and the format rate: the share of answers that end
with a `#### <number>` line.

What the lesson shows: the dev loss falls and the format rate climbs first, because the ending is the same in
every example and is the easiest thing to copy. The accuracy stays low. A fine-tune of a few hundred examples
teaches the shape of an answer, not the maths.

What it shows for the big runs: the first thing a fine-tune of Qwen3 learns is the format too. In this
project, though, the 4-shot prompt already gives a base model the format, and the first full LoRA fine-tune
at the default dials moved Qwen3-0.6B from 59.7 % to 55.2 % on dev. So a fine-tune must teach something the
prompt does not, or it can only lose.
""",
    questions=[
        _q(
            "In lesson 1, why can the format rate reach almost 100 % while the accuracy stays low?",
            [
                "The format is the same in every example and easy to copy, while calculating is not learned "
                "from a few hundred examples.",
                "The format rate and the accuracy are the same measurement.",
                "The model sees the right answers at test time.",
            ],
            0,
            "Copying a fixed ending is cheap. Learning to calculate needs a bigger model or much "
            "more training.",
        ),
        _q(
            "What does the dev loss measure?",
            [
                "How surprised the model is by the answer words of problems it never trained on.",
                "How many problems it answers right.",
                "How fast the training runs.",
            ],
            0,
            "It is a smooth number that falls as the model learns the style of the answers, even before the "
            "accuracy moves.",
        ),
    ],
    own_words_prompt=(
        "In your own words: what did the fine-tune change in lesson 1, and what did it not change?"
    ),
    model_answer=(
        "It lowered the dev loss and made the answers end with the #### number line, so the model learned "
        "the shape of an answer. It did not make the model calculate better, because a small model and a few "
        "hundred examples do not teach that."
    ),
)

_C08 = _lab(
    8,
    "Learning rate",
    why=(
        "The learning rate is the dial that matters most, and the easiest to get wrong. Lesson 2 lets you "
        "see too small and too large side by side."
    ),
    body="""
Open lesson 2 in the Lab. It trains the same setup at learning rates of 1e-5, 1e-4, 1e-3 and 1e-2 and
shows the dev loss after training and the training loss chart of each.

What it shows: at 1e-5 the steps are so small that the model has hardly moved and the dev loss is still
close to its start. At 1e-2 the steps overshoot, the training loss zigzags and the dev loss ends higher. In
between there is a range where the loss falls steadily. LoRA adapters start at zero and add a small change,
so they tolerate a higher rate than full fine-tuning.

What it shows for the big runs: the learning rate dial runs from 1e-5 to 5e-4, with 2e-4 as the default. The
default LoRA fine-tune of Qwen3-0.6B lost 4.4 points on dev, and the project notes say 2e-4 may be too high
for a model that is already good at the task. Try one value on each side of the default on the 0.6B model
before you change anything else.
""",
    questions=[
        _q(
            "Why do both a too-small and a too-large learning rate end with a high dev loss?",
            [
                "Small steps barely move the model, and large steps overshoot and bounce around.",
                "Both of them skip the dev problems.",
                "Both make the adapter bigger.",
            ],
            0,
            "The loss falls only when the steps are big enough to move and small enough to stay stable.",
        ),
        _q(
            "A big LoRA run on Qwen3-0.6B gets worse than the base model at 2e-4. What is a good next try?",
            [
                "Raise the learning rate to 5e-4.",
                "Lower it, for example to 1e-4 or below, and compare on dev.",
                "Stop, because fine-tuning can never help.",
            ],
            1,
            "The lab shows that a rate too high for the task damages the model. Change one dial at a time.",
        ),
    ],
    own_words_prompt="In your own words: what happens to the model when the learning rate is far too high?",
    model_answer=(
        "The updates are so big that they overshoot the good region: the training loss jumps up and down and "
        "the dev loss ends higher than with a gentler rate, or the run diverges. A moderate rate "
        "lets the loss "
        "fall steadily."
    ),
)

_C09 = _lab(
    9,
    "Epochs and overfitting",
    why=(
        "Training on the same examples again looks like free learning. Lesson 3 shows when it stops being "
        "that and turns into memorising."
    ),
    body="""
Open lesson 3 in the Lab. One variant trains on 64 problems for 12 epochs, the other on 768 different
problems for 1 epoch: the same number of examples seen, and about the same time.

What it shows: with the 64 repeated problems the training loss keeps falling, because the model starts to
remember those exact answers. The dev loss, measured on problems it has not seen, stops falling early and
then rises: that is overfitting. The 768 different problems keep giving the model something new, so its
dev loss keeps falling and ends lower. Compare the best dev loss and the step where it happened.

What it shows for the big runs: epochs run from 1 to 3. A second epoch over the same training examples is
repeating. If a second epoch does not lower the dev accuracy, spend the time on more training examples
instead.
""",
    questions=[
        _q(
            "How can you tell from the charts that a run has started to overfit?",
            [
                "The training loss rises while the dev loss falls.",
                "The training loss keeps falling while the dev loss stops falling and rises.",
                "Both losses are exactly equal.",
            ],
            1,
            "The model is fitting the training examples more and more but is getting worse on new ones.",
        ),
        _q(
            "For the same time budget, which is usually better for the dev loss?",
            [
                "Many different problems once.",
                "Few problems repeated many times.",
                "They are always equal.",
            ],
            0,
            "New problems teach more than repeated ones, which the model can start to remember.",
        ),
    ],
    own_words_prompt="In your own words: what is overfitting, and what in lesson 3 told you about it?",
    model_answer=(
        "Overfitting is when a model learns its training examples by heart and gets worse on new problems. "
        "In lesson 3 the training loss of the repeated 64 problems kept falling while the dev loss stopped "
        "falling and rose again."
    ),
)

_C10 = _lab(
    10,
    "How much data",
    why=(
        "Data is the other thing you pay for. Lesson 4 shows what each extra batch of examples buys and what "
        "it costs."
    ),
    body="""
Open lesson 4 in the Lab. It trains on 200, 800 and 1,600 problems and shows the dev loss and the minutes of
each.

What it shows: the first hundreds of examples teach the format and the style, which is most of what a small
model can pick up. After that each extra example adds less: the dev loss still falls but more slowly, which
is called diminishing returns. The time, however, grows in a straight line, so the 1,600-example run takes
eight times as long as the 200-example one.

What it shows for the big runs: the training examples dial runs from 50 to 6,973. Because the gain flattens,
a run on a quarter of the data is a cheap way to compare other dials, and the full set is worth its time
only for the final run. The course runs use 100 to 400 examples for the same reason: they take minutes.
""",
    questions=[
        _q(
            "What does going from 800 to 1,600 examples do compared with going from 200 to 800?",
            [
                "It gains about as much.",
                "It gains less: each extra example helps a bit less than the one before.",
                "It gains nothing at all.",
            ],
            1,
            "Diminishing returns: the loss keeps falling, but more slowly, while the time grows in a "
            "straight line.",
        ),
        _q(
            "Why is it sensible to compare other dials on a quarter of the data?",
            [
                "The quarter gives exactly the same result as all of it.",
                "It costs a quarter of the time and shows the same kind of difference between dials.",
                "The other dials only work on small data.",
            ],
            1,
            "It is a cheap test run. The final run then uses all the data.",
        ),
    ],
    own_words_prompt="In your own words: when does more training data stop being worth its time?",
    model_answer=(
        "When the loss gain per extra example gets small compared with the extra minutes, which happens "
        "after the first few hundred examples for a small model. Use less data to compare ideas and the "
        "full data only for the run you will keep."
    ),
)

_C11 = _lab(
    11,
    "LoRA rank",
    why=(
        "LoRA is the method the course trains with, and its rank sets how many weights it trains. Lesson 5 "
        "shows that a small adapter can be enough."
    ),
    body="""
Open lesson 5 in the Lab. It trains LoRA adapters of rank 1, 8 and 64 with alpha at twice the rank and shows
the trainable weights and the dev loss of each.

What it shows: LoRA does not change the original weights. For each linear layer it learns two thin matrices
whose product is added to the layer, and the rank is how thin they are. Rank 64 has about sixty times as
many trainable weights as rank 1. Learning the style of an answer is a simple change, though, so the three
dev losses land close together. A bigger rank costs more memory and time per step and does not help much.

What it shows for the big runs: the rank dial (4 to 64) and the alpha dial scale together. In this project
the default is rank 16 with alpha 32, and the 1.7B adapter has about 17 million trainable weights against
1.7 billion in the model. If rank 16 and rank 64 score the same on dev, keep the smaller one.
""",
    questions=[
        _q(
            "What does the rank of a LoRA adapter set?",
            [
                "How many layers of the model are used.",
                "How thin the two matrices are, and so how many weights the adapter trains.",
                "The learning rate of the adapter.",
            ],
            1,
            "A higher rank means wider matrices, so more trainable weights and a more flexible change.",
        ),
        _q(
            "Why is alpha usually raised together with the rank?",
            [
                "Alpha sets how strongly the adapter's change is added, and it is kept in proportion to the "
                "rank so the update size stays comparable.",
                "Alpha is the number of epochs.",
                "Alpha decides which layers are frozen.",
            ],
            0,
            "The lesson sets alpha to twice the rank for every variant, so the comparison is fair.",
        ),
    ],
    own_words_prompt="In your own words: why can a small LoRA rank be enough for this task?",
    model_answer=(
        "The change needed to learn the style of an answer is simple, so a few trainable weights per layer "
        "can capture most of it. A larger rank adds weights and time without lowering the dev loss much."
    ),
)

_C12 = _lab(
    12,
    "LoRA or every weight",
    why=(
        "Why train a tiny adapter at all, when every weight could be trained? Lesson 6 shows the "
        "price and the "
        "gain, and step c19 turns the price into gigabytes."
    ),
    body="""
Open lesson 6 in the Lab. It trains the same model twice: with LoRA, and with every weight, at a ten times
lower learning rate for the full run. It shows the trainable weights, the seconds per step, the peak memory
and the dev loss.

What it shows: training every weight makes the optimizer keep extra numbers for all 31 million weights, so
each step takes longer and uses more memory. With that freedom the full fine-tune can fit the data better,
so its dev loss often ends lower on a model this small.

What it shows for the big runs: the big runs use LoRA because a 1.7B model does not fit when all its weights
are trained: at 16 bytes a weight, 1.7 billion weights would need about 27 GB. The lab shows what you give
up, a little fitting power, for a large saving in memory and time.
""",
    questions=[
        _q(
            "Compared with LoRA, training every weight is...",
            [
                "Faster and lighter, because there are no extra layers.",
                "Slower and heavier, and it can reach a lower dev loss on a small model.",
                "Identical on every number.",
            ],
            1,
            "Every weight needs a gradient and optimizer state, but all of them can adapt.",
        ),
        _q(
            "Why does the full run need a lower learning rate than the LoRA run?",
            [
                "Because changing every weight at the LoRA rate would be too violent for the model.",
                "Because LoRA runs have no learning rate.",
                "Because the full run has fewer steps.",
            ],
            0,
            "An adapter starts at zero and adds a small change. Every weight of the real model is already "
            "good, and big steps would damage it.",
        ),
    ],
    own_words_prompt="In your own words: what do you give up, and what do you save, by using LoRA?",
    model_answer=(
        "You give up some fitting power, because only a small adapter is trained. You save a large part of "
        "the memory and time, because gradients and optimizer states are needed only for the adapter's "
        "weights, which makes a 1.7B model trainable on an 8 GB card."
    ),
)

_C13 = _lab(
    13,
    "Batch size",
    why=(
        "Batch size trades the smoothness of a step against the number of steps, and on the GPU it is also a "
        "memory limit. Lesson 7 shows both sides."
    ),
    body="""
Open lesson 7 in the Lab. It trains on 800 examples for one epoch at batch sizes 1, 8 and 32, which is
800, 100 and 25 steps, and shows the steps, the seconds per step, the minutes and the dev loss.

What it shows: a larger batch gives a smoother, more reliable direction for each step, but each step takes
longer and the model gets fewer updates from the same data. A batch of 1 is noisy, so its training loss
jumps. On a CPU a larger batch uses the processor better, so the total time usually falls. With fewer
steps at the same learning rate the model is often less trained.

What it shows for the big runs: the batch size dial runs from 1 to 16 and is limited to 2 on the 1.7B model by
the GPU's memory (batch size 4 ran out of memory in this project). When you raise the batch size the
number of steps falls, so the learning rate may need to rise a little with it.
""",
    questions=[
        _q(
            "What does a bigger batch size do for the same data and one epoch?",
            [
                "More steps, because each is smaller.",
                "Fewer steps, so less time per epoch but also fewer updates.",
                "Nothing, because it only changes memory use.",
            ],
            1,
            "The number of steps is the number of examples divided by the batch size.",
        ),
        _q(
            "Why is the batch size 2 for the 1.7B big runs?",
            [
                "Because 2 is the best value for accuracy.",
                "Because a larger batch ran out of the 8 GB GPU memory.",
                "Because the 1.7B model has 2 layers.",
            ],
            1,
            "Activations grow with the batch size, and they must fit next to the weights and the adapter.",
        ),
    ],
    own_words_prompt="In your own words: what do you win and lose by raising the batch size?",
    model_answer=(
        "A larger batch gives a smoother direction and usually less time per epoch, but fewer "
        "updates, so the "
        "model can end up less trained at the same learning rate. It also needs more memory, which on this "
        "GPU caps the batch size."
    ),
)

_C14 = _lab(
    14,
    "What the loss counts",
    why=(
        "The loss decides what the model is rewarded for. Lesson 8 compares grading only the answer with "
        "grading the question as well."
    ),
    body="""
Open lesson 8 in the Lab. One variant counts only the answer words in the loss; the other counts the
question and the answer. The dev loss always counts the answer words only, so the two can be compared by it.

What it shows: with answer-only loss, every update is about writing better answers. With the whole text the
model is also rewarded for predicting the question, which it will never have to write at test time, so
part of each update goes to waste. The training loss of the second variant is a mix of two kinds of words,
so it cannot be compared with the first one's.

What it shows for the big runs: the big sft runs already count only the answer words, as the lab's default
does. Keep it that way.
""",
    questions=[
        _q(
            "Why can't you compare the training loss of the two variants, but you can compare their "
            "dev loss?",
            [
                "The training loss is only measured on the question.",
                "The training losses average over different words; the dev loss counts the same answer words "
                "for both.",
                "The dev loss is always smaller.",
            ],
            1,
            "Compare things that are measured the same way.",
        ),
        _q(
            "Counting the question words in the loss makes the answer-only dev loss...",
            [
                "Lower, because the model learns more from more words.",
                "About the same or a little worse, because some effort goes into learning to repeat "
                "questions.",
                "Much worse, because the model forgets how to answer.",
            ],
            1,
            "At test time the model never writes the question, so learning it is wasted effort.",
        ),
    ],
    own_words_prompt="In your own words: why do the big runs count only the answer words in the loss?",
    model_answer=(
        "The model has to write only the answer at test time, so every update should improve that. Counting "
        "the question words would spend some of the learning on text that the model never has to produce."
    ),
)

_C15 = _lab(
    15,
    "Answer format",
    why=(
        "Whether to train on worked steps or on the bare number looks like a small choice and is "
        "not. Lesson 9 "
        "shows why the steps matter."
    ),
    body="""
Open lesson 9 in the Lab. It trains once on answers with their steps and once on the final number alone and
shows the accuracy and the format rate. The dev losses are measured over different texts, so they are not
compared.

What it shows: a language model writes one word at a time and cannot calculate in its head between words. When
the answer shows its steps, each step is an easy piece of calculation that the next words can build on. In
the number-only format the model must jump from the question to the final number in one guess. Both
formats learn the `####` ending, so the format rate is the fair first number; the accuracy follows.

What it shows for the big runs: the answer format dial has the same two values, and the terse method trains
the number-only style. Expect step-by-step to win on Qwen3, where the steps really help.
""",
    questions=[
        _q(
            "Why is a model that writes its steps usually more accurate than one that writes the "
            "number only?",
            [
                "Each written step is a small calculation the following words can build on.",
                "Longer answers are always scored higher.",
                "The steps are checked by the scorer.",
            ],
            0,
            "A model cannot calculate silently between tokens. The written steps are its working memory.",
        ),
        _q(
            "Why is the dev loss not a fair way to compare the two formats?",
            [
                "It is the same text in both formats.",
                "The losses are measured over different target texts, so they are not on the same scale.",
                "The dev loss is not computed for the terse format.",
            ],
            1,
            "Compare accuracy and format rate instead.",
        ),
    ],
    own_words_prompt=(
        "In your own words: why do the worked steps help a model that cannot calculate silently?"
    ),
    model_answer=(
        "A model produces one token at a time and has no scratch space except the text it has written. When "
        "it writes the steps, each step turns a hard jump into an easy one and gives the next tokens a "
        "result to build on."
    ),
)

_C16 = _lab(
    16,
    "Warm-up and schedule",
    why=(
        "How the learning rate changes during a run matters as much as its value. Lesson 10 shows a "
        "warm-up, a "
        "flat rate and a hot start."
    ),
    body="""
Open lesson 10 in the Lab. It trains with a warm-up and then a decay, with a flat rate and no warm-up,
and with a three times higher rate and no warm-up. It shows the early training loss and the dev loss.

What it shows: at the first step the optimizer knows nothing about good directions, and a big step in a bad
one can damage the model early. A warm-up raises the rate over the first steps. Decaying the rate to zero
at the end makes the last steps small, which settles the model instead of bouncing around the best place.
The hot start shows its damage in the first steps of its training loss.

What it shows for the big runs: the warm-up ratio dial runs from 0 to 0.2 with 0.03 as the default, and the
big runs always decay the rate. If a run's loss spikes early, raise the warm-up ratio before lowering the
learning rate.
""",
    questions=[
        _q(
            "What does starting at a high learning rate with no warm-up do?",
            [
                "The training loss spikes at the start and the run may end worse.",
                "It learns faster and ends better.",
                "Nothing.",
            ],
            0,
            "Early steps are the least informed, so large steps are the most dangerous.",
        ),
        _q(
            "What does a decaying learning rate do in the last steps that a flat one does not?",
            [
                "It makes the steps small so the model settles instead of bouncing around.",
                "It adds new training examples.",
                "It raises the batch size.",
            ],
            0,
            "Small steps at the end average out the noise of the earlier steps.",
        ),
    ],
    own_words_prompt="In your own words: why warm up at the start and decay at the end?",
    model_answer=(
        "At the start the optimizer has no information, so small steps protect the model from a bad first "
        "move. At the end small steps let the model settle in a good place, while a flat rate keeps it "
        "bouncing around it."
    ),
)

_C17 = _lab(
    17,
    "Seed noise",
    why=(
        "Before you believe any difference between two runs, you need to know how much a run differs from "
        "itself. Lesson 11 measures that with nothing changed but the seed."
    ),
    body="""
Open lesson 11 in the Lab. It trains the same setup with seeds 1, 2 and 3 and shows the last dev loss of each
and the spread between the largest and the smallest.

What it shows: the seed decides the order of the examples and the start of the adapter, so each seed gives a
slightly different run, though nothing else changed. The spread is the noise of this setup. A difference
between two variants in any other lesson that is smaller than this spread may be luck. It is usually small
compared with the gain of a good learning rate, which is why such effects can be trusted.

What it shows for the big runs: the seed dial runs from 0 to 2,147,483,647. Before you say one setting beats
another, repeat the best and the default with a second seed. The same holds for accuracy: on 100 dev problems
the sampling noise alone is plus or minus 10 points, and on the 496 of the reference runs about 4.
""",
    questions=[
        _q(
            "A change of the learning rate lowers the dev loss by less than the seed spread. What "
            "do you conclude?",
            [
                "The change worked.",
                "The change may be luck; it is within the noise of the setup.",
                "The change made things worse.",
            ],
            1,
            "A difference only counts when it is clearly larger than what the seed alone can cause.",
        ),
        _q(
            "What does the seed change in a run?",
            [
                "The model's design.",
                "The order of the training examples and the start of the adapter.",
                "The test problems.",
            ],
            1,
            "Everything else is fixed, which makes the spread a clean measure of noise.",
        ),
    ],
    own_words_prompt="In your own words: how do you decide whether a difference between two runs is real?",
    model_answer=(
        "Compare it with the noise: the spread you get when only the seed changes, or the interval of the "
        "accuracy. Only a difference clearly larger than that is a finding; otherwise repeat the runs with "
        "another seed."
    ),
)

_C18 = _lab(
    18,
    "Where the time goes",
    why=(
        "Training time is the budget of the whole course. Lesson 12 shows where a step spends it and which "
        "savings are real."
    ),
    body="""
Open lesson 12 in the Lab. It runs three variants: tokenize once, group the examples by length, and tokenize
again at every step. It shows the seconds per step, the one-time tokenize seconds, the extra seconds per
step of re-tokenizing and the padding fraction.

What it shows: the text is turned into token numbers once, before the first step. Doing it again at every
step costs only a small slice, because the model's forward and backward pass takes almost all of a step.
Padding is a different cost: the examples in a batch are padded to the longest, and the padded places are
computed and thrown away. Grouping examples of similar length cuts that waste.

What it shows for the big runs: the big sft runs tokenize once as well. What you can tune is the batch
size and the maximum sequence length: shorter examples and less padding mean faster steps.
""",
    questions=[
        _q(
            "Why does re-tokenizing add little time per step, while padding can waste much more?",
            [
                "Tokenizing is a small cost next to the model's pass, but padded places go through the whole "
                "pass and are thrown away.",
                "Padding is free.",
                "Tokenizing happens on the GPU.",
            ],
            0,
            "Compare each cost with the size of the model's forward and backward pass.",
        ),
        _q(
            "Which change makes a big run's steps faster?",
            [
                "Tokenizing every step.",
                "Cutting the maximum sequence length to what the answers need, so there is less padding.",
                "Raising the number of epochs.",
            ],
            1,
            "Shorter sequences mean less to compute at every step.",
        ),
    ],
    own_words_prompt="In your own words: where does a training step spend its time, and what can you save?",
    model_answer=(
        "Almost all of a step is the model's forward and backward pass. You can save the padded places by "
        "grouping examples of similar length and by keeping the sequences short; tokenizing once is already "
        "cheap."
    ),
)

_C19 = _step(
    19,
    4,
    "Memory budget: prompting, full, LoRA, QLoRA",
    "read",
    why=(
        "On an 8 GB card, the memory decides what you can train long before time does. This step turns the "
        "weights counted in step c04 into gigabytes for four approaches, so you know in advance which ones "
        "fit."
    ),
    body="""
There are four ways to make a model better at a task, and they differ in what they keep in memory.

- **Prompting only.** Nothing is trained. The memory is the weights alone, 2 bytes each in bf16, plus the
  text being read. The project's baseline is prompting only: the 4-shot prompt of step c01.
- **Full fine-tuning.** Every weight is trained. For each weight the GPU holds the bf16 weight (2 bytes), its
  gradient (2 bytes) and the AdamW optimizer's two fp32 states with an fp32 master copy of the weight (12
  bytes): 16 bytes a weight. Qwen3-0.6B needs about 9.5 GB and Qwen3-1.7B about 27.5 GB.
- **LoRA.** The base weights are frozen in bf16, so they need no gradient and no optimizer state: 2
  bytes a weight. Only the adapter is trained, at the same 16 bytes per adapter weight. At rank 16 on every
  linear layer, the 0.6B adapter has about 10 million weights and the 1.7B adapter about 17 million.
  Totals: about 1.4 GB and 3.7 GB.
- **QLoRA.** As LoRA, but the frozen base is stored in 4-bit, about 0.55 bytes a weight with the
  quantisation constants, and decoded to bf16 on the fly. The adapter is still trained in bf16. Totals: about
  0.5 GB and 1.2 GB.

Compare each with the 6.5 GB that is usable on this PC (the 8 GB card less about 1.5 GB for the desktop and
the activations): full fine-tuning fits only the two smallest course models (Pythia and SmolLM2) and
none of the Qwen
models, LoRA fits all five, and QLoRA fits them with room to spare.

The figures leave out activations, which grow with batch size and sequence length. They are why the real
peak is higher: the 1.7B LoRA run peaked at 5.0 GB at batch size 2 against 3.7 GB of weights and adapter.
The table on the page is worked out from the real configurations of step c04.
""",
    questions=[
        _q(
            "Why does full fine-tuning need about 16 bytes a weight, and LoRA only about 2?",
            [
                "Full fine-tuning keeps a gradient and optimizer states for every weight; LoRA freezes the "
                "base, so only the small adapter has them.",
                "LoRA stores the weights in 4-bit.",
                "Full fine-tuning keeps four copies of the training data.",
            ],
            0,
            "Gradients and AdamW states are needed only for the weights that are trained.",
        ),
        _q(
            "What does QLoRA change compared with LoRA?",
            [
                "It trains every weight.",
                "It stores the frozen base weights in 4-bit, so the base takes about a quarter of "
                "the memory.",
                "It removes the adapter.",
            ],
            1,
            "The adapter and its training are the same as LoRA; only the frozen base is stored smaller.",
        ),
        _q(
            "The memory table says LoRA on the 1.7B model needs 3.7 GB, yet the run peaked at 5.0 GB. Why?",
            [
                "The table has an error.",
                "The table leaves out the activations, which grow with the batch size and the "
                "sequence length.",
                "The GPU reserves memory for the next run.",
            ],
            1,
            "Weights, adapter and optimizer are the fixed part; activations are the part that depends on how "
            "the batch is shaped.",
        ),
    ],
    own_words_prompt=(
        "In your own words: which approach would you pick for a 1.7B model on an 8 GB card, and why not the "
        "others?"
    ),
    model_answer=(
        "LoRA or QLoRA. Full fine-tuning needs about 16 bytes a weight, around 27 GB, far above 8 GB, while "
        "LoRA keeps the base frozen and trains a small adapter and QLoRA stores the base in 4-bit as well. "
        "Prompting alone needs no training memory but cannot teach the model anything new."
    ),
)

_C20 = _step(
    20,
    4,
    "LoRA or QLoRA on the GPU",
    "gpu",
    why=(
        "The memory table said QLoRA saves memory, and the lab said nothing is free. This step "
        "trains the same "
        "model both ways, so you can read the saving and its price off the run."
    ),
    body="""
This step queues two runs on Qwen3-0.6B-Base that differ in one setting: `lora` trains a LoRA adapter on 300
training problems with the base in bf16, and `qlora` does the same with the frozen base loaded in 4-bit
NF4 (quantize `4bit`). Each then scores the first 100 dev problems.

What to look at when they finish, on the Training page and in the course table:

- **Peak GPU memory.** QLoRA's should be below LoRA's: the base weights take about a quarter of the room.
- **Time.** QLoRA's training steps take about 1.5 times as long, because the 4-bit weights must be decoded to
  bf16 in every forward and backward pass. Memory is paid for with time.
- **Accuracy.** Both scores come from 100 problems, so their intervals are about plus or minus 10 points
  and the difference between them is noise. QLoRA saves memory and does not claim to be more accurate.

On a model this small the saving is a few hundred megabytes, which does not matter on this PC. It matters
for models that would not fit otherwise: a 7B model's 4-bit base is about 3.5 GB, small enough to
train on a card like this one.
""",
    questions=[
        _q(
            "What should the QLoRA run show next to the LoRA run?",
            [
                "A lower peak GPU memory and slower steps.",
                "A higher peak GPU memory and faster steps.",
                "The same memory and a much higher accuracy.",
            ],
            0,
            "The frozen base is stored smaller (less memory) but decoded at every pass (more time).",
        ),
        _q(
            "QLoRA scores 3 points below LoRA on the 100 dev problems. What do you conclude?",
            [
                "QLoRA damages the model.",
                "Nothing yet: 3 points is far inside the plus or minus 10 points of 100 problems.",
                "LoRA has a bug.",
            ],
            1,
            "The two runs differ in how the base is stored; any small score gap on 100 problems is noise.",
        ),
    ],
    own_words_prompt="In your own words: what does QLoRA trade, and what does it keep the same as LoRA?",
    model_answer=(
        "It trades time for memory: the frozen base is stored in 4-bit, so the peak memory falls, but "
        "every step decodes it again and takes longer. It keeps the same trained adapter and the same "
        "recipe, so the accuracy is expected to be similar."
    ),
)

_C21 = _step(
    21,
    5,
    "Supervised fine-tune",
    "gpu",
    why=(
        "You know the dials, the memory and the noise. Now run the first real step of the pipeline: a "
        "supervised fine-tune, which later steps start from or compare with."
    ),
    body="""
Supervised fine-tuning (SFT) shows the model problems paired with their reference solutions from the
GSM8K training split and trains it to make each next word of the solution more likely. Only the answer words
count in the loss (lesson 8). It does not check whether an answer is right: it makes the model imitate
the reference text.

This run uses LoRA on Qwen3-0.6B-Base with 400 training problems, one epoch, the default dials (learning
rate 2e-4, rank 16), and then scores the first 100 dev problems. It also keeps its adapter, which step c23
starts from.

What to look at: the accuracy and its interval against your c01 base run, and the loss curve on the
Training page. Do not expect a big gain: in the project's own reference run, a fine-tune of Qwen3-0.6B on all
6,973 training problems scored 55.2 % on dev against 59.7 % for the base model, and the reasons are the
ones from the lab: the 4-shot prompt already gives the format, the reference solutions are terse, and the
default learning rate may be high. A fine-tune that does not help is a result too.
""",
    questions=[
        _q(
            "What does supervised fine-tuning optimise?",
            [
                "The probability of the reference solutions' next words, not directly whether "
                "answers are right.",
                "The accuracy of the final number.",
                "The model's size.",
            ],
            0,
            "It imitates the reference text. If imitating it does not make the model more correct, the "
            "accuracy does not rise.",
        ),
        _q(
            "Your SFT run scores 4 points above c01 on the 100 dev problems. What can you say?",
            [
                "SFT improves the model by 4 points.",
                "It is within the noise of 100 problems; repeating with other seeds or on more "
                "problems would "
                "tell.",
                "The base model was broken.",
            ],
            1,
            "Plus or minus 10 points of interval means 4 points is not a result on its own.",
        ),
        _q(
            "Why does the course start step c23 from this run's adapter?",
            [
                "GRPO needs a model that already writes answers in the right shape, which SFT gives.",
                "GRPO cannot run on a base model.",
                "The adapter holds the dev problems.",
            ],
            0,
            "Reinforcement learning works from the answers the model samples. If it never writes a "
            "#### line, "
            "there is little reward to find.",
        ),
    ],
    own_words_prompt="In your own words: what does SFT teach the model, and what can it not teach?",
    model_answer=(
        "SFT teaches the model to write like the reference solutions: their style and ending. It does not "
        "check correctness, so it cannot teach the model to reason better than the examples let it, and a "
        "small run may not move the accuracy at all."
    ),
)

_C22 = _step(
    22,
    5,
    "Self-taught reasoning",
    "gpu",
    why=(
        "SFT copies someone else's solutions. Self-taught reasoning asks whether the model can "
        "learn from its "
        "own correct solutions instead, which are in its own words and need no reference text."
    ),
    body="""
The step has two runs, one after the other. First `cotgen` takes 100 training problems and samples 4
solutions for each at temperature 0.7 (some randomness, so the four differ). It keeps a solution only if it
ends with a `####` line holding the right number and has at least one line of working before it; at most one
per problem, the first correct one. The row for this run is not an accuracy: it is the kept fraction.

Then `selfcot` fine-tunes the model on those kept solutions, up to 100 of them, and scores the first 100 dev
problems. If fewer than 50 solutions were kept, the step says so and asks you to run it again instead
of training on too little.

Why this can work: the model learns from solutions that are right and are already in its own style, so there
is no mismatch with a reference style. What it cannot do is learn what it never got right: problems it
solved in none of 4 samples are missing from the data. In the project's runs on the 1.7B model, 89.6 % of
the training problems yielded a correct solution, and the self-taught fine-tune reached 76.2 % on dev
against 79.0 % for the base: no gain either.
""",
    questions=[
        _q(
            "Why does self-taught reasoning keep only the correct solutions?",
            [
                "Wrong solutions are too long.",
                "Training on a wrong solution would teach the model to repeat the mistake; a check "
                "on the final "
                "number is a cheap teacher.",
                "The scorer only reads correct solutions.",
            ],
            1,
            "The right final number is the only signal available, so it filters the data.",
        ),
        _q(
            "What does the cotgen row's value mean?",
            [
                "The accuracy on 100 dev problems.",
                "The kept fraction: how many of the 100 training problems gave at least one correct "
                "solution.",
                "The number of tokens written.",
            ],
            1,
            "It is a keep rate, so it is not compared with the accuracies in the table.",
        ),
        _q(
            "Which problems cannot appear in the self-taught data?",
            [
                "Problems the model got right in some sample.",
                "Problems the model never solved in any of its 4 samples.",
                "Problems from the training split.",
            ],
            1,
            "It learns only from what it can already do some of the time, so it sharpens, not extends.",
        ),
    ],
    own_words_prompt=(
        "In your own words: how does the model teach itself here, and what is its limit compared with SFT?"
    ),
    model_answer=(
        "It samples several solutions for training problems, keeps the ones whose final number is right and "
        "trains on them, so the data is in its own style. The limit is that it can only learn from "
        "problems it "
        "already sometimes solves, while SFT can show it solutions it could not write itself."
    ),
)

_C23 = _step(
    23,
    5,
    "Reinforcement learning with GRPO",
    "gpu",
    why=(
        "SFT imitates and self-taught reasoning filters. GRPO is the third idea: let the model try, "
        "score its "
        "tries, and push it toward the better ones. It is the last stage of the pipeline."
    ),
    body="""
GRPO (group relative policy optimisation) works on one training problem at a time. The model samples 4
answers to it. Each answer gets a reward: 1 for the right final number, plus 0.1 for a `####` line. The
model is then moved toward the answers that scored above the average of their group and away from those
below it, so no separate model has to judge them. A KL term keeps the model close to the base model it
started from, so it cannot drift into text that scores but is no longer sensible.

The run takes 20 steps, one problem each, starting from the adapter of your latest finished c21 run (the
base model when there is none; if c21's folder was deleted the step asks you to run c21 again). It
then scores the
first 100 dev problems.

What to look at in its metrics lines: the reward (does the average rise?), the KL (how far from the start
the model has moved) and the answer length. With only 20 problems seen, do not expect the accuracy to change
beyond noise. The step shows how the method works, and how little a short run can show; a real GRPO run needs
hundreds of steps.
""",
    questions=[
        _q(
            'What does "group relative" mean in GRPO?',
            [
                "Each answer is compared with the average reward of the other answers to the same problem.",
                "The model is trained on groups of problems from different splits.",
                "Rewards come from a second model that judges the answers.",
            ],
            0,
            "Answers above their group's average are made more likely, answers below less likely.",
        ),
        _q(
            "What does the KL term do?",
            [
                "It raises the reward.",
                "It penalises the model for moving far from its starting model.",
                "It selects the training problems.",
            ],
            1,
            "Without it the model could drift into answers that exploit the reward and are no "
            "longer sensible.",
        ),
        _q(
            "Why is a 20-step GRPO run unlikely to change the dev accuracy beyond noise?",
            [
                "GRPO cannot improve accuracy.",
                "It sees only 20 training problems, and 100 dev problems cannot show a small change.",
                "The reward is always zero.",
            ],
            1,
            "Both the training signal and the test are tiny. The run shows the method, not a result.",
        ),
    ],
    own_words_prompt="In your own words: how does GRPO learn from the answers the model writes?",
    model_answer=(
        "The model writes several answers to a problem and each is scored by whether its final number is "
        "right. It is then pushed toward the answers that beat the group's average and away from the ones "
        "below it, while a KL penalty keeps it near where it started."
    ),
)

_C24 = _step(
    24,
    5,
    "What moved the score, and noise",
    "read",
    why=(
        "You have run every stage of the pipeline. The last step puts all the course runs in one table and "
        "asks the question the whole project rests on: which of these differences are real?"
    ),
    body="""
The comparison on the page lists every finished course run (except `cotgen`, whose row is a keep rate): its
model, method, accuracy on its 100 problems with the 95 % interval, its gain over your c01 base run for
Qwen3-0.6B runs, and the minutes. A gain is labelled "within noise" when the two intervals overlap.

Read it with three facts in mind:

- 100 problems give an interval about plus or minus 10 points wide, so two runs have to be 15 to 20 points
  apart before the intervals clearly separate. Nothing in the course comes close to that, except the
  comparisons between very different models in step c05.
- The reference runs in `results/runs.csv` use 496 problems, and an interval of about plus or minus 4
  points. Those are the numbers to trust, and even they call a gain of less than about 4 points noise.
- What moved the score in the project: model size (Qwen3-1.7B-Base over Qwen3-0.6B-Base, 19 points on
  dev). The fine-tuned runs so far did not beat their base models.

The course did not make Qwen3-0.6B better; it showed you how each stage works and how to tell a result from
luck.
""",
    questions=[
        _q(
            "Two course runs score 62 % and 55 % on 100 problems each. Is the 7-point gap real?",
            [
                "Yes: 7 points is a lot.",
                "Not shown: the intervals (about plus or minus 10 points) overlap, so it is within noise.",
                "No, they are exactly equal.",
            ],
            1,
            'The label "within noise" means the two intervals overlap.',
        ),
        _q(
            "Why do the project's reference runs use 496 problems and not 100?",
            [
                "The interval narrows with more problems (about plus or minus 4 points instead of 10), so "
                "smaller differences can be seen.",
                "496 is the size of the training split.",
                "100 problems are too slow to score.",
            ],
            0,
            "The interval shrinks with the square root of the number of problems.",
        ),
        _q(
            "What moved the score the most in this project?",
            [
                "The learning rate.",
                "The size of the model: Qwen3-1.7B-Base scores about 19 points above Qwen3-0.6B-Base on dev.",
                "GRPO.",
            ],
            1,
            "That gap is far outside the noise. The tuned runs so far were within it or below it.",
        ),
    ],
    own_words_prompt=(
        "In your own words: look at the comparison table. What can you conclude from it, and what "
        "can you not?"
    ),
    model_answer=(
        "You can conclude things only where the gaps are larger than the intervals, such as the larger model "
        "against the smaller one. The small gains and losses between the fine-tuning runs overlap, so with "
        "100 problems they are noise and need the 496-problem reference runs and several seeds before they "
        "count."
    ),
)

STEPS: tuple[Step, ...] = (
    _C01,
    _C02,
    _C03,
    _C04,
    _C05,
    _C06,
    _C07,
    _C08,
    _C09,
    _C10,
    _C11,
    _C12,
    _C13,
    _C14,
    _C15,
    _C16,
    _C17,
    _C18,
    _C19,
    _C20,
    _C21,
    _C22,
    _C23,
    _C24,
)
STEP_IDS: tuple[str, ...] = tuple(step.id for step in STEPS)
_BY_ID = {step.id: step for step in STEPS}


def get_step(step_id: str) -> Step | None:
    """The step with this id, or None when there is none."""
    return _BY_ID.get(step_id)
