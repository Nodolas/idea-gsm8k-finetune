"""The fine-tuning lab (u11-finetune-lab, contract C8): twelve short CPU experiments on a very small model.

This package imports no torch, transformers or peft at module level and sets no environment variable on
import: ``gsm8k`` imports every command module when it builds its parser, so GPU runs import it too.
"""
