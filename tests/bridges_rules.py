"""The rules of はしわたし, written from the rules rather than from the game.

A bridge runs straight between two islands that can see each other, at most
two to a pair, crossing nothing. Every island carries the number of bridge
ends it must have, and when the board is finished every island must be
reachable from every other. Everything here is worked out from those
sentences and a list of island positions and numbers.
"""
import itertools


def edges_of(islands):
    """Pairs that could be bridged: nearest island to the right, and below."""
    at = {(i["r"], i["c"]): n for n, i in enumerate(islands)}
    last_r = max(i["r"] for i in islands)
    last_c = max(i["c"] for i in islands)
    out = []
    for n, island in enumerate(islands):
        for dr, dc in ((0, 1), (1, 0)):
            r, c = island["r"] + dr, island["c"] + dc
            while r <= last_r and c <= last_c:
                if (r, c) in at:
                    out.append((n, at[(r, c)]))
                    break
                r += dr
                c += dc
    return out


def _span(islands, edge):
    a, b = islands[edge[0]], islands[edge[1]]
    return (min(a["r"], b["r"]), max(a["r"], b["r"]),
            min(a["c"], b["c"]), max(a["c"], b["c"]))


def crossings(islands, edges):
    """For each bridge, the bridges it would cross."""
    spans = [_span(islands, e) for e in edges]
    out = [[] for _ in edges]
    for i, j in itertools.combinations(range(len(edges)), 2):
        r1, r2, c1, c2 = spans[i]
        s1, s2, d1, d2 = spans[j]
        flat_i, flat_j = r1 == r2, s1 == s2
        if flat_i == flat_j:
            continue
        h, v = (spans[i], spans[j]) if flat_i else (spans[j], spans[i])
        if v[2] > h[2] and v[2] < h[3] and h[0] > v[0] and h[0] < v[1]:
            out[i].append(j)
            out[j].append(i)
    return out


def joined(islands, edges, counts):
    """Is every island reachable from every other over the bridges laid?"""
    near = [[] for _ in islands]
    for n, (a, b) in enumerate(edges):
        if counts[n] > 0:
            near[a].append(b)
            near[b].append(a)
    seen = {0}
    stack = [0]
    while stack:
        for nxt in near[stack.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return len(seen) == len(islands)


def faults(islands, edges, counts):
    """Everything wrong with a finished board, named."""
    cross = crossings(islands, edges)
    wrong = []
    ends = [0] * len(islands)
    for n, (a, b) in enumerate(edges):
        if counts[n] < 0 or counts[n] > 2:
            wrong.append(f"bridge {n} has {counts[n]} spans")
        ends[a] += counts[n]
        ends[b] += counts[n]
        if counts[n] > 0 and any(counts[x] > 0 for x in cross[n]):
            wrong.append(f"bridge {n} crosses another")
    for n, island in enumerate(islands):
        if ends[n] != island["need"]:
            wrong.append(f"island {n} wants {island['need']} and has {ends[n]}")
    if not joined(islands, edges, counts):
        wrong.append("the islands are not all joined up")
    return wrong


# How much searching the last call to solutions() needed. A board that falls
# out in a handful of steps is one a person can reason through; a board that
# takes hundreds is one where the solver had to try things and back out.
STEPS = 0


def solutions(islands, edges, limit=2, require_joined=True):
    """Count the ways to finish the board, stopping at `limit`.

    With require_joined off it also returns the arrangements where every
    number is right but the islands fall into separate groups -- the thing a
    player hits when the board looks finished and is not.
    """
    global STEPS
    STEPS = 0
    cross = crossings(islands, edges)
    inc = [[] for _ in islands]
    for n, (a, b) in enumerate(edges):
        inc[a].append(n)
        inc[b].append(n)
    counts = [-1] * len(edges)
    found = []

    def far(e, i):
        a, b = edges[e]
        return b if a == i else a

    def room(e, i):
        if counts[e] >= 0:
            return counts[e]
        if any(counts[x] > 0 for x in cross[e]):
            return 0
        other = far(e, i)
        used = sum(counts[f] for f in inc[other] if counts[f] > 0)
        return min(2, islands[other]["need"] - used)

    def ways(i):
        used, free = 0, []
        for e in inc[i]:
            if counts[e] >= 0:
                used += counts[e]
            else:
                free.append(e)
        need = islands[i]["need"] - used
        if need < 0:
            return None
        caps = [room(e, i) for e in free]
        if sum(caps) < need:
            return None
        out = []
        for pick in itertools.product(*(range(c + 1) for c in caps)):
            if sum(pick) == need:
                out.append(pick)
        return free, out

    def reachable_still():
        maybe = [1 if c == -1 else c for c in counts]
        return joined(islands, edges, maybe)

    def walk():
        global STEPS
        STEPS += 1
        pick, best = -1, None
        for i in range(len(islands)):
            if all(counts[e] >= 0 for e in inc[i]):
                continue
            got = ways(i)
            if got is None:
                return
            if best is None or len(got[1]) < len(best[1]):
                best, pick = got, i
                if len(got[1]) <= 1:
                    break
        if pick == -1:
            if not require_joined or joined(islands, edges, counts):
                found.append(counts[:])
            return
        free, options = best
        for option in options:
            if len(found) >= limit:
                return
            for e, k in zip(free, option):
                counts[e] = k
            ok = all(not (counts[e] > 0 and any(counts[x] > 0 for x in cross[e])) for e in free)
            if ok and (not require_joined or reachable_still()):
                walk()
            for e in free:
                counts[e] = -1

    walk()
    return found


def brute_force(islands, edges):
    """Every arrangement there is, tried one by one. Only for tiny boards."""
    if len(edges) > 13:
        raise ValueError("too many bridges to try them all")
    out = []
    for pick in itertools.product((0, 1, 2), repeat=len(edges)):
        if not faults(islands, edges, list(pick)):
            out.append(list(pick))
    return out


def deduce(islands, edges):
    """How far plain reasoning gets, with no guessing anywhere.

    Each bridge is held between a lowest and a highest number it could be.
    An island narrows its own bridges, a bridge that must exist rules out the
    ones it would cross, and this is repeated until nothing more moves.
    """
    cross = crossings(islands, edges)
    inc = [[] for _ in islands]
    for n, (a, b) in enumerate(edges):
        inc[a].append(n)
        inc[b].append(n)
    lo = [0] * len(edges)
    hi = [2] * len(edges)

    moved = True
    while moved:
        moved = False
        for i, island in enumerate(islands):
            mine = inc[i]
            for e in mine:
                rest_hi = sum(hi[f] for f in mine if f != e)
                rest_lo = sum(lo[f] for f in mine if f != e)
                want_lo = max(lo[e], island["need"] - rest_hi)
                want_hi = min(hi[e], island["need"] - rest_lo)
                if want_lo > want_hi:
                    return lo, hi, False
                if want_lo != lo[e] or want_hi != hi[e]:
                    lo[e], hi[e] = want_lo, want_hi
                    moved = True
        for e in range(len(edges)):
            if lo[e] > 0:
                for x in cross[e]:
                    if hi[x] > 0:
                        hi[x] = 0
                        moved = True
                        if lo[x] > 0:
                            return lo, hi, False
    return lo, hi, all(lo[e] == hi[e] for e in range(len(edges)))
