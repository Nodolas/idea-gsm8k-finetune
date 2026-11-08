/**
 * Plain-language explanations of the run settings (AC4.6.8) and of what every fine-tune already
 * does on the NVIDIA GPU (AC4.6.9). Static text, keyed by the dial names of `GET /dials`; the
 * dials panel shows it behind an "Explain <label>" button. The facts follow `train_sft`
 * (src/gsm8k/training/sft.py): bf16, fused AdamW, gradient checkpointing, LoRA, a linear schedule
 * with warm-up, one example batch per step with no gradient accumulation.
 */

export interface DialEffect {
  /** "Higher", "Lower", or the name of a choice. */
  label: string;
  text: string;
}

export interface DialInfo {
  /** What the setting does, in one or two sentences. */
  what: string;
  /** What raising or lowering it does (numbers), or what each choice does (selects). */
  effects: DialEffect[];
  /** A hint for this project's 8 GB GPU and the GSM8K runs. */
  tip: string;
}

const higher = (text: string): DialEffect => ({ label: "Higher", text });
const lower = (text: string): DialEffect => ({ label: "Lower", text });

/** Keyed by dial name (`model`, `learning_rate`, ...) plus `method` for the method choice. */
export const DIAL_INFO: Record<string, DialInfo> = {
  method: {
    what:
      "Chooses what the run does. SFT (supervised fine-tuning) trains the model on GSM8K worked " +
      "solutions with LoRA and then scores it on the dev split. Evaluate on dev only scores the " +
      "untouched base model, which gives the baseline every fine-tune is compared against.",
    effects: [
      {
        label: "SFT",
        text: "Changes the model, so it uses every setting below. It takes minutes to hours.",
      },
      {
        label: "Evaluate on dev",
        text: "Never changes the model. Only the model and the random seed matter; the other settings are ignored.",
      },
    ],
    tip: "Run Evaluate on dev once per model first: a fine-tune only means something against its own baseline.",
  },
  model: {
    what:
      "The pretrained model that is fine-tuned or scored. Both are Qwen3 base models: they have " +
      "never been taught to chat or to follow instructions.",
    effects: [
      {
        label: "Qwen3-0.6B-Base",
        text: "0.6 billion weights. Fast and light on memory; its measured baseline on dev is about 60%.",
      },
      {
        label: "Qwen3-1.7B-Base",
        text: "1.7 billion weights. Starts much stronger (about 79% on dev here), but each step is slower and needs more GPU memory.",
      },
    ],
    tip: "On this 8 GB GPU use batch size 2 or less with the 1.7B model, or the run can end with GPU out of memory.",
  },
  learning_rate: {
    what:
      "How big a step the optimiser takes each time it updates the LoRA weights. After the warm-up " +
      "it starts at this value and falls in a straight line to zero at the last step.",
    effects: [
      higher(
        "Learns faster, but too high makes the loss jump around or climb, and the model can forget what it knew. Spikes also show in the gradient norm.",
      ),
      lower(
        "Safer and smoother, but the model may barely move from where it started in one epoch.",
      ),
    ],
    tip: "LoRA likes a larger rate than full fine-tuning; 2e-4 is the default. If the loss spikes in the first minutes, stop and try a lower rate.",
  },
  epochs: {
    what: "How many times the run goes through the whole set of training problems.",
    effects: [
      higher(
        "More learning from the same problems, but a longer run (time grows with the epochs) and a growing risk of memorising the training answers.",
      ),
      lower(
        "A shorter run with fewer weight updates and less risk of overfitting. One epoch is the default.",
      ),
    ],
    tip: "If the dev accuracy peaks and then falls while the loss keeps dropping, the model is overfitting: use fewer epochs.",
  },
  lora_rank: {
    what:
      "LoRA trains two small matrices next to each adapted layer instead of changing the whole " +
      "model. The rank is how wide those matrices are, so it sets how many weights can change.",
    effects: [
      higher(
        "More capacity to learn, but more trainable weights, more memory and a slightly slower step.",
      ),
      lower(
        "A smaller adapter that is lighter and faster, but it may be too small to hold what the task needs.",
      ),
    ],
    tip: "16 is a sound default for GSM8K. The rank usually moves the score less than the learning rate does.",
  },
  lora_alpha: {
    what:
      "A multiplier on what the adapter adds to the model: the adapter's output is scaled by alpha " +
      "divided by the rank.",
    effects: [
      higher("A stronger push from the adapter; it acts a little like a bigger learning rate."),
      lower("A gentler adapter, so learning is slower."),
    ],
    tip: "The default 32 with rank 16 gives a scale of 2. If you change the rank, keep alpha at twice the rank to keep the same scale.",
  },
  max_seq_len: {
    what:
      "The most tokens (word pieces) one training example may use, question and answer together. " +
      "A longer example is cut off at this length.",
    effects: [
      higher(
        "Keeps long solutions whole, but the memory a step needs grows with the longest example in the batch.",
      ),
      lower(
        "Saves memory, but cuts the end of long solutions, including the final #### answer line.",
      ),
    ],
    tip: "Most GSM8K solutions are far shorter than 512 tokens, so raising this rarely helps. Lower it only to save GPU memory.",
  },
  train_examples: {
    what:
      "How many training problems the run learns from: the first N of the training split by " +
      "index, or all of them (6,973; 500 more are held out as the dev split and never trained on).",
    effects: [
      higher("More to learn from, but more steps and a longer run."),
      lower("A faster run for a quick experiment, with less to learn from."),
    ],
    tip: "Use 50 to 500 to check that a setup works, then all for a run that counts.",
  },
  batch_size: {
    what: "How many training examples go through the model together before each weight update.",
    effects: [
      higher(
        "Smoother, more stable updates and fewer steps, but memory use grows; too high ends the run with GPU out of memory.",
      ),
      lower("Less memory, but more and noisier steps, so the run takes longer."),
    ],
    tip: "The 1.7B model needs 2 or less on this 8 GB GPU. Steps in a run = examples × epochs ÷ batch size.",
  },
  warmup_ratio: {
    what:
      "The share of the steps at the start in which the learning rate climbs from zero to its " +
      "full value, so the first updates do not shock the model.",
    effects: [
      higher("A longer, gentler start, and less time at the full learning rate."),
      lower("Reaches the full rate sooner. 0 means no warm-up."),
    ],
    tip: "The default 0.03 is 3% of the steps. The Live numbers panel says warming up while it happens.",
  },
  seed: {
    what:
      "A number that fixes the random choices of a run: the order the training examples are shown " +
      "in and the starting values of the adapter.",
    effects: [
      {
        label: "Same seed",
        text: "The same settings give almost the same run (GPU maths is not perfectly repeatable).",
      },
      {
        label: "Different seed",
        text: "A different order and start, which shows how much a score moves from luck alone.",
      },
    ],
    tip: "A difference of a few points can come from the seed alone: run a second seed before believing a small gain.",
  },
  answer_format: {
    what: "What the model is taught to write after the question.",
    effects: [
      {
        label: "step-by-step",
        text: "The full worked solution, ending with the #### answer line. This is the reference setup; it teaches the model to reason before it answers.",
      },
      {
        label: "terse",
        text: "Only the #### answer line. Runs are shorter, but the model is trained to answer without working, which is expected to lower the score on multi-step problems.",
      },
    ],
    tip: "Keep step-by-step unless you are testing exactly that question.",
  },
};

/** What every fine-tune on the GPU already does (not dials: `train_sft` fixes them). */
export const GPU_NOTES: ReadonlyArray<{ name: string; why: string }> = [
  {
    name: "bf16 mixed precision",
    why: "The training maths runs in bfloat16 on the GPU's tensor cores: about half the memory of 32-bit numbers and faster steps, with the range of 32-bit so it does not overflow like fp16.",
  },
  {
    name: "Fused AdamW optimiser",
    why: "The AdamW weight update runs as one fused CUDA kernel over all weights instead of many small ones, which cuts the time of each step.",
  },
  {
    name: "Gradient checkpointing",
    why: "The activations are recomputed in the backward pass instead of kept: each step is somewhat slower, but much less GPU memory is used, which is what lets the 1.7B model fit in 8 GB.",
  },
  {
    name: "LoRA adapters",
    why: "Only the small adapter matrices get gradients and optimiser state, so the optimiser needs a tiny share of the memory a full fine-tune would.",
  },
  {
    name: "Linear learning-rate decay after warm-up",
    why: "The learning rate climbs during the warm-up and then falls in a straight line to zero, so the last updates are small and settle the weights.",
  },
];
