import sys
from collections import deque

def parse(level):
    lines = level.strip("\n").split("\n")
    width = max(len(l) for l in lines)
    lines = [l.ljust(width) for l in lines]
    walls = set()
    goals = set()
    boxes = set()
    player = None
    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            if ch == "#":
                walls.add((x, y))
            elif ch == ".":
                goals.add((x, y))
            elif ch == "$":
                boxes.add((x, y))
            elif ch == "*":
                goals.add((x, y))
                boxes.add((x, y))
            elif ch == "@":
                player = (x, y)
            elif ch == "+":
                goals.add((x, y))
                player = (x, y)
    return walls, goals, frozenset(boxes), player, width, len(lines)

DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}

def solve(level, max_states=2_000_000):
    walls, goals, boxes0, player0, w, h = parse(level)
    start = (player0, boxes0)
    seen = {start}
    q = deque([(player0, boxes0, "")])
    count = 0
    while q:
        player, boxes, path = q.popleft()
        count += 1
        if count > max_states:
            return None, count, "TOO_MANY_STATES"
        if boxes == goals:
            return path, count, "OK"
        for d, (dx, dy) in DIRS.items():
            np = (player[0] + dx, player[1] + dy)
            if np in walls:
                continue
            nboxes = boxes
            if np in boxes:
                nbp = (np[0] + dx, np[1] + dy)
                if nbp in walls or nbp in boxes:
                    continue
                nboxes = frozenset((boxes - {np}) | {nbp})
            state = (np, nboxes)
            if state in seen:
                continue
            seen.add(state)
            q.append((np, nboxes, path + d))
    return None, count, "NO_SOLUTION"

def render_check(level):
    walls, goals, boxes, player, w, h = parse(level)
    print(f"  size={w}x{h} walls={len(walls)} goals={len(goals)} boxes={len(boxes)} player={player}")
    if len(goals) != len(boxes):
        print("  !! goal/box count mismatch")

levels = {}
exec(open(sys.argv[1]).read(), levels)

for name, lvl in levels["LEVELS"]:
    print(f"=== {name} ===")
    render_check(lvl)
    sol, states, status = solve(lvl)
    if status == "OK":
        print(f"  SOLVED in {len(sol)} moves, explored {states} states")
    else:
        print(f"  FAILED: {status} (explored {states} states)")
