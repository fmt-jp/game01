from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto("http://localhost:8390/stack/index.html")
    page.wait_for_timeout(400)
    page.screenshot(path=f"{SHOTS}/stack_initial.png")

    stage = page.query_selector(".stage-wrap")
    box = stage.bounding_box()
    cx = box["x"] + box["width"] / 2
    cy = box["y"] + box["height"] / 2

    def tap():
        page.mouse.click(cx, cy)

    # first tap starts the game
    tap()
    page.wait_for_timeout(300)

    results = []
    for i in range(40):
        page.wait_for_timeout(250)
        tap()
        page.wait_for_timeout(50)
        score = page.inner_text("#score")
        overlay_hidden = page.get_attribute("#overlay", "hidden")
        results.append((i, score, overlay_hidden))
        if overlay_hidden is None:
            break

    print("errors:", errors)
    print("last results:", results[-5:])
    print("final score:", page.inner_text("#score"), "best:", page.inner_text("#best"))
    page.screenshot(path=f"{SHOTS}/stack_playing.png")

    overlay_hidden = page.get_attribute("#overlay", "hidden")
    print("game over shown:", overlay_hidden is None)
    if overlay_hidden is None:
        page.screenshot(path=f"{SHOTS}/stack_gameover.png")
        msg = page.inner_text("#overlay-message")
        print("overlay message:", msg)
        # restart
        page.click("#overlay-btn")
        page.wait_for_timeout(300)
        print("score after restart:", page.inner_text("#score"))

    browser.close()
