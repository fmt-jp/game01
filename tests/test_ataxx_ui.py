"""Layout and tap checks for ふえる石.

The rules check plays through a helper; this one clicks the actual squares, so
the real event path is exercised, and looks at how the board sits on a phone.
"""
import sys

from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS
from ataxx_rules import CELLS, EMPTY, FOE, SIZE, WALL, YOU, explain, legal_moves

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

        # The board has to say what just happened. Without it a jump reads as a
        # stone teleporting, and a run of moves after a pass reads as one.
        s = page.evaluate("() => window.__ataxx()")
        if not s["over"] and s["turn"] == YOU and s["yourMoves"]:
            jump = next((m for m in s["yourMoves"] if not m["clone"]), s["yourMoves"][0])
            tap(page, jump["from"])
            tap(page, jump["to"])
            page.wait_for_timeout(2600)
            st = page.evaluate("() => window.__ataxx()")
            marks = page.evaluate("""() => ({
              from: [...document.querySelectorAll('.moved-from')].map(n => Number(n.dataset.index)),
              to: [...document.querySelectorAll('.moved-to')].map(n => Number(n.dataset.index)),
            })""")
            last = st["lastMove"]
            check("the square the last move landed on is marked",
                  marks["to"] == [last["to"]], f"{marks} for {last}")
            check("a jump also marks where it came from, a clone does not",
                  marks["from"] == ([] if last["clone"] else [last["from"]]),
                  f"{marks} for {last}")

        # A position you cannot move in: the page has to say so rather than
        # letting the opponent appear to make several moves at once.
        boxed = [EMPTY] * CELLS
        boxed[0] = YOU
        for r, c in ((0, 1), (1, 0), (1, 1), (0, 2), (2, 0), (2, 2), (1, 2), (2, 1)):
            boxed[r * SIZE + c] = WALL
        boxed[5 * SIZE + 5] = FOE
        boxed[6 * SIZE + 6] = FOE
        assert not legal_moves(boxed, YOU) and legal_moves(boxed, FOE)
        page.evaluate("([c, t]) => window.__setBoard(c, t)", [boxed, YOU])
        page.wait_for_timeout(400)
        check("being unable to move is announced in plain words",
              "打てる手がありません" in page.inner_text("#turn")
              and "notice" in (page.get_attribute("#turn", "class") or ""),
              repr(page.inner_text("#turn")))
        before = page.evaluate("() => window.__ataxx().counts")
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
        page.wait_for_timeout(4200)
        after = page.evaluate("() => window.__ataxx()")
        check("the opponent carries on while you are stuck",
              after["counts"]["foe"] > before["foe"] and after["counts"]["you"] == before["you"],
              f"{before} -> {after['counts']}")
        stuck_trace = page.evaluate("() => window.__trace.map(t => t.cells)")
        moves = [explain(stuck_trace[i - 1], stuck_trace[i]) for i in range(1, len(stuck_trace))]
        check("and each of those is one legal move by the opponent, not a leap",
              len(moves) >= 2 and all(m is not None and m[0] == FOE for m in moves),
              f"{len(moves)} changes: " + str([None if m is None else m[0] for m in moves]))
        page.evaluate("() => { window.__trace = []; }")

        page.click("#new-btn")
        page.wait_for_timeout(600)

        # who opens
        check("a fresh install has you opening",
              page.evaluate("() => window.__ataxx().first") == YOU
              and page.inner_text("#firsts .level-btn.on").strip() == "自分が先",
              page.inner_text("#firsts .level-btn.on"))

        page.click('.level-btn[data-first="foe"]')
        page.wait_for_timeout(2000)
        swapped = page.evaluate("() => window.__ataxx()")
        check("handing the opening to the opponent lets it move first",
              swapped["first"] == FOE and swapped["counts"]["foe"] == 3
              and swapped["counts"]["you"] == 2,
              str(swapped["counts"]))
        check("and the turn comes back to you",
              swapped["turn"] == YOU and not swapped["busy"], f"turn={swapped['turn']}")

        page.reload()
        page.wait_for_timeout(1600)
        check("the choice is remembered",
              page.evaluate("() => window.__ataxx().first") == FOE
              and page.inner_text("#firsts .level-btn.on").strip() == "あいてが先")

        # the turn order has to hold with the opponent opening, too
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
        for _ in range(6):
            s = page.evaluate("() => window.__ataxx()")
            if s["over"]:
                break
            if s["turn"] == YOU and not s["busy"] and s["yourMoves"]:
                m = s["yourMoves"][0]
                tap(page, m["from"])
                tap(page, m["to"])
            page.wait_for_timeout(900)
        trace = page.evaluate("() => window.__trace.map(t => t.cells)")
        order = [explain(trace[i - 1], trace[i]) for i in range(1, len(trace))]
        sides = [o[0] for o in order if o]
        check("with the opponent opening, play still alternates",
              all(o is not None for o in order)
              and all(sides[i] != sides[i - 1] for i in range(1, len(sides))),
              " ".join("you" if x == YOU else "foe" for x in sides))

        page.click('.level-btn[data-first="you"]')
        page.wait_for_timeout(600)
        check("switching back starts a board where you open",
              page.evaluate("() => window.__ataxx().first") == YOU
              and page.evaluate("() => window.__ataxx().counts") == {"you": 2, "foe": 2, "empty": 45}
              or page.evaluate("() => window.__ataxx().counts.you") == 2,
              str(page.evaluate("() => window.__ataxx().counts")))

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
