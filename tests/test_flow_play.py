"""Drive the real board with pointer events and confirm win detection.

Math.random is replaced with a resettable seeded PRNG before load, so the test
can regenerate the exact puzzle the game is showing (solution included) and
trace it with real drags.
"""
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

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
    page.goto("http://localhost:8390/flow/index.html")
    page.wait_for_timeout(500)

    print("initial status:", page.inner_text("#pairs-status"), page.inner_text("#fill-status"))
    page.screenshot(path=f"{SHOTS}/flow_start.png")

    puzzle = solve_board(page, 20260920, 5, 4)
    print("puzzle endpoints:", puzzle["endpoints"])

    box = page.query_selector("#board").bounding_box()
    size = puzzle["size"]

    # Trace every colour's path with real pointer drags.
    for seg in puzzle["solution"]:
        x, y = cell_xy(box, size, seg[0])
        page.mouse.move(x, y)
        page.mouse.down()
        for cell in seg[1:]:
            x, y = cell_xy(box, size, cell)
            page.mouse.move(x, y)
        page.mouse.up()
        page.wait_for_timeout(40)

    page.wait_for_timeout(200)
    print("after solve:", page.inner_text("#pairs-status"), page.inner_text("#fill-status"))
    overlay_hidden = page.get_attribute("#overlay", "hidden")
    print("cleared overlay shown:", overlay_hidden is None)
    if overlay_hidden is None:
        print("message:", page.inner_text("#overlay-message"), "|", page.inner_text("#overlay-sub"))
    print("cleared counter:", page.inner_text("#cleared"))
    page.screenshot(path=f"{SHOTS}/flow_cleared.png")

    # advance to next puzzle
    page.click("#overlay-btn")
    page.wait_for_timeout(400)
    print("level after next:", page.inner_text("#level"),
          "status:", page.inner_text("#pairs-status"), page.inner_text("#fill-status"))
    page.screenshot(path=f"{SHOTS}/flow_level2.png")

    print("errors:", errors)
    browser.close()
