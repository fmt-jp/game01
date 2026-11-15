"""かさねとり on a phone: the pile is driven with real taps, and what the
screen actually shows is measured rather than assumed."""
import io
import sys
from playwright.sync_api import sync_playwright
from PIL import Image
from _common import CHROMIUM, SHOTS, BASE

failures = []


def check(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(f"{label} {detail}".strip())


def note(text):
    print("       " + text)


def luminance(shot):
    im = Image.open(io.BytesIO(shot)).convert("RGB")
    raw = im.tobytes()
    n = len(raw) // 3
    return sum(0.2126 * raw[i * 3] + 0.7152 * raw[i * 3 + 1] + 0.0722 * raw[i * 3 + 2]
               for i in range(n)) / n


def tile(page, i):
    return page.locator(f'.tile[data-i="{i}"]')


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
        page.goto(f"{BASE}/tiles/index.html")
        page.wait_for_timeout(600)
        page.evaluate("() => window.__start(9)")      # a deep pile, the demanding case
        page.wait_for_timeout(300)

        check("no horizontal overflow",
              page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))

        box = page.evaluate("""() => {
          const b = document.getElementById('board').getBoundingClientRect();
          const t = document.querySelector('.tile').getBoundingClientRect();
          const bar = document.querySelector('.toolbar').getBoundingClientRect();
          return { top: b.top, bottom: b.bottom, left: b.left, right: b.right,
                   tw: t.width, th: t.height, bar: bar.bottom, vh: window.innerHeight,
                   vw: window.innerWidth, scroll: window.scrollY };
        }""")
        check("the whole pile is on screen without scrolling",
              box["top"] >= 0 and box["bottom"] <= box["vh"] + 1 and box["scroll"] == 0,
              f"board {box['top']:.0f}..{box['bottom']:.0f} of {box['vh']}")
        check("and inside the page's width", box["left"] >= 0 and box["right"] <= box["vw"] + 1)
        check("a tile is big enough to hit", box["tw"] >= 36 and box["th"] >= 46,
              f"{box['tw']:.0f}x{box['th']:.0f}")
        note(f"tile {box['tw']:.0f}x{box['th']:.0f}, pile ends at {box['bottom']:.0f}, "
             f"buttons end at {box['bar']:.0f} of {box['vh']}")

        # A tile you are allowed to take must be the thing under your finger:
        # the layer above is offset, and if it reached across the middle of
        # the tile below, the tap would land on the wrong one.
        stolen = page.evaluate("""() => {
          const bad = [];
          for (const i of window.__tiles().free) {
            const el = document.querySelector('.tile[data-i="' + i + '"]');
            const r = el.getBoundingClientRect();
            const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
            if (!hit || hit.closest('.tile') !== el) bad.push(i);
          }
          return bad;
        }""")
        check("every takeable tile owns the point at its own centre", not stolen, str(stolen))

        # Measure a locked tile that nothing is standing on, so the reading is
        # of that tile and not of whatever is painted over it. A tile with
        # another one on top is dealt with below.
        state = page.evaluate("() => window.__tiles()")
        free = set(state["free"])
        on_top = {(t["x"], t["y"], t["z"] - 1) for t in state["tiles"] if t["alive"]}
        plain_locked = [i for i, t in enumerate(state["tiles"])
                        if t["alive"] and i not in free and (t["x"], t["y"], t["z"]) not in on_top]
        bright = luminance(tile(page, state["free"][0]).screenshot())
        dim = luminance(tile(page, plain_locked[0]).screenshot())
        check("a tile that cannot be taken is plainly darker than one that can",
              bright - dim > 55, f"{bright:.0f} vs {dim:.0f}")
        note(f"free tile {bright:.0f}, blocked tile {dim:.0f} (of 255), "
             f"{len(plain_locked)} tiles are blocked by their neighbours alone")

        # And a tile with another standing on it is partly hidden by it,
        # which is what makes the pile read as a pile. Measuring that needs
        # a tile whose right-hand edge is its own: the layer above is offset
        # up and to the left, so a neighbour one square over would cover the
        # very strip being measured. Take the ones that qualify and use the
        # middle reading, not the first tile that comes to hand.
        alive_at = {(t["x"], t["y"], t["z"]) for t in state["tiles"] if t["alive"]}
        candidates = [
            i for i, t in enumerate(state["tiles"])
            if t["alive"]
            and (t["x"], t["y"], t["z"] + 1) in alive_at          # something on top
            and (t["x"] + 1, t["y"], t["z"] + 1) not in alive_at  # nothing over its right edge
            and (t["x"] + 1, t["y"], t["z"]) not in alive_at      # nor beside it
        ]
        gaps = []
        for i in candidates[:8]:
            shot = tile(page, i).screenshot()
            im = Image.open(io.BytesIO(shot)).convert("L")
            w, h = im.size
            above = im.crop((0, 0, int(w * 0.55), int(h * 0.55)))      # the tile standing on it
            edge = im.crop((int(w * 0.82), int(h * 0.35), w, int(h * 0.85)))   # its own right edge
            up = sum(above.tobytes()) / len(above.tobytes())
            low = sum(edge.tobytes()) / len(edge.tobytes())
            gaps.append(up - low)
        if gaps:
            gaps.sort()
            middle = gaps[len(gaps) // 2]
            check("a tile with one standing on it shows as a darker edge under it",
                  middle > 20,
                  f"{middle:.0f} between them, over {len(gaps)} tiles: "
                  f"{[round(g) for g in gaps]}")
            note(f"{len(gaps)} buried tiles measured, middle gap {middle:.0f}")
        else:
            note("no tile on this pile has both something on top and a clear right edge")

        # --- real taps ---------------------------------------------------
        before = page.evaluate("() => window.__tiles().left")
        a, b = page.evaluate("() => window.__pairs()[0]")
        page.click(f'.tile[data-i="{a}"]')
        page.wait_for_timeout(120)
        check("tapping a free tile picks it up",
              page.evaluate("() => window.__tiles().picked") == a)
        page.click(f'.tile[data-i="{b}"]')
        page.wait_for_timeout(420)
        after = page.evaluate("() => window.__tiles()")
        check("tapping its match takes both off the pile",
              after["left"] == before - 2 and after["picked"] is None,
              f"{before} -> {after['left']}")
        check("and they are gone from the screen",
              tile(page, a).is_hidden() and tile(page, b).is_hidden())

        # a tile under another one does not answer
        state = page.evaluate("() => window.__tiles()")
        buried = [i for i, t in enumerate(state["tiles"])
                  if t["alive"] and i not in set(state["free"])]
        page.evaluate("(i) => { const el = document.querySelector('.tile[data-i=\"' + i + '\"]'); el.click(); }", buried[0])
        page.wait_for_timeout(120)
        check("a buried tile cannot be picked up",
              page.evaluate("() => window.__tiles().picked") is None)

        # two that do not match: the pick moves, nothing is taken
        state = page.evaluate("() => window.__tiles()")
        kinds = {i: state["tiles"][i]["kind"] for i in state["free"]}
        mismatch = None
        for i in state["free"]:
            for j in state["free"]:
                if i != j and kinds[i] != kinds[j]:
                    mismatch = (i, j)
                    break
            if mismatch:
                break
        page.click(f'.tile[data-i="{mismatch[0]}"]')
        page.click(f'.tile[data-i="{mismatch[1]}"]')
        page.wait_for_timeout(150)
        now = page.evaluate("() => window.__tiles()")
        check("two different faces take nothing, and the pick moves to the second",
              now["left"] == state["left"] and now["picked"] == mismatch[1],
              f"left {now['left']} picked {now['picked']}")
        page.click(f'.tile[data-i="{mismatch[1]}"]')     # tapping it again lets go
        page.wait_for_timeout(120)
        check("tapping the picked tile again puts it back",
              page.evaluate("() => window.__tiles().picked") is None)

        # --- the buttons ---------------------------------------------------
        page.click("#undo-btn")
        page.wait_for_timeout(200)
        back = page.evaluate("() => window.__tiles()")
        check("もどす puts the last pair back", back["left"] == state["left"] + 2,
              f"{state['left']} -> {back['left']}")

        hints_before = page.evaluate("() => window.__tiles().hints")
        page.click("#hint-btn")
        page.wait_for_timeout(200)
        hinted = page.locator(".tile.hinted")
        shown = hinted.count()
        pair_kinds = page.evaluate("""() => [...document.querySelectorAll('.tile.hinted')]
            .map((el) => el.dataset.kind)""")
        check("ヒント lights up a real pair and costs one",
              shown == 2 and len(set(pair_kinds)) == 1
              and page.evaluate("() => window.__tiles().hints") == hints_before - 1,
              f"{shown} tiles, kinds {pair_kinds}")

        # --- the page still behaves like a page ------------------------------
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(200)
        check("the page scrolls", page.evaluate("() => window.scrollY") > 0)
        check("遊び方 is reachable",
              page.locator(".about h2").bounding_box()["y"] < height)
        page.evaluate("() => window.scrollTo(0, 0)")

        page.screenshot(path=f"{SHOTS}/tiles_{width}.png")
        check("no page errors", not errors, str(errors))
        context.close()

    # ------------------------------------------------------------------
    print("\n-- clearing a pile, and the one after it")
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/tiles/index.html")
    page.wait_for_timeout(600)
    page.evaluate("() => window.__start(1)")
    page.wait_for_timeout(300)
    total = page.evaluate("() => window.__tiles().left")

    taps = 0
    while True:
        pairs = page.evaluate("() => window.__pairs()")
        if not pairs:
            break
        a, b = pairs[0]
        page.click(f'.tile[data-i="{a}"]')
        page.click(f'.tile[data-i="{b}"]')
        page.wait_for_timeout(60)
        taps += 2
        if taps > total + 8:
            break
    page.wait_for_timeout(500)
    state = page.evaluate("() => window.__tiles()")
    check(f"a whole pile of {total} tiles comes off with real taps",
          state["left"] == 0 and state["cleared"], f"{state['left']} left")
    check("and the overlay says so", not page.locator("#overlay").is_hidden()
          and "取り切" in page.inner_text("#overlay-message"))
    note(page.inner_text("#overlay-sub").replace("\n", " / "))

    # The pile that is cleared sets a timer to raise that overlay. Starting the
    # next pile inside that moment used to let the old timer land on the new
    # one and freeze it, so the next pile is started at once, with no wait.
    page.click("#overlay-btn")
    page.wait_for_timeout(50)
    fresh = page.evaluate("() => window.__tiles()")
    check("the next pile starts right away at the next level",
          fresh["level"] == 2 and fresh["left"] > 0 and not fresh["cleared"],
          f"level {fresh['level']}, {fresh['left']} tiles")
    page.wait_for_timeout(400)
    a, b = page.evaluate("() => window.__pairs()[0]")
    page.click(f'.tile[data-i="{a}"]')
    page.click(f'.tile[data-i="{b}"]')
    page.wait_for_timeout(300)
    check("and it answers taps, with no timer left over from the pile before",
          page.evaluate("() => window.__tiles().left") == fresh["left"] - 2,
          str(page.evaluate("() => window.__tiles().left")))

    # the level is remembered
    page.reload()
    page.wait_for_timeout(700)
    check("the level survives a reload",
          page.evaluate("() => window.__tiles().level") == 2,
          str(page.evaluate("() => window.__tiles().level")))
    check("no page errors", not errors, str(errors))
    page.screenshot(path=f"{SHOTS}/tiles_cleared.png")
    context.close()
    browser.close()

print("\n" + ("ALL UI CHECKS PASSED" if not failures else f"FAILURES: {failures}"))
sys.exit(1 if failures else 0)
