# Checks

Run everything:

    tests/run.sh

Run one game's checks:

    tests/run.sh maze3d

`run.sh` serves the repository on :8390 and runs each `test_*.py` against it.
Settings come from the environment, so a checkout elsewhere still works:

    CHROMIUM=/usr/bin/chromium tests/run.sh

`GAME_SHOTS` moves the screenshots the checks take (default `tests/_shots/`,
which is not in the repository).

## What these are

Not unit tests. Each one drives the real page in a real browser and checks the
result from outside it — see the *Checking the work* section of `CLAUDE.md` for
why they are written that way.

Some files are shared machinery rather than checks: `sokoban_solver.py`,
`picross_solver.py`, `astar15.py`, `tiles_rules.py` and `bridges_rules.py` are
the independent solvers and rule books the game checks compare against, `autopilot.js` steers きょだい迷路 through its own key handlers,
and `build_words.py` regenerates ことばの輪's word list (it needs `janome` and
`wordfreq`, which the checks themselves do not).

## Self-checking, versus printing for a person to read

**Every check decides for itself and exits non-zero when something is wrong**, so
`run.sh` catches a regression anywhere:

- `test_2048.py`
- `test_ataxx.py`
- `test_ataxx_ui.py`
- `test_barcode.py`
- `test_bridges.py`
- `test_bridges_ui.py`
- `test_fifteen.py`
- `test_flow.py`
- `test_flow_play.py`
- `test_gems.py`
- `test_hub.py`
- `test_maze.py`
- `test_maze3d.py`
- `test_maze3d_perspective.py`
- `test_maze3d_ui.py`
- `test_maze_items.py`
- `test_maze_play.py`
- `test_maze_ui.py`
- `test_picross.py`
- `test_pwa.py`
- `test_rhythm.py`
- `test_rhythm_ui.py`
- `test_sokoban.py`
- `test_stack.py`
- `test_tiles.py`
- `test_tiles_ui.py`
- `test_words.py`
- `test_words_ui.py`

Several of these began as scripts that printed what they saw for a person to
read and always exited 0; they were converted one game at a time. The shared
`check` / `note` / `head` / `finish` helpers in `_common.py` are what a new
check should use.

Where a check measures something noisy -- a clear rate over fifteen runs, say
-- it asserts on the steadier figure behind it (fuel left at the exit rather
than how often a run happened to be won) and prints the noisy one. A check
that fails one run in ten is worse than no check at all.
