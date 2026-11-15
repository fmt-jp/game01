"""そうこばん: every level is solved from outside the game and then played
through the real buttons.

The solver in sokoban_solver.py is a plain breadth-first search over
(player, boxes) written from the rules of box pushing. If the game's idea of
a push and the solver's ever part company, the planned moves stop working and
this says so.
"""
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE, check, note, head, finish
import sokoban_solver

KEY = {"U": ".dpad-up", "D": ".dpad-down", "L": ".dpad-left", "R": ".dpad-right"}

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(f"{BASE}/sokoban/index.html")
    page.wait_for_timeout(500)

    head("[1] every level, solved outside the game and then played inside it")
    total = page.evaluate("() => window.__sokoban().levels")
    check("the game has its ten levels", total == 10, str(total))

    unsolvable, misplayed = [], []
    lengths = []
    for n in range(total):
        page.evaluate("(n) => window.__start ? window.__start(n) : null", n)
        state = page.evaluate("() => window.__sokoban()")
        if state["level"] != n:
            # no jump hook: walk forward by finishing each level in turn
            pass
        text = state["text"]
        path, seen, why = sokoban_solver.solve(text)
        if path is None:
            unsolvable.append(f"level {n + 1}: {why} after {seen} states")
            continue
        lengths.append(len(path))
        for step in path:
            page.click(KEY[step])
            page.wait_for_timeout(28)
        page.wait_for_timeout(200)
        after = page.evaluate("() => window.__sokoban()")
        if not after["won"]:
            misplayed.append(f"level {n + 1}: the solver's {len(path)} moves did not finish it")
        elif page.get_attribute("#overlay", "hidden") is not None:
            misplayed.append(f"level {n + 1}: finished, but said nothing about it")
        if n < total - 1:
            page.click("#overlay-btn")
            page.wait_for_timeout(250)

    check(f"all {total} levels can be solved by a search that never saw the game",
          not unsolvable, "; ".join(unsolvable))
    check("and the game agrees, move for move",
          not misplayed, "; ".join(misplayed[:3]))
    note(f"solutions run {min(lengths)}-{max(lengths)} moves, {sum(lengths)} in all")

    head("[2] the controls")
    # Level one is over in a single push, so a stray probe finishes it and the
    # overlay swallows everything after. Start again and step to level two,
    # where there is room to move about.
    page.reload()
    page.wait_for_timeout(600)
    first = page.evaluate("() => window.__sokoban()")
    for step in sokoban_solver.solve(first["text"])[0]:
        page.click(KEY[step])
        page.wait_for_timeout(60)
    page.wait_for_timeout(200)
    page.click("#overlay-btn")
    page.wait_for_timeout(300)
    start = page.evaluate("() => window.__sokoban()")
    check("we are on level two, with somewhere to walk", start["level"] == 1, str(start["level"]))
    before = start["player"]
    moved = None
    for key in (".dpad-down", ".dpad-up", ".dpad-left", ".dpad-right"):
        page.click(key)
        page.wait_for_timeout(120)
        now = page.evaluate("() => window.__sokoban()")
        if now["player"] != before:
            moved = key
            break
    check("a button moves the mover", moved is not None, "none of the four did anything")
    after_move = page.evaluate("() => window.__sokoban()")
    check("and the move counter follows", after_move["moves"] == 1, str(after_move["moves"]))

    page.click("#undo-btn")
    page.wait_for_timeout(150)
    undone = page.evaluate("() => window.__sokoban()")
    check("もどす puts the mover back where it was",
          undone["player"] == before and undone["moves"] == 0,
          f'{undone["player"]} vs {before}, moves {undone["moves"]}')

    # A swipe on the board does the same as a button. Which way is free
    # depends on the level, so try each in turn rather than assume.
    box = page.locator("#board").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    swiped = None
    for dx, dy, way in ((0, 60, "down"), (0, -60, "up"), (-60, 0, "left"), (60, 0, "right")):
        page.evaluate("""([cx, cy, dx, dy]) => {
          const board = document.getElementById('board');
          const from = new Touch({ identifier: 1, target: board, clientX: cx, clientY: cy });
          const to = new Touch({ identifier: 1, target: board, clientX: cx + dx, clientY: cy + dy });
          board.dispatchEvent(new TouchEvent('touchstart', { touches: [from], changedTouches: [from], bubbles: true }));
          board.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [to], bubbles: true }));
        }""", [cx, cy, dx, dy])
        page.wait_for_timeout(180)
        now = page.evaluate("() => window.__sokoban()")
        if now["moves"] >= 1:
            swiped = way
            break
    check("a swipe counts as a move too", swiped is not None,
          "none of the four directions registered")
    note(f"the swipe that took was {swiped}")

    page.click("#reset-btn")
    page.wait_for_timeout(200)
    reset = page.evaluate("() => window.__sokoban()")
    check("やりなおし sets the move counter back", reset["moves"] == 0, str(reset["moves"]))
    check("and puts the mover and the boxes back where the level began",
          reset["player"] == start["player"] and sorted(reset["boxes"]) == sorted(start["boxes"]),
          f'mover {reset["player"]} vs {start["player"]}, '
          f'boxes {sorted(reset["boxes"])} vs {sorted(start["boxes"])}')

    page.screenshot(path=f"{SHOTS}/sokoban_l1.png")
    check("no page errors", not errors, str(errors))
    browser.close()

finish("SOKOBAN CHECKS")
