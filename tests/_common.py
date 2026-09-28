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
