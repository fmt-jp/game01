"""The rules of ふえる石, written from the description rather than from the
game's JavaScript, so a check that compares the two can actually disagree.

Used by test_ataxx.py (replaying whole games) and test_ataxx_ui.py (checking
that the board on screen only ever changes by one legal move at a time).
"""
SIZE = 7
CELLS = SIZE * SIZE
EMPTY, YOU, FOE, WALL = 0, 1, 2, 3

from collections import Counter


def rc(i):
    return divmod(i, SIZE)


def around(i, reach):
    r, c = rc(i)
    out = []
    for dr in range(-reach, reach + 1):
        for dc in range(-reach, reach + 1):
            if dr == 0 and dc == 0:
                continue
            if max(abs(dr), abs(dc)) != reach:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < SIZE and 0 <= nc < SIZE:
                out.append(nr * SIZE + nc)
    return out


NEAR = [around(i, 1) for i in range(CELLS)]
FAR = [around(i, 2) for i in range(CELLS)]


def legal_moves(cells, side):
    moves = set()
    for src in range(CELLS):
        if cells[src] != side:
            continue
        for dst in NEAR[src]:
            if cells[dst] == EMPTY:
                moves.add((src, dst, True))
        for dst in FAR[src]:
            if cells[dst] == EMPTY:
                moves.add((src, dst, False))
    return moves


def apply_move(cells, src, dst, clone, side):
    out = list(cells)
    if not clone:
        out[src] = EMPTY
    out[dst] = side
    foe = FOE if side == YOU else YOU
    for n in NEAR[dst]:
        if out[n] == foe:
            out[n] = side
    return out


def counts(cells):
    c = Counter(cells)
    return {"you": c[YOU], "foe": c[FOE], "empty": c[EMPTY]}


def is_over(cells):
    n = counts(cells)
    if n["you"] == 0 or n["foe"] == 0 or n["empty"] == 0:
        return True
    return not legal_moves(cells, YOU) and not legal_moves(cells, FOE)


def winner(cells):
    n = counts(cells)
    return 0 if n["you"] == n["foe"] else (YOU if n["you"] > n["foe"] else FOE)


def explain(before, after):
    """Which single move, if any, turns `before` into `after`?"""
    for side in (YOU, FOE):
        for src, dst, clone in legal_moves(before, side):
            if apply_move(before, src, dst, clone, side) == after:
                return side, src, dst, clone
    return None
