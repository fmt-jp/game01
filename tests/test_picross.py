from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

PUZZLES = [
[
"00100",
"00100",
"11111",
"00100",
"00100",
],
[
"01010",
"11111",
"11111",
"01110",
"00100",
],
[
"00011000",
"00111100",
"01111110",
"11111111",
"11000011",
"11000011",
"11011011",
"11011011",
],
[
"10000001",
"11000011",
"01111110",
"01011010",
"01111110",
"01100110",
"01111110",
"00000000",
],
[
"0000110000",
"0001111000",
"0011111100",
"0111111110",
"1111111111",
"0001100000",
"0001100000",
"0001100000",
"0001110000",
"0000000000",
],
]

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://localhost:8390/picross/index.html")
    page.wait_for_timeout(300)

    for idx, sol in enumerate(PUZZLES):
        for r, row in enumerate(sol):
            for c, ch in enumerate(row):
                if ch == "1":
                    page.click(f'.cell[data-row="{r}"][data-col="{c}"]')
                    page.wait_for_timeout(3)
        page.wait_for_timeout(150)
        hidden = page.get_attribute("#overlay", "hidden")
        msg = page.inner_text("#overlay-message") if hidden is None else "NOT CLEARED"
        print(f"puzzle {idx+1}: cleared={hidden is None} message={msg}")
        page.screenshot(path=f"{SHOTS}/picross_solved_{idx+1}.png")
        if idx < len(PUZZLES) - 1:
            page.click("#overlay-btn")
            page.wait_for_timeout(200)

    print("errors:", errors)
    browser.close()
