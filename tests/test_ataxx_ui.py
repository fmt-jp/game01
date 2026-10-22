"""Layout and tap checks for ふえる石.

The rules check plays through a helper; this one clicks the actual squares, so
the real event path is exercised, and looks at how the board sits on a phone.
"""
import sys

from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS
from ataxx_rules import CELLS, FOE, YOU, explain

BASE = "http://localhost:8390"
failures = []


def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(label)


def tap(page, index):
    page.locator(f'.square[data-index="{index}"]').click()


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    for name, viewport in (("iPhone SE", {"width": 320, "height": 568}),
                           ("iPhone 12", {"width": 390, "height": 844})):
        ctx = browser.new_context(viewport=viewport, has_touch=True, is_mobile=True)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{BASE}/ataxx/index.html")
        page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
        page.reload()
        page.wait_for_timeout(800)
        print(f"\n-- {name} {viewport['width']}x{viewport['height']}")

        check("no horizontal overflow",
              page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))
        board = page.locator("#board").bounding_box()
        check("the board fits the width", board["width"] <= viewport["width"] - 20, str(board))
        square = page.locator(".square").first.bounding_box()
        check("the squares are big enough to tap", square["width"] >= 38,
              f"{square['width']}px")
        check("the whole board is on screen without scrolling",
              board["y"] + board["height"] <= viewport["height"],
              f"bottom at {board['y'] + board['height']:.0f} of {viewport['height']}")

        state = page.evaluate("() => window.__ataxx()")
        move = state["yourMoves"][0]
        tap(page, move["from"])
        page.wait_for_timeout(200)
        check("tapping your stone selects it",
              page.evaluate("() => window.__ataxx().picked") == move["from"])
        tap(page, move["to"])
        page.wait_for_timeout(300)
        after = page.evaluate("() => window.__ataxx()")
        check("tapping a marked square plays the move",
              after["counts"]["you"] + after["counts"]["foe"] > 4
              or after["cells"][move["to"]] == 1,
              str(after["counts"]))
        check("nothing stays selected afterwards", after["picked"] == -1)

        # tapping a square it cannot reach just clears the selection
        page.wait_for_timeout(2200)
        s = page.evaluate("() => window.__ataxx()")
        if not s["over"] and s["turn"] == 1:
            mine = s["yourMoves"][0]["from"]
            reachable = {m["to"] for m in s["yourMoves"] if m["from"] == mine}
            far = next((i for i in range(49)
                        if s["cells"][i] == 0 and i not in reachable), None)
            if far is not None:
                tap(page, mine)
                page.wait_for_timeout(150)
                before = page.evaluate("() => window.__ataxx().cells")
                tap(page, far)
                page.wait_for_timeout(250)
                nowc = page.evaluate("() => window.__ataxx()")
                check("tapping out of range changes nothing",
                      nowc["cells"] == before and nowc["picked"] == -1)

        # Tapping again while the opponent is still thinking must not get a
        # second move in. It used to, and the stray turn put two chains of play
        # against each other, so the opponent answered twice running — which
        # looks exactly like a stone jumping further than the rules allow.
        page.evaluate("""() => {
          window.__trace = [];
          const snap = () => {
            const s = window.__ataxx();
            const key = s.cells.join("");
            const last = window.__trace[window.__trace.length - 1];
            if (!last || last.key !== key) window.__trace.push({key, cells: s.cells});
            requestAnimationFrame(snap);
          };
          snap();
        }""")
        for _ in range(10):
            s = page.evaluate("() => window.__ataxx()")
            if s["over"]:
                break
            if s["turn"] == YOU and not s["busy"] and s["yourMoves"]:
                m = s["yourMoves"][0]
                tap(page, m["from"])
                tap(page, m["to"])
                page.wait_for_timeout(120)
                impatient = page.evaluate("() => window.__ataxx()")
                if impatient["yourMoves"]:
                    m2 = impatient["yourMoves"][-1]
                    tap(page, m2["from"])
                    tap(page, m2["to"])
            page.wait_for_timeout(900)
        trace = page.evaluate("() => window.__trace.map(t => t.cells)")
        sides, strange = [], 0
        for i in range(1, len(trace)):
            what = explain(trace[i - 1], trace[i])
            if what is None:
                strange += 1
            else:
                sides.append(what[0])
        doubles = sum(1 for i in range(1, len(sides)) if sides[i] == sides[i - 1])
        check("every change to the board is one legal move", strange == 0,
              f"{strange} of {len(trace) - 1} transitions were not")
        check("nobody ever moves twice in a row, however fast you tap",
              doubles == 0, f"{doubles} double moves in {len(sides)}")
        print(f"      {len(sides)} moves watched while tapping ahead")
        page.evaluate("() => { window.__trace = []; }")

        page.click('.level-btn[data-level="hard"]')
        page.wait_for_timeout(600)
        check("choosing a level starts a fresh board on that level",
              page.evaluate("() => window.__ataxx().level") == "hard"
              and page.evaluate("() => window.__ataxx().counts.you") == 2)
        page.reload()
        page.wait_for_timeout(700)
        check("and the level is remembered",
              page.evaluate("() => window.__ataxx().level") == "hard")

        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(250)
        check("the page scrolls", page.evaluate("() => window.scrollY") > 50)
        check("遊び方 is reachable",
              page.locator(".about dl").bounding_box()["y"] < viewport["height"])
        if name == "iPhone SE":
            page.evaluate("() => window.scrollTo(0, 0)")
            page.wait_for_timeout(200)
            page.screenshot(path=f"{SHOTS}/ataxx_small.png")
        check("no page errors", not [e for e in errors if "ERR_" not in e], str(errors))
        ctx.close()
    browser.close()

print("\n" + ("ALL UI CHECKS PASSED" if not failures else f"FAILURES: {failures}"))
sys.exit(1 if failures else 0)
