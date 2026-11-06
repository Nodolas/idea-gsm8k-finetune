"""``python -m gsm8k``: the same command line as the ``gsm8k`` console script (contract C5)."""

import sys

from gsm8k import cli  # importing the gsm8k package first sets the in-folder caches (BR1.1)

if __name__ == "__main__":
    sys.exit(cli.main())
