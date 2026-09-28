"""Touch-level checks: swipe input, page scrolling, small-screen layout."""
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

ok = []
def check(label, cond, detail=""):
    ok.append((label, cond, detail))
    print(("ok   " if cond else "FAIL ") + label + ("  " + detail if detail and not cond else ""))

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROMIUM)
    for name, vp in (("iPhone SE", {"width": 320, "height": 568}),
                     ("iPhone 12", {"width": 390, "height": 844})):
        c = b.new_context(viewport=vp, has_touch=True, is_mobile=True)
        p = c.new_page()
        errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto("http://localhost:8390/maze/index.html")
        p.wait_for_timeout(500)
        print(f"\n-- {name} {vp['width']}x{vp['height']}")

        box = p.locator("#board").bounding_box()
        check("board fits the viewport width", box["width"] <= vp["width"] - 8,
              f"{box['width']}")
        check("board is square-ish", abs(box["width"] - box["height"]) < 2,
              f"{box['width']}x{box['height']}")
        check("no horizontal overflow",
              p.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))

        # the fuel bar must actually take the spare width, not collapse
        bar = p.locator(".fuel-bar").bounding_box()
        check("fuel bar stretches", bar["width"] > 80, f"{bar['width']}")

        # swipe on the canvas moves the player
        before = p.evaluate("() => document.getElementById('fuel-status').textContent")
        # a real touch swipe, the input path a phone actually uses. Which way is
        # open depends on the maze, so try each until one is a legal move.
        swipe = """([x, y, dx, dy]) => {
          const el = document.getElementById('board');
          const mk = (type, cx, cy) => new TouchEvent(type, {
            bubbles: true, cancelable: true,
            changedTouches: [new Touch({identifier: 1, target: el, clientX: cx, clientY: cy})],
          });
          el.dispatchEvent(mk('touchstart', x, y));
          el.dispatchEvent(mk('touchend', x + dx, y + dy));
        }"""
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        after = before
        for dx, dy in ((0, 90), (90, 0), (0, -90), (-90, 0)):
            p.evaluate(swipe, [cx, cy, dx, dy])
            p.wait_for_timeout(900)
            after = p.evaluate("() => document.getElementById('fuel-status').textContent")
            if after != before:
                break
        check("a swipe on the board spends fuel (the player moved)", after != before,
              f"{before} -> {after}")

        # the whole page, including 遊び方, must be reachable by scrolling
        p.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        p.wait_for_timeout(250)
        y = p.evaluate("() => window.scrollY")
        check("the page scrolls", y > 50, f"scrollY={y}")
        check("遊び方 is on screen after scrolling",
              p.locator(".about dl").bounding_box()["y"] < vp["height"])
        if name == "iPhone 12":
            p.screenshot(path=f"{SHOTS}/maze_howto.png")
        check("no page errors", not [e for e in errs if "ERR_" not in e], str(errs))
        c.close()
    b.close()

bad = [l for l, c, _ in ok if not c]
print("\n" + ("ALL UI CHECKS PASSED" if not bad else f"FAILURES: {bad}"))
