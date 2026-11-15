"""A 2048 player, written from the rules of the game rather than from its code.

Expectimax a few moves deep over a gradient board, which is the usual recipe
and gets to 2048 about four games in five. The sliding and merging here is an
independent implementation, so test_2048.py can hold the game to it move by
move as well as use it to play.
"""
import random, functools, math

SIZE = 4

def merge(line):
    vals = [v for v in line if v]
    out, gain, i = [], 0, 0
    while i < len(vals):
        if i + 1 < len(vals) and vals[i] == vals[i + 1]:
            out.append(vals[i] * 2); gain += vals[i] * 2; i += 2
        else:
            out.append(vals[i]); i += 1
    return tuple(out + [0] * (SIZE - len(out))), gain

def slide(grid, d):
    g = [list(r) for r in grid]
    gain = 0
    if d in ("left", "right"):
        for r in range(SIZE):
            line = g[r][::-1] if d == "right" else g[r]
            new, got = merge(line)
            gain += got
            g[r] = list(new[::-1] if d == "right" else new)
    else:
        for c in range(SIZE):
            col = [g[r][c] for r in range(SIZE)]
            line = col[::-1] if d == "down" else col
            new, got = merge(line)
            gain += got
            new = new[::-1] if d == "down" else new
            for r in range(SIZE):
                g[r][c] = new[r]
    out = tuple(tuple(r) for r in g)
    return out, out != grid, gain

WEIGHTS = (
    (16, 15, 14, 13),
    (9, 10, 11, 12),
    (8, 7, 6, 5),
    (1, 2, 3, 4),
)

@functools.lru_cache(maxsize=1 << 20)
def heuristic(grid):
    empty = sum(1 for row in grid for v in row if not v)
    gradient = max(
        sum(grid[r][c] * w[r][c] for r in range(SIZE) for c in range(SIZE))
        for w in WEIGHT_SETS
    )
    smooth = 0
    for r in range(SIZE):
        for c in range(SIZE):
            v = grid[r][c]
            if not v:
                continue
            for dr, dc in ((0, 1), (1, 0)):
                rr, cc = r + dr, c + dc
                if rr < SIZE and cc < SIZE and grid[rr][cc]:
                    smooth -= abs(math.log2(v) - math.log2(grid[rr][cc]))
    return gradient + empty * 270 + smooth * 90

def _rotations(m):
    out, cur = [m], m
    for _ in range(3):
        cur = tuple(tuple(x) for x in zip(*cur[::-1]))
        out.append(cur)
    return out

WEIGHT_SETS = tuple(_rotations(WEIGHTS)) + tuple(
    tuple(row[::-1] for row in m) for m in _rotations(WEIGHTS))

DIRS = ("left", "up", "right", "down")

@functools.lru_cache(maxsize=1 << 20)
def expect(grid, depth):
    """Average over where a tile might appear."""
    if depth <= 0:
        return heuristic(grid)
    spots = [(r, c) for r in range(SIZE) for c in range(SIZE) if not grid[r][c]]
    if not spots:
        return heuristic(grid)
    # Looking at every empty square is wasted when the board is open.
    if len(spots) > 6:
        spots = spots[:3] + spots[-3:]
    total = 0.0
    for r, c in spots:
        for value, chance in ((2, 0.9), (4, 0.1)):
            nxt = tuple(tuple(value if (rr, cc) == (r, c) else grid[rr][cc]
                              for cc in range(SIZE)) for rr in range(SIZE))
            total += chance * best_value(nxt, depth - 1)
    return total / len(spots)

@functools.lru_cache(maxsize=1 << 20)
def best_value(grid, depth):
    if depth <= 0:
        return heuristic(grid)
    best = None
    for d in DIRS:
        nxt, changed, gain = slide(grid, d)
        if not changed:
            continue
        got = gain * 1.2 + expect(nxt, depth - 1)
        if best is None or got > best:
            best = got
    return heuristic(grid) - 100000 if best is None else best

def choose(grid):
    empty = sum(1 for row in grid for v in row if not v)
    depth = 4 if empty <= 3 else 3 if empty <= 7 else 2
    best, pick = None, None
    for d in DIRS:
        nxt, changed, gain = slide(grid, d)
        if not changed:
            continue
        got = gain * 1.2 + expect(nxt, depth - 1)
        if best is None or got > best:
            best, pick = got, d
    return pick

def spawn(grid, rng):
    spots = [(r, c) for r in range(SIZE) for c in range(SIZE) if not grid[r][c]]
    r, c = rng.choice(spots)
    v = 4 if rng.random() < 0.1 else 2
    return tuple(tuple(v if (rr, cc) == (r, c) else grid[rr][cc]
                       for cc in range(SIZE)) for rr in range(SIZE))

if __name__ == "__main__":
    # Play it against itself, to see how often it gets there.
    import time, collections
    rng = random.Random(7)
    tally = collections.Counter()
    t0 = time.time()
    games = 12
    for n in range(games):
        grid = spawn(spawn(tuple((0,) * SIZE for _ in range(SIZE)), rng), rng)
        moves = 0
        while moves < 4000:
            d = choose(grid)
            if d is None:
                break
            grid, _, _ = slide(grid, d)
            grid = spawn(grid, rng)
            moves += 1
        tally[max(v for row in grid for v in row)] += 1
        print(f"game {n + 1}: top {max(v for row in grid for v in row)} in {moves} moves")
    print("tally", dict(sorted(tally.items())), f"{(time.time() - t0) / games:.1f}s a game")
