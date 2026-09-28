from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

KEY_MAP = {"left": "ArrowLeft", "down": "ArrowDown", "right": "ArrowRight", "up": "ArrowUp"}

# Classic "snake" weight matrix — 4 rotations tried, best orientation wins.
BASE_WEIGHTS = [
    [15, 14, 13, 12],
    [8,  9,  10, 11],
    [7,  6,  5,  4],
    [0,  1,  2,  3],
]

def rotations(m):
    mats = [m]
    cur = m
    for _ in range(3):
        cur = [list(row) for row in zip(*cur[::-1])]
        mats.append(cur)
    return mats

WEIGHT_VARIANTS = rotations(BASE_WEIGHTS) + [
    [row[::-1] for row in m] for m in rotations(BASE_WEIGHTS)
]

def read_grid(page):
    data = page.evaluate("""() => {
        return [...document.querySelectorAll('.tile')].map(t => {
            const style = getComputedStyle(t);
            return {
                left: parseFloat(t.style.left),
                top: parseFloat(t.style.top),
                value: t.dataset.value === 'super' ? 4096 : parseInt(t.dataset.value, 10)
            };
        });
    }""")
    if not data:
        return [[0]*4 for _ in range(4)]
    xs = sorted(set(round(d["left"]) for d in data))
    ys = sorted(set(round(d["top"]) for d in data))
    # cluster xs/ys into up to 4 buckets (positions might not be perfectly distinct if fewer tiles)
    def bucket(vals):
        vals = sorted(vals)
        buckets = []
        for v in vals:
            if not buckets or v - buckets[-1][-1] > 5:
                buckets.append([v])
            else:
                buckets[-1].append(v)
        return [sum(b)/len(b) for b in buckets]
    xb = bucket(xs)
    yb = bucket(ys)
    grid = [[0]*4 for _ in range(4)]
    for d in data:
        col = min(range(len(xb)), key=lambda i: abs(xb[i]-d["left"]))
        row = min(range(len(yb)), key=lambda i: abs(yb[i]-d["top"]))
        grid[row][col] = d["value"]
    return grid

def merge_line(line):
    vals = [v for v in line if v != 0]
    merged = []
    i = 0
    gained = 0
    while i < len(vals):
        if i + 1 < len(vals) and vals[i] == vals[i+1]:
            merged.append(vals[i]*2)
            gained += vals[i]*2
            i += 2
        else:
            merged.append(vals[i])
            i += 1
    merged += [0]*(4-len(merged))
    return merged, gained

def simulate(grid, direction):
    g = [row[:] for row in grid]
    changed = False
    gained = 0
    if direction in ("left", "right"):
        for r in range(4):
            line = g[r][:]
            if direction == "right":
                line = line[::-1]
            new_line, gain = merge_line(line)
            gained += gain
            if direction == "right":
                new_line = new_line[::-1]
            if new_line != g[r]:
                changed = True
            g[r] = new_line
    else:
        for c in range(4):
            line = [g[r][c] for r in range(4)]
            if direction == "down":
                line = line[::-1]
            new_line, gain = merge_line(line)
            gained += gain
            if direction == "down":
                new_line = new_line[::-1]
            for r in range(4):
                if g[r][c] != new_line[r]:
                    changed = True
                g[r][c] = new_line[r]
    return g, changed, gained

def evaluate(grid):
    empty = sum(1 for r in range(4) for c in range(4) if grid[r][c] == 0)
    best = -1e18
    for w in WEIGHT_VARIANTS:
        s = sum(grid[r][c] * w[r][c] for r in range(4) for c in range(4))
        best = max(best, s)
    return best + empty * 800

def choose_move(grid):
    best_dir = None
    best_score = -1e18
    for d in ["left", "down", "right", "up"]:
        g2, changed, gained = simulate(grid, d)
        if not changed:
            continue
        score = evaluate(g2) + gained * 2
        if score > best_score:
            best_score = score
            best_dir = d
    return best_dir

def max_val(grid):
    return max(max(row) for row in grid)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto("http://localhost:8390/2048/index.html")
    page.wait_for_timeout(300)

    for attempt in range(1):
        page.click("#new-game-btn")
        page.wait_for_timeout(100)
        moves = 0
        won = False
        while moves < 400:
            hidden = page.get_attribute("#overlay", "hidden")
            if hidden is None:
                msg = page.inner_text("#overlay-message")
                won = "2048" in msg or "達成" in msg
                break
            grid = read_grid(page)
            d = choose_move(grid)
            if d is None:
                break
            page.keyboard.press(KEY_MAP[d])
            page.wait_for_timeout(140)
            moves += 1

        grid = read_grid(page)
        score = page.inner_text("#score")
        print(f"Attempt {attempt+1}: won={won} moves={moves} max_tile={max_val(grid)} score={score}")
        if won:
            page.screenshot(path=f"{SHOTS}/won_2048.png")
            break

    browser.close()
