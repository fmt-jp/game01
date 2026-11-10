"""The rules of かさねとり, written from the rules rather than from the game.

A tile can be taken when nothing rests on it and one of its two sides is
clear. Everything here -- which tiles are free, which pairs are takeable, and
whether a pile can be emptied at all -- is worked out from that sentence and
the list of (x, y, z) places, with no reference to how the game does it. If
the game and this file disagree, the checks that use both will say so.
"""
from functools import lru_cache
import random


def free_set(tiles, alive):
    """The tiles that could be lifted off right now."""
    occupied = {(tiles[i]["x"], tiles[i]["y"], tiles[i]["z"]) for i in alive}
    out = set()
    for i in alive:
        t = tiles[i]
        x, y, z = t["x"], t["y"], t["z"]
        if (x, y, z + 1) in occupied:
            continue
        if (x - 1, y, z) in occupied and (x + 1, y, z) in occupied:
            continue
        out.add(i)
    return out


def takeable(tiles, alive):
    """Every pair of free tiles that share a face."""
    free = sorted(free_set(tiles, alive))
    out = []
    for n, a in enumerate(free):
        for b in free[n + 1:]:
            if tiles[a]["kind"] == tiles[b]["kind"]:
                out.append((a, b))
    return out


def replay(tiles, order, alive=None):
    """Walk a claimed removal order and say where, if anywhere, it breaks."""
    live = set(range(len(tiles))) if alive is None else set(alive)
    for step, (a, b) in enumerate(order):
        if a not in live or b not in live:
            return f"step {step}: tile already gone"
        if tiles[a]["kind"] != tiles[b]["kind"]:
            return f"step {step}: {tiles[a]['kind']} does not match {tiles[b]['kind']}"
        free = free_set(tiles, live)
        if a not in free or b not in free:
            return f"step {step}: tile {a if a not in free else b} is not free"
        live -= {a, b}
    if live:
        return f"{len(live)} tiles left over"
    return None


def _greedy(tiles, alive, rng):
    """One careless playthrough: take a random pair, over and over."""
    live = set(alive)
    order = []
    while live:
        options = takeable(tiles, live)
        if not options:
            return None
        a, b = rng.choice(options)
        live -= {a, b}
        order.append((a, b))
    return order


def solve(tiles, alive=None, tries=120, budget=120000, seed=0):
    """Find a way to empty the pile, deciding for ourselves.

    First a few careless playthroughs, which settle an easy pile quickly. If
    none of them get there, search properly: depth first over the states, with
    every state seen remembered so a dead end is only paid for once.

    Returns the removal order, False when the whole space was searched without
    finding one, or None when the search ran out of budget (undecided).
    """
    live = frozenset(range(len(tiles)) if alive is None else alive)
    rng = random.Random(seed)
    for _ in range(tries):
        got = _greedy(tiles, live, rng)
        if got is not None:
            return got

    dead = set()
    spent = 0
    out_of_budget = False

    def walk(state):
        nonlocal spent, out_of_budget
        if not state:
            return []
        if state in dead:
            return None
        spent += 1
        if spent > budget:
            out_of_budget = True
            return None
        options = takeable(tiles, state)
        # Dig from the top: taking a high tile opens more than a low one.
        options.sort(key=lambda p: -(tiles[p[0]]["z"] + tiles[p[1]]["z"]))
        for a, b in options:
            rest = walk(state - {a, b})
            if rest is not None:
                return [(a, b)] + rest
            if out_of_budget:
                return None
        dead.add(state)
        return None

    found = walk(live)
    if found is not None:
        return found
    return None if out_of_budget else False
