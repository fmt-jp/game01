import heapq

SIZE = 4
GOAL = tuple(list(range(1, 16)) + [0])
GOAL_POS = {v: i for i, v in enumerate(GOAL)}

def manhattan(state):
    total = 0
    for i, v in enumerate(state):
        if v == 0:
            continue
        gi = GOAL_POS[v]
        r1, c1 = i // SIZE, i % SIZE
        r2, c2 = gi // SIZE, gi % SIZE
        total += abs(r1 - r2) + abs(c1 - c2)
    return total

def linear_conflict(state):
    conflict = 0
    grid = [state[r*SIZE:(r+1)*SIZE] for r in range(SIZE)]
    # rows
    for r in range(SIZE):
        row_tiles = [(c, grid[r][c]) for c in range(SIZE) if grid[r][c] != 0 and GOAL_POS[grid[r][c]] // SIZE == r]
        for i in range(len(row_tiles)):
            for j in range(i+1, len(row_tiles)):
                c1, v1 = row_tiles[i]
                c2, v2 = row_tiles[j]
                if GOAL_POS[v1] % SIZE > GOAL_POS[v2] % SIZE:
                    conflict += 1
    # cols
    for c in range(SIZE):
        col_tiles = [(r, grid[r][c]) for r in range(SIZE) if grid[r][c] != 0 and GOAL_POS[grid[r][c]] % SIZE == c]
        for i in range(len(col_tiles)):
            for j in range(i+1, len(col_tiles)):
                r1, v1 = col_tiles[i]
                r2, v2 = col_tiles[j]
                if GOAL_POS[v1] // SIZE > GOAL_POS[v2] // SIZE:
                    conflict += 1
    return conflict * 2

def heuristic(state):
    return manhattan(state) + linear_conflict(state)

def neighbors(p):
    r, c = p // SIZE, p % SIZE
    result = []
    if r > 0: result.append(p - SIZE)
    if r < SIZE - 1: result.append(p + SIZE)
    if c > 0: result.append(p - 1)
    if c < SIZE - 1: result.append(p + 1)
    return result

def solve(start, max_nodes=400000):
    start = tuple(start)
    if start == GOAL:
        return []
    g_score = {start: 0}
    h0 = heuristic(start)
    counter = 0
    heap = [(h0, 0, counter, start, [])]
    visited = set()
    nodes = 0
    while heap:
        f, g, _, state, path = heapq.heappop(heap)
        if state in visited:
            continue
        visited.add(state)
        nodes += 1
        if nodes > max_nodes:
            return None
        blank = state.index(0)
        for n in neighbors(blank):
            new_state = list(state)
            new_state[blank], new_state[n] = new_state[n], new_state[blank]
            new_state = tuple(new_state)
            if new_state in visited:
                continue
            ng = g + 1
            if new_state not in g_score or ng < g_score[new_state]:
                g_score[new_state] = ng
                new_path = path + [n]
                if new_state == GOAL:
                    return new_path
                counter += 1
                heapq.heappush(heap, (ng + heuristic(new_state), ng, counter, new_state, new_path))
    return None
