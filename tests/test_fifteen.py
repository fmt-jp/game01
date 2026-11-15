"""15パズル: every shuffle is checked to be solvable from the outside, and one
of them is actually solved through real taps.

Whether a scramble can be solved at all is decided here by counting
inversions -- a fact about the arrangement, worked out without asking the
game -- and the route through it comes from astar15.py.
"""
import time
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE, check, note, head, finish
from astar15 import solve, GOAL


def solvable(tiles):
    """A 4x4 sliding puzzle can be solved iff the inversions and the blank's
    row from the bottom have different parity."""
    order = [v for v in tiles if v]
    inversions = sum(1 for i in range(len(order)) for j in range(i + 1, len(order))
                     if order[i] > order[j])
    blank_row_from_bottom = 4 - (tiles.index(0) // 4)
    return (inversions % 2) != (blank_row_from_bottom % 2)


def adjacent(a, b):
    return abs(a // 4 - b // 4) + abs(a % 4 - b % 4) == 1


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/fifteen/index.html")
    page.wait_for_timeout(400)

    def state():
        return page.evaluate("() => window.__fifteen()")

    head("[1] the shuffles")
    unsolvable, too_easy = [], []
    scrambles = []
    for n in range(24):
        page.click("#shuffle-btn")
        page.wait_for_timeout(90)
        tiles = state()["tiles"]
        scrambles.append(tuple(tiles))
        if sorted(tiles) != list(range(16)):
            unsolvable.append(f"shuffle {n}: not a set of 1-15 and a space: {tiles}")
        elif not solvable(tiles):
            unsolvable.append(f"shuffle {n}: cannot be solved: {tiles}")
        wrong_place = sum(1 for i, v in enumerate(tiles) if v and v != i + 1)
        if wrong_place < 8:
            too_easy.append(f"shuffle {n}: only {wrong_place} tiles out of place")
    check("all 24 shuffles can be solved, by the parity rule",
          not unsolvable, "; ".join(unsolvable[:2]))
    check("and none of them is nearly solved already", not too_easy, "; ".join(too_easy[:2]))
    check("the shuffles are not all the same", len(set(scrambles)) == len(scrambles),
          f"{len(set(scrambles))} different out of {len(scrambles)}")
    check("a fresh shuffle counts no moves", state()["moves"] == 0, str(state()["moves"]))

    head("[2] what a tap does")
    now = state()
    blank = now["blank"]
    neighbour = next(i for i in range(16) if adjacent(i, blank))
    far = next(i for i in range(16) if i != blank and not adjacent(i, blank))
    value = now["tiles"][neighbour]
    page.click(f'.tile[data-value="{value}"]')
    page.wait_for_timeout(150)
    after = state()
    check("tapping a tile beside the space slides it in",
          after["tiles"][blank] == value and after["blank"] == neighbour,
          f'{now["tiles"]} -> {after["tiles"]}')
    check("and that counts as one move", after["moves"] == 1, str(after["moves"]))

    far_value = after["tiles"][far]
    if far_value:
        before = state()
        page.click(f'.tile[data-value="{far_value}"]')
        page.wait_for_timeout(150)
        check("tapping one nowhere near it does nothing",
              state()["tiles"] == before["tiles"] and state()["moves"] == before["moves"])

    head("[3] solving one all the way, by tapping")
    solved_it = None
    for attempt in range(3):
        page.click("#shuffle-btn")
        page.wait_for_timeout(150)
        tiles = state()["tiles"]
        t0 = time.time()
        # A heavier weight gives a longer route for far fewer nodes, which is
        # the right trade when all that is wanted is a route that works.
        path = solve(tuple(tiles), weight=2.0)
        took = time.time() - t0
        if path is None:
            note(f"attempt {attempt + 1}: no route found in time")
            continue
        note(f"{len(path)} moves found in {took:.1f}s")
        # Wait for each tile to finish sliding before aiming at the next one.
        # Clicking on a fixed rhythm drops a move now and then, and a dropped
        # move leaves the puzzle one step short with nothing to say why.
        missed = []
        for n, position in enumerate(path):
            was = state()
            value = was["tiles"][position]
            page.click(f'.tile[data-value="{value}"]')
            for _ in range(20):
                page.wait_for_timeout(15)
                if state()["moves"] == was["moves"] + 1:
                    break
            else:
                missed.append(f"move {n} ({value}) never took")
                break
        page.wait_for_timeout(250)
        check("every tap in the route registered", not missed, "; ".join(missed))
        solved_it = state()
        break

    check("a route was found and played", solved_it is not None)
    if solved_it:
        check("the tiles end up in order", solved_it["solved"], str(solved_it["tiles"]))
        check("and the game says so",
              page.get_attribute("#overlay", "hidden") is None
              and page.inner_text("#overlay-message").strip() != "")
        check("the move counter matches the route taken",
              solved_it["moves"] == len(path), f'{solved_it["moves"]} vs {len(path)}')
        note(f'{page.inner_text("#overlay-sub")}')
        page.screenshot(path=f"{SHOTS}/fifteen_cleared.png")

    best = page.inner_text("#best")
    check("a best time is recorded", best.strip() not in ("", "--:--"), repr(best))
    page.reload()
    page.wait_for_timeout(400)
    check("and kept across a reload", page.inner_text("#best") == best,
          f'{page.inner_text("#best")} vs {best}')

    check("no page errors", not errors, str(errors))
    browser.close()

finish("FIFTEEN CHECKS")
