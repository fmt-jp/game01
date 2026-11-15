"""おえかきロジック: the clues are solved from outside the game, the answer is
shown to be the only one, and then it is filled in through real taps.

picross_solver.py works from the clue numbers alone and knows nothing about
the pictures the game holds, so "the clues have exactly one answer, and it is
the picture" is a claim about the game, decided elsewhere.
"""
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE, check, note, head, finish
import picross_solver

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(f"{BASE}/picross/index.html")
    page.wait_for_timeout(500)

    total = page.evaluate("() => window.__picross().puzzles")
    head(f"[1] all {total} puzzles, from the clues alone")

    ambiguous, mismatched, unfinished = [], [], []
    for n in range(total):
        state = page.evaluate("() => window.__picross()")

        # the clues the game shows must be the clues the picture implies
        want_rows, want_cols, picture = picross_solver.bitmap_to_clues(state["bitmap"])
        if [list(c) for c in want_rows] != state["clues"]["rows"] or \
           [list(c) for c in want_cols] != state["clues"]["cols"]:
            mismatched.append(f"puzzle {n + 1}: the numbers do not describe the picture")

        answers = picross_solver.solve(state["clues"]["rows"], state["clues"]["cols"], max_solutions=2)
        if len(answers) != 1:
            ambiguous.append(f"puzzle {n + 1}: {len(answers)} ways to read it")
        elif [list(r) for r in answers[0]] != picture:
            mismatched.append(f"puzzle {n + 1}: the one answer is not the picture")

        # fill it in the way a player would
        for r, row in enumerate(picture):
            for c, on in enumerate(row):
                if on:
                    page.click(f'.cell[data-row="{r}"][data-col="{c}"]')
                    page.wait_for_timeout(3)
        page.wait_for_timeout(180)
        done = page.evaluate("() => window.__picross()")
        if not done["solved"] or page.get_attribute("#overlay", "hidden") is not None:
            unfinished.append(f"puzzle {n + 1}: filled in, and the game did not call it done")
        if n == 0:
            page.screenshot(path=f"{SHOTS}/picross_solved_1.png")
        if n < total - 1:
            page.click("#overlay-btn")
            page.wait_for_timeout(250)

    check("every puzzle's numbers have exactly one reading", not ambiguous, "; ".join(ambiguous))
    check("and that reading is the picture the game is hiding",
          not mismatched, "; ".join(mismatched[:3]))
    check("filling it in by tapping finishes the puzzle",
          not unfinished, "; ".join(unfinished[:3]))
    sizes = page.evaluate("() => window.__picross()")
    note(f"puzzles run from 5x5 up to {sizes['rows']}x{sizes['cols']}")

    head("[2] the two ways of tapping")
    page.reload()
    page.wait_for_timeout(500)
    fresh = page.evaluate("() => window.__picross()")
    empty = page.evaluate("() => window.__picross().state.flat().filter((v) => v).length")
    check("a fresh puzzle starts blank", empty == 0, str(empty))

    page.click('.cell[data-row="0"][data-col="0"]')
    page.wait_for_timeout(120)
    filled = page.evaluate("() => window.__picross().state[0][0]")
    check("a tap fills a square", bool(filled), repr(filled))
    page.click('.cell[data-row="0"][data-col="0"]')
    page.wait_for_timeout(120)
    check("and tapping it again empties it",
          not page.evaluate("() => window.__picross().state[0][0]"))

    marks = page.query_selector_all(".mode-btn")
    if len(marks) >= 2:
        marks[1].click()
        page.wait_for_timeout(120)
        check("the other mode is picked up",
              page.evaluate("() => window.__picross().mode") != fresh["mode"],
              page.evaluate("() => window.__picross().mode"))
        page.click('.cell[data-row="0"][data-col="1"]')
        page.wait_for_timeout(120)
        marked = page.evaluate("() => window.__picross().state[0][1]")
        check("and in it a tap marks rather than fills",
              marked and marked != filled, repr(marked))
        marks[0].click()
        page.wait_for_timeout(120)

    page.click("#reset-btn")
    page.wait_for_timeout(200)
    check("やりなおし wipes the board",
          page.evaluate("() => window.__picross().state.flat().filter((v) => v).length") == 0)

    check("no page errors", not errors, str(errors))
    browser.close()

finish("PICROSS CHECKS")
