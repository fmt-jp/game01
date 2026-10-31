"""Layout and touch checks for おとのつぶ.

The timing check plays through a helper; this one waits for a note to reach the
line and taps the lane for real, so the pointer path and the lane geometry are
exercised the way a thumb would.
"""
import sys
import time

from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

BASE = "http://localhost:8390"
failures = []


def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(label)


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    for name, viewport in (("iPhone SE", {"width": 320, "height": 568}),
                           ("iPhone 12", {"width": 390, "height": 844})):
        ctx = browser.new_context(viewport=viewport, has_touch=True, is_mobile=True)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{BASE}/rhythm/index.html")
        page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
        page.reload()
        page.wait_for_timeout(700)
        print(f"\n-- {name} {viewport['width']}x{viewport['height']}")

        check("no horizontal overflow",
              page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))
        stage = page.locator("#stage").bounding_box()
        check("the lanes are wide enough for a thumb", stage["width"] / 3 >= 44,
              f"{stage['width'] / 3:.0f}px each")
        check("the whole stage is on screen without scrolling",
              stage["y"] + stage["height"] <= viewport["height"],
              f"bottom at {stage['y'] + stage['height']:.0f} of {viewport['height']}")

        page.click("#overlay-btn")
        page.wait_for_timeout(400)
        check("it starts playing", page.evaluate("() => window.__rhythm().state") == "playing")

        # wait for a real note to arrive, then tap its lane for real
        hit = None
        for _ in range(40):
            s = page.evaluate("() => window.__rhythm()")
            upcoming = [n for n in s["notes"] if not n["judged"] and n["time"] - s["position"] > 0.7]
            if not upcoming:
                page.wait_for_timeout(200)
                continue
            note = upcoming[0]
            wait = note["time"] - s["position"]
            lane_x = stage["x"] + stage["width"] * (note["lane"] + 0.5) / 3
            lane_y = stage["y"] + stage["height"] - 40
            time.sleep(max(0, wait - 0.02))
            page.mouse.click(lane_x, lane_y)
            page.wait_for_timeout(120)
            after = page.evaluate("() => window.__rhythm()")
            hit = next((n for n in after["notes"]
                        if abs(n["time"] - note["time"]) < 1e-9 and n["lane"] == note["lane"]), None)
            break
        check("tapping the lane as the note lands registers a hit",
              hit is not None and hit["judged"] in ("perfect", "good"),
              str(hit))
        check("and the combo counts it",
              page.evaluate("() => window.__rhythm().combo") >= 1,
              str(page.evaluate("() => window.__rhythm().combo")))

        # a tap in an empty lane must not break anything
        before = page.evaluate("() => window.__rhythm()")
        page.mouse.click(stage["x"] + stage["width"] * 0.5, stage["y"] + 30)
        page.wait_for_timeout(150)
        after = page.evaluate("() => window.__rhythm()")
        check("a tap at the wrong moment is not punished",
              after["tally"]["miss"] == before["tally"]["miss"],
              f"{before['tally']} -> {after['tally']}")

        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(250)
        check("the page scrolls", page.evaluate("() => window.scrollY") > 50)
        check("遊び方 is reachable",
              page.locator(".about dl").bounding_box()["y"] < viewport["height"])
        check("the offset controls are reachable",
              page.locator("#offset-auto").bounding_box()["width"] > 20)
        if name == "iPhone SE":
            page.evaluate("() => window.scrollTo(0, 0)")
            page.wait_for_timeout(200)
            page.screenshot(path=f"{SHOTS}/rhythm_small.png")
        check("no page errors", not [e for e in errors if "ERR_" not in e], str(errors))
        ctx.close()
    browser.close()

print("\n" + ("ALL UI CHECKS PASSED" if not failures else f"FAILURES: {failures}"))
sys.exit(1 if failures else 0)
