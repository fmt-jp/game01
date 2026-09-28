"""Check the key/oil placement and the lantern budget from outside the browser.

Per generated level the script verifies, independently of the game code:
  - the maze is still a perfect maze and every cell is reachable
  - the keys are distinct cells, never the entrance or the exit
  - the oil sits in dead ends whenever the maze has enough of them
  - the "collect every key, then reach the exit" route length the game computed
    matches a route length derived here by BFS + brute-force key ordering
  - the starting fuel really covers that perfect route

Then it plays each maze with a blind explorer that only ever sees what the
game's own reveal rule would show it, to check the fuel budget is survivable
but not generous, and that picking up oil actually matters.
"""
import sys
from collections import deque
from itertools import permutations
from playwright.sync_api import sync_playwright
from _common import CHROMIUM

N, E, S, W = 1, 2, 4, 8
DIRS = (N, E, S, W)
DELTA = {N: (0, -1), E: (1, 0), S: (0, 1), W: (-1, 0)}
OPP = {N: S, E: W, S: N, W: E}


def neighbor(m, cell, d):
    if not (m["cells"][cell] & d):
        return -1
    x, y = cell % m["w"], cell // m["w"]
    dx, dy = DELTA[d]
    return (y + dy) * m["w"] + (x + dx)


def open_neighbors(m, cell):
    return [nb for d in DIRS if (nb := neighbor(m, cell, d)) != -1]


def bfs(m, src):
    dist = [-1] * (m["w"] * m["h"])
    dist[src] = 0
    q = deque([src])
    while q:
        c = q.popleft()
        for nb in open_neighbors(m, c):
            if dist[nb] == -1:
                dist[nb] = dist[c] + 1
                q.append(nb)
    return dist


def structure_problem(m):
    w, h, cells = m["w"], m["h"], m["cells"]
    total = w * h
    passages = 0
    for cell in range(total):
        x, y = cell % w, cell // w
        for d, (dx, dy) in DELTA.items():
            if not (cells[cell] & d):
                continue
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                return f"cell {cell} opens outside the grid"
            if not (cells[ny * w + nx] & OPP[d]):
                return f"one-sided wall between {cell} and {ny*w+nx}"
            passages += 1
    if passages // 2 != total - 1:
        return f"{passages//2} passages, expected {total-1}"
    dist = bfs(m, m["start"])
    if any(v == -1 for v in dist):
        return "unreachable cells"
    return None


def dead_ends(m):
    return {c for c in range(m["w"] * m["h"])
            if sum(1 for d in DIRS if m["cells"][c] & d) == 1}


def route_length(m, keys):
    tables = {m["start"]: bfs(m, m["start"])}
    for k in keys:
        tables[k] = bfs(m, k)
    goal_table = bfs(m, m["goal"])
    if not keys:
        return goal_table[m["start"]]
    best = None
    for order in permutations(keys):
        total = tables[m["start"]][order[0]]
        for a, b in zip(order, order[1:]):
            total += tables[a][b]
        total += goal_table[order[-1]]
        best = total if best is None else min(best, total)
    return best


def items_problem(lv):
    m = lv
    keys, oils = lv["keys"], lv["oils"]
    special = {m["start"], m["goal"]}
    if len(set(keys)) != len(keys):
        return "duplicate keys"
    if len(set(oils)) != len(oils):
        return "duplicate oil"
    if set(keys) & special or set(oils) & special:
        return "item on the entrance or the exit"
    if set(keys) & set(oils):
        return "key and oil share a cell"
    if len(keys) != lv["wantKeys"]:
        return f"{len(keys)} keys, config asked for {lv['wantKeys']}"
    if len(oils) != lv["oilCount"]:
        return f"{len(oils)} oil, plan asked for {lv['oilCount']}"
    pockets = dead_ends(m) - special - set(keys)
    if len(pockets) >= len(oils) and not set(oils) <= pockets:
        return f"oil outside dead ends although {len(pockets)} were free"
    mine = route_length(m, keys)
    if mine != lv["optimal"]:
        return f"route {lv['optimal']} reported, {mine} computed here"
    if lv["startFuel"] < mine:
        return f"start fuel {lv['startFuel']} cannot cover the {mine}-step route"
    return None


# ---------- blind explorer ----------

def sight_limits(m, ratio):
    if ratio <= 0.12:
        return 0, 2
    if ratio <= 0.3:
        return 1, 6
    return 2, m["w"] + m["h"]


def reveal(m, pos, ratio):
    depth, corridor = sight_limits(m, ratio)
    seen = {pos}
    frontier = [pos]
    for _ in range(depth):
        nxt = []
        for c in frontier:
            for nb in open_neighbors(m, c):
                if nb not in seen:
                    seen.add(nb)
                    nxt.append(nb)
        frontier = nxt
    for d in DIRS:
        c = pos
        for _ in range(corridor):
            nb = neighbor(m, c, d)
            if nb == -1:
                break
            seen.add(nb)
            c = nb
    return seen


def run_path(m, pos, d, keys_left, oils_left):
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


def known_bfs(m, src, explored):
    """Distances reachable by walking out of cells we have already seen."""
    dist = {src: 0}
    prev = {src: None}
    q = deque([src])
    while q:
        c = q.popleft()
        if c not in explored:
            continue  # unknown cell: a frontier leaf, we cannot plan past it
        for nb in open_neighbors(m, c):
            if nb not in dist:
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


def play(lv, use_oil=True, oil_threshold=0.55, step_cap=4000):
    m = lv
    keys_left = set(lv["keys"])
    oils_left = set(lv["oils"])
    max_fuel = lv["startFuel"]
    oil_value = lv["oilValue"]
    fuel = max_fuel
    pos = m["start"]
    explored = set()
    seen_items = set()
    steps = 0
    detours = 0

    def look():
        vis = reveal(m, pos, fuel / max_fuel)
        explored.update(vis)
        for c in vis:
            if c in keys_left or c in oils_left:
                seen_items.add(c)

    look()
    for _ in range(step_cap):
        if pos == m["goal"] and not keys_left:
            return {"won": True, "steps": steps, "fuel": fuel, "detours": detours,
                    "slack": fuel / max_fuel}
        dist, prev = known_bfs(m, pos, explored)
        target = None
        if use_oil and fuel / max_fuel < oil_threshold:
            cands = [(dist[c], c) for c in oils_left
                     if c in seen_items and c in dist and dist[c] < fuel]
            if cands:
                target = min(cands)[1]
                detours += 1
        if target is None and keys_left:
            cands = [(dist[c], c) for c in keys_left if c in seen_items and c in dist]
            if cands:
                target = min(cands)[1]
        if target is None and not keys_left and m["goal"] in dist:
            target = m["goal"]
        if target is None:
            cands = [(d, c) for c, d in dist.items() if c not in explored]
            if not cands:
                return {"won": False, "steps": steps, "fuel": fuel,
                        "reason": "nowhere left to look", "detours": detours}
            target = min(cands)[1]
        if target == pos:
            return {"won": False, "steps": steps, "fuel": fuel,
                    "reason": "stuck on target", "detours": detours}

        path = run_path(m, pos, first_dir(m, prev, target), keys_left, oils_left)
        if not path:
            return {"won": False, "steps": steps, "fuel": fuel,
                    "reason": "run rule refused to move", "detours": detours}
        for cell in path:
            pos = cell
            steps += 1
            fuel -= 1
            if pos in keys_left:
                keys_left.discard(pos)
                seen_items.discard(pos)
            if pos in oils_left:
                oils_left.discard(pos)
                seen_items.discard(pos)
                fuel = min(max_fuel, fuel + oil_value)
            look()
            if pos == m["goal"] and not keys_left:
                break
            if fuel <= 0:
                return {"won": False, "steps": steps, "fuel": 0,
                        "reason": "lantern died", "detours": detours,
                        "keysLeft": len(keys_left)}
    return {"won": False, "steps": steps, "fuel": fuel, "reason": "step cap",
            "detours": detours}


GEN = """
([levels, per]) => {
  const out = [];
  for (const level of levels) {
    for (let i = 0; i < per; i++) {
      const cfg = MazeGen.levelConfig(level);
      const maze = MazeGen.generate(cfg.w, cfg.h);
      const items = MazeGen.placeItems(maze, cfg.keys, MazeGen.oilCountFor(maze));
      const plan = MazeGen.fuelPlan(maze, items.keys);
      out.push({
        level, w: maze.w, h: maze.h, cells: Array.from(maze.cells),
        start: maze.start, goal: maze.goal, goalDistance: maze.goalDistance,
        wantKeys: cfg.keys, keys: items.keys, oils: items.oils,
        oilCount: plan.oilCount, optimal: plan.optimal,
        startFuel: plan.startFuel, oilValue: plan.oilValue,
      });
    }
  }
  return out;
}
"""

per = int(sys.argv[1]) if len(sys.argv) > 1 else 15
levels = [1, 3, 5, 8]

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://localhost:8390/maze/index.html")
    page.wait_for_timeout(400)
    data = page.evaluate(GEN, [levels, per])
    timing = page.evaluate("""() => {
      const out = {};
      for (const level of [1,3,5,8]) {
        const cfg = MazeGen.levelConfig(level);
        const t = [];
        for (let i=0;i<30;i++){
          const t0 = performance.now();
          const m = MazeGen.generate(cfg.w, cfg.h);
          const it = MazeGen.placeItems(m, cfg.keys, MazeGen.oilCountFor(m));
          MazeGen.fuelPlan(m, it.keys);
          t.push(performance.now()-t0);
        }
        t.sort((a,b)=>a-b);
        out[`lv${level}`] = {median:+t[15].toFixed(2), worst:+t[29].toFixed(2)};
      }
      return out;
    }""")
    print("page errors:", [e for e in errors if "ERR_" not in e])
    browser.close()

fails = 0
for i, lv in enumerate(data):
    problem = structure_problem(lv) or items_problem(lv)
    if problem:
        fails += 1
        print(f"  lv{lv['level']} #{i}: FAIL: {problem}")
print(f"checked {len(data)} generated levels, failures: {fails}")

by_level = {}
for lv in data:
    by_level.setdefault(lv["level"], []).append(lv)

print("\nper level (generation):")
for level, group in sorted(by_level.items()):
    opt = [g["optimal"] for g in group]
    print(f"  lv{level} {group[0]['w']}x{group[0]['h']} keys={group[0]['wantKeys']} "
          f"oil={group[0]['oilCount']} route min={min(opt)} avg={sum(opt)/len(opt):.0f} max={max(opt)} "
          f"fuel={group[0]['startFuel']}(+{group[0]['oilValue']}/can)")

print("\nblind explorer (only sees what the lantern shows):")
for label, use_oil in (("grabs oil", True), ("ignores oil", False)):
    print(f"  strategy: {label}")
    for level, group in sorted(by_level.items()):
        results = [play(g, use_oil=use_oil) for g in group]
        won = [r for r in results if r["won"]]
        rate = len(won) / len(results) * 100
        extra = ""
        if won:
            slack = sum(r["slack"] for r in won) / len(won)
            walk = sum(r["steps"] for r in won) / len(won)
            optimal = sum(g["optimal"] for g in group) / len(group)
            extra = (f" avg {walk:.0f} steps vs {optimal:.0f} perfect, "
                     f"fuel left {slack*100:.0f}%")
        reasons = {}
        for r in results:
            if not r["won"]:
                reasons[r.get("reason", "?")] = reasons.get(r.get("reason", "?"), 0) + 1
        print(f"    lv{level}: cleared {len(won)}/{len(results)} ({rate:.0f}%){extra}"
              + (f"  lost: {reasons}" if reasons else ""))

print("\ngeneration ms:", timing)
