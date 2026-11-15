"""Reading barcodes without a library.

barcode/js/scanner.js is what the game falls back to where the browser has no
reader of its own -- which, before this, meant fetching one from a CDN and so
not scanning at all with the network down. ean13.py writes the codes from the
published tables; the game reads them back. Neither was written from the
other, so a round trip through a picture says something.
"""
import random
import sys
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE, check, note, head, finish
import ean13

rng = random.Random(20261115)
CODES = [ean13.with_check("".join(str(rng.randrange(10)) for _ in range(12))) for _ in range(30)]
SHORT = [ean13.with_check("".join(str(rng.randrange(10)) for _ in range(7))) for _ in range(6)]

# What a camera does to a barcode on the way in.
PAINT = """
([modules, opts]) => {
  const unit = opts.unit, height = 120, quiet = 10;
  const width = (modules.length + quiet * 2) * unit;
  const canvas = document.createElement('canvas');
  canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = '#111';
  for (let i = 0; i < modules.length; i += 1) {
    if (modules[i] === '1') ctx.fillRect((quiet + i) * unit, 0, unit, height);
  }
  if (opts.upsideDown) {
    const flipped = document.createElement('canvas');
    flipped.width = width; flipped.height = height;
    const f = flipped.getContext('2d', { willReadFrequently: true });
    f.translate(width, height); f.rotate(Math.PI);
    f.drawImage(canvas, 0, 0);
    return window.__read(flipped, opts);
  }
  return window.__read(canvas, opts);
}
"""

READ = """
(canvas, opts) => {
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const d = image.data;
  if (opts.blur) {
    // a box blur across the row, as a lens out of focus would
    const r = opts.blur, w = canvas.width;
    for (let y = 0; y < canvas.height; y += 1) {
      const row = new Float64Array(w);
      for (let x = 0; x < w; x += 1) row[x] = d[(y * w + x) * 4];
      for (let x = 0; x < w; x += 1) {
        let sum = 0, n = 0;
        for (let k = -r; k <= r; k += 1) {
          const at = x + k;
          if (at >= 0 && at < w) { sum += row[at]; n += 1; }
        }
        const v = sum / n;
        const i = (y * w + x) * 4;
        d[i] = d[i + 1] = d[i + 2] = v;
      }
    }
  }
  if (opts.noise) {
    for (let i = 0; i < d.length; i += 4) {
      const n = (Math.random() * 2 - 1) * opts.noise;
      d[i] = Math.max(0, Math.min(255, d[i] + n));
      d[i + 1] = d[i + 2] = d[i];
    }
  }
  if (opts.shade) {
    // bright at one end, dim at the other, as a hand-held packet is
    for (let y = 0; y < canvas.height; y += 1) {
      for (let x = 0; x < canvas.width; x += 1) {
        const i = (y * canvas.width + x) * 4;
        const f = 0.4 + 0.6 * (x / canvas.width);
        d[i] = d[i] * f; d[i + 1] = d[i + 1] * f; d[i + 2] = d[i + 2] * f;
      }
    }
  }
  return Scanner.decode(d, canvas.width, canvas.height);
}
"""

CONDITIONS = [
    ("as printed", {"unit": 4}),
    ("small in the frame", {"unit": 2}),
    ("large in the frame", {"unit": 7}),
    ("out of focus", {"unit": 4, "blur": 3}),
    ("grainy", {"unit": 4, "noise": 55}),
    ("soft and grainy", {"unit": 4, "blur": 2, "noise": 35}),
    ("lit from one side", {"unit": 4, "shade": True}),
    ("held upside down", {"unit": 4, "upsideDown": True}),
]

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/barcode/index.html")
    page.wait_for_timeout(400)
    # Wrapped: handed over bare, Playwright takes the arrow function for
    # something to call rather than something to assign.
    page.evaluate("() => { window.__read = " + READ + "; }")

    head("[1] codes written here, read back there")
    check("the page has a reader of its own, and asks nobody for it",
          page.evaluate("() => typeof Scanner === 'object'"))
    worst = None
    for label, opts in CONDITIONS:
        read, misread = 0, []
        for code in CODES:
            got = page.evaluate(PAINT, [ean13.encode(code), opts])
            if got == code:
                read += 1
            elif got:
                misread.append(f"{code} read as {got}")
        rate = read / len(CODES)
        note(f"{label}: read {read}/{len(CODES)}"
             + (f", MISREAD {len(misread)}" if misread else ""))
        check(f"nothing is misread when {label}", not misread, "; ".join(misread[:2]))
        if worst is None or rate < worst[1]:
            worst = (label, rate)
    check("every condition reads most of the time", worst[1] >= 0.8,
          f"worst was {worst[0]} at {worst[1] * 100:.0f}%")

    head("[2] the shorter codes, and what must not read")
    eights = sum(1 for code in SHORT
                 if page.evaluate(PAINT, [ean13.encode(code), {"unit": 4}]) == code)
    check("eight digit codes read too", eights == len(SHORT), f"{eights}/{len(SHORT)}")

    # A code whose last digit is wrong is not a code.
    bad = []
    for code in CODES[:10]:
        wrong = code[:12] + str((int(code[12]) + 5) % 10)
        modules = ean13.encode(code)
        # rebuild the last digit's bars as the wrong digit would print them
        broken = modules[:-14] + ean13.RIGHT[(int(code[12]) + 5) % 10] + modules[-3:]
        got = page.evaluate(PAINT, [broken, {"unit": 4}])
        if got is not None:
            bad.append(f"{wrong} was accepted as {got}")
    check("a code whose check digit does not add up is refused", not bad, "; ".join(bad[:2]))

    noise_reads = page.evaluate("""() => {
      let hits = 0;
      for (let n = 0; n < 40; n += 1) {
        const canvas = document.createElement('canvas');
        canvas.width = 480; canvas.height = 80;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        for (let x = 0; x < 480; x += 1) {
          ctx.fillStyle = Math.random() < 0.5 ? '#111' : '#eee';
          ctx.fillRect(x, 0, 1, 80);
        }
        if (Scanner.decodeCanvas(canvas)) hits += 1;
      }
      return hits;
    }""")
    check("random stripes are not read as anything", noise_reads == 0, str(noise_reads))

    head("[3] fast enough to run on every frame")
    ms = page.evaluate(PAINT.replace("return window.__read(canvas, opts);", """
      const t0 = performance.now();
      for (let i = 0; i < 20; i += 1) window.__read(canvas, opts);
      return (performance.now() - t0) / 20;
    """).replace("return window.__read(flipped, opts);", "return 0;"),
        [ean13.encode(CODES[0]), {"unit": 4}])
    check("a frame is read in a few milliseconds", ms < 16, f"{ms:.1f}ms")
    note(f"{ms:.1f}ms to look over one frame")

    head("[4] a whole scan, through a pretend camera")
    mock = browser.new_page(viewport={"width": 390, "height": 844})
    mock_errors = []
    mock.on("pageerror", lambda e: mock_errors.append(str(e)))
    wanted = CODES[0]
    mock.add_init_script("""
      (() => {
        const modules = "%s";
        // No reader of the browser's own: this is the path the fallback takes.
        delete window.BarcodeDetector;
        navigator.mediaDevices.getUserMedia = async () => {
          const c = document.createElement('canvas');
          c.width = 640; c.height = 360;
          const g = c.getContext('2d');
          const unit = 4, quiet = 20;
          g.fillStyle = '#fff'; g.fillRect(0, 0, 640, 360);
          g.fillStyle = '#111';
          for (let i = 0; i < modules.length; i += 1) {
            if (modules[i] === '1') g.fillRect((quiet + i) * unit, 80, unit, 200);
          }
          // A canvas that was never painted gives a stream that never becomes
          // ready, and play() then hangs -- so paint before capturing.
          return c.captureStream(12);
        };
      })();
    """ % ean13.encode(CODES[0]))
    mock.goto(f"{BASE}/barcode/index.html")
    mock.wait_for_timeout(600)
    mock.click("#scan-main-btn")
    mock.wait_for_timeout(3000)
    landed = check("a scan with no browser reader still lands on a monster",
                   mock.get_attribute("#screen-result", "hidden") is None,
                   f'status says {mock.inner_text("#scan-status").strip()!r}')
    if landed:
        stored = mock.evaluate('() => JSON.parse(localStorage.getItem("barcode-monster-dex") || "[]").map((m) => m.code)')
        check("and it is the monster that code makes", stored and stored[-1] == wanted,
              f"{stored} should end with {wanted}")
        note(f"caught {mock.inner_text('#result-card .m-name').strip()} from {wanted}")
    mock.screenshot(path=f"{SHOTS}/barcode_own_scan.png")
    check("no page errors in the scan", not mock_errors, str(mock_errors))

    check("no page errors", not errors, str(errors))
    browser.close()

finish("BARCODE SCANNER CHECKS")
