"""The twelve lab lessons (US11.1, contract C8): each changes one dial against the same starting point.

Pure data; no model is loaded. The texts are the teaching: plain words, one idea per lesson, and the
numbers to look at named in ``watch`` and ``why``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Variant:
    name: str
    label: str
    changes: dict[str, Any]


@dataclass(frozen=True)
class Lesson:
    id: str
    number: int
    title: str
    question: str
    watch: str
    guess_prompt: str
    guess_options: tuple[str, str, str]
    variants: tuple[Variant, ...]
    why: str
    big_run: str
    check: str


LESSONS: tuple[Lesson, ...] = (
    Lesson(
        id="l01",
        number=1,
        title="What a fine-tune does",
        question=(
            "What happens to a small model when you fine-tune it on a few hundred worked maths answers?"
        ),
        watch=(
            "Dev loss before and after training, and the format rate: the share of answers that end with "
            "a '#### <number>' line."
        ),
        guess_prompt="After the run, what has changed the most?",
        guess_options=(
            "The model gets most of the answers right.",
            "The dev loss falls and the answers start to end with a '#### number' line, "
            "but most are still wrong.",
            "Nothing changes, because the model is too small to learn anything.",
        ),
        variants=(Variant("baseline", "Starting point", {}),),
        why=(
            "Fine-tuning shows the model many examples of a question followed by a worked answer and nudges "
            "its weights so that each next word of the answer becomes a little more likely. The dev loss is "
            "the average surprise of the model at the answer words of problems it never trained on, so it "
            "falls when the model has learned the style of the answers. The format rate climbs first "
            "because the ending '#### number' is the same in every example and is easy to copy. Accuracy "
            "stays low: this model has only 31 million weights and never learned to calculate, and a few "
            "hundred examples teach the shape of an answer, not the maths. Compare 'dev loss before' with "
            "'dev loss after' and the format rate before and after."
        ),
        big_run=(
            "The same thing happens in the big sft runs: the first thing a fine-tune of Qwen3 learns is the "
            "answer format. If your format rate is already high at the start, extra training examples "
            "can only help with the maths itself."
        ),
        check=("Why can the format rate reach almost 100 percent while the accuracy stays low?"),
    ),
    Lesson(
        id="l02",
        number=2,
        title="Learning rate",
        question="How big should each update step be?",
        watch=(
            "The dev loss after training for each learning rate, and whether the training loss jumps around."
        ),
        guess_prompt="Which learning rate gives the lowest dev loss?",
        guess_options=(
            "The smallest, 1e-5, because small steps are the safest.",
            "A middle one, 1e-4 or 1e-3: big enough to learn, small enough to stay stable.",
            "The largest, 1e-2, because it learns the fastest.",
        ),
        variants=(
            Variant("lr-1e-5", "Learning rate 1e-5", {"learning_rate": 1e-5}),
            Variant("lr-1e-4", "Learning rate 1e-4", {"learning_rate": 1e-4}),
            Variant("lr-1e-3", "Learning rate 1e-3", {"learning_rate": 1e-3}),
            Variant("lr-1e-2", "Learning rate 1e-2", {"learning_rate": 1e-2}),
        ),
        why=(
            "The learning rate scales every weight update. With 1e-5 the steps are so small that the model "
            "has barely moved when the run ends, so the dev loss is still close to its starting value. "
            "With 1e-2 the steps overshoot: the training loss jumps up and down and the dev loss ends "
            "higher than a gentler rate would give, or training diverges. In between there is a range "
            "where the dev loss falls steadily. LoRA adapters tolerate a higher rate than full "
            "fine-tuning, because they start at zero and only add a small change. Compare the dev loss "
            "after training across the four runs, and look at the training loss chart for the one that "
            "zigzags."
        ),
        big_run=(
            "The learning rate dial is the one that matters most. The big runs allow 1e-5 to 5e-4 with "
            "a default of 2e-4, so try one value on each side of the default (for example 1e-4 and 4e-4) "
            "on the 0.6B model before changing anything else."
        ),
        check="Why does a too-small learning rate and a too-large one both end with a high dev loss?",
    ),
    Lesson(
        id="l03",
        number=3,
        title="Epochs and overfitting",
        question=("Is it better to see 64 problems twelve times, or 768 different problems once?"),
        watch=(
            "Training loss against dev loss for each variant, the best dev loss and the step where it "
            "happened."
        ),
        guess_prompt="Which variant ends with the lower dev loss?",
        guess_options=(
            "Both end about the same, because both see 768 examples in total.",
            "64 problems twelve times, because repeating makes the model know them well.",
            "768 problems once, because new problems teach more than repeated ones.",
        ),
        variants=(
            Variant("few-many", "64 problems, 12 epochs", {"train_examples": 64, "epochs": 12}),
            Variant("many-once", "768 problems, 1 epoch", {"train_examples": 768, "epochs": 1}),
        ),
        why=(
            "Both variants take the same number of steps with the same number of examples per step, so they "
            "cost about the same time. The difference is what the model sees. With 64 problems repeated, "
            "the training loss keeps falling because the model starts to remember those exact answers. "
            "The dev loss, measured on problems it has not seen, stops falling early and then rises "
            "again: that is overfitting. The 768 different problems give the model new things to "
            "learn at every step, so its dev loss keeps falling and ends lower. Look at the best dev loss "
            "and its step for 'few-many': if the best step is well before the end, the later training "
            "only hurt."
        ),
        big_run=(
            "The epochs dial allows 1 to 3. More epochs over the same training examples is repeating, "
            "and the dev loss will tell you when it turns into overfitting. If a second epoch does not "
            "lower the dev accuracy, use the time for more training examples instead."
        ),
        check="How can you tell from the two charts that a run has started to overfit?",
    ),
    Lesson(
        id="l04",
        number=4,
        title="How much data",
        question="How much does a fine-tune gain from more training examples?",
        watch="Dev loss after training for 200, 800 and 1,600 examples, and how much each doubling gains.",
        guess_prompt="What does going from 800 to 1,600 examples do compared with 200 to 800?",
        guess_options=(
            "It gains about as much, because the gain is proportional to the data.",
            "It gains less: each extra example helps a bit less than the one before.",
            "It gains nothing at all beyond 800 examples.",
        ),
        variants=(
            Variant("data-200", "200 problems", {"train_examples": 200}),
            Variant("data-800", "800 problems", {"train_examples": 800}),
            Variant("data-1600", "1,600 problems", {"train_examples": 1600}),
        ),
        why=(
            "More examples mean more steps, because one epoch is one pass over the data. The first "
            "hundreds of examples teach the format and the style of the answers, which is most of what "
            "a small model can pick up. After that each extra example adds less: the dev loss keeps "
            "falling, but more slowly, a pattern called diminishing returns. The time grows in a straight "
            "line with the data, so the third variant takes eight times as long as the first. Compare the "
            "drop in dev loss between the three runs with the minutes each one took."
        ),
        big_run=(
            "The training examples dial runs from 50 to 6,973. Because the gain flattens, a run on a "
            "quarter of the data is a cheap way to compare other dials, and the full set is worth its "
            "time only for the final run."
        ),
        check="If doubling the data gives a smaller gain each time, when does more data stop being worth it?",
    ),
    Lesson(
        id="l05",
        number=5,
        title="LoRA rank",
        question="How many trainable weights does a LoRA adapter need?",
        watch="Trainable weights for each rank, and the dev loss after training.",
        guess_prompt="What happens to the dev loss when the rank goes from 8 to 64?",
        guess_options=(
            "It falls a lot, because eight times more trainable weights can learn eight times more.",
            "It barely changes: a small rank is already enough for this task.",
            "It rises, because a bigger adapter always overfits.",
        ),
        variants=(
            Variant("rank-1", "Rank 1", {"lora_rank": 1, "lora_alpha": 2}),
            Variant("rank-8", "Rank 8", {"lora_rank": 8, "lora_alpha": 16}),
            Variant("rank-64", "Rank 64", {"lora_rank": 64, "lora_alpha": 128}),
        ),
        why=(
            "LoRA does not change the original weights. For each linear layer it learns two thin matrices "
            "whose product is added to the layer, and the rank is how thin they are. Rank 1 has the fewest "
            "trainable weights, rank 64 about sixty times more, and the table shows the exact numbers. "
            "Here alpha is twice the rank in every variant, so the size of the update stays comparable. "
            "Learning the answer style is a simple change, so even a small rank captures most of it and "
            "the dev loss of the three runs lands close together. A larger rank costs more memory and "
            "time per step without helping much. Compare 'trainable weights' with the dev loss after "
            "training."
        ),
        big_run=(
            "The LoRA rank dial (4 to 64 on the big runs) and the LoRA alpha dial scale together. "
            "If rank 16 and rank 64 score the same on dev, take the smaller one: it trains faster and "
            "its adapter is smaller to keep."
        ),
        check="Why is it usual to raise the LoRA alpha together with the LoRA rank?",
    ),
    Lesson(
        id="l06",
        number=6,
        title="LoRA or every weight",
        question="What changes if you train all the weights instead of a small adapter?",
        watch=(
            "Trainable weights, seconds per step, peak memory and the dev loss after training for the "
            "two methods."
        ),
        guess_prompt="Compared with LoRA, training every weight is...",
        guess_options=(
            "Slower and heavier, and it reaches a lower dev loss on this small model.",
            "Faster, because there are no extra adapter layers to compute.",
            "The same on every number, because the model ends up equally good.",
        ),
        variants=(
            Variant("lora", "LoRA adapters", {}),
            Variant("full", "Every weight", {"method": "full", "learning_rate": 1e-4}),
        ),
        why=(
            "With LoRA the model's own weights are frozen and only the small adapters are trained, "
            "a small fraction of the model. Training every weight means the optimizer keeps extra "
            "numbers for all 31 million weights, so each step takes longer and uses more memory. The "
            "full run uses a ten times lower learning rate, because changing every weight at the LoRA rate "
            "would be too violent. With enough freedom the full fine-tune can fit the data better, so its "
            "dev loss often ends lower on a model this small. Read 'trainable weights' and 'seconds per "
            "step' next to the dev loss: this is the price and the gain."
        ),
        big_run=(
            "The big runs use LoRA through the sft method because the 1.7B model does not fit in 8 GB when "
            "all its weights are trained. The lab shows what you give up: a little fitting power for a "
            "large saving in memory and time."
        ),
        check="Why does the full run need a lower learning rate than the LoRA run?",
    ),
    Lesson(
        id="l07",
        number=7,
        title="Batch size",
        question="How many examples should one update step look at?",
        watch="Steps, seconds per step, total minutes, and the dev loss after training.",
        guess_prompt="What does a bigger batch size do for the same data and one epoch?",
        guess_options=(
            "Fewer steps and a fair amount of time saved, but the model also gets fewer updates.",
            "More steps, because each one is smaller.",
            "Nothing: the batch size only changes the memory use.",
        ),
        variants=(
            Variant("batch-1", "Batch size 1", {"batch_size": 1}),
            Variant("batch-8", "Batch size 8", {"batch_size": 8}),
            Variant("batch-32", "Batch size 32", {"batch_size": 32}),
        ),
        why=(
            "One epoch over 800 examples is 800 steps at batch size 1, 100 at batch size 8 and 25 at batch "
            "size 32. A larger batch gives a smoother, more reliable direction for each step, but each step "
            "takes longer, and the model gets fewer updates from the same data. A batch of 1 is noisy: "
            "the training loss jumps from step to step. On a CPU a bigger batch also uses the processor "
            "more efficiently, so the total time usually falls. At the same learning rate, fewer steps "
            "often leave the model less trained. Look at 'steps' and 'seconds per step' together with "
            "the dev loss after training."
        ),
        big_run=(
            "The batch size dial runs from 1 to 16 and is limited to 2 or less on the 1.7B model by "
            "the GPU's memory. When you raise the batch size, the number of steps falls, so the learning "
            "rate may need to rise a little with it."
        ),
        check=(
            "Why does the same amount of data take fewer minutes with a bigger batch but give fewer updates?"
        ),
    ),
    Lesson(
        id="l08",
        number=8,
        title="What the loss counts",
        question="Should the model be graded on the question words too, or only on the answer?",
        watch=(
            "Training loss and dev loss after training. The dev loss always counts the answer words only, "
            "so the two variants can be compared."
        ),
        guess_prompt="Counting the question words in the loss makes the answer-only dev loss...",
        guess_options=(
            "Lower, because the model learns more from more words.",
            "About the same or a little worse: some effort goes into learning to repeat the question.",
            "Much worse, because the model forgets how to answer.",
        ),
        variants=(
            Variant("answer-only", "Answer words only", {}),
            Variant("whole-text", "Question and answer", {"loss_on": "all"}),
        ),
        why=(
            "The model reads the question and writes the answer, and only the answer needs to be right. "
            "With 'answer words only' the question words are given to the model but they are hidden from the "
            "loss, so every update is about writing better answers. With 'question and answer' the model "
            "is also rewarded for predicting the question, which it will never have to write at test "
            "time, so part of every update goes to learning that. The training loss of the second variant "
            "is a mix of the two kinds of words and cannot be compared with the first. Judge both by the "
            "dev loss, which is measured the same way for both."
        ),
        big_run=(
            "The big sft runs already count only the answer words, as the lab's default does. "
            "That is the right choice for the training examples dial too: every example then teaches "
            "only the part that is graded."
        ),
        check=(
            "Why can't you compare the training loss of the two variants, but you can compare their dev loss?"
        ),
    ),
    Lesson(
        id="l09",
        number=9,
        title="Answer format",
        question="Should the model learn to show its steps, or only the final number?",
        watch=(
            "The accuracy and the format rate after training. The dev losses are over different answer "
            "texts, so do not compare them."
        ),
        guess_prompt="Which format gets more answers right?",
        guess_options=(
            "The terse one: with only the number to write there is less to get wrong.",
            "Step-by-step: writing the steps gives the model room to work out the answer.",
            "They are the same, because the final number is what is scored.",
        ),
        variants=(
            Variant("step-by-step", "Step by step", {}),
            Variant("terse", "Number only", {"answer_format": "terse"}),
        ),
        why=(
            "A language model writes one word at a time and cannot calculate in its head between words. "
            "When the answer shows the steps, each step is an easy piece of calculation that the next "
            "words can build on. In the terse format the model must jump from the question to the final "
            "number in a single guess. The terse dev loss is small simply because the text is short, and "
            "it is not comparable with the step-by-step one. The format rate is the fair first number to "
            "read: both formats learn to end with '#### number'. Then compare the accuracy after training. "
            "A model this small is rarely right in either format, so expect low numbers and a small "
            "gap."
        ),
        big_run=(
            "The answer format dial has the same two values, step-by-step and terse, and the terse "
            "method of the big runs trains the number-only style. Expect step-by-step to win on the "
            "1.7B model, where the steps really help."
        ),
        check="Why is the dev loss of the two formats not a fair way to compare them?",
    ),
    Lesson(
        id="l10",
        number=10,
        title="Warm-up and schedule",
        question="Should the learning rate start small, and should it shrink during the run?",
        watch=(
            "The learning rate chart's shape in the training results, the training loss in the first "
            "steps, and the dev loss after training."
        ),
        guess_prompt="What does starting at a high learning rate with no warm-up do?",
        guess_options=(
            "The training loss spikes at the start and the run may end worse.",
            "It learns faster and ends better.",
            "Nothing: the warm-up is only decoration.",
        ),
        variants=(
            Variant("warmup-decay", "Warm-up, then decay", {}),
            Variant("constant", "Warm-up, then flat", {"schedule": "constant", "warmup_ratio": 0}),
            Variant("hot-start", "High start, no warm-up", {"learning_rate": 3e-3, "warmup_ratio": 0}),
        ),
        why=(
            "At the first step the optimizer knows nothing about the direction of good changes, and a "
            "big step in a bad direction can damage the model early. A warm-up raises the learning "
            "rate over the first steps so that the optimizer can find its feet. Decaying the rate to zero "
            "at the end makes the last steps small, which settles the model into a good place instead "
            "of bouncing around it. The 'constant' variant keeps the rate flat all the way, so it ends "
            "with a noisier model. The 'hot-start' variant has a three times higher rate and no warm-up, "
            "and its training loss shows the damage in the first steps. Compare the dev loss after "
            "training and look at the early training loss of each."
        ),
        big_run=(
            "The warmup ratio dial runs from 0 to 0.2 with a default of 0.03. The big runs always decay "
            "the learning rate, so if a run's loss spikes early, raise the warmup ratio before "
            "lowering the learning rate."
        ),
        check=(
            "What does a decaying learning rate do in the last steps of a run that a constant one does not?"
        ),
    ),
    Lesson(
        id="l11",
        number=11,
        title="Seed noise",
        question="If you change nothing but the random seed, how much does the result move?",
        watch="The last dev loss of the three runs, and the difference between the largest and the smallest.",
        guess_prompt="How different are the three dev losses?",
        guess_options=(
            "Identical, because the data and the settings are the same.",
            "Slightly different: a small spread that is noise, not a real effect.",
            "Very different, so one run tells you nothing.",
        ),
        variants=(
            Variant("seed-1", "Seed 1", {"seed": 1}),
            Variant("seed-2", "Seed 2", {"seed": 2}),
            Variant("seed-3", "Seed 3", {"seed": 3}),
        ),
        why=(
            "The seed decides the order in which the training examples are shuffled and the starting values "
            "of the LoRA adapter. Different seeds therefore give a slightly different run, even "
            "though nothing else changed. The spread between the three dev losses is the noise of this "
            "setup: a difference between two variants in any other lesson that is smaller than this spread "
            "may be luck and not an effect of the dial. Look at the spread, which the page works out as the "
            "largest dev loss minus the smallest. It is usually small compared with the gains of a "
            "good learning rate, which is why those effects can be trusted."
        ),
        big_run=(
            "The random seed dial runs from 0 to 2147483647. Before you conclude that one setting beats "
            "another on the big runs, repeat the best and the default with a second seed. If the gap "
            "is about as big as the spread you saw here, you have found noise."
        ),
        check=(
            "A change of the learning rate lowers the dev loss by less "
            "than the seed spread. What do you conclude?"
        ),
    ),
    Lesson(
        id="l12",
        number=12,
        title="Where the time goes",
        question="Where does a training step spend its time, and what can be saved?",
        watch=(
            "Seconds per step for the three variants, the one-time tokenize seconds, the extra seconds "
            "per step when tokenizing again, and the padding fraction."
        ),
        guess_prompt="Which change makes the biggest difference to the time per step?",
        guess_options=(
            "Tokenizing the text once instead of at every step.",
            "Grouping examples of similar length into the same batch.",
            "Neither: the step is dominated by the forward and backward pass of the model.",
        ),
        variants=(
            Variant("tokenize-once", "Tokenize once", {}),
            Variant("by-length", "Group by length", {"batching": "by-length"}),
            Variant("retokenize", "Tokenize every step", {"retokenize": True}),
        ),
        why=(
            "The text is turned into token numbers once, before the first step, and the same numbers are "
            "used in every epoch: the 'tokenize seconds' is paid one time. The 'retokenize' variant does "
            "the work again at every step so that you can see what it costs; it is a small slice of a "
            "step, because the model's forward and backward pass takes almost all of the time. Padding is "
            "a different cost: examples in a batch are padded to the longest one, and the padded places "
            "are computed and thrown away. Grouping examples of similar length cuts the padding "
            "fraction, so a step does less wasted work. Compare the padding fraction of the first two "
            "variants and the seconds per step of the first and the third."
        ),
        big_run=(
            "The big sft runs tokenize once as well, so there is nothing to save there. What you can "
            "tune is the batch size and the max sequence length: shorter examples and less padding mean "
            "faster steps. Cutting the max sequence length to the longest answer you need saves time "
            "on every step."
        ),
        check="Why does re-tokenizing add little time per step, while padding can waste much more?",
    ),
)
