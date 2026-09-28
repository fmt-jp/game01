"""Generate mazes in the browser, then check each one independently.

Per maze:
  - walls are symmetric (if A opens toward B, B opens back toward A)
  - every cell is reachable from the start
  - it is a perfect maze: exactly cells-1 passages, so no loops and no islands
  - the recorded goal really is a farthest cell, and its distance matches
"""
import sys
from collections import deque
from playwright.sync_api import sync_playwright
from _common import CHROMIUM

N, E, S, W = 1, 2, 4, 8
DELTA = {N: (0, -1), E: (1, 0), S: (0, 1), W: (-1, 0)}
OPP = {N: S, E: W, S: N, W: E}


def check(maze):
    w, h = maze["w"], maze["h"]
    cells = maze["cells"]
    total = w * h
    if len(cells) != total:
        return f"cell count {len(cells)} != {total}"

    passages = 0
    for cell in range(total):
        x, y = cell % w, cell // w
        for d, (dx, dy) in DELTA.items():
            if not (cells[cell] & d):
                continue
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                return f"cell {cell} opens outside the grid"
            nb = ny * w + nx
            if not (cells[nb] & OPP[d]):
                return f"one-sided wall between {cell} and {nb}"
            passages += 1
    passages //= 2
    if passages != total - 1:
        return f"{passages} passages, expected {total - 1} (loops or islands)"

    dist = [-1] * total
    dist[maze["start"]] = 0
    q = deque([maze["start"]])
    while q:
        cell = q.popleft()
        x, y = cell % w, cell // w
        for d, (dx, dy) in DELTA.items():
            if cells[cell] & d:
                nb = (y + dy) * w + (x + dx)
                if dist[nb] == -1:
                    dist[nb] = dist[cell] + 1
                    q.append(nb)
    if any(v == -1 for v in dist):
        return f"{sum(1 for v in dist if v == -1)} unreachable cells"

    far = max(dist)
    if dist[maze["goal"]] != far:
        return f"goal distance {dist[maze['goal']]} is not the maximum {far}"
    if maze.get("goalDistance") != far:
        return f"reported goalDistance {maze.get('goalDistance')} != {far}"
    return None


GEN = """
([count]) => {
  const sizes = [[9,9],[11,11],[13,13],[15,15]];
  const out = [];
  for (let i = 0; i < count; i++) {
    const [w, h] = sizes[i % sizes.length];
    const m = MazeGen.generate(w, h);
    out.push({w: m.w, h: m.h, cells: Array.from(m.cells), start: m.start,
              goal: m.goal, goalDistance: m.goalDistance});
  }
  return out;
}
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://localhost:8390/maze/index.html")
    page.wait_for_timeout(400)
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    mazes = page.evaluate(GEN, [count])
    timing = page.evaluate("""() => {
      const out = {};
      for (const [w,h] of [[9,9],[11,11],[13,13],[15,15]]) {
        const t = [];
        for (let i=0;i<40;i++){const t0=performance.now();MazeGen.generate(w,h);t.push(performance.now()-t0);}
        t.sort((a,b)=>a-b);
        out[`${w}x${h}`] = {median:+t[20].toFixed(2), worst:+t[39].toFixed(2)};
      }
      return out;
    }""")
    print("page errors:", errors)
    browser.close()

fails = 0
dists = {}
for i, m in enumerate(mazes):
    problem = check(m)
    if problem:
        fails += 1
        print(f"  #{i} ({m['w']}x{m['h']}): FAIL: {problem}")
    key = f"{m['w']}x{m['h']}"
    dists.setdefault(key, []).append(m["goalDistance"])

print(f"checked {len(mazes)} mazes, failures: {fails}")
for k, v in sorted(dists.items()):
    print(f"  {k}: goal distance min={min(v)} avg={sum(v)/len(v):.1f} max={max(v)}")
print("generation ms:", timing)
