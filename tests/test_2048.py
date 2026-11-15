"""2048: the game's own sliding is held to an independent implementation of
the rules, and then a bot plays until it gets to 2048.

bot2048.py knows the rules of 2048 and nothing about this game's code. Phase
one uses it as a judge -- every move the game makes must land where the rules
say it should, give or take the one new tile -- and phase two uses it as a
player, to show the title is reachable rather than merely hoped for.
"""
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE, check, note, head, finish
import bot2048

KEYS = {"left": "ArrowLeft", "right": "ArrowRight", "up": "ArrowUp", "down": "ArrowDown"}


def as_tuple(grid):
    return tuple(tuple(row) for row in grid)


def spawned(before, after):
    """What appeared between two boards, if it was one new tile."""
    new = [(r, c, after[r][c]) for r in range(4) for c in range(4)
           if before[r][c] != after[r][c]]
    return new


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/2048/index.html")
    page.wait_for_timeout(400)

    def state():
        return page.evaluate("() => window.__2048()")

    head("[1] does it slide the way the rules say?")
    page.click("#new-game-btn")
    page.wait_for_timeout(200)
    start = state()
    check("a new game starts with two tiles",
          sum(1 for row in start["grid"] for v in row if v) == 2, str(start["grid"]))
    check("and a score of nothing", start["score"] == 0, str(start["score"]))

    wrong, checked, scored_wrong = [], 0, []
    grid = as_tuple(start["grid"])
    score = start["score"]
    for _ in range(140):
        move = bot2048.choose(grid)
        if move is None:
            break
        want, changed, gain = bot2048.slide(grid, move)
        page.keyboard.press(KEYS[move])
        page.wait_for_timeout(55)
        now = state()
        got = as_tuple(now["grid"])
        checked += 1
        new = spawned(want, got)
        if len(new) != 1 or new[0][2] not in (2, 4) or want[new[0][0]][new[0][1]] != 0:
            wrong.append(f"after {move}: expected {want} plus one tile, got {got}")
            break
        if now["score"] != score + gain:
            scored_wrong.append(f"after {move}: {score} + {gain} should be {score + gain}, got {now['score']}")
        grid, score = got, now["score"]
        if now["over"]:
            break

    check(f"{checked} moves all landed where the rules put them", not wrong, "; ".join(wrong[:1]))
    check("and every merge scored what it should", not scored_wrong, "; ".join(scored_wrong[:2]))
    note(f"best tile after {checked} moves: {max(v for row in grid for v in row)}, score {score}")

    head("[2] a bot plays it to 2048")
    reached, tries, moves_taken = None, 0, 0
    for attempt in range(3):
        tries += 1
        page.click("#new-game-btn")
        page.wait_for_timeout(200)
        grid = as_tuple(state()["grid"])
        moves = 0
        while moves < 3000:
            move = bot2048.choose(grid)
            if move is None:
                break
            page.keyboard.press(KEYS[move])
            page.wait_for_timeout(22)
            now = state()
            grid = as_tuple(now["grid"])
            moves += 1
            if max(v for row in grid for v in row) >= 2048:
                reached = now
                break
            if now["over"]:
                break
        moves_taken = moves
        if reached:
            break
        note(f"attempt {attempt + 1} stopped at {max(v for row in grid for v in row)} after {moves} moves")

    check(f"2048 is reachable, and the bot got there in {tries} attempt(s)",
          reached is not None, "the bot never made it")
    if reached:
        check("and the game knows it has been won", reached["won"], str(reached["won"]))
        note(f"{moves_taken} moves, score {reached['score']}")
        page.screenshot(path=f"{SHOTS}/won_2048.png")

    head("[3] the controls and what is kept")
    best = state()["best"]
    check("the best score is at least this game's", best >= reached["score"] if reached else True,
          f"best {best}")
    page.click("#new-game-btn")
    page.wait_for_timeout(250)
    fresh = state()
    check("新しいゲーム clears the board",
          fresh["score"] == 0 and sum(1 for row in fresh["grid"] for v in row if v) == 2,
          str(fresh["grid"]))
    check("and keeps the best", fresh["best"] == best, f'{fresh["best"]} vs {best}')

    # a swipe does what an arrow key does
    box = page.locator("#board").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    moved = False
    for dx, dy in ((0, 90), (90, 0), (0, -90), (-90, 0)):
        before = as_tuple(state()["grid"])
        page.evaluate("""([cx, cy, dx, dy]) => {
          const board = document.getElementById('board');
          const from = new Touch({ identifier: 1, target: board, clientX: cx, clientY: cy });
          const to = new Touch({ identifier: 1, target: board, clientX: cx + dx, clientY: cy + dy });
          board.dispatchEvent(new TouchEvent('touchstart', { touches: [from], changedTouches: [from], bubbles: true }));
          board.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [to], bubbles: true }));
        }""", [cx, cy, dx, dy])
        page.wait_for_timeout(200)
        if as_tuple(state()["grid"]) != before:
            moved = True
            break
    check("a swipe moves the tiles too", moved)

    page.reload()
    page.wait_for_timeout(400)
    check("the best survives a reload", state()["best"] == best, str(state()["best"]))

    check("no page errors", not errors, str(errors))
    browser.close()

finish("2048 CHECKS")
