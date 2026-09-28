from playwright.sync_api import sync_playwright
from _common import CHROMIUM
import random

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto("http://localhost:8390/gems/index.html")
    page.wait_for_timeout(400)

    random.seed(42)
    max_score = 0
    for i in range(60):
        hidden = page.get_attribute("#overlay", "hidden")
        if hidden is None:
            print(f"game over after {i} pieces")
            break
        # randomly move left/right a few times, sometimes rotate, then drop
        moves = random.randint(0, 3)
        direction = random.choice(["#btn-left", "#btn-right"])
        for _ in range(moves):
            page.click(direction)
            page.wait_for_timeout(20)
        if random.random() < 0.5:
            page.click("#btn-rotate")
            page.wait_for_timeout(20)
        page.click("#btn-drop")
        page.wait_for_timeout(150)
        score = int(page.inner_text("#score"))
        max_score = max(max_score, score)

    print("final score:", page.inner_text("#score"), "max seen:", max_score, "best:", page.inner_text("#best"))
    print("errors:", errors)

    # test swipe controls fresh game
    page.click("#overlay-btn") if page.get_attribute("#overlay", "hidden") is None else None
    page.wait_for_timeout(200)
    board = page.query_selector("#board")
    box = board.bounding_box()
    cx, cy = box["x"]+box["width"]/2, box["y"]+box["height"]/2

    # swipe left
    page.evaluate("""([cx, cy]) => {
        const el = document.getElementById('board');
        const start = new Touch({identifier:1, target: el, clientX: cx, clientY: cy});
        const end = new Touch({identifier:1, target: el, clientX: cx-60, clientY: cy});
        el.dispatchEvent(new TouchEvent('touchstart', {touches:[start], changedTouches:[start], bubbles:true}));
        el.dispatchEvent(new TouchEvent('touchend', {touches:[], changedTouches:[end], bubbles:true}));
    }""", [cx, cy])
    page.wait_for_timeout(100)

    # tap (rotate)
    page.evaluate("""([cx, cy]) => {
        const el = document.getElementById('board');
        const start = new Touch({identifier:2, target: el, clientX: cx, clientY: cy});
        const end = new Touch({identifier:2, target: el, clientX: cx+2, clientY: cy+2});
        el.dispatchEvent(new TouchEvent('touchstart', {touches:[start], changedTouches:[start], bubbles:true}));
        el.dispatchEvent(new TouchEvent('touchend', {touches:[], changedTouches:[end], bubbles:true}));
    }""", [cx, cy])
    page.wait_for_timeout(100)

    # swipe down (hard drop)
    page.evaluate("""([cx, cy]) => {
        const el = document.getElementById('board');
        const start = new Touch({identifier:3, target: el, clientX: cx, clientY: cy});
        const end = new Touch({identifier:3, target: el, clientX: cx, clientY: cy+100});
        el.dispatchEvent(new TouchEvent('touchstart', {touches:[start], changedTouches:[start], bubbles:true}));
        el.dispatchEvent(new TouchEvent('touchend', {touches:[], changedTouches:[end], bubbles:true}));
    }""", [cx, cy])
    page.wait_for_timeout(200)
    print("score after swipe test:", page.inner_text("#score"))
    print("errors after swipe:", errors)

    browser.close()
