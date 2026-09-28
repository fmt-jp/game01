"""Play めいろ探検 through its own buttons and check every rule from outside.

The RNG is seeded before load, so this script regenerates the exact maze the
game is showing and re-implements the run rule, the fuel drain, the oil refill
and the key gate independently. Every button press is followed by asserting the
on-screen key counter and fuel readout against the numbers computed here, so a
disagreement between the two implementations fails the test.

Covered: the key-gated exit (walking onto it early must NOT clear the level),
collecting every key and escaping, the lantern running dry, and the retry that
keeps the map you already uncovered.
"""
import sys
from collections import deque
from itertools import permutations
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

N, E, S, W = 1, 2, 4, 8
DIRS = (N, E, S, W)
DELTA = {N: (0, -1), E: (1, 0), S: (0, 1), W: (-1, 0)}
OPP = {N: S, E: W, S: N, W: E}
BUTTON = {N: "#btn-up", E: "#btn-right", S: "#btn-down", W: "#btn-left"}

SEED_SCRIPT = """
(() => {
  let state = 123456789;
  window.__seed = (n) => { state = n >>> 0; };
  window.__seed(20260926);
  Math.random = () => {
    state |= 0; state = (state + 0x6D2B79F5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
})();
"""

failures = []


def check(label, ok, detail=""):
    if ok:
        print(f"    ok   {label}")
    else:
        failures.append(f"{label}: {detail}")
        print(f"    FAIL {label}  {detail}")


def neighbor(m, cell, d):
    if not (m["cells"][cell] & d):
        return -1
    x, y = cell % m["w"], cell // m["w"]
    dx, dy = DELTA[d]
    return (y + dy) * m["w"] + (x + dx)


def bfs(m, src):
    dist = {src: 0}
    prev = {src: None}
    q = deque([src])
    while q:
        c = q.popleft()
        for d in DIRS:
            nb = neighbor(m, c, d)
            if nb != -1 and nb not in dist:
                dist[nb] = dist[c] + 1
                prev[nb] = c
                q.append(nb)
    return dist, prev


def first_dir(m, prev, target):
    cur = target
    while prev[cur] is not None and prev[prev[cur]] is not None:
        cur = prev[cur]
    src = prev[cur]
    return next(d for d in DIRS if neighbor(m, src, d) == cur)


def run_path(m, pos, d, keys_left, oils_left):
    """Independent re-implementation of the game's run rule."""
    path = []
    cell, heading = pos, d
    for _ in range(m["w"] * m["h"]):
        nxt = neighbor(m, cell, heading)
        if nxt == -1:
            break
        path.append(nxt)
        cell = nxt
        if cell == m["goal"] and not keys_left:
            break
        if cell in keys_left or cell in oils_left:
            break
        exits = [x for x in DIRS if x != OPP[heading] and (m["cells"][cell] & x)]
        if len(exits) != 1:
            break
        heading = exits[0]
    return path


def key_order(m, keys):
    tables = {c: bfs(m, c)[0] for c in [m["start"], m["goal"], *keys]}
    best, order = None, None
    for perm in permutations(keys):
        total = tables[m["start"]][perm[0]]
        for a, b in zip(perm, perm[1:]):
            total += tables[a][b]
        total += tables[m["goal"]][perm[-1]]
        if best is None or total < best:
            best, order = total, perm
    return list(order)


class Sim:
    """Mirror of the game's state, advanced one button press at a time."""

    def __init__(self, lv):
        self.m = lv
        self.keys_left = set(lv["keys"])
        self.oils_left = set(lv["oils"])
        self.max_fuel = lv["startFuel"]
        self.oil_value = lv["oilValue"]
        self.fuel = self.max_fuel
        self.pos = lv["start"]
        self.total_keys = len(lv["keys"])
        self.dead = False
        self.cleared = False
        self.goal_visits = 0

    def press(self, d):
        path = run_path(self.m, self.pos, d, self.keys_left, self.oils_left)
        if not path:
            return None
        for cell in path:
            self.pos = cell
            self.fuel -= 1
            if cell == self.m["goal"]:
                self.goal_visits += 1
            self.keys_left.discard(cell)
            if cell in self.oils_left:
                self.oils_left.discard(cell)
                self.fuel = min(self.max_fuel, self.fuel + self.oil_value)
            if self.pos == self.m["goal"] and not self.keys_left:
                self.cleared = True
                return path
            if self.fuel <= 0:
                self.fuel = 0
                self.dead = True
                return path
        return path

    def hud(self):
        return (f"{self.total_keys - len(self.keys_left)}/{self.total_keys}",
                str(max(0, self.fuel)))


def drive(page, sim, d, path_len):
    page.click(BUTTON[d])
    page.wait_for_timeout(path_len * 55 + 110)
    return page.inner_text("#key-status").strip(), page.inner_text("#fuel-status").strip()


def unexplored_pixels(page):
    return page.evaluate("""() => {
      const c = document.getElementById("board");
      const g = c.getContext("2d");
      const d = g.getImageData(0, 0, c.width, c.height).data;
      let dark = 0;
      for (let i = 0; i < d.length; i += 4) {
        if (d[i] === 13 && d[i+1] === 21 && d[i+2] === 38) dark++;
      }
      return dark;
    }""")


LEVEL_SNAPSHOT = """
([seed, level]) => {
  window.__seed(seed);
  const cfg = MazeGen.levelConfig(level);
  const maze = MazeGen.generate(cfg.w, cfg.h);
  const items = MazeGen.placeItems(maze, cfg.keys, MazeGen.oilCountFor(maze));
  const plan = MazeGen.fuelPlan(maze, items.keys);
  return {w: maze.w, h: maze.h, cells: Array.from(maze.cells), start: maze.start,
          goal: maze.goal, keys: items.keys, oils: items.oils,
          startFuel: plan.startFuel, oilValue: plan.oilValue, optimal: plan.optimal};
}
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 390, "height": 844},
                              has_touch=True, is_mobile=True)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(SEED_SCRIPT)
    page.goto("http://localhost:8390/maze/index.html")
    page.wait_for_timeout(500)
    page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
    page.screenshot(path=f"{SHOTS}/maze_start.png")

    # ---- 1. the exit stays shut until every key is in hand -------------------
    print("\n[1] key-gated exit (level 1)")
    seed = 77001
    page.evaluate("(s)=>window.__seed(s)", seed)
    page.click("#new-btn")
    page.wait_for_timeout(250)
    lv = page.evaluate(LEVEL_SNAPSHOT, [seed, 1])
    sim = Sim(lv)
    check("HUD starts at 0 keys and full fuel",
          (page.inner_text("#key-status").strip(), page.inner_text("#fuel-status").strip())
          == (f"0/{len(lv['keys'])}", str(lv["startFuel"])),
          f"screen={page.inner_text('#key-status')}/{page.inner_text('#fuel-status')} "
          f"expected=0/{len(lv['keys'])} {lv['startFuel']}")

    # Walk straight at the exit, ignoring the keys.
    for _ in range(80):
        if sim.goal_visits > 0 or sim.dead:
            break
        dist, prev = bfs(sim.m, sim.pos)
        if sim.pos == lv["goal"]:
            break
        d = first_dir(sim.m, prev, lv["goal"])
        path = sim.press(d)
        if path is None:
            break
        seen_keys, seen_fuel = drive(page, sim, d, len(path))
        want_keys, want_fuel = sim.hud()
        if (seen_keys, seen_fuel) != (want_keys, want_fuel):
            check("HUD tracks the walk toward the exit", False,
                  f"screen={seen_keys}/{seen_fuel} sim={want_keys}/{want_fuel}")
            break
    check("the run really passed over the exit cell", sim.goal_visits > 0,
          f"goal_visits={sim.goal_visits}")
    check("standing on a locked exit does not clear the level",
          page.get_attribute("#overlay", "hidden") is not None and not sim.cleared,
          f"keys left in sim: {len(sim.keys_left)}")
    page.screenshot(path=f"{SHOTS}/maze_locked.png")

    # ---- 2. collect the keys, then escape -----------------------------------
    # A fresh maze: phase 1 deliberately wasted fuel walking at a locked exit.
    print("\n[2] collect every key and escape")
    seed = 77002
    page.evaluate("(s)=>window.__seed(s)", seed)
    page.click("#new-btn")
    page.wait_for_timeout(250)
    lv = page.evaluate(LEVEL_SNAPSHOT, [seed, 1])
    sim = Sim(lv)
    order = [k for k in key_order(sim.m, lv["keys"]) if k in sim.keys_left]
    presses = 0
    while not sim.cleared and not sim.dead and presses < 300:
        order = [k for k in order if k in sim.keys_left]
        target = order[0] if order else lv["goal"]
        dist, prev = bfs(sim.m, sim.pos)
        if target == sim.pos:
            order = order[1:]
            continue
        d = first_dir(sim.m, prev, target)
        path = sim.press(d)
        presses += 1
        seen_keys, seen_fuel = drive(page, sim, d, len(path))
        want_keys, want_fuel = sim.hud()
        if (seen_keys, seen_fuel) != (want_keys, want_fuel):
            check(f"HUD after press {presses}", False,
                  f"screen={seen_keys}/{seen_fuel} sim={want_keys}/{want_fuel}")
            break
    check("every press matched the independent simulation",
          not any("HUD after press" in f for f in failures))
    check("the level cleared once all keys were collected", sim.cleared,
          f"cleared={sim.cleared} dead={sim.dead} keys_left={len(sim.keys_left)}")
    page.wait_for_timeout(200)
    check("the clear overlay is showing",
          page.get_attribute("#overlay", "hidden") is None)
    if page.get_attribute("#overlay", "hidden") is None:
        print("      overlay:", page.inner_text("#overlay-message"), "|",
              page.inner_text("#overlay-sub"))
        check("the clear overlay offers the next maze only",
              page.get_attribute("#overlay-alt-btn", "hidden") is not None,
              "the retry button should be hidden after a win")
    print(f"      route: perfect {lv['optimal']} steps, walked with "
          f"{lv['startFuel']}->{max(0,sim.fuel)} fuel left")
    page.screenshot(path=f"{SHOTS}/maze_cleared.png")

    # ---- 3. burn the lantern out, then retry the same maze -------------------
    print("\n[3] the lantern runs dry, and retry keeps the map")
    seed = 77003
    page.evaluate("(s)=>window.__seed(s)", seed)
    page.click("#overlay-btn")          # the clear overlay advances to level 2
    page.wait_for_timeout(250)
    lv2 = page.evaluate(LEVEL_SNAPSHOT, [seed, 2])
    sim = Sim(lv2)
    fresh_dark = unexplored_pixels(page)

    def pace(sim):
        """Longest run that cannot end the level: never empty the key ring."""
        best = None
        for d in DIRS:
            probe = run_path(sim.m, sim.pos, d, sim.keys_left, sim.oils_left)
            if not probe:
                continue
            if not (sim.keys_left - set(probe)):
                continue          # would unlock the exit, and might walk onto it
            if best is None or len(probe) > len(best[1]):
                best = (d, probe)
        return best[0] if best else None

    presses = 0
    while not sim.dead and presses < 400:
        choice = pace(sim)
        if choice is None:
            break
        path = sim.press(choice)
        presses += 1
        seen_keys, seen_fuel = drive(page, sim, choice, len(path))
        want_keys, want_fuel = sim.hud()
        if (seen_keys, seen_fuel) != (want_keys, want_fuel):
            check(f"HUD while burning fuel (press {presses})", False,
                  f"screen={seen_keys}/{seen_fuel} sim={want_keys}/{want_fuel}")
            break
    check("the lantern ran out after wandering", sim.dead,
          f"fuel={sim.fuel} presses={presses}")
    page.wait_for_timeout(250)
    check("the burnout overlay is showing",
          page.get_attribute("#overlay", "hidden") is None)
    if page.get_attribute("#overlay", "hidden") is None:
        print("      overlay:", page.inner_text("#overlay-message"), "|",
              page.inner_text("#overlay-sub"), "|",
              page.inner_text("#overlay-btn"), "/", page.inner_text("#overlay-alt-btn"))
        check("burnout offers both retry and a new maze",
              page.get_attribute("#overlay-alt-btn", "hidden") is None
              and "やり直" in page.inner_text("#overlay-btn"))
    check("fuel readout bottomed out at 0", page.inner_text("#fuel-status").strip() == "0",
          page.inner_text("#fuel-status"))
    page.screenshot(path=f"{SHOTS}/maze_burnout.png")

    dark_after_death = unexplored_pixels(page)
    page.click("#overlay-btn")          # retry the same maze
    page.wait_for_timeout(300)
    dark_after_retry = unexplored_pixels(page)
    check("retry hides the overlay", page.get_attribute("#overlay", "hidden") is not None)
    check("retry refills the lantern and resets the keys",
          (page.inner_text("#key-status").strip(), page.inner_text("#fuel-status").strip())
          == (f"0/{len(lv2['keys'])}", str(lv2["startFuel"])),
          f"screen={page.inner_text('#key-status')}/{page.inner_text('#fuel-status')}")
    check("retry keeps the map you uncovered",
          dark_after_retry < fresh_dark * 0.92,
          f"unexplored pixels: fresh {fresh_dark}, at death {dark_after_death}, "
          f"after retry {dark_after_retry}")
    page.screenshot(path=f"{SHOTS}/maze_retry.png")

    # ---- 4. a fresh maze really is fresh ------------------------------------
    print("\n[4] 新しい迷路にする starts over")
    page.evaluate("""() => {
      const o = document.getElementById("overlay");
      o.hidden = false;
      document.getElementById("overlay-alt-btn").hidden = false;
    }""")
    page.click("#overlay-alt-btn")
    page.wait_for_timeout(300)
    check("a new maze is mostly unexplored again",
          unexplored_pixels(page) > dark_after_retry,
          f"{unexplored_pixels(page)} vs {dark_after_retry}")
    check("level did not advance on a new maze", page.inner_text("#level").strip() == "2",
          page.inner_text("#level"))

    print("\npage errors:", [e for e in errors if "ERR_" not in e])
    browser.close()

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURES"))
for f in failures:
    print("  -", f)
sys.exit(1 if failures else 0)
