"""The thing that makes this installable: the manifest, the icons, and the
service worker's own housekeeping.

What a game does offline is checked in test_hub.py. This one is about the
shell around them -- whether a phone would install it, and whether bumping
CACHE_NAME actually throws the old copy away, which is the one step the house
rules call not optional.
"""
import json
import pathlib
import re
import struct
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE, check, note, head, finish

ROOT = pathlib.Path(__file__).resolve().parent.parent
manifest = json.loads((ROOT / "manifest.webmanifest").read_text())
sw = (ROOT / "sw.js").read_text()
cache_name = re.search(r'CACHE_NAME = "([^"]+)"', sw).group(1)
shell = [s for s in re.findall(r'"\./([^"]*)"', sw) if s]


def png_size(path):
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", raw[16:24])


head("[1] the manifest")
for field in ("name", "short_name", "start_url", "scope", "display", "theme_color",
              "background_color", "icons", "lang"):
    check(f"the manifest has {field}", field in manifest)
check("it asks to run as an app, not a tab", manifest.get("display") == "standalone",
      str(manifest.get("display")))
check("its paths are relative, so it works from a subdirectory",
      manifest["start_url"].startswith("./") and manifest["scope"].startswith("./"),
      f'{manifest["start_url"]} / {manifest["scope"]}')
check("it has a description, and a short one",
      0 < len(manifest.get("description", "")) <= 120,
      str(len(manifest.get("description", ""))))

sizes = {}
bad_icons = []
for icon in manifest["icons"]:
    path = ROOT / icon["src"]
    if not path.exists():
        bad_icons.append(f"{icon['src']} is not there")
        continue
    got = png_size(path)
    sizes[icon["src"]] = got
    if got is None:
        bad_icons.append(f"{icon['src']} is not a PNG")
    elif f"{got[0]}x{got[1]}" != icon["sizes"]:
        bad_icons.append(f"{icon['src']} is {got[0]}x{got[1]}, listed as {icon['sizes']}")
check("every icon is on disk, a PNG, and the size it claims to be",
      not bad_icons, "; ".join(bad_icons))
check("there is a maskable icon, which is what a phone rounds off",
      any(i.get("purpose") == "maskable" for i in manifest["icons"]))
check("and one at least 512 across, for the splash screen",
      any(max(sizes.get(i["src"], (0, 0))) >= 512 for i in manifest["icons"]))
note(f"icons: {', '.join(f'{k} {v[0]}x{v[1]}' for k, v in sizes.items())}")

head("[2] every page says it belongs to the app")
pages = sorted(ROOT.glob("*/index.html")) + [ROOT / "index.html"]
missing = []
for page_path in pages:
    text = page_path.read_text()
    where = page_path.relative_to(ROOT)
    for needle, what in (
        ('rel="manifest"', "the manifest"),
        ('name="theme-color"', "a theme colour"),
        ('name="apple-mobile-web-app-capable"', "the iOS flag"),
        ('rel="apple-touch-icon"', "an iOS icon"),
        ('name="viewport"', "a viewport"),
    ):
        if needle not in text:
            missing.append(f"{where} has no {what}")
    if "<title>" not in text:
        missing.append(f"{where} has no title")
check(f"all {len(pages)} pages carry the app's own metadata", not missing,
      "; ".join(missing[:4]))

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    noise = []
    page.on("pageerror", lambda e: noise.append(str(e)))
    # Resource failures are worth watching, but two are nobody's fault: a page
    # opened on its own asks for a favicon that was never meant to exist, and
    # the fonts come from Google, which is not there with the network pulled.
    broken = []
    page.on("response", lambda r: broken.append(f"{r.status} {r.url}")
            if r.status >= 400 and "favicon" not in r.url else None)
    page.on("requestfailed", lambda r: broken.append(f"failed {r.url}")
            if "fonts.googleapis" not in r.url and "fonts.gstatic" not in r.url else None)

    head("[3] the service worker")
    page.goto(f"{BASE}/index.html")
    # `ready` resolves as soon as there is an active worker, which can still
    # be a moment short of activated -- so wait for the state itself.
    state = page.evaluate("""async () => {
      if (!('serviceWorker' in navigator)) return 'unsupported';
      const reg = await navigator.serviceWorker.ready;
      const worker = reg.active;
      if (!worker) return 'no-active';
      if (worker.state === 'activated') return worker.state;
      await new Promise((done) => {
        const tick = () => { if (worker.state === 'activated') done(); };
        worker.addEventListener('statechange', tick);
        setTimeout(done, 3000);
      });
      return worker.state;
    }""")
    check("it installs and takes over", state == "activated", state)
    page.wait_for_timeout(2500)

    got = page.evaluate("""async () => {
      const names = await caches.keys();
      const out = {};
      for (const name of names) {
        out[name] = (await (await caches.open(name)).keys()).map((r) => r.url);
      }
      return out;
    }""")
    check("there is exactly one cache, named as sw.js names it",
          list(got) == [cache_name], str(list(got)))
    held = {u.split(f"{BASE}/")[-1] for u in got.get(cache_name, [])}
    held |= {u for u in held if not u.endswith("/")}
    absent = [s for s in shell if s not in held and s.rstrip("/") + "/" not in held]
    check(f"and it holds all {len(shell)} files the shell lists", not absent,
          f"missing {absent[:4]}")
    note(f"{len(got.get(cache_name, []))} things cached under {cache_name}")

    head("[4] bumping the name really does throw the old one away")
    page.evaluate("""async () => {
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map((r) => r.unregister()));
      const stale = await caches.open('pocket-arcade-from-before');
      await stale.put('/stale', new Response('old'));
    }""")
    before = page.evaluate("() => caches.keys()")
    check("a cache from an older version is there to be cleared",
          "pocket-arcade-from-before" in before, str(before))
    page.goto(f"{BASE}/index.html")
    page.evaluate("() => navigator.serviceWorker.ready")
    page.wait_for_timeout(2500)
    after = page.evaluate("() => caches.keys()")
    check("and the worker deletes it when it takes over", after == [cache_name], str(after))

    head("[5] with the network pulled out")
    context.set_offline(True)
    page.goto(f"{BASE}/index.html")
    page.wait_for_timeout(400)
    check("the hub still opens", page.locator(".game-card").count() >= 15,
          str(page.locator(".game-card").count()))
    page.goto(f"{BASE}/2048/index.html")
    page.wait_for_timeout(500)
    check("2048 still opens", page.locator(".tile").count() > 0 and page.title() == "2048")
    page.goto(f"{BASE}/manifest.webmanifest")
    offline_manifest = page.evaluate("() => document.body.innerText")
    check("and the manifest itself is served from the cache",
          manifest["name"] in offline_manifest, offline_manifest[:60])
    page.screenshot(path=f"{SHOTS}/pwa_offline_hub.png")
    context.set_offline(False)

    check("no page threw", not noise, str(noise))
    check("and nothing the app asked for came back broken", not broken, str(broken[:4]))
    browser.close()

finish("PWA CHECKS")
