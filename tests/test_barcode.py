"""Check the 図鑑 delete flow and the redrawn monsters.

The dex is seeded in the OLD storage shape -- entries saved before the new
visual traits existed -- so this also proves the artwork still renders for
monsters caught by an earlier version.
"""
import sys
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

CODES = ["4901777318601", "4902102072618", "4901085141434", "4987176000101", "0123456789012"]
failures = []


def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(f"{label}: {detail}")


SEED = """
([codes]) => {
  // exactly what an older build wrote: no hornType / mouthType / pattern
  const list = codes.map((code) => {
    const m = MonsterGen.fromCode(code);
    return {code, name: m.name, type: m.type, color: m.color, hp: m.maxHp,
            atk: m.atk, def: m.def, spd: m.spd,
            visual: {spikeCount: m.visual.spikeCount, eyeCount: m.visual.eyeCount,
                     bodyShape: m.visual.bodyShape}};
  });
  localStorage.setItem("barcode-monster-dex", JSON.stringify(list));
  return list.map((m) => m.name);
}
"""

STORED = '() => JSON.parse(localStorage.getItem("barcode-monster-dex") || "[]").map((m) => m.code)'
SHOWN = '() => [...document.querySelectorAll(".dex-name")].map((el) => el.textContent)'

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True,
                              is_mobile=True, device_scale_factor=2)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://localhost:8390/barcode/index.html")
    page.wait_for_timeout(500)
    names = page.evaluate(SEED, [CODES])
    page.reload()
    page.wait_for_timeout(600)

    print("\n[1] the dex as it stands")
    check("all five monsters are listed", page.locator(".dex-item").count() == 5,
          str(page.locator(".dex-item").count()))
    check("old saved entries still draw", page.evaluate("""() => {
            const c = document.querySelector(".dex-item canvas");
            const g = c.getContext("2d");
            const d = g.getImageData(0, 0, c.width, c.height).data;
            let painted = 0;
            for (let i = 3; i < d.length; i += 4) if (d[i] > 8) painted++;
            return painted;
          }""") > 200)
    check("the ✕ buttons are hidden until you ask to edit",
          not page.locator(".dex-remove").first.is_visible())
    check("the edit button is showing", page.locator("#dex-edit-btn").is_visible())
    page.screenshot(path=f"{SHOTS}/dex_normal.png")

    print("\n[2] edit mode")
    page.click("#dex-edit-btn")
    page.wait_for_timeout(200)
    check("the ✕ buttons appear", page.locator(".dex-remove").first.is_visible())
    check("the button becomes 完了", page.inner_text("#dex-edit-btn").strip() == "完了",
          page.inner_text("#dex-edit-btn"))
    box = page.locator(".dex-remove").first.bounding_box()
    check("the ✕ is a reachable tap target", box["width"] >= 24 and box["height"] >= 24, str(box))
    page.screenshot(path=f"{SHOTS}/dex_editing.png")

    print("\n[3] deleting, and taking it back")
    before_codes = page.evaluate(STORED)
    target_index = 2
    target_name = names[target_index]
    page.locator(".dex-remove").nth(target_index).click()
    page.wait_for_timeout(300)
    after_codes = page.evaluate(STORED)
    check("the monster is gone from the list", page.locator(".dex-item").count() == 4,
          str(page.locator(".dex-item").count()))
    check("it is gone from storage too", CODES[target_index] not in after_codes, str(after_codes))
    check("nothing else was disturbed",
          after_codes == [c for c in before_codes if c != CODES[target_index]], str(after_codes))
    check("the count in the heading follows", "(4)" in page.inner_text("#dex-count"),
          page.inner_text("#dex-count"))
    check("an undo offer appears", page.get_attribute("#undo-toast", "hidden") is None)
    check("the offer names the monster", target_name in page.inner_text("#undo-text"),
          page.inner_text("#undo-text"))
    page.screenshot(path=f"{SHOTS}/dex_undo.png")

    page.click("#undo-btn")
    page.wait_for_timeout(300)
    check("undo puts it back", page.evaluate(STORED) == before_codes, str(page.evaluate(STORED)))
    check("and back in its original place", page.evaluate(SHOWN)[target_index] == target_name,
          str(page.evaluate(SHOWN)))
    check("the offer goes away", page.get_attribute("#undo-toast", "hidden") is not None)

    print("\n[4] the offer expires on its own")
    page.locator(".dex-remove").nth(0).click()
    page.wait_for_timeout(300)
    check("offer shown", page.get_attribute("#undo-toast", "hidden") is None)
    page.wait_for_timeout(7200)
    check("the offer times out", page.get_attribute("#undo-toast", "hidden") is not None)
    check("the deletion stands", len(page.evaluate(STORED)) == 4, str(page.evaluate(STORED)))

    print("\n[5] leaving the 図鑑 withdraws the offer")
    page.locator(".dex-remove").nth(0).click()
    page.wait_for_timeout(200)
    check("offer shown", page.get_attribute("#undo-toast", "hidden") is None)
    page.click("#scan-main-btn")
    page.wait_for_timeout(400)
    check("the offer is withdrawn when the screen changes",
          page.get_attribute("#undo-toast", "hidden") is not None)
    page.click("#scan-cancel-btn")
    page.wait_for_timeout(300)

    print("\n[6] deleting everything")
    while page.locator(".dex-item").count() > 0:
        page.locator(".dex-remove").nth(0).click()
        page.wait_for_timeout(150)
    check("the dex hides itself when empty", page.get_attribute("#dex-wrap", "hidden") is not None)
    check("storage is empty", page.evaluate(STORED) == [], str(page.evaluate(STORED)))
    check("undo still works on the last one", True)
    page.click("#undo-btn")
    page.wait_for_timeout(300)
    check("the last monster comes back", page.locator(".dex-item").count() == 1,
          str(page.locator(".dex-item").count()))
    check("the dex reappears with it", page.get_attribute("#dex-wrap", "hidden") is None)
    check("edit mode was dropped when the dex emptied",
          page.inner_text("#dex-edit-btn").strip() == "編集", page.inner_text("#dex-edit-btn"))

    print("\n[7] the artwork has depth")
    stats = page.evaluate("""([codes]) => {
      const out = [];
      for (const code of codes) {
        const c = document.createElement("canvas");
        c.style.width = "140px"; c.style.height = "140px";
        document.body.appendChild(c);
        MonsterGen.draw(c, MonsterGen.fromCode(code));
        const g = c.getContext("2d");
        const W = c.width, H = c.height, d = g.getImageData(0, 0, W, H).data;
        const colors = new Set();
        let minX = W, maxX = 0, minY = H, maxY = 0, soft = 0;
        for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
          const i = (y * W + x) * 4, a = d[i + 3];
          if (a === 0) continue;
          if (a > 240) {
            colors.add(`${d[i]},${d[i+1]},${d[i+2]}`);
            if (x < minX) minX = x; if (x > maxX) maxX = x;
            if (y < minY) minY = y; if (y > maxY) maxY = y;
          } else if (a > 8) soft++;
        }
        const lum = (x0, x1, y0, y1) => {
          let s = 0, n = 0;
          for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
            const i = (y * W + x) * 4;
            if (d[i + 3] < 240) continue;
            s += 0.2126*d[i] + 0.7152*d[i+1] + 0.0722*d[i+2]; n++;
          }
          return n ? s / n : 0;
        };
        const mx = (minX + maxX) >> 1, my = (minY + maxY) >> 1;
        let shadow = 0, sn = 0;
        for (let y = maxY + 2; y < Math.min(H, maxY + 18); y++)
          for (let x = minX; x < maxX; x++) { shadow += d[(y*W+x)*4+3]; sn++; }
        c.remove();
        out.push({code, colors: colors.size, soft,
                  lit: lum(minX, mx, minY, my) - lum(mx, maxX, my, maxY),
                  shadow: sn ? shadow / sn : 0});
      }
      return out;
    }""", [CODES])
    check("the bodies are shaded, not flat fills",
          min(s["colors"] for s in stats) > 800,
          f"fewest distinct colours: {min(s['colors'] for s in stats)}")
    check("lit from one side: the near corner is brighter than the far one",
          min(s["lit"] for s in stats) > 10,
          f"smallest difference: {min(s['lit'] for s in stats):.1f}")
    check("each monster casts a shadow on the ground",
          min(s["shadow"] for s in stats) > 15,
          f"faintest shadow: {min(s['shadow'] for s in stats):.1f}")

    clipped = page.evaluate("""() => {
      // Every trait combination has to fit, not just the ones some barcode
      // happens to produce: draw() falls back to an explicit visual when the
      // monster carries no code, so they can all be enumerated.
      const bad = [];
      const colors = MonsterGen.TYPES.map((t) => t.color);
      for (let bodyShape = 0; bodyShape < 3; bodyShape++)
      for (let eyeCount = 1; eyeCount <= 2; eyeCount++)
      for (let spikeCount = 0; spikeCount < 4; spikeCount++)
      for (let hornType = 0; hornType < 3; hornType++)
      for (let mouthType = 0; mouthType < 3; mouthType++)
      for (let pattern = 0; pattern < 3; pattern++) {
        const visual = {bodyShape, eyeCount, spikeCount, hornType, mouthType, pattern};
        const c = document.createElement("canvas");
        c.style.width = "140px"; c.style.height = "140px";
        document.body.appendChild(c);
        MonsterGen.draw(c, {color: colors[bodyShape % colors.length], visual});
        const W = c.width, H = c.height;
        const d = c.getContext("2d").getImageData(0, 0, W, H).data;
        const hot = (x, y) => d[(y * W + x) * 4 + 3] > 16;
        const edges = [];
        for (let x = 0; x < W; x++) if (hot(x, 0)) { edges.push("top"); break; }
        for (let x = 0; x < W; x++) if (hot(x, H - 1)) { edges.push("bottom"); break; }
        for (let y = 0; y < H; y++) if (hot(0, y)) { edges.push("left"); break; }
        for (let y = 0; y < H; y++) if (hot(W - 1, y)) { edges.push("right"); break; }
        c.remove();
        if (edges.length) bad.push({visual, edges});
      }
      return bad;
    }""")
    check("none of the 648 trait combinations is clipped by its canvas", clipped == [],
          f"{len(clipped)} clipped, e.g. {clipped[:2]}")

    same = page.evaluate("""() => {
      const shot = () => {
        const c = document.createElement("canvas");
        c.style.width = "140px"; c.style.height = "140px";
        document.body.appendChild(c);
        MonsterGen.draw(c, MonsterGen.fromCode("4901777318601"));
        const data = c.getContext("2d").getImageData(0, 0, c.width, c.height).data.join(",");
        c.remove();
        return data;
      };
      return shot() === shot();
    }""")
    check("the same barcode always draws the same monster", same)

    check("no page errors", not [e for e in errors if "ERR_" not in e], str(errors))

    print("\n[8] the whole flow still works: scan, card, battle")
    mock = ctx.new_page()
    mock_errors = []
    mock.on("pageerror", lambda e: mock_errors.append(str(e)))
    mock.add_init_script("""
      navigator.mediaDevices.getUserMedia = async () => {
        const c = document.createElement("canvas");
        c.width = 320; c.height = 240;
        const g = c.getContext("2d");
        g.fillStyle = "#888"; g.fillRect(0, 0, 320, 240);
        return c.captureStream(10);
      };
      let calls = 0;
      window.BarcodeDetector = class {
        async detect() {
          calls++;
          return calls > 3 ? [{rawValue: "4901234567894"}] : [];
        }
      };
    """)
    mock.goto("http://localhost:8390/barcode/index.html")
    mock.wait_for_timeout(500)
    mock.click("#scan-main-btn")
    mock.wait_for_timeout(1500)
    check("a scan lands on the monster card", mock.get_attribute("#screen-result", "hidden") is None)
    card_name = mock.inner_text("#result-card .m-name").strip()
    check("the card shows the monster it made", len(card_name) > 0, card_name)
    check("the card's portrait is drawn", mock.evaluate("""() => {
            const c = document.querySelector("#result-card canvas");
            const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
            let painted = 0;
            for (let i = 3; i < d.length; i += 4) if (d[i] > 8) painted++;
            return painted;
          }""") > 3000)
    mock.screenshot(path=f"{SHOTS}/result_card.png")

    mock.click("#battle-random-btn")
    mock.wait_for_timeout(600)
    check("the battle starts", mock.get_attribute("#screen-battle", "hidden") is None)
    check("both fighters are drawn", mock.evaluate("""() => {
            return [...document.querySelectorAll(".fighter canvas")].every((c) => {
              const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
              let painted = 0;
              for (let i = 3; i < d.length; i += 4) if (d[i] > 8) painted++;
              return painted > 500;
            });
          }"""))
    mock.wait_for_selector("#battle-result:not([hidden])", timeout=45000)
    mock.wait_for_timeout(200)
    check("the battle reaches a result", "勝利" in mock.inner_text("#battle-result")
          or "引き分け" in mock.inner_text("#battle-result"), mock.inner_text("#battle-result"))
    mock.screenshot(path=f"{SHOTS}/battle.png")
    mock.click("#battle-again-btn")
    mock.wait_for_timeout(400)
    check("it returns to the 図鑑 with the new monster saved",
          mock.get_attribute("#screen-home", "hidden") is None
          and mock.locator(".dex-item").count() >= 1,
          str(mock.locator(".dex-item").count()))
    check("no page errors during the flow",
          not [e for e in mock_errors if "ERR_" not in e], str(mock_errors))

    browser.close()

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURES"))
for f in failures:
    print("  -", f)
sys.exit(1 if failures else 0)
