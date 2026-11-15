"""はしわたし: the boards, checked from outside the game.

The game builds a board in the browser and hands it out. Everything that says
whether it is a puzzle at all lives in bridges_rules.py, written from the
rules rather than from the game's code: which islands can see each other,
which bridges would cross, and -- the point of the whole thing -- how many
ways there are to finish it.
"""
import collections
import sys
from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS, BASE
import bridges_rules as R

failures = []


def check(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(label)


def note(text):
    print("       " + text)


def build(page, level, count):
    return page.evaluate("""([level, count]) => {
      const out = [];
      for (let i = 0; i < count; i += 1) {
        const p = Puzzle.generate(level);
        out.push(p && { w: p.w, h: p.h, steps: p.steps,
                        islands: p.islands.map((i) => ({ r: i.r, c: i.c, need: i.need })),
                        edges: p.edges.map((e) => [e.a, e.b]),
                        answer: p.answer });
      }
      return out;
    }""", [level, count])


LEVELS = [1, 3, 6, 9, 12, 16, 20]
PER_LEVEL = 7

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/bridges/index.html")
    page.wait_for_timeout(600)

    boards = {lv: [b for b in build(page, lv, PER_LEVEL) if b] for lv in LEVELS}

    # ------------------------------------------------------------------
    print("[1] the boards it builds")
    check("every ask for a board produced one",
          all(len(boards[lv]) == PER_LEVEL for lv in LEVELS),
          str({lv: len(boards[lv]) for lv in LEVELS}))

    bad = []
    for lv, group in boards.items():
        for n, b in enumerate(group):
            islands = b["islands"]
            where = {(i["r"], i["c"]) for i in islands}
            tag = f"lv{lv}#{n}"
            if len(where) != len(islands):
                bad.append(f"{tag}: two islands in one place")
            if any(i["r"] < 0 or i["c"] < 0 or i["r"] >= b["h"] or i["c"] >= b["w"] for i in islands):
                bad.append(f"{tag}: an island is off the board")
            if any(not 1 <= i["need"] <= 8 for i in islands):
                bad.append(f"{tag}: a number outside 1-8")
            # two islands side by side would leave no water for a bridge
            for r, c in where:
                if (r, c + 1) in where or (r + 1, c) in where:
                    bad.append(f"{tag}: two islands are touching")
                    break
            ours = sorted(tuple(sorted(e)) for e in R.edges_of(islands))
            theirs = sorted(tuple(sorted(e)) for e in b["edges"])
            if ours != theirs:
                bad.append(f"{tag}: the game and the rules disagree on which islands can see each other")
            wrong = R.faults(islands, [tuple(e) for e in b["edges"]], b["answer"])
            if wrong:
                bad.append(f"{tag}: the board's own answer is not legal: {wrong[0]}")
    check("every board is laid out legally, and its answer obeys the rules",
          not bad, "; ".join(sorted(set(bad))[:3]))

    for lv in LEVELS:
        isl = [len(b["islands"]) for b in boards[lv]]
        clues = [i["need"] for b in boards[lv] for i in b["islands"]]
        note(f"lv{lv:>2}: {min(isl)}-{max(isl)} islands, numbers up to {max(clues)}, "
             f"{sum(1 for c in clues if c >= 5) / len(boards[lv]):.1f} big ones a board")

    # ------------------------------------------------------------------
    print("\n[2] is there exactly one answer?")
    counts = collections.Counter()
    off = []
    for lv, group in boards.items():
        for n, b in enumerate(group):
            islands = b["islands"]
            edges = R.edges_of(islands)
            found = R.solutions(islands, edges, 3)
            counts[len(found)] += 1
            if len(found) != 1:
                off.append(f"lv{lv}#{n}: {len(found)} answers")
            elif found[0] != b["answer"]:
                off.append(f"lv{lv}#{n}: the one answer is not the one the game kept")
    total = sum(len(g) for g in boards.values())
    check(f"all {total} boards have exactly one answer, and it is the game's",
          not off, "; ".join(off[:3]))
    note(f"answers per board: {dict(counts)}")

    # the smallest boards are small enough to try every arrangement there is
    tried = 0
    brute_bad = []
    for b in boards[1]:
        edges = R.edges_of(b["islands"])
        if len(edges) > 13:
            continue
        every = R.brute_force(b["islands"], edges)
        tried += 1
        if len(every) != 1 or every[0] != b["answer"]:
            brute_bad.append(f"{len(every)} work out of {3 ** len(edges)}")
    check(f"and on {tried} small boards, all {3 ** 8}-odd arrangements were tried one by one",
          tried > 0 and not brute_bad, "; ".join(brute_bad[:3]))

    # ------------------------------------------------------------------
    print("\n[3] how hard they are")
    depth = {}
    for lv in LEVELS:
        steps, plain = [], 0
        for b in boards[lv]:
            edges = R.edges_of(b["islands"])
            R.solutions(b["islands"], edges, 2)
            steps.append(R.STEPS)
            if R.deduce(b["islands"], edges)[2]:
                plain += 1
        depth[lv] = sum(steps) / len(steps)
        note(f"lv{lv:>2}: {depth[lv]:5.1f} search steps on average (worst {max(steps)}), "
             f"{100 * plain / len(boards[lv]):3.0f}% fall out of plain reasoning alone")
    check("a late board takes more working out than the first one",
          depth[LEVELS[-1]] > depth[1] * 1.8, f"lv1 {depth[1]:.1f} vs lv{LEVELS[-1]} {depth[LEVELS[-1]]:.1f}")

    # ------------------------------------------------------------------
    print("\n[4] the game's rules against ours")
    laid = 0
    for lv in (1, 5, 11, 17):
        page.evaluate("(lv) => window.__start(lv)", lv)
        page.wait_for_timeout(250)
        state = page.evaluate("() => window.__bridges()")
        islands = [{"r": i["r"], "c": i["c"], "need": i["need"]} for i in state["islands"]]
        edges = [(e["a"], e["b"]) for e in state["edges"]]
        found = R.solutions(islands, R.edges_of(islands), 2)
        answer = found[0] if len(found) == 1 else None
        if answer is None:
            failures.append(f"lv{lv}: the board on screen has no single answer")
            continue
        # lay out the answer our solver found, through the game's own hands
        page.evaluate("""(plan) => {
          plan.forEach(([a, b, n]) => { for (let k = 0; k < n; k += 1) window.__toggle(a, b); });
        }""", [[edges[i][0], edges[i][1], n] for i, n in enumerate(answer) if n])
        page.wait_for_timeout(250)
        after = page.evaluate("() => window.__bridges()")
        laid += 1
        if not after["solved"]:
            failures.append(f"lv{lv}: the game did not call our answer a win")
    check(f"the answer our solver found wins the game, on {laid} boards", laid == 4)

    # a bridge may not be laid over another, and the game has to say so
    page.evaluate("() => window.__start(14)")
    page.wait_for_timeout(250)
    state = page.evaluate("() => window.__bridges()")
    islands = [{"r": i["r"], "c": i["c"], "need": i["need"]} for i in state["islands"]]
    edges = [(e["a"], e["b"]) for e in state["edges"]]
    cross = R.crossings(islands, edges)
    pair = next(((i, cross[i][0]) for i in range(len(edges)) if cross[i]), None)
    if pair is None:
        note("this board has no two bridges that would cross; skipped")
    else:
        first, second = pair
        page.evaluate("(e) => window.__toggle(e[0], e[1])", list(edges[first]))
        page.wait_for_timeout(120)
        page.evaluate("(e) => window.__toggle(e[0], e[1])", list(edges[second]))
        page.wait_for_timeout(120)
        now = page.evaluate("() => window.__bridges()")
        check("a bridge across another one is turned down, and said so",
              now["edges"][second]["n"] == 0 and "交差" in now["notice"],
              f"{now['edges'][second]['n']} spans, notice {now['notice']!r}")

    # ------------------------------------------------------------------
    print("\n[5] every number right, islands still apart")
    found_case = False
    for lv in (6, 9, 12, 15, 18, 21, 4, 7):
        page.evaluate("(lv) => window.__start(lv)", lv)
        page.wait_for_timeout(250)
        state = page.evaluate("() => window.__bridges()")
        islands = [{"r": i["r"], "c": i["c"], "need": i["need"]} for i in state["islands"]]
        edges = [(e["a"], e["b"]) for e in state["edges"]]
        loose = [s for s in R.solutions(islands, edges, 6, require_joined=False)
                 if not R.joined(islands, edges, s)]
        if not loose:
            continue
        plan = [[edges[i][0], edges[i][1], n] for i, n in enumerate(loose[0]) if n]
        page.evaluate("""(plan) => {
          plan.forEach(([a, b, n]) => { for (let k = 0; k < n; k += 1) window.__toggle(a, b); });
        }""", plan)
        page.wait_for_timeout(250)
        now = page.evaluate("() => window.__bridges()")
        check("a board with every number right but in two pieces is not a win",
              now["left"] == 0 and not now["solved"] and not now["connected"],
              f"left {now['left']}, solved {now['solved']}, joined {now['connected']}")
        check("and the game says what is wrong with it", "離れて" in now["notice"],
              repr(now["notice"]))
        note(f"found on a level {lv} board")
        found_case = True
        break
    check("such a board exists to try at all", found_case)

    check("no page errors", not errors, str(errors))
    page.screenshot(path=f"{SHOTS}/bridges_rules.png")
    browser.close()

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURES"))
for f in failures:
    print("  -", f)
sys.exit(1 if failures else 0)
