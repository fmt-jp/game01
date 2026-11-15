"""Drive the real board with pointer events and confirm win detection.

Math.random is replaced with a resettable seeded PRNG before load, so the test
can regenerate the exact puzzle the game is showing (solution included) and
trace it with real drags.
"""
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE, check, note, head, finish

SEED_SCRIPT = """
(() => {
  let state = 123456789;
  window.__seed = (n) => { state = n >>> 0; };
  window.__seed(20260920);
  Math.random = () => {
    // mulberry32
    state |= 0; state = (state + 0x6D2B79F5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
})();
"""


def cell_xy(box, size, cell):
    cs = box["width"] / size
    r, c = divmod(cell, size)
    return box["x"] + c * cs + cs / 2, box["y"] + r * cs + cs / 2


def solve_board(page, seed, size, colors):
    """Reset RNG to the same seed the game used, regenerate identical puzzle."""
    return page.evaluate(
        "([seed, size, colors]) => { window.__seed(seed); return FlowPuzzle.generate(size, colors); }",
        [seed, size, colors],
    )


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(f"{m.type}:{m.text}") if m.type == "error" else None)

    page.add_init_script(SEED_SCRIPT)
    page.goto(f"{BASE}/flow/index.html")
    page.wait_for_timeout(500)

    head("[1] the board it opens with")
    pairs, fill = page.inner_text("#pairs-status"), page.inner_text("#fill-status")
    check("nothing is joined up yet", pairs.startswith("0/"), pairs)
    check("and nothing is filled in", fill.startswith("0/"), fill)
    page.screenshot(path=f"{SHOTS}/flow_start.png")

    # The page's Math.random was replaced before it loaded, so asking for the
    # same seed again rebuilds the very puzzle on screen, answer and all.
    puzzle = solve_board(page, 20260920, 5, 4)
    check("the puzzle on screen can be rebuilt from its seed",
          puzzle and len(puzzle["endpoints"]) == 4, str(puzzle and puzzle["endpoints"]))

    box = page.query_selector("#board").bounding_box()
    size = puzzle["size"]

    def trace(cells):
        x, y = cell_xy(box, size, cells[0])
        page.mouse.move(x, y)
        page.mouse.down()
        for cell in cells[1:]:
            x, y = cell_xy(box, size, cell)
            page.mouse.move(x, y)
        page.mouse.up()
        page.wait_for_timeout(40)

    head("[2] a line that goes nowhere")
    # Drag from one colour's dot into the middle and stop: the pair is not
    # joined, and the status must not pretend otherwise.
    stray = puzzle["solution"][0]
    if len(stray) > 2:
        trace(stray[:-1])
        check("a line stopped short joins nothing",
              page.inner_text("#pairs-status").startswith("0/"),
              page.inner_text("#pairs-status"))
        trace([stray[0]])          # tap the dot to clear that line again
        page.wait_for_timeout(60)

    head("[3] tracing every colour, with real drags")
    for seg in puzzle["solution"]:
        trace(seg)

    page.wait_for_timeout(250)
    pairs, fill = page.inner_text("#pairs-status"), page.inner_text("#fill-status")
    joined, of = [int(n) for n in pairs.split("/")]
    done, cells = [int(n) for n in fill.split("/")]
    check("every pair is joined", joined == of == len(puzzle["endpoints"]), pairs)
    check("and every square is used", done == cells == size * size, fill)
    check("the game calls it finished",
          page.get_attribute("#overlay", "hidden") is None
          and page.inner_text("#overlay-message").strip() != "")
    check("and counts a puzzle cleared", page.inner_text("#cleared").strip() == "1",
          page.inner_text("#cleared"))
    note(f'{page.inner_text("#overlay-message")} | {page.inner_text("#overlay-sub")}')
    page.screenshot(path=f"{SHOTS}/flow_cleared.png")

    head("[4] on to the next one")
    was = page.inner_text("#level")
    page.click("#overlay-btn")
    page.wait_for_timeout(500)
    check("the level goes up", page.inner_text("#level") != was,
          f'{was} -> {page.inner_text("#level")}')
    check("and the new board starts empty",
          page.inner_text("#pairs-status").startswith("0/")
          and page.inner_text("#fill-status").startswith("0/"),
          f'{page.inner_text("#pairs-status")} {page.inner_text("#fill-status")}')
    page.screenshot(path=f"{SHOTS}/flow_level2.png")

    check("no page errors", not errors, str(errors))
    browser.close()

finish("FLOW PLAY CHECKS")
