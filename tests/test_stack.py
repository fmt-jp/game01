"""つみあげ: a tower is actually built, by timing the taps against where the
block really is.

The old version of this tapped on a fixed rhythm, lost on the second block
every time, and printed the result for a person to shrug at. Aiming the taps
is what makes "the game can be played" something a check can say.
"""
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE, check, note, head, finish

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(f"{BASE}/stack/index.html")
    page.wait_for_timeout(500)

    stage = page.locator(".stage-wrap").bounding_box()
    cx = stage["x"] + stage["width"] / 2
    cy = stage["y"] + stage["height"] / 2

    def tap():
        page.mouse.click(cx, cy)

    def state():
        return page.evaluate("() => window.__stack()")

    head("[1] starting it")
    begin = state()
    check("it waits for the first tap", begin["status"] == "ready", begin["status"])
    check("and the score starts at nothing", begin["score"] == 0)
    tap()
    page.wait_for_timeout(300)
    going = state()
    check("the first tap sets it going", going["status"] == "playing", going["status"])
    check("and a block is sliding about", going["mover"] is not None)

    head("[2] playing it properly")
    # Wait until the sliding block is over the one below, then tap. Being a
    # little late only shaves the block; being wildly out ends the game.
    # Watching for the moment to arrive and then asking the browser to click
    # is always late: the round trip is longer than the window. Work out when
    # the block will be over the tower instead, wait that long, and tap then.
    FRAME = 1000 / 60
    LAG = 16          # what the click itself costs, measured against the misses
    landed, misses = 0, 0
    while landed < 18:
        now = state()
        if now["status"] != "playing":
            break
        mover, top = now["mover"], now["top"]
        if not mover or not top:
            page.wait_for_timeout(16)
            continue
        gap = top["x"] - mover["x"]
        if gap * mover["dir"] < 0:          # sliding away; let it turn round
            page.wait_for_timeout(60)
            misses += 1
            if misses > 60:
                break
            continue
        wait = abs(gap) / mover["speed"] * FRAME - LAG
        if wait > 0:
            page.wait_for_timeout(wait)
        tap()
        landed += 1
        page.wait_for_timeout(40)

    played = state()
    check("a tower of a dozen or more goes up when the taps are aimed",
          played["score"] >= 12, f'score {played["score"]} after {landed} taps')
    check("and the game is still going after all of them",
          played["status"] == "playing", played["status"])
    check("and the blocks have not worn away to nothing",
          played["mover"] is None or played["mover"]["width"] > 4,
          str(played["mover"]))
    note(f'score {played["score"]}, {played["height"]} blocks high, '
         f'narrowest block {played["mover"]["width"]:.0f}px' if played["mover"] else "")
    page.screenshot(path=f"{SHOTS}/stack_playing.png")

    head("[3] missing")
    # Tap when the block is as far from the tower as it gets: the overhang is
    # cut off, and when nothing is left the game is over.
    before_width = (state()["mover"] or {}).get("width", 0)
    ended = False
    for _ in range(400):
        now = state()
        if now["status"] != "playing":
            ended = True
            break
        mover, top = now["mover"], now["top"]
        if not mover or not top:
            page.wait_for_timeout(16)
            continue
        if abs(mover["x"] - top["x"]) > mover["width"] * 0.55:
            tap()
            page.wait_for_timeout(45)
        else:
            page.wait_for_timeout(8)

    over = state()
    check("badly aimed taps end the game", ended and over["status"] == "gameover",
          over["status"])
    check("and it says so", page.get_attribute("#overlay", "hidden") is None
          and page.inner_text("#overlay-message").strip() != "")
    note(f'ended on {over["score"]}, from a widest block of {before_width:.0f}px')
    page.screenshot(path=f"{SHOTS}/stack_gameover.png")

    head("[4] the best, and starting again")
    best = over["best"]
    check("the best score is at least the one just played", best >= over["score"],
          f'best {best}, just scored {over["score"]}')
    page.click("#overlay-btn")
    page.wait_for_timeout(300)
    again = state()
    check("the button starts a fresh tower", again["score"] == 0 and again["status"] in ("ready", "playing"),
          f'score {again["score"]}, {again["status"]}')
    check("and the best is remembered across it", again["best"] == best,
          f'{again["best"]} vs {best}')
    page.reload()
    page.wait_for_timeout(500)
    check("and across a reload", state()["best"] == best, str(state()["best"]))

    check("no page errors", not errors, str(errors))
    browser.close()

finish("STACK CHECKS")
