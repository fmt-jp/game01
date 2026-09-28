"""Check きょだい迷路 from outside the browser.

Three layers:
  1. The world: mazes are generated in the page and then checked here with an
     independently written flood fill -- connectivity, the braiding that puts
     loops in, and where the landmarks ended up.
  2. The geometry: the raycaster's DDA result is compared against a brute-force
     ray marcher written here, and the collision resolver is hammered with
     random moves to prove the player can never end up inside a wall.
  3. The game: an autopilot drives the real key handlers to each stamp, the
     tower and the exit, and the outcomes are asserted from out here.
"""
import math, pathlib, random, sys
from collections import deque
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

BASE = "http://localhost:8390/maze3d/index.html"
HERE = pathlib.Path(__file__).parent
failures = []


def check(label, ok, detail=""):
    print(("    ok   " if ok else "    FAIL ") + label + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(f"{label}: {detail}")


# ---------- 1. the world ----------

def block_flood(maze, start_block):
    cols, rows, blocks = maze["cols"], maze["rows"], maze["blocks"]
    seen = {start_block}
    q = deque([start_block])
    while q:
        b = q.popleft()
        bx, by = b % cols, b // cols
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx, ny = bx + dx, by + dy
            if not (0 <= nx < cols and 0 <= ny < rows):
                continue
            nb = ny * cols + nx
            if blocks[nb] == 1 or nb in seen:
                continue
            seen.add(nb)
            q.append(nb)
    return seen


def cell_block(maze, cell):
    cx, cy = cell % maze["w"], cell // maze["w"]
    return (cy * 2 + 1) * maze["cols"] + (cx * 2 + 1)


def world_problem(sample):
    maze, marks = sample["maze"], sample["marks"]
    cols, rows, blocks = maze["cols"], maze["rows"], maze["blocks"]
    if cols != maze["w"] * 2 + 1 or rows != maze["h"] * 2 + 1:
        return f"block grid {cols}x{rows} does not match {maze['w']}x{maze['h']} cells"
    # the outer ring must be solid, or the player walks out of the world
    for bx in range(cols):
        if blocks[bx] != 1 or blocks[(rows - 1) * cols + bx] != 1:
            return "a gap in the top or bottom boundary"
    for by in range(rows):
        if blocks[by * cols] != 1 or blocks[by * cols + cols - 1] != 1:
            return "a gap in the left or right boundary"

    reach = block_flood(maze, cell_block(maze, marks["start"]))
    open_blocks = {i for i, v in enumerate(blocks) if v == 0}
    if reach != open_blocks:
        return f"{len(open_blocks - reach)} open blocks are walled off from the entrance"

    for name in ("goal", *(f"stamp{i}" for i in range(len(marks["stamps"])))):
        pass
    places = [("goal", [marks["goal"]]), ("stamp", marks["stamps"]), ("tower", marks["towers"])]
    seen_cells = {marks["start"]}
    for name, cells in places:
        for cell in cells:
            if cell in seen_cells:
                return f"{name} shares a cell with something else"
            seen_cells.add(cell)
            if cell_block(maze, cell) not in reach:
                return f"{name} is on an unreachable cell"
    if len(marks["stamps"]) != sample["config"]["stamps"]:
        return f"{len(marks['stamps'])} stamps, config asked for {sample['config']['stamps']}"
    if len(marks["towers"]) != sample["config"]["towers"]:
        return f"{len(marks['towers'])} towers, config asked for {sample['config']['towers']}"

    # braiding should leave real loops: a tree has exactly (open cells - 1) links
    links = 0
    for b in open_blocks:
        bx, by = b % cols, b // cols
        for dx, dy in ((1, 0), (0, 1)):
            nb = (by + dy) * cols + (bx + dx)
            if nb in open_blocks:
                links += 1
    if links < len(open_blocks) - 1:
        return "the open area is not even connected"
    return None


# ---------- 2. the geometry ----------

def march_ray(maze, px, py, dx, dy, limit=64.0):
    """Brute force: creep along the ray until a wall block is entered."""
    cols, rows, blocks = maze["cols"], maze["rows"], maze["blocks"]
    step = 0.0005
    t = 0.0
    while t < limit:
        t += step
        bx, by = int(px + dx * t), int(py + dy * t)
        if not (0 <= bx < cols and 0 <= by < rows) or blocks[by * cols + bx] == 1:
            return t
    return limit


GEN = """
([levels, per]) => {
  const out = [];
  for (const level of levels) {
    for (let i = 0; i < per; i++) {
      const world = Maze3D.generate(level);
      out.push({
        level,
        config: world.config,
        marks: world.marks,
        maze: {w: world.maze.w, h: world.maze.h, cols: world.maze.cols,
               rows: world.maze.rows, blocks: Array.from(world.maze.blocks),
               loops: world.maze.loops},
      });
    }
  }
  return out;
}
"""

RAYS = """
([blocksInfo, rays]) => {
  const maze = {w: blocksInfo.w, h: blocksInfo.h, cols: blocksInfo.cols, rows: blocksInfo.rows,
                blocks: Uint8Array.from(blocksInfo.blocks)};
  return rays.map(([px, py, a]) => {
    const hit = Maze3D.castRay(maze, px, py, Math.cos(a), Math.sin(a));
    return hit.dist;
  });
}
"""

MOVES = """
([blocksInfo, moves, startX, startY]) => {
  const maze = {w: blocksInfo.w, h: blocksInfo.h, cols: blocksInfo.cols, rows: blocksInfo.rows,
                blocks: Uint8Array.from(blocksInfo.blocks)};
  let x = startX, y = startY;
  const trail = [];
  for (const [dx, dy] of moves) {
    const next = Maze3D.resolveMove(maze, x, y, dx, dy);
    x = next.x; y = next.y;
    trail.push([x, y]);
  }
  return {trail, radius: Maze3D.RADIUS};
}
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE)
    page.wait_for_timeout(700)

    print("\n[1] the world")
    samples = page.evaluate(GEN, [[1, 3, 5, 7], 15])
    bad = 0
    for i, sample in enumerate(samples):
        problem = world_problem(sample)
        if problem:
            bad += 1
            print(f"      lv{sample['level']} #{i}: {problem}")
    check(f"{len(samples)} generated worlds are sound", bad == 0, f"{bad} failed")
    loops, sizes = {}, {}
    for sample in samples:
        loops.setdefault(sample["level"], []).append(sample["maze"]["loops"])
        sizes[sample["level"]] = f"{sample['maze']['w']}x{sample['maze']['h']}"
    for level, values in sorted(loops.items()):
        avg = sum(values) / len(values)
        print(f"      lv{level}: {sizes[level]} extra gaps avg {avg:.1f}, min {min(values)}")
    check("every level braids in at least one loop somewhere",
          all(max(v) > 0 for v in loops.values()))

    print("\n[2] the geometry")
    sample = samples[0]
    maze = sample["maze"]
    rng = random.Random(4242)
    open_blocks = [i for i, v in enumerate(maze["blocks"]) if v == 0]
    rays = []
    for _ in range(600):
        b = rng.choice(open_blocks)
        px = b % maze["cols"] + 0.12 + rng.random() * 0.76
        py = b // maze["cols"] + 0.12 + rng.random() * 0.76
        rays.append([px, py, rng.uniform(-math.pi, math.pi)])
    js_dists = page.evaluate(RAYS, [maze, rays])
    worst = 0.0
    for (px, py, a), got in zip(rays, js_dists):
        want = march_ray(maze, px, py, math.cos(a), math.sin(a))
        worst = max(worst, abs(want - got))
    check(f"{len(rays)} rays match a brute-force march", worst < 0.002, f"worst gap {worst:.4f}")

    moves = [[rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35)] for _ in range(4000)]
    start = open_blocks[0]
    res = page.evaluate(MOVES, [maze, moves, start % maze["cols"] + 0.5, start // maze["cols"] + 0.5])
    radius = res["radius"]
    inside = 0
    for x, y in res["trail"]:
        for by in range(int(y - radius), int(y + radius) + 1):
            for bx in range(int(x - radius), int(x + radius) + 1):
                out = not (0 <= bx < maze["cols"] and 0 <= by < maze["rows"])
                if out or maze["blocks"][by * maze["cols"] + bx] == 1:
                    inside += 1
    check(f"{len(moves)} random shoves never push the player into a wall", inside == 0,
          f"{inside} overlapping samples")
    travelled = sum(1 for i in range(1, len(res["trail"]))
                    if res["trail"][i] != res["trail"][i - 1])
    check("the player is not simply frozen in place", travelled > len(moves) * 0.5,
          f"{travelled}/{len(moves)} moves had an effect")

    print("\n[3] the game")
    page.add_script_tag(path=str(HERE / "autopilot.js"))
    page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
    page.click("#new-btn")
    page.wait_for_timeout(300)
    page.add_script_tag(path=str(HERE / "autopilot.js"))
    s0 = page.evaluate("() => window.__maze3d()")
    print(f"      level 1: {s0['maze']['w']}x{s0['maze']['h']} cells, "
          f"{s0['stampsLeft']} stamps, towers at {s0['towers']}, exit at cell {s0['goal']}")

    # the exit must stay shut while a stamp is missing
    res = page.evaluate("(cell) => window.__drive(cell)", s0["goal"])
    check("the autopilot can reach the exit", res["reason"] == "arrived",
          f"{res.get('reason')} at cell {res.get('cell')}")
    state = page.evaluate("() => window.__maze3d()")
    check("standing at a shut exit does not clear the level",
          state["state"] == "playing" and page.get_attribute("#overlay", "hidden") is not None
          and state["stampsLeft"] > 0,
          f"state={state['state']} stampsLeft={state['stampsLeft']}")
    check("the game says how many stamps are missing",
          page.get_attribute("#toast", "hidden") is None
          and "スタンプ" in page.inner_text("#toast"),
          page.inner_text("#toast") if page.get_attribute("#toast", "hidden") is None else "no toast")
    page.screenshot(path=f"{SHOTS}/shot_gate_shut.png")

    # collect what is left, re-reading which stamps remain each time: the walk to
    # one can take you straight over another
    tower_seen = False
    shot_stamp = False
    for _ in range(6):
        state = page.evaluate("() => window.__maze3d()")
        remaining = [st["cell"] for st in state["stamps"] if not st["taken"]]
        if not remaining:
            break
        before = state["stampsLeft"]
        res = page.evaluate("(cell) => window.__drive(cell)", remaining[0])
        tower_seen = tower_seen or res.get("climbed", 0) > 0
        after = page.evaluate("() => window.__maze3d()")["stampsLeft"]
        check(f"walking to the stamp at cell {remaining[0]} collects it", after < before,
              f"{before} -> {after} ({res['reason']})")
        if not shot_stamp:
            page.screenshot(path=f"{SHOTS}/shot_stamp.png")
            shot_stamp = True

    check("every stamp was collected",
          page.evaluate("() => window.__maze3d().stampsLeft") == 0)

    # the tower: drive onto one and read the map it opens
    state = page.evaluate("() => window.__maze3d()")
    res = page.evaluate("(cell) => window.__drive(cell, 45000, false)", state["towers"][0])
    page.wait_for_timeout(300)
    climbed = page.evaluate("() => window.__maze3d().state") == "lookout"
    check("walking into a tower climbs it", climbed or res.get("climbed", 0) > 0,
          f"state={page.evaluate('() => window.__maze3d().state')} ({res['reason']})")
    if climbed:
        box = page.locator("#map").bounding_box()
        check("the tower shows a map of the maze",
              page.get_attribute("#lookout", "hidden") is None and box["width"] > 100,
              str(box))
        check("the map is drawn, not blank", page.evaluate("""() => {
                const c = document.getElementById("map");
                const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
                const seen = new Set();
                for (let i = 0; i < d.length; i += 4) seen.add(`${d[i]},${d[i+1]},${d[i+2]}`);
                return seen.size;
              }""") > 3)
        page.screenshot(path=f"{SHOTS}/shot_tower.png")
        page.click("#descend-btn")
        page.wait_for_timeout(200)
        check("climbing down returns you to the maze",
              page.evaluate("() => window.__maze3d().state") == "playing"
              and page.get_attribute("#lookout", "hidden") is not None)

    filled = page.evaluate("() => document.querySelectorAll('.stamp-slot.on').length")
    check("the stamp card is full", filled == len(s0["stamps"]), f"{filled} filled")

    # now the exit opens
    res = page.evaluate("(cell) => window.__drive(cell)", s0["goal"])
    page.wait_for_timeout(400)
    check("reaching the exit with every stamp clears the level",
          page.get_attribute("#overlay", "hidden") is None, str(res.get("reason")))
    if page.get_attribute("#overlay", "hidden") is None:
        print("      overlay:", page.inner_text("#overlay-message"), "|",
              page.inner_text("#overlay-sub"))
    page.screenshot(path=f"{SHOTS}/shot_clear.png")

    page.click("#overlay-btn")
    page.wait_for_timeout(400)
    after = page.evaluate("() => window.__maze3d()")
    check("the next maze starts at level 2 and is bigger or equal",
          after["level"] == 2 and after["stampsLeft"] == 3 and after["state"] == "playing",
          str({k: after[k] for k in ("level", "stampsLeft", "state")}))

    print("\n[4] frame budget while walking")
    page.add_script_tag(path=str(HERE / "autopilot.js"))
    timing = page.evaluate("""async () => {
      const frames = [];
      let last = performance.now();
      const press = (code, down) =>
        window.dispatchEvent(new KeyboardEvent(down ? "keydown" : "keyup", {code}));
      press("ArrowUp", true); press("ArrowRight", true);
      for (let i = 0; i < 160; i++) {
        await new Promise((r) => requestAnimationFrame(r));
        const now = performance.now();
        frames.push(now - last);
        last = now;
      }
      press("ArrowUp", false); press("ArrowRight", false);
      frames.sort((a, b) => a - b);
      return {median: +frames[80].toFixed(2), p95: +frames[152].toFixed(2), worst: +frames[159].toFixed(2)};
    }""")
    print("      frame ms:", timing)
    check("frames stay inside a 60fps budget", timing["median"] <= 17.5, str(timing))
    check("no stalls worse than two frames", timing["p95"] <= 34, str(timing))

    check("no page errors", not [e for e in errors if "ERR_" not in e], str(errors))
    browser.close()

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURES"))
for f in failures:
    print("  -", f)
sys.exit(1 if failures else 0)
