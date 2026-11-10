"""かさねとり: the pile, checked from outside the game.

The game builds a pile in the browser and hands it out; everything that
decides whether it is any good is in tiles_rules.py, written from the rules of
the game rather than from its code. If the two disagree about what can be
taken, phase 4 says so.
"""
import json
import random
import sys
import collections
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE
import tiles_rules as R

failures = []


def check(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(label)


def note(text):
    print("       " + text)


def deal(page, level, count):
    """Ask the game for freshly dealt piles at one level."""
    return page.evaluate("""([level, count]) => {
      const out = [];
      for (let i = 0; i < count; i += 1) {
        const b = Board.deal(level);
        if (!b) { out.push(null); continue; }
        out.push({ w: b.w, d: b.d, layers: b.layers,
                   tiles: b.tiles.map((t) => ({ x: t.x, y: t.y, z: t.z, kind: t.kind })),
                   solution: b.solution });
      }
      return out;
    }""", [level, count])


LEVELS = [1, 2, 4, 6, 9, 12, 16, 20]
PER_LEVEL = 8

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/tiles/index.html")
    page.wait_for_timeout(600)

    piles = {}
    for level in LEVELS:
        piles[level] = [p for p in deal(page, level, PER_LEVEL) if p]

    # ---------------------------------------------------------------
    print("[1] the piles it builds")
    dealt = all(len(piles[lv]) == PER_LEVEL for lv in LEVELS)
    check("every ask for a pile produced one", dealt,
          str({lv: len(piles[lv]) for lv in LEVELS}))

    bad = []
    for level, group in piles.items():
        for pile in group:
            tiles = pile["tiles"]
            seen = collections.Counter((t["x"], t["y"], t["z"]) for t in tiles)
            if max(seen.values()) > 1:
                bad.append(f"lv{level}: two tiles in one place")
            places = set(seen)
            for t in tiles:
                if t["z"] > 0 and (t["x"], t["y"], t["z"] - 1) not in places:
                    bad.append(f"lv{level}: a tile at z={t['z']} rests on nothing")
            if len(tiles) % 2:
                bad.append(f"lv{level}: an odd number of tiles cannot be paired off")
            faces = collections.Counter(t["kind"] for t in tiles)
            if any(n % 2 for n in faces.values()):
                bad.append(f"lv{level}: a face appears an odd number of times")
            if any(n > 4 for n in faces.values()):
                bad.append(f"lv{level}: more than four of one face")
            if max(t["x"] for t in tiles) >= pile["w"] or max(t["y"] for t in tiles) >= pile["d"]:
                bad.append(f"lv{level}: a tile sits outside the pile's own box")
            # mirrored down the middle, which is what makes it look built
            heights = collections.Counter((t["x"], t["y"]) for t in tiles)
            for (x, y), n in heights.items():
                if heights.get((pile["w"] - 1 - x, y), 0) != n:
                    bad.append(f"lv{level}: the pile is not mirrored at ({x},{y})")
                    break
    check("every pile is stacked legally and mirrored", not bad, "; ".join(sorted(set(bad))[:3]))

    sizes = {lv: sorted({len(p["tiles"]) for p in piles[lv]}) for lv in LEVELS}
    for lv in LEVELS:
        faces = [len({t["kind"] for t in p["tiles"]}) for p in piles[lv]]
        note(f"lv{lv:>2}: {sizes[lv][0]}-{sizes[lv][-1]} tiles, "
             f"{sum(faces)/len(faces):.0f} different faces")
    grows = all(max(sizes[a]) <= max(sizes[b]) for a, b in zip(LEVELS, LEVELS[1:]))
    check("the piles grow with the level", grows, str(sizes))

    # ---------------------------------------------------------------
    print("\n[2] can they actually be emptied?")
    undecided, unsolvable = 0, []
    for level, group in piles.items():
        for n, pile in enumerate(group):
            got = R.solve(pile["tiles"], seed=level * 100 + n)
            if got is None:
                undecided += 1
            elif got is False:
                unsolvable.append(f"lv{level}#{n}")
            else:
                broken = R.replay(pile["tiles"], got)
                if broken:
                    unsolvable.append(f"lv{level}#{n}: own answer invalid: {broken}")
    total = sum(len(g) for g in piles.values())
    check(f"all {total} piles were emptied by a solver that never saw the game's answer",
          not unsolvable and undecided == 0,
          f"unsolvable {unsolvable[:3]}, undecided {undecided}")

    broken = []
    for level, group in piles.items():
        for n, pile in enumerate(group):
            why = R.replay(pile["tiles"], [tuple(p) for p in pile["solution"]])
            if why:
                broken.append(f"lv{level}#{n}: {why}")
    check("and the order the game dealt them in is legal under these rules",
          not broken, "; ".join(broken[:3]))

    # ---------------------------------------------------------------
    print("\n[3] how hard they are")
    rng = random.Random(11)
    for level in LEVELS:
        rates = []
        for pile in piles[level]:
            live = set(range(len(pile["tiles"])))
            wins = sum(1 for _ in range(30) if R._greedy(pile["tiles"], live, rng) is not None)
            rates.append(wins / 30)
        note(f"lv{level:>2}: careless play clears {100*sum(rates)/len(rates):5.1f}% "
             f"(worst pile {100*min(rates):3.0f}%)")
    easy = sum(sum(1 for _ in range(30) if R._greedy(p["tiles"], set(range(len(p["tiles"]))), rng) is not None) / 30
               for p in piles[1]) / len(piles[1])
    hard = sum(sum(1 for _ in range(30) if R._greedy(p["tiles"], set(range(len(p["tiles"]))), rng) is not None) / 30
               for p in piles[16]) / len(piles[16])
    check("a late pile punishes careless play more than the first one does",
          hard < easy - 0.1, f"lv1 {easy:.2f} vs lv16 {hard:.2f}")

    opening = []
    for group in piles.values():
        for pile in group:
            opening.append(len(R.takeable(pile["tiles"], set(range(len(pile["tiles"]))))))
    check("every pile opens with something to take", min(opening) >= 3,
          f"fewest {min(opening)}")
    note(f"openings offer {min(opening)}-{max(opening)} pairs, {sum(opening)/len(opening):.1f} on average")

    # ---------------------------------------------------------------
    print("\n[4] the game's idea of a free tile, against ours")
    page.evaluate("() => window.__start(9)")
    page.wait_for_timeout(300)
    states, mismatches = 0, []
    for round_ in range(14):
        page.evaluate("(lv) => window.__start(lv)", 4 + round_)
        page.wait_for_timeout(120)
        state = page.evaluate("() => window.__tiles()")
        tiles = [{"x": t["x"], "y": t["y"], "z": t["z"], "kind": t["kind"]} for t in state["tiles"]]
        live = {i for i, t in enumerate(state["tiles"]) if t["alive"]}
        while True:
            theirs = sorted(page.evaluate("() => window.__tiles().free"))
            ours = sorted(R.free_set(tiles, live))
            states += 1
            if theirs != ours:
                mismatches.append(f"{len(live)} tiles left: game {theirs[:6]} vs rules {ours[:6]}")
                break
            options = R.takeable(tiles, live)
            if not options:
                break
            a, b = rng.choice(options)
            page.evaluate("([a, b]) => { window.__tap(a); window.__tap(b); }", [a, b])
            page.wait_for_timeout(30)
            live -= {a, b}
            if page.evaluate("() => window.__tiles().left") != len(live):
                mismatches.append("the game did not take the pair the rules say it should")
                break
    check(f"{states} positions, and the two agreed on every one of them",
          not mismatches, "; ".join(mismatches[:2]))

    # ---------------------------------------------------------------
    print("\n[5] stacking the rest again")
    page.evaluate("() => window.__start(12)")
    page.wait_for_timeout(200)
    before = page.evaluate("() => window.__tiles()")
    bag_before = collections.Counter(t["kind"] for t in before["tiles"] if t["alive"])
    page.evaluate("() => { for (let i = 0; i < 9; i += 1) { const p = window.__pairs(); if (!p.length) break; window.__tap(p[0][0]); window.__tap(p[0][1]); } }")
    page.wait_for_timeout(200)
    mid = page.evaluate("() => window.__tiles()")
    mid_bag = collections.Counter(t["kind"] for t in mid["tiles"] if t["alive"])
    page.evaluate("() => window.__restack()")
    page.wait_for_timeout(200)
    after = page.evaluate("() => window.__tiles()")
    after_bag = collections.Counter(t["kind"] for t in after["tiles"] if t["alive"])
    check("stacking again keeps every face that was still on the pile", mid_bag == after_bag,
          f"{sorted(mid_bag.items())[:4]} vs {sorted(after_bag.items())[:4]}")
    check("and the same places are still filled",
          {(t["x"], t["y"], t["z"]) for t in mid["tiles"] if t["alive"]} ==
          {(t["x"], t["y"], t["z"]) for t in after["tiles"] if t["alive"]})
    tiles = [{"x": t["x"], "y": t["y"], "z": t["z"], "kind": t["kind"]} for t in after["tiles"]]
    live = {i for i, t in enumerate(after["tiles"]) if t["alive"]}
    got = R.solve(tiles, live, seed=5)
    check("and what is left can still be emptied", bool(got) and R.replay(tiles, got, live) is None)
    note(f"{len(live)} tiles were still up, {len(bag_before) - len(mid_bag)} faces had gone")

    # ---------------------------------------------------------------
    print("\n[6] the faces themselves")
    missing = page.evaluate("""() => {
      // A glyph the font cannot have. Anything that draws the same as this is
      // a missing character showing as a box, not a tile face.
      const canvas = document.createElement('canvas');
      canvas.width = 60; canvas.height = 60;
      const ctx = canvas.getContext('2d');
      const draw = (ch) => {
        ctx.clearRect(0, 0, 60, 60);
        ctx.font = '40px "Zen Maru Gothic", "Noto Sans JP", serif';
        ctx.fillText(ch, 6, 46);
        return ctx.getImageData(0, 0, 60, 60).data.join(',');
      };
      const tofu = draw('\\uFFFF');
      const blank = draw(' ');
      const out = [];
      for (const ch of ['一','二','三','四','五','六','七','八','九','萬','東','南','西','北','中','發']) {
        const px = draw(ch);
        if (px === tofu || px === blank) out.push(ch);
      }
      return out;
    }""")
    check("every character on a tile has a glyph to draw it with", not missing, str(missing))

    kinds = page.evaluate("() => Faces.KINDS")
    svgs = page.evaluate("() => Faces.KINDS.map((k) => Faces.svg(k))")
    check("all 34 faces exist and are different", len(kinds) == 34 and len(set(svgs)) == 34,
          f"{len(kinds)} faces, {len(set(svgs))} different drawings")

    check("no page errors", not errors, str(errors))
    page.screenshot(path=f"{SHOTS}/tiles_rules.png")
    browser.close()

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURES"))
for f in failures:
    print("  -", f)
sys.exit(1 if failures else 0)
