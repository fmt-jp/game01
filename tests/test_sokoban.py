from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto("http://localhost:8390/sokoban/index.html")
    page.wait_for_timeout(400)
    page.screenshot(path=f"{SHOTS}/sokoban_l1.png")

    # Level 1: player at (3,1), box at (2,1), goal at (1,1). Move left once to win.
    page.click(".dpad-left")
    page.wait_for_timeout(300)
    hidden = page.get_attribute("#overlay", "hidden")
    print("level1 overlay hidden:", hidden, "moves:", page.inner_text("#moves"))
    page.screenshot(path=f"{SHOTS}/sokoban_l1_win.png")

    # advance to level 2
    page.click("#overlay-btn")
    page.wait_for_timeout(300)
    print("level after advance:", page.inner_text("#level-num"))
    page.screenshot(path=f"{SHOTS}/sokoban_l2.png")

    # test undo: move down then undo
    page.click(".dpad-down")
    page.wait_for_timeout(150)
    moves_after_move = page.inner_text("#moves")
    page.click("#undo-btn")
    page.wait_for_timeout(150)
    moves_after_undo = page.inner_text("#moves")
    print("moves after move/undo:", moves_after_move, moves_after_undo)

    # test swipe on board
    board = page.query_selector("#board")
    box = board.bounding_box()
    cx, cy = box["x"] + box["width"]/2, box["y"] + box["height"]/2
    page.evaluate("""([cx, cy]) => {
        const board = document.getElementById('board');
        const start = new Touch({identifier: 1, target: board, clientX: cx, clientY: cy});
        const end = new Touch({identifier: 1, target: board, clientX: cx, clientY: cy+60});
        board.dispatchEvent(new TouchEvent('touchstart', {touches:[start], changedTouches:[start], bubbles:true}));
        board.dispatchEvent(new TouchEvent('touchend', {touches:[], changedTouches:[end], bubbles:true}));
    }""", [cx, cy])
    page.wait_for_timeout(150)
    print("moves after swipe:", page.inner_text("#moves"))

    # test reset
    page.click("#reset-btn")
    page.wait_for_timeout(150)
    print("moves after reset:", page.inner_text("#moves"))

    print("errors:", errors)
    browser.close()
