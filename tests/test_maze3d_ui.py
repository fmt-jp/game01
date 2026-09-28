"""Touch and layout checks: the thumb stick, the look drag, the hold buttons,
and that the page still scrolls to the instructions on a small phone."""
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

fails = []
def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(label)

TOUCH = """
([x, y, dx, dy, steps]) => {
  const el = document.getElementById("view");
  const mk = (type, cx, cy) => new TouchEvent(type, {
    bubbles: true, cancelable: true,
    changedTouches: [new Touch({identifier: 7, target: el, clientX: cx, clientY: cy})],
  });
  el.dispatchEvent(mk("touchstart", x, y));
  for (let i = 1; i <= steps; i++) {
    el.dispatchEvent(mk("touchmove", x + (dx * i) / steps, y + (dy * i) / steps));
  }
  return true;
}
"""
RELEASE = """
([x, y]) => {
  const el = document.getElementById("view");
  el.dispatchEvent(new TouchEvent("touchend", {
    bubbles: true, cancelable: true,
    changedTouches: [new Touch({identifier: 7, target: el, clientX: x, clientY: y})],
  }));
}
"""

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROMIUM)
    for name, vp in (("iPhone SE", {"width": 320, "height": 568}),
                     ("iPhone 12", {"width": 390, "height": 844})):
        c = b.new_context(viewport=vp, has_touch=True, is_mobile=True)
        p = c.new_page()
        errs = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto("http://localhost:8390/maze3d/index.html")
        p.wait_for_timeout(700)
        print(f"\n-- {name} {vp['width']}x{vp['height']}")

        box = p.locator("#view").bounding_box()
        check("the view fits the viewport", box["width"] <= vp["width"] + 1, str(box))
        check("no horizontal overflow",
              p.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))

        # thumb stick on the left half walks you forward
        before = p.evaluate("() => window.__maze3d()")
        p.evaluate(TOUCH, [box["x"] + box["width"] * 0.25, box["y"] + box["height"] / 2, 0, -50, 5])
        check("the thumb stick appears where you touch",
              p.get_attribute("#joystick", "hidden") is None)
        p.wait_for_timeout(700)
        moved = p.evaluate("() => window.__maze3d()")
        p.evaluate(RELEASE, [box["x"] + box["width"] * 0.25, box["y"] + box["height"] / 2 - 50])
        dist = ((moved["x"] - before["x"]) ** 2 + (moved["y"] - before["y"]) ** 2) ** 0.5
        check("dragging the left half walks the player", dist > 0.2, f"moved {dist:.3f} blocks")
        check("releasing puts the stick away", p.get_attribute("#joystick", "hidden") is not None)

        # dragging the right half turns the view
        before = p.evaluate("() => window.__maze3d().angle")
        p.evaluate(TOUCH, [box["x"] + box["width"] * 0.75, box["y"] + box["height"] / 2, 70, 0, 7])
        p.wait_for_timeout(250)
        after = p.evaluate("() => window.__maze3d().angle")
        p.evaluate(RELEASE, [box["x"] + box["width"] * 0.75 + 70, box["y"] + box["height"] / 2])
        check("dragging the right half turns the view", abs(after - before) > 0.15,
              f"{before:.3f} -> {after:.3f}")

        # the hold buttons
        before = p.evaluate("() => window.__maze3d().angle")
        p.locator("#btn-right").scroll_into_view_if_needed()
        p.wait_for_timeout(150)
        btn = p.locator("#btn-right").bounding_box()
        p.mouse.move(btn["x"] + btn["width"] / 2, btn["y"] + btn["height"] / 2)
        p.mouse.down()
        p.wait_for_timeout(400)
        p.mouse.up()
        after = p.evaluate("() => window.__maze3d().angle")
        check("holding the turn button turns the view", abs(after - before) > 0.3,
              f"{before:.3f} -> {after:.3f}")
        p.wait_for_timeout(300)
        settled = p.evaluate("() => window.__maze3d().angle")
        check("releasing the button stops the turn", abs(settled - after) < 0.02,
              f"{after:.3f} -> {settled:.3f}")

        p.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        p.wait_for_timeout(250)
        check("the page scrolls", p.evaluate("() => window.scrollY") > 50)
        check("遊び方 is reachable",
              p.locator(".about dl").bounding_box()["y"] < vp["height"])
        if name == "iPhone SE":
            p.screenshot(path=f"{SHOTS}/small_screen.png")
        check("no page errors", not [e for e in errs if "ERR_" not in e], str(errs))
        c.close()
    b.close()

print("\n" + ("ALL UI CHECKS PASSED" if not fails else f"FAILURES: {fails}"))
