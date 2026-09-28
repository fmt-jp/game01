from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    logs = []
    page.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
    page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))

    # 1. Load hub online, wait for SW to be ready
    page.goto("http://localhost:8390/index.html")
    page.wait_for_timeout(300)
    sw_state = page.evaluate("""async () => {
        if (!('serviceWorker' in navigator)) return 'unsupported';
        const reg = await navigator.serviceWorker.ready;
        return reg.active ? reg.active.state : 'no-active';
    }""")
    print("SW state after hub load:", sw_state)

    # visit both games online so SW can cache them too
    page.goto("http://localhost:8390/2048/index.html")
    page.wait_for_timeout(400)
    page.goto("http://localhost:8390/stack/index.html")
    page.wait_for_timeout(400)
    page.goto("http://localhost:8390/index.html")
    page.wait_for_timeout(400)

    # check cache contents
    cache_keys = page.evaluate("""async () => {
        const names = await caches.keys();
        const out = {};
        for (const name of names) {
            const cache = await caches.open(name);
            const reqs = await cache.keys();
            out[name] = reqs.map(r => r.url);
        }
        return out;
    }""")
    for name, urls in cache_keys.items():
        print(f"Cache '{name}': {len(urls)} entries")
        for u in urls:
            print("   ", u)

    # 2. Go offline
    context.set_offline(True)
    print("\\n--- OFFLINE ---")

    page.goto("http://localhost:8390/index.html")
    page.wait_for_timeout(300)
    title = page.title()
    cards = page.query_selector_all(".game-card")
    print("Offline hub title:", title, "cards:", len(cards))
    page.screenshot(path=f"{SHOTS}/pwa_offline_hub.png")

    page.goto("http://localhost:8390/2048/index.html")
    page.wait_for_timeout(400)
    tiles = page.query_selector_all(".tile")
    print("Offline 2048 title:", page.title(), "tiles:", len(tiles))
    page.screenshot(path=f"{SHOTS}/pwa_offline_2048.png")

    page.goto("http://localhost:8390/stack/index.html")
    page.wait_for_timeout(400)
    stage = page.query_selector(".stage-wrap")
    print("Offline stack title:", page.title(), "stage present:", stage is not None)
    page.screenshot(path=f"{SHOTS}/pwa_offline_stack.png")

    print("\\nconsole/page errors:")
    for l in logs:
        print(" ", l)

    browser.close()
