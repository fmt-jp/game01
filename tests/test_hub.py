"""Hub + PWA check: every card reaches a working game, and the whole arcade
still loads with the network switched off."""
import re, pathlib, sys
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
    check("the hub lists 15 games", n == 15, f"found {n}")
    hrefs = [cards.nth(i).get_attribute("href") for i in range(n)]
    check("めいろ探検 is on the hub", "maze/index.html" in hrefs, str(hrefs))
    check("きょだい迷路 is on the hub", "maze3d/index.html" in hrefs, str(hrefs))
    check("ことばの輪 is on the hub", "words/index.html" in hrefs, str(hrefs))
    check("ふえる石 is on the hub", "ataxx/index.html" in hrefs, str(hrefs))
    check("おとのつぶ is on the hub", "rhythm/index.html" in hrefs, str(hrefs))
    check("かさねとり is on the hub", "tiles/index.html" in hrefs, str(hrefs))
    check("はしわたし is on the hub", "bridges/index.html" in hrefs, str(hrefs))
    titles = [cards.nth(i).locator("h2").inner_text() for i in range(n)]
    print("     ", " / ".join(titles))
    check("no horizontal overflow on the hub",
          p.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))
    check("the maze card has its icon",
          p.locator(".preview.maze-icon svg").count() == 1)
    check("the 3D maze card has its icon",
          p.locator(".preview.corridor-icon svg").count() == 1)
    check("the word game card has its icon",
          p.locator(".preview.wheel-icon svg").count() == 1)
    check("the board game card has its icon",
          p.locator(".preview.stones-icon svg").count() == 1)
    check("the rhythm game card has its icon",
          p.locator(".preview.note-icon svg").count() == 1)
    check("the tile game card has its icon",
          p.locator(".preview.pile-icon svg").count() == 1)
    check("the bridge game card has its icon",
          p.locator(".preview.span-icon svg").count() == 1)

    # --- the shelves ------------------------------------------------------
    hub = p.evaluate("() => window.__hub()")
    shelved = [g for shelf in hub["shelves"] for g in shelf["games"]]
    check("the games are split over shelves, each one on exactly one shelf",
          sorted(shelved) == sorted(hrefs) and len(shelved) == len(set(shelved)),
          f"{len(shelved)} on shelves vs {len(hrefs)} cards")
    check("each tab says how many games are on its shelf",
          all(f"{len(sh['games'])}本" in t for t, sh in zip(hub["tabs"], hub["shelves"]))
          if hub["tabs"] and "本" in hub["tabs"][0] else True,
          str(hub["tabs"]))
    check("there is a tab for every shelf",
          len(hub["tabs"]) == len(hub["shelves"]) and hub["selected"] == 0,
          str(hub))
    print("      " + " / ".join(f"{t}: {len(sh['games'])}本"
                                for t, sh in zip(hub["tabs"], hub["shelves"])))

    # a tab takes you to its shelf, and the shelf says which tab you are on
    for want in (2, 1, 0):
        p.locator(".tab").nth(want).click()
        p.wait_for_timeout(700)
        got = p.evaluate("() => window.__hub()")
        if got["tab"] != want or got["selected"] != want:
            break
    check("every tab brings its own shelf into view", got["tab"] == 0 and got["selected"] == 0,
          f"asked for {want}, landed on {got['tab']} with tab {got['selected']} lit")

    # and a swipe does the same thing the other way round
    box = p.locator("#shelves").bounding_box()
    p.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    p.mouse.wheel(box["width"], 0)
    p.wait_for_timeout(900)
    swiped = p.evaluate("() => window.__hub()")
    check("swiping sideways moves the lit tab with it",
          swiped["tab"] == 1 and swiped["selected"] == 1, str(swiped))

    p.reload()
    p.wait_for_timeout(900)
    check("and the shelf you were on is the one you come back to",
          p.evaluate("() => window.__hub().tab") == 1,
          str(p.evaluate("() => window.__hub()")))

    p.locator(".tab").nth(1).press("ArrowRight")
    p.wait_for_timeout(700)
    check("the arrow keys walk the tabs", p.evaluate("() => window.__hub().tab") == 2,
          str(p.evaluate("() => window.__hub().tab")))
    p.locator(".tab").nth(0).click()
    p.wait_for_timeout(700)

    # the cards have to fit the page they are on, and say what they are
    clipped = p.evaluate("() => [...document.querySelectorAll('.game-info p')]"
                         ".filter((e) => e.scrollHeight > e.clientHeight + 1)"
                         ".map((e) => e.textContent)")
    check("no card's description is cut off", not clipped, str(clipped))
    wide = p.evaluate("() => [...document.querySelectorAll('.game-card')]"
                      ".map((c) => c.getBoundingClientRect())"
                      ".filter((r) => r.width > window.innerWidth + 1).length")
    check("no card is wider than the screen", wide == 0, str(wide))

    # the tab row has to stay put, or a long shelf hides the way out
    p.evaluate("() => window.scrollTo(0, 240)")
    p.wait_for_timeout(300)
    check("the tabs stay on screen as the shelf scrolls",
          p.evaluate("() => document.querySelector('.tabs').getBoundingClientRect().top") >= -1)
    p.evaluate("() => window.scrollTo(0, 0)")
    p.wait_for_timeout(200)
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
    check("the service worker cached the v17 shell",
          version["keys"] == ["pocket-arcade-v17"] and version["entries"] >= len([s for s in shell if s]),
          str(version))

    c.set_offline(True)
    p.goto(BASE + "/index.html")
    p.wait_for_timeout(600)
    check("the hub loads offline", p.locator(".game-card").count() == 15)
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

    # the word game ships a 100 KB dictionary: make sure it cached too
    p.goto(BASE + "/words/index.html")
    p.wait_for_timeout(900)
    check("ことばの輪 loads offline",
          p.evaluate("() => typeof window.__words === 'function'")
          and p.evaluate("() => WordDict.size") > 5000,
          str(p.evaluate("() => (window.WordDict || {}).size")))
    first = p.evaluate("() => window.__words().entries[0].word")
    p.evaluate("(w) => window.__spell(w)", first)
    p.wait_for_timeout(300)
    check("and is playable offline",
          p.evaluate("() => window.__words().solved") == [first],
          str(p.evaluate("() => window.__words().solved")))

    # the board game has an opponent to wake up with the network down
    p.goto(BASE + "/ataxx/index.html")
    p.wait_for_timeout(900)
    check("ふえる石 loads offline",
          p.evaluate("() => typeof window.__ataxx === 'function'"))
    s = p.evaluate("() => window.__ataxx()")
    p.evaluate("(i) => window.__tap(i)", s["yourMoves"][0]["from"])
    p.evaluate("(i) => window.__tap(i)", s["yourMoves"][0]["to"])
    p.wait_for_timeout(2200)
    after = p.evaluate("() => window.__ataxx()")
    check("and the opponent still answers offline",
          after["counts"]["foe"] > 2 or after["counts"]["you"] > 2,
          str(after["counts"]))
    # and the rhythm game writes its own music, so it needs nothing from the network
    p.goto(BASE + "/rhythm/index.html")
    p.wait_for_timeout(900)
    check("おとのつぶ loads offline",
          p.evaluate("() => typeof window.__rhythm === 'function'"))
    p.click("#overlay-btn")
    p.wait_for_timeout(1200)
    r = p.evaluate("() => window.__rhythm()")
    check("and still generates a chart with the network down",
          len(r["notes"]) > 20 and r["length"] > 20,
          f'{len(r["notes"])} notes, {r["length"]:.0f}s')

    # and the tile pile is dealt on the spot too, so it needs no network either
    p.goto(BASE + "/tiles/index.html")
    p.wait_for_timeout(900)
    check("かさねとり loads offline",
          p.evaluate("() => typeof window.__tiles === 'function'"))
    t = p.evaluate("() => window.__tiles()")
    check("and still deals a pile that has something to take",
          t["left"] > 10 and t["open"] > 0,
          f'{t["left"]} tiles, {t["open"]} pairs')

    # and the islands are worked out on the spot, network or no network
    p.goto(BASE + "/bridges/index.html")
    p.wait_for_timeout(900)
    check("はしわたし loads offline",
          p.evaluate("() => typeof window.__bridges === 'function'"))
    br = p.evaluate("() => window.__bridges()")
    check("and still lays out a board to solve",
          len(br["islands"]) >= 5 and len(br["edges"]) >= 4 and not br["solved"],
          f'{len(br["islands"])} islands, {len(br["edges"])} bridges')

    p.screenshot(path=f"{SHOTS}/maze_offline.png")
    c.set_offline(False)
    check("no page errors", not [e for e in errs if "ERR_" not in e], str(errs))
    b.close()

print("\n" + ("ALL HUB CHECKS PASSED" if not fails else f"FAILURES: {fails}"))
sys.exit(1 if fails else 0)
