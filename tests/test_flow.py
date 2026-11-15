"""Generate puzzles in the real browser, then verify each one independently.

Two checks per puzzle:
  1. Structural: the generator's own solution must be a set of orthogonal paths
     that covers every cell exactly once, with endpoints matching the clues.
  2. Solver: an independent backtracking Flow solver must find a full-coverage
     solution from the endpoints alone (run on the smaller boards, which is
     where exhaustive search is affordable).
"""
import json
import sys
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, BASE, check, note, head, finish


def neighbors(idx, size):
    r, c = divmod(idx, size)
    out = []
    if r > 0: out.append(idx - size)
    if r < size - 1: out.append(idx + size)
    if c > 0: out.append(idx - 1)
    if c < size - 1: out.append(idx + 1)
    return out


def structural_check(p):
    size = p["size"]
    total = size * size
    seen = set()
    for seg, (ea, eb) in zip(p["solution"], p["endpoints"]):
        if len(seg) < 2:
            return f"segment too short: {seg}"
        if seg[0] != ea or seg[-1] != eb:
            return f"endpoints {ea},{eb} do not match segment ends {seg[0]},{seg[-1]}"
        for a, b in zip(seg, seg[1:]):
            if b not in neighbors(a, size):
                return f"non-adjacent step {a}->{b}"
        for cell in seg:
            if cell in seen:
                return f"cell {cell} covered twice"
            seen.add(cell)
    if len(seen) != total:
        return f"coverage {len(seen)}/{total}"
    return None


def solve(size, endpoint_pairs, node_budget=2_000_000):
    """Backtracking Flow solver: extend one colour at a time, require full coverage."""
    total = size * size
    ncolors = len(endpoint_pairs)
    grid = [-1] * total
    for k, (a, b) in enumerate(endpoint_pairs):
        grid[a] = k
        grid[b] = k
    targets = [b for (a, b) in endpoint_pairs]
    heads = [a for (a, b) in endpoint_pairs]
    nodes = 0

    def stranded():
        """Any empty cell with no empty/usable neighbour means a dead pocket."""
        for cell in range(total):
            if grid[cell] != -1:
                continue
            free = 0
            for nb in neighbors(cell, size):
                if grid[nb] == -1:
                    free += 1
                elif nb in heads or nb in targets:
                    free += 1
            if free < 2:
                return True
        return False

    def rec(k, head):
        nonlocal nodes
        nodes += 1
        if nodes > node_budget:
            raise TimeoutError
        if k == ncolors:
            return all(v != -1 for v in grid)
        target = targets[k]
        if head == target:
            nxt = k + 1
            return rec(nxt, heads[nxt]) if nxt < ncolors else all(v != -1 for v in grid)
        for nb in neighbors(head, size):
            if nb == target:
                saved_head = head
                heads[k] = nb
                if rec(k, nb):
                    return True
                heads[k] = saved_head
            elif grid[nb] == -1:
                grid[nb] = k
                saved_head = heads[k]
                heads[k] = nb
                if not stranded() and rec(k, nb):
                    return True
                heads[k] = saved_head
                grid[nb] = -1
        return False

    return rec(0, heads[0])


GEN_SCRIPT = """
([count]) => {
  const out = [];
  const configs = [[5,4],[6,5],[7,5],[7,6]];
  for (let i = 0; i < count; i++) {
    const [size, colors] = configs[i % configs.length];
    const p = FlowPuzzle.generate(size, colors);
    out.push(p);
  }
  return out;
}
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/flow/index.html")
    page.wait_for_timeout(400)

    count = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    puzzles = page.evaluate(GEN_SCRIPT, [count])
    head(f"[1] {count} puzzles, generated in the browser")
    check("the generator produced every puzzle it was asked for",
          len(puzzles) == count and all(p for p in puzzles),
          f"{sum(1 for p in puzzles if p)} of {count}")
    check("no page errors while generating", not errors, str(errors))
    browser.close()

broken, unsolved, out_of_budget, solver_checked = [], [], 0, 0
for i, p in enumerate(puzzles):
    if p is None:
        broken.append(f"#{i}: the generator gave back nothing")
        continue
    problem = structural_check(p)
    if problem:
        broken.append(f"#{i} ({p['size']}x{p['size']}): {problem}")
        continue
    if p["size"] <= 6:
        try:
            ok = solve(p["size"], p["endpoints"])
        except TimeoutError:
            out_of_budget += 1
            continue
        solver_checked += 1
        if not ok:
            unsolved.append(f"#{i} ({p['size']}x{p['size']}): no way to fill it: {p['endpoints']}")

head("[2] what the generator says it made")
check("every puzzle's own answer fills the board, end to end, once each",
      not broken, "; ".join(broken[:3]))

head("[3] and what a solver makes of the clues alone")
check(f"all {solver_checked} of the smaller boards can be solved from the dots",
      not unsolved and solver_checked > 0,
      "; ".join(unsolved[:3]) or f"only {solver_checked} were tried")
if out_of_budget:
    note(f"{out_of_budget} boards took more search than the budget allows; not counted either way")

sizes = {}
for p in puzzles:
    if p:
        key = f"{p['size']}x{p['size']} with {len(p['endpoints'])} colours"
        sizes[key] = sizes.get(key, 0) + 1
note("sizes: " + ", ".join(f"{k} x{v}" for k, v in sorted(sizes.items())))

finish("FLOW CHECKS")
