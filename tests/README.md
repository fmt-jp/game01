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

Two of them are shared machinery rather than checks: `sokoban_solver.py`,
`picross_solver.py` and `astar15.py` are the independent solvers the game checks
compare against, and `autopilot.js` steers きょだい迷路 through its own key
handlers.

## Self-checking, versus printing for a person to read

**These decide for themselves and exit non-zero when something is wrong**, so
`run.sh` catches a regression in them:

- `test_barcode.py`
- `test_maze3d.py`
- `test_maze_play.py`

**These print their findings and always exit 0.** They were written to answer a
question during development, and a person read the output. `run.sh` will not
catch a regression in them — read what they print:

- `test_2048.py`
- `test_fifteen.py`
- `test_flow.py`
- `test_flow_play.py`
- `test_gems.py`
- `test_hub.py`
- `test_maze.py`
- `test_maze3d_perspective.py`
- `test_maze3d_ui.py`
- `test_maze_items.py`
- `test_maze_ui.py`
- `test_picross.py`
- `test_pwa.py`
- `test_sokoban.py`
- `test_stack.py`

Converting the second group into assertions is worth doing; until then, do not
read a green `run.sh` as more than "nothing crashed" for those games.
