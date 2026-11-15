"""はしわたし on a phone: the bridges are drawn with real drags, and what the
screen shows is measured rather than assumed."""
import sys
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE
import bridges_rules as R

failures = []


def check(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(f"{label} {detail}".strip())


def note(text):
    print("       " + text)


def drag(page, a, b):
    """Draw from island a to island b, the way a finger would."""
    A = page.evaluate("(i) => window.__spotOf(i)", a)
    B = page.evaluate("(i) => window.__spotOf(i)", b)
    page.mouse.move(A["x"], A["y"])
    page.mouse.down()
    page.mouse.move((A["x"] + B["x"]) / 2, (A["y"] + B["y"]) / 2, steps=4)
    page.mouse.move(B["x"], B["y"], steps=4)
    page.mouse.up()
    page.wait_for_timeout(90)


def tap(page, i):
    spot = page.evaluate("(i) => window.__spotOf(i)", i)
    page.mouse.click(spot["x"], spot["y"])
    page.wait_for_timeout(90)


PHONES = [("iPhone SE", 320, 568), ("iPhone 12", 390, 844)]

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)

    for name, width, height in PHONES:
        print(f"\n-- {name} {width}x{height}")
        context = browser.new_context(viewport={"width": width, "height": height},
                                      has_touch=True, is_mobile=True)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{BASE}/bridges/index.html")
        page.wait_for_timeout(600)
        page.evaluate("() => window.__start(13)")        # the biggest board there is
        page.wait_for_timeout(300)

        check("no horizontal overflow",
              page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))

        box = page.evaluate("""() => {
          const b = document.getElementById('board').getBoundingClientRect();
          const bar = document.querySelector('.toolbar').getBoundingClientRect();
          return { top: b.top, bottom: b.bottom, left: b.left, right: b.right,
                   w: b.width, h: b.height, bar: bar.bottom,
                   vh: window.innerHeight, vw: window.innerWidth, scroll: window.scrollY };
        }""")
        check("the whole board is on screen without scrolling",
              box["top"] >= 0 and box["bottom"] <= box["vh"] + 1 and box["scroll"] == 0,
              f"board {box['top']:.0f}..{box['bottom']:.0f} of {box['vh']}")
        check("and inside the page's width", box["left"] >= 0 and box["right"] <= box["vw"] + 1)

        state = page.evaluate("() => window.__bridges()")
        metrics = page.evaluate("() => window.__metrics()")
        check("an island is big enough to aim at", metrics["reach"] * 2 >= 40,
              f"{metrics['reach'] * 2:.0f}px across what a tap will reach")

        # The test that matters is not how far apart the islands are -- two
        # can sit corner to corner quite legally -- but whether a tap meant
        # for one ever lands on another. Ask the game itself, all round the
        # edge of every island it has drawn.
        wrong = page.evaluate("""() => {
          const m = window.__metrics();
          const st = window.__bridges();
          const bad = [];
          st.islands.forEach((is, i) => {
            const cx = m.pad + is.c * m.cell + m.cell / 2;
            const cy = m.pad + is.r * m.cell + m.cell / 2;
            for (let k = 0; k < 8; k += 1) {
              const t = (k / 8) * Math.PI * 2;
              const hit = window.__islandAt(cx + Math.cos(t) * m.radius,
                                            cy + Math.sin(t) * m.radius);
              if (hit !== i) bad.push([i, k, hit]);
            }
          });
          return bad;
        }""")
        check("a tap anywhere on an island belongs to that island",
              not wrong, f"{len(wrong)} points went elsewhere, e.g. {wrong[:3]}")
        note(f"board {box['w']:.0f}x{box['h']:.0f}, {metrics['cell']:.0f}px squares, "
             f"islands {metrics['radius'] * 2:.0f}px across with a {metrics['reach'] * 2:.0f}px reach, "
             f"buttons end at {box['bar']:.0f} of {box['vh']}")

        # --- drawing a bridge -------------------------------------------
        a, b = state["edges"][0]["a"], state["edges"][0]["b"]
        drag(page, a, b)
        check("a drag from island to island lays a bridge",
              page.evaluate("() => window.__bridges().edges[0].n") == 1)
        drag(page, a, b)
        check("drawing it again makes it a double",
              page.evaluate("() => window.__bridges().edges[0].n") == 2)
        drag(page, a, b)
        check("and once more takes it away",
              page.evaluate("() => window.__bridges().edges[0].n") == 0)

        tap(page, a)
        tap(page, b)
        check("two taps do the same as a drag",
              page.evaluate("() => window.__bridges().edges[0].n") == 1)

        # a drag that ends in open water leaves the board alone
        before = page.evaluate("() => window.__bridges().edges.map((e) => e.n)")
        A = page.evaluate("(i) => window.__spotOf(i)", a)
        page.mouse.move(A["x"], A["y"])
        page.mouse.down()
        page.mouse.move(A["x"] + metrics["cell"] * 0.5, A["y"] + metrics["cell"] * 0.5, steps=4)
        page.mouse.up()
        page.wait_for_timeout(120)
        check("a drag that ends in open water changes nothing",
              page.evaluate("() => window.__bridges().edges.map((e) => e.n)") == before)

        # --- the buttons -------------------------------------------------
        page.click("#undo-btn")
        page.wait_for_timeout(150)
        check("もどす takes the last bridge back",
              page.evaluate("() => window.__bridges().edges[0].n") == 0)

        drag(page, a, b)
        page.click("#clear-btn")
        page.wait_for_timeout(150)
        check("やりなおし clears the board",
              all(e["n"] == 0 for e in page.evaluate("() => window.__bridges().edges")))

        hints_before = page.evaluate("() => window.__bridges().hints")
        page.click("#hint-btn")
        page.wait_for_timeout(200)
        after_hint = page.evaluate("() => window.__bridges()")
        right = [e for e in after_hint["edges"] if e["n"] == e["answer"] and e["n"] > 0]
        check("ヒント puts one bridge where it belongs, and costs one",
              after_hint["hints"] == hints_before - 1 and len(right) >= 1,
              f"{len(right)} right, {after_hint['hints']} hints left")

        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(200)
        check("the page scrolls", page.evaluate("() => window.scrollY") > 0)
        check("遊び方 is reachable", page.locator(".about h2").bounding_box()["y"] < height)
        page.evaluate("() => window.scrollTo(0, 0)")

        page.screenshot(path=f"{SHOTS}/bridges_{width}.png")
        check("no page errors", not errors, str(errors))
        context.close()

    # ------------------------------------------------------------------
    print("\n-- finishing a board, and the one after it")
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/bridges/index.html")
    page.wait_for_timeout(600)
    page.evaluate("() => window.__start(1)")
    page.wait_for_timeout(300)

    state = page.evaluate("() => window.__bridges()")
    islands = [{"r": i["r"], "c": i["c"], "need": i["need"]} for i in state["islands"]]
    edges = [(e["a"], e["b"]) for e in state["edges"]]
    answer = R.solutions(islands, edges, 2)
    check("the board on screen has one answer to aim for", len(answer) == 1)
    drags = 0
    for i, n in enumerate(answer[0]):
        for _ in range(n):
            drag(page, edges[i][0], edges[i][1])
            drags += 1
    page.wait_for_timeout(300)
    done = page.evaluate("() => window.__bridges()")
    check(f"a whole board goes in with {drags} real drags",
          done["solved"] and done["left"] == 0)
    check("and the overlay says so", not page.locator("#overlay").is_hidden()
          and "つながった" in page.inner_text("#overlay-message"))
    note(page.inner_text("#overlay-sub").replace("\n", " / "))

    # The win is raised on a timer. Starting the next board inside that moment
    # must not leave the old one's timers landing on the new one.
    page.click("#overlay-btn")
    page.wait_for_timeout(50)
    fresh = page.evaluate("() => window.__bridges()")
    check("the next board starts right away at the next level",
          fresh["level"] == 2 and not fresh["solved"] and fresh["left"] > 0,
          f"level {fresh['level']}, {fresh['left']} to go")
    page.wait_for_timeout(300)
    drag(page, fresh["edges"][0]["a"], fresh["edges"][0]["b"])
    check("and it answers a drag, with no timer left over from the board before",
          page.evaluate("() => window.__bridges().edges[0].n") == 1)

    page.reload()
    page.wait_for_timeout(700)
    check("the level survives a reload",
          page.evaluate("() => window.__bridges().level") == 2,
          str(page.evaluate("() => window.__bridges().level")))
    check("no page errors", not errors, str(errors))
    page.screenshot(path=f"{SHOTS}/bridges_done.png")
    context.close()
    browser.close()

print("\n" + ("ALL UI CHECKS PASSED" if not failures else f"FAILURES: {failures}"))
sys.exit(1 if failures else 0)
