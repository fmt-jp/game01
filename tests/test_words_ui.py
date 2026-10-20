"""Layout and touch checks for ことばの輪.

The puzzle check spells words through a helper; this one drags a finger across
the wheel the way a player does, so the pointer handling is exercised for real.
"""
import sys

from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

BASE = "http://localhost:8390"
failures = []


def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(label)


def letter_centres(page):
    out = []
    for i in range(page.locator(".letter").count()):
        node = page.locator(".letter").nth(i)
        box = node.bounding_box()
        out.append({"ch": node.inner_text().strip(),
                    "x": box["x"] + box["width"] / 2,
                    "y": box["y"] + box["height"] / 2,
                    "size": box["width"]})
    return out


def drag_word(page, word):
    """Trace the word on the wheel with one continuous drag."""
    page.locator(".wheel-wrap").scroll_into_view_if_needed()
    page.wait_for_timeout(150)
    centres = letter_centres(page)
    used = []
    path = []
    for ch in word:
        pick = next((i for i, l in enumerate(centres) if l["ch"] == ch and i not in used), None)
        if pick is None:
            return False
        used.append(pick)
        path.append(centres[pick])
    page.mouse.move(path[0]["x"], path[0]["y"])
    page.mouse.down()
    for point in path[1:]:
        # a couple of steps per hop, as a finger would pass between them
        page.mouse.move(point["x"], point["y"], steps=6)
        page.wait_for_timeout(30)
    page.mouse.up()
    return True


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    for name, viewport in (("iPhone SE", {"width": 320, "height": 568}),
                           ("iPhone 12", {"width": 390, "height": 844})):
        ctx = browser.new_context(viewport=viewport, has_touch=True, is_mobile=True)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{BASE}/words/index.html")
        page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
        page.reload()
        page.wait_for_timeout(800)
        print(f"\n-- {name} {viewport['width']}x{viewport['height']}")

        check("no horizontal overflow",
              page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))
        grid = page.locator("#grid").bounding_box()
        check("the grid fits the width", grid["width"] <= viewport["width"] - 20, str(grid))
        wheel = page.locator(".wheel-wrap").bounding_box()
        check("the wheel fits the width", wheel["width"] <= viewport["width"] - 20, str(wheel))
        centres = letter_centres(page)
        check("the letters are big enough to hit", min(l["size"] for l in centres) >= 44,
              f"smallest {min(l['size'] for l in centres)}")

        # An unopened square has to read as a square. It was once 7% white on a
        # near-black page, which left it all but invisible.
        contrast = page.evaluate("""() => {
          const parse = (css) => {
            const n = css.match(/[\\d.]+/g).map(Number);
            return {r: n[0], g: n[1], b: n[2], a: n.length > 3 ? n[3] : 1};
          };
          const over = (top, bottom) => ({
            r: bottom.r + (top.r - bottom.r) * top.a,
            g: bottom.g + (top.g - bottom.g) * top.a,
            b: bottom.b + (top.b - bottom.b) * top.a,
          });
          const lum = (c) => 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
          const page = parse(getComputedStyle(document.body).backgroundColor);
          const closed = document.querySelector(".cell:not(.blank):not(.open)");
          const shut = over(parse(getComputedStyle(closed).backgroundColor), page);
          const open = over(parse("rgba(241, 238, 247, 1)"), page);
          return {closed: lum(shut) - lum(page), open: lum(open) - lum(shut)};
        }""")
        check("an unopened square stands out from the page behind it",
              contrast["closed"] >= 18, f"only {contrast['closed']:.1f} brighter")
        check("and an opened one still reads as a different thing entirely",
              contrast["open"] >= 100, f"{contrast['open']:.1f}")

        state = page.evaluate("() => window.__words()")
        word = [e["word"] for e in state["entries"]][0]
        check("a real drag across the wheel finds a word", drag_word(page, word))
        page.wait_for_timeout(400)
        after = page.evaluate("() => window.__words()")
        check("the dragged word is the one that got solved", after["solved"] == [word],
              f"wanted {word}, got {after['solved']}")
        check("the cells it fills are open",
              sum(sum(r) for r in after["openCells"]) == len(word))

        # a drag that spells nonsense must leave the board alone
        junk = state["letters"][0] + state["letters"][0]
        drag_word(page, junk)
        page.wait_for_timeout(300)
        check("a nonsense drag changes nothing",
              page.evaluate("() => window.__words().solved") == [word])

        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(250)
        check("the page scrolls", page.evaluate("() => window.scrollY") > 50)
        check("遊び方 is reachable",
              page.locator(".about dl").bounding_box()["y"] < viewport["height"])
        if name == "iPhone SE":
            page.evaluate("() => window.scrollTo(0, 0)")
            page.wait_for_timeout(200)
            page.screenshot(path=f"{SHOTS}/words_small.png")
        check("no page errors", not [e for e in errors if "ERR_" not in e], str(errors))
        ctx.close()
    browser.close()

print("\n" + ("ALL UI CHECKS PASSED" if not failures else f"FAILURES: {failures}"))
sys.exit(1 if failures else 0)
