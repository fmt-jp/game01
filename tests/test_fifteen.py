import sys, time
from astar15 import solve
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

def read_grid(page):
    return page.evaluate("""() => {
        const cellSize = document.querySelector('.tile').getBoundingClientRect().width;
        const gap = 8;
        const tiles = [...document.querySelectorAll('.tile')];
        const grid = Array(16).fill(0);
        tiles.forEach(t => {
            const c = Math.round(parseFloat(t.style.left) / (cellSize + gap));
            const r = Math.round(parseFloat(t.style.top) / (cellSize + gap));
            grid[r*4+c] = parseInt(t.textContent, 10);
        });
        return grid;
    }""")

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://localhost:8390/fifteen/index.html")
    page.wait_for_timeout(400)

    grid = read_grid(page)
    print("scrambled grid:", grid)

    t0 = time.time()
    path = solve(grid)
    print(f"solver found path of {len(path) if path else None} moves in {time.time()-t0:.1f}s")

    if path is None:
        print("SOLVER FAILED (too many nodes) -- trying a fresh shuffle via reload")
        browser.close()
        raise SystemExit

    cell_info = page.evaluate("""() => {
        const cellSize = document.querySelector('.tile').getBoundingClientRect().width;
        const boardRect = document.getElementById('board').getBoundingClientRect();
        return {cellSize, x: boardRect.x, y: boardRect.y};
    }""")
    cell = cell_info["cellSize"]
    bx, by = cell_info["x"], cell_info["y"]

    def click_pos(p):
        r, c = p // 4, p % 4
        cx = bx + c*(cell+8) + cell/2
        cy = by + r*(cell+8) + cell/2
        page.mouse.click(cx, cy)

    for i, move_pos in enumerate(path):
        click_pos(move_pos)
        page.wait_for_timeout(20)

    page.wait_for_timeout(300)
    hidden = page.get_attribute("#overlay", "hidden")
    print("solved via UI, overlay shown (cleared):", hidden is None)
    if hidden is None:
        print("message:", page.inner_text("#overlay-message"), "|", page.inner_text("#overlay-sub"))
    print("moves counter:", page.inner_text("#moves"))
    print("best:", page.inner_text("#best"))
    page.screenshot(path=f"{SHOTS}/fifteen_cleared.png")
    print("errors:", errors)
    browser.close()
