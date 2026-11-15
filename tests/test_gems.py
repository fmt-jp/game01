"""宝石パズル: played with the real buttons, and watched for the one rule that
has to hold at all times -- three of a colour in a line never survives.

The run-finding here is written from the rule ("three in a row, column or
diagonal go"), not from the game's own matcher, so a disagreement shows up as
a run left sitting on a settled board.
"""
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE, check, note, head, finish


def runs_on(board):
    """Every line of three or more of one colour, found from the rule."""
    rows, cols = len(board), len(board[0])
    out = []
    for r in range(rows):
        for c in range(cols):
            colour = board[r][c]
            if colour is None:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                before_r, before_c = r - dr, c - dc
                if 0 <= before_r < rows and 0 <= before_c < cols and board[before_r][before_c] == colour:
                    continue                      # not the start of this line
                n = 0
                rr, cc = r, c
                while 0 <= rr < rows and 0 <= cc < cols and board[rr][cc] == colour:
                    n += 1
                    rr += dr
                    cc += dc
                if n >= 3:
                    out.append((r, c, dr, dc, n, colour))
    return out


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(f"{BASE}/gems/index.html")
    page.wait_for_timeout(500)

    def state():
        return page.evaluate("() => window.__gems()")

    head("[1] it starts with something falling")
    begin = state()
    check("there is a piece", begin["piece"] is not None and len(begin["piece"]["colors"]) == 3,
          str(begin["piece"]))
    check("the board is empty to begin with",
          all(cell is None for row in begin["board"] for cell in row))
    check("and the next piece is shown", len(begin["next"]) == 3, str(begin["next"]))
    page.wait_for_timeout(900)
    fell = state()
    check("the piece comes down on its own",
          fell["piece"] is None or fell["piece"]["row"] > begin["piece"]["row"]
          or any(cell for row in fell["board"] for cell in row),
          f'{begin["piece"]} -> {fell["piece"]}')

    head("[2] the controls")
    now = state()
    col = now["piece"]["col"]
    page.click("#btn-left")
    page.wait_for_timeout(120)
    moved_left = state()["piece"]["col"]
    page.click("#btn-right")
    page.wait_for_timeout(120)
    moved_back = state()["piece"]["col"]
    check("左 and 右 move the piece across",
          moved_left != col and moved_back == col or moved_left == 0,
          f"{col} -> {moved_left} -> {moved_back}")
    before_colours = state()["piece"]["colors"]
    page.click("#btn-rotate")
    page.wait_for_timeout(120)
    after_colours = state()["piece"]["colors"]
    check("回転 cycles the three gems",
          after_colours != before_colours and sorted(after_colours) == sorted(before_colours),
          f"{before_colours} -> {after_colours}")
    deep = state()["piece"]["row"]
    page.click("#btn-drop")
    page.wait_for_timeout(200)
    after_drop = state()
    check("落とす plants it at once",
          after_drop["piece"] is None or after_drop["piece"]["row"] < deep
          or any(cell for row in after_drop["board"] for cell in row),
          f'row {deep} -> {after_drop["piece"]}')

    head("[3] playing on, with the rule watched all the way")
    # Spread the pieces over the columns rather than piling them all on the
    # spawn point, or the board fills in six drops and nothing ever lines up.
    left_over, samples, cleared_at, restarts = [], 0, [], 0
    last_score = state()["score"]
    for n in range(150):
        now = state()
        if now["state"] == "gameover":
            page.click("#overlay-btn")
            page.wait_for_timeout(200)
            restarts += 1
            last_score = 0
            continue
        if now["state"] == "clearing" or not now["piece"]:
            page.wait_for_timeout(60)
            continue

        samples += 1
        found = runs_on(now["board"])
        if found:
            left_over.append((n, found[0]))
        if now["score"] > last_score:
            cleared_at.append(now["score"] - last_score)
        last_score = max(last_score, now["score"])

        want = n % now["cols"]
        for _ in range(abs(want - now["piece"]["col"])):
            page.click("#btn-left" if want < now["piece"]["col"] else "#btn-right")
        page.click("#btn-drop")
        page.wait_for_timeout(45)

    over = state()
    check(f"over {samples} settled boards, no three of a colour was left standing",
          not left_over, f"e.g. {left_over[:2]}")
    check("gems did vanish, and scored when they did", len(cleared_at) >= 3,
          f"{len(cleared_at)} clears")
    note(f"{len(cleared_at)} clears worth {cleared_at[:8]}..., over {samples} pieces "
         f"and {restarts} boards")
    page.screenshot(path=f"{SHOTS}/gems_playing.png")

    head("[4] filling it up")
    for _ in range(300):
        if state()["state"] == "gameover":
            break
        page.click("#btn-drop")
        page.wait_for_timeout(40)
    ended = state()
    check("stacking it to the top ends the game", ended["state"] == "gameover", ended["state"])
    check("and it says so", page.get_attribute("#overlay", "hidden") is None
          and page.inner_text("#overlay-message").strip() != "")
    check("the best score is at least what was just scored",
          ended["best"] >= ended["score"], f'{ended["best"]} vs {ended["score"]}')
    note(f'ended on {ended["score"]}, best {ended["best"]}')

    page.click("#overlay-btn")
    page.wait_for_timeout(300)
    again = state()
    check("the button starts a fresh board",
          again["score"] == 0 and again["state"] != "gameover"
          and all(cell is None for row in again["board"] for cell in row),
          f'score {again["score"]}, {again["state"]}')
    page.reload()
    page.wait_for_timeout(500)
    check("the best survives a reload", state()["best"] == ended["best"],
          f'{state()["best"]} vs {ended["best"]}')

    check("no page errors", not errors, str(errors))
    browser.close()

finish("GEMS CHECKS")
