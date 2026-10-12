"""Fixed CLI diagnostics: argparse must not repeat private argument values."""

import argparse
import sys


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        print("Invalid command arguments. See --help for usage.", file=sys.stderr)
        raise SystemExit(2) from None
