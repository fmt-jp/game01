"""Settings the checks share.

Both can be overridden from the environment, so a checkout on another machine
does not need the paths this was written on:

    CHROMIUM=/usr/bin/chromium GAME_SHOTS=/tmp/shots python3 tests/test_hub.py
"""
import os
import pathlib

# Where Playwright finds a browser. The default is the one preinstalled in the
# Claude Code container.
CHROMIUM = os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium")

# Screenshots the checks take along the way. Kept out of the repository.
SHOTS = os.environ.get("GAME_SHOTS", str(pathlib.Path(__file__).parent / "_shots"))
pathlib.Path(SHOTS).mkdir(parents=True, exist_ok=True)

# Every check talks to this, which run.sh serves from the repository root.
BASE = os.environ.get("GAME_URL", "http://localhost:8390")


# ---------------------------------------------------------------------------
# Saying whether something passed.
#
# Most of these checks began as scripts that printed what they saw for a
# person to read, which meant run.sh could not tell a regression from a
# working game. Everything that decides for itself now goes through check(),
# and finish() at the end of a file makes the exit code say so.
import sys as _sys

_failures = []


def check(label, cond, detail=""):
    """Assert something, and say so either way."""
    print(("  ok   " if cond else "  FAIL ") + label + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        _failures.append(label)
    return bool(cond)


def note(text):
    """Something worth printing that nothing hangs on."""
    print("       " + str(text))


def head(text):
    print("\n" + str(text))


def finish(title="CHECKS"):
    print("\n" + (f"ALL {title} PASSED" if not _failures else f"{len(_failures)} FAILURES"))
    for f in _failures:
        print("  -", f)
    _sys.exit(1 if _failures else 0)
