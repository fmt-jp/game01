"""Hub + PWA check: every card reaches a working game, and the whole arcade
still loads with the network switched off."""
import re, pathlib
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

BASE = "http://localhost:8390"
ROOT = pathlib.Path(__file__).resolve().parent.parent
shell = re.findall(r'"\./([^"]*)"', (ROOT / "sw.js").read_text())
fails = []


def check(label, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(label)


# every precached path must exist on disk
root = ROOT
missing = [p for p in shell if p and not (root / p).exists() and not p.endswith("/")]
check("every precached file exists", not missing, str(missing))

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROMIUM)
    c = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True,
                      service_workers="allow")
    p = c.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(BASE + "/index.html")
    p.wait_for_timeout(800)

    cards = p.locator(".game-card")
    n = cards.count()
    check("the hub lists 10 games", n == 10, f"found {n}")
    hrefs = [cards.nth(i).get_attribute("href") for i in range(n)]
    check("めいろ探検 is on the hub", "maze/index.html" in hrefs, str(hrefs))
    check("きょだい迷路 is on the hub", "maze3d/index.html" in hrefs, str(hrefs))
    titles = [cards.nth(i).locator("h2").inner_text() for i in range(n)]
    print("     ", " / ".join(titles))
    check("no horizontal overflow on the hub",
          p.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))
    check("the maze card has its icon",
          p.locator(".preview.maze-icon svg").count() == 1)
    check("the 3D maze card has its icon",
          p.locator(".preview.corridor-icon svg").count() == 1)
    p.screenshot(path=f"{SHOTS}/hub.png", full_page=True)

    # each card opens a game that boots without errors
    for href in hrefs:
        sub = c.new_page()
        e2 = []
        sub.on("pageerror", lambda e: e2.append(str(e)))
        sub.goto(f"{BASE}/{href}")
        sub.wait_for_timeout(700)
        title = sub.title()
        check(f"{href} boots cleanly", not [x for x in e2 if "ERR_" not in x], str(e2))
        sub.close()

    # let the service worker precache, then cut the network
    p.goto(BASE + "/maze/index.html")
    p.wait_for_timeout(500)
    p.evaluate("() => navigator.serviceWorker.ready")
    p.wait_for_timeout(2500)
    version = p.evaluate("""async () => {
      const keys = await caches.keys();
      const c = await caches.open(keys[0]);
      return {keys, entries: (await c.keys()).length};
    }""")
    check("the service worker cached the v9 shell",
          version["keys"] == ["pocket-arcade-v9"] and version["entries"] >= len([s for s in shell if s]),
          str(version))

    c.set_offline(True)
    p.goto(BASE + "/index.html")
    p.wait_for_timeout(600)
    check("the hub loads offline", p.locator(".game-card").count() == 10)
    p.goto(BASE + "/maze/index.html")
    p.wait_for_timeout(900)
    check("めいろ探検 loads offline",
          p.locator("#board").count() == 1 and p.inner_text("#key-status").strip() != "")
    before = p.inner_text("#fuel-status")
    for sel in ("#btn-right", "#btn-down", "#btn-left", "#btn-up"):
        p.click(sel)
        p.wait_for_timeout(500)
        if p.inner_text("#fuel-status") != before:
            break
    check("the maze is playable offline", p.inner_text("#fuel-status") != before,
          f"{before} -> {p.inner_text('#fuel-status')}")

    # the 3D maze has three script files: make sure every one of them cached
    p.goto(BASE + "/maze3d/index.html")
    p.wait_for_timeout(1000)
    check("きょだい迷路 loads offline",
          p.evaluate("() => typeof window.__maze3d === 'function'")
          and p.evaluate("() => typeof window.MazeView === 'object'"))
    pos = p.evaluate("() => window.__maze3d()")
    p.keyboard.down("ArrowUp")
    p.wait_for_timeout(700)
    p.keyboard.up("ArrowUp")
    p.wait_for_timeout(200)
    moved = p.evaluate("() => window.__maze3d()")
    check("the 3D maze is walkable offline",
          abs(moved["x"] - pos["x"]) + abs(moved["y"] - pos["y"]) > 0.2
          or abs(moved["angle"] - pos["angle"]) > 0.1,
          f"{pos['x']:.2f},{pos['y']:.2f} -> {moved['x']:.2f},{moved['y']:.2f}")
    p.screenshot(path=f"{SHOTS}/maze_offline.png")
    c.set_offline(False)
    check("no page errors", not [e for e in errs if "ERR_" not in e], str(errs))
    b.close()

print("\n" + ("ALL HUB CHECKS PASSED" if not fails else f"FAILURES: {fails}"))
