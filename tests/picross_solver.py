import sys
from functools import lru_cache

def clue(line):
    runs = []
    count = 0
    for c in line:
        if c == 1:
            count += 1
        else:
            if count:
                runs.append(count)
            count = 0
    if count:
        runs.append(count)
    return runs or [0]

def line_placements(clue_vals, length):
    """All binary lines of given length matching clue_vals (list of run lengths, [0] means empty)."""
    if clue_vals == [0]:
        return [tuple([0]*length)]
    results = []
    n = len(clue_vals)
    min_len = sum(clue_vals) + (n - 1)

    def rec(pos, idx, current):
        if idx == n:
            results.append(tuple(current + [0]*(length-pos)))
            return
        run = clue_vals[idx]
        remaining_min = sum(clue_vals[idx+1:]) + (n-idx-1)
        max_start = length - remaining_min - run
        for start in range(pos, max_start+1):
            new_current = current + [0]*(start-pos) + [1]*run
            if idx == n-1:
                rec(start+run, idx+1, new_current)
            else:
                new_current2 = new_current + [0]
                rec(start+run+1, idx+1, new_current2)

    rec(0, 0, [])
    return results

def solve(row_clues, col_clues, max_solutions=2):
    rows = len(row_clues)
    cols = len(col_clues)
    grid = [[-1]*cols for _ in range(rows)]  # -1 unknown, 0 empty, 1 filled

    row_options = [line_placements(row_clues[r], cols) for r in range(rows)]
    col_options = [line_placements(col_clues[c], rows) for c in range(cols)]

    def consistent(line, opt):
        for a, b in zip(line, opt):
            if a != -1 and a != b:
                return False
        return True

    def propagate():
        changed = True
        while changed:
            changed = False
            for r in range(rows):
                valid = [o for o in row_options[r] if consistent(grid[r], o)]
                row_options[r] = valid
                if not valid:
                    return False
                for c in range(cols):
                    vals = set(o[c] for o in valid)
                    if len(vals) == 1:
                        v = vals.pop()
                        if grid[r][c] != v:
                            grid[r][c] = v
                            changed = True
            for c in range(cols):
                colline = [grid[r][c] for r in range(rows)]
                valid = [o for o in col_options[c] if consistent(colline, o)]
                col_options[c] = valid
                if not valid:
                    return False
                for r in range(rows):
                    vals = set(o[r] for o in valid)
                    if len(vals) == 1:
                        v = vals.pop()
                        if grid[r][c] != v:
                            grid[r][c] = v
                            changed = True
        return True

    solutions = []

    def backtrack():
        if len(solutions) >= max_solutions:
            return
        if not propagate():
            return
        # find unknown cell
        target = None
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == -1:
                    target = (r, c)
                    break
            if target:
                break
        if target is None:
            solutions.append([row[:] for row in grid])
            return
        r, c = target
        for v in (0, 1):
            saved_grid = [row[:] for row in grid]
            saved_row_opts = [list(o) for o in row_options]
            saved_col_opts = [list(o) for o in col_options]
            grid[r][c] = v
            backtrack()
            for rr in range(rows):
                grid[rr] = saved_grid[rr][:]
            row_options[:] = saved_row_opts
            col_options[:] = saved_col_opts
            if len(solutions) >= max_solutions:
                return

    backtrack()
    return solutions


def bitmap_to_clues(bitmap):
    grid = [[1 if ch == '1' else 0 for ch in row] for row in bitmap]
    row_clues = [clue(row) for row in grid]
    col_clues = [clue([grid[r][c] for r in range(len(grid))]) for c in range(len(grid[0]))]
    return row_clues, col_clues, grid


if __name__ == "__main__":
    ns = {}
    exec(open(sys.argv[1]).read(), ns)
    for name, bitmap in ns["PUZZLES"]:
        row_clues, col_clues, grid = bitmap_to_clues(bitmap)
        sols = solve(row_clues, col_clues, max_solutions=2)
        status = "UNIQUE" if len(sols) == 1 else ("NO SOLUTION" if len(sols)==0 else "AMBIGUOUS (>=2 solutions)")
        print(f"{name}: size={len(bitmap)}x{len(bitmap[0])} filled={sum(r.count('1') for r in bitmap)} -> {status}")
