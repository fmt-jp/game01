"""Check ふえる石: the rules, the walls, the opponent, and playing a game.

The rules are implemented again here, from the description rather than from the
JavaScript, and whole games played in the page are replayed against this copy
move by move. If the two disagree about what is legal or about what a move does
to the board, the replay stops matching and the check fails.
"""
import random
import sys
from collections import Counter

from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

BASE = "http://localhost:8390"
SIZE = 7
CELLS = SIZE * SIZE
EMPTY, YOU, FOE, WALL = 0, 1, 2, 3
failures = []


def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(f"{label}: {detail}")


# ---------- the rules, written here from the description ----------

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


# Plays whole games in the page and records every step, for replay out here.
TRACE = """
([games, level]) => {
  const out = [];
  for (let g = 0; g < games; g++) {
    let cells = Ataxx.newBoard();
    const start = Array.from(cells);
    const steps = [];
    let side = Ataxx.YOU, passes = 0;
    for (let turn = 0; turn < 300 && !Ataxx.isOver(cells); turn++) {
      const moves = Ataxx.legalMoves(cells, side);
      if (moves.length === 0) {
        steps.push({side, pass: true, legal: 0});
        passes++;
        if (passes >= 2) break;
        side = side === Ataxx.YOU ? Ataxx.FOE : Ataxx.YOU;
        continue;
      }
      passes = 0;
      const move = level === "random"
        ? moves[Math.floor(Math.random() * moves.length)]
        : AtaxxAI.chooseMove(cells, side, level);
      const applied = Ataxx.applyMove(cells, move, side);
      cells = applied.cells;
      steps.push({side, from: move.from, to: move.to, clone: move.clone,
                  legal: moves.length, after: Array.from(cells),
                  flipped: applied.flipped});
      side = side === Ataxx.YOU ? Ataxx.FOE : Ataxx.YOU;
    }
    out.push({start, steps, over: Ataxx.isOver(cells),
              winner: Ataxx.winner(cells), counts: Ataxx.counts(cells)});
  }
  return out;
}
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True,
                              is_mobile=True, device_scale_factor=2)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/ataxx/index.html")
    page.wait_for_timeout(800)

    print("\n[1] the board it starts from")
    boards = page.evaluate("""(n) => {
      const out = [];
      for (let i = 0; i < n; i++) out.push(Array.from(Ataxx.newBoard()));
      return out;
    }""", 120)
    bad = []
    for cells in boards:
        walls = [i for i, v in enumerate(cells) if v == WALL]
        if any(cells[CELLS - 1 - i] != WALL for i in walls):
            bad.append("a wall with no opposite number")
        elif not (0 <= len(walls) <= 8) or len(walls) % 2:
            bad.append(f"{len(walls)} walls")
        elif [cells[i] for i in (0, CELLS - 1)] != [YOU, YOU] or \
             [cells[i] for i in (SIZE - 1, CELLS - SIZE)] != [FOE, FOE]:
            bad.append("the corners are not set up")
        elif not legal_moves(cells, YOU) or not legal_moves(cells, FOE):
            bad.append("a side starts with nowhere to go")
    check(f"all {len(boards)} opening boards are fair", not bad, str(bad[:3]))
    spread = Counter(sum(1 for v in c if v == WALL) for c in boards)
    print(f"      walls per board: {dict(sorted(spread.items()))}")
    check("the boards are not all identical",
          len({tuple(c) for c in boards}) > 3, f"{len({tuple(c) for c in boards})} distinct")

    print("\n[2] the rules, replayed against a separate implementation")
    traces = page.evaluate(TRACE, [14, "random"])
    disagreements = []
    moves_checked = 0
    for g, trace in enumerate(traces):
        cells = list(trace["start"])
        side = YOU
        for n, step in enumerate(trace["steps"]):
            mine = legal_moves(cells, step["side"])
            if step["side"] != side:
                disagreements.append(f"game {g} step {n}: played out of turn")
                break
            if step.get("pass"):
                if mine:
                    disagreements.append(f"game {g} step {n}: passed with {len(mine)} moves available")
                    break
            else:
                if len(mine) != step["legal"]:
                    disagreements.append(
                        f"game {g} step {n}: {step['legal']} moves offered, {len(mine)} found here")
                    break
                key = (step["from"], step["to"], step["clone"])
                if key not in mine:
                    disagreements.append(f"game {g} step {n}: {key} is not a legal move here")
                    break
                cells = apply_move(cells, *key, step["side"])
                if cells != step["after"]:
                    disagreements.append(f"game {g} step {n}: the board after {key} differs")
                    break
                moves_checked += 1
            side = FOE if side == YOU else YOU
        else:
            if is_over(cells) != trace["over"]:
                disagreements.append(f"game {g}: disagree on whether it is over")
            elif counts(cells) != trace["counts"]:
                disagreements.append(f"game {g}: final counts differ")
            elif winner(cells) != trace["winner"]:
                disagreements.append(f"game {g}: disagree on the winner")
    check(f"{len(traces)} games, {moves_checked} moves replayed with no disagreement",
          not disagreements, str(disagreements[:2]))

    print("\n[3] the opponent")
    illegal = page.evaluate("""() => {
      // every move it offers from a scrambled position must be legal
      let bad = 0, tried = 0;
      for (let g = 0; g < 40; g++) {
        let cells = Ataxx.newBoard();
        for (let k = 0; k < 10 && !Ataxx.isOver(cells); k++) {
          const side = k % 2 ? Ataxx.FOE : Ataxx.YOU;
          const ms = Ataxx.legalMoves(cells, side);
          if (!ms.length) break;
          cells = Ataxx.applyMove(cells, ms[Math.floor(Math.random() * ms.length)], side).cells;
        }
        if (Ataxx.isOver(cells)) continue;
        for (const level of ["easy", "normal", "hard"]) {
          const legal = Ataxx.legalMoves(cells, Ataxx.FOE);
          if (!legal.length) continue;
          const move = AtaxxAI.chooseMove(cells, Ataxx.FOE, level);
          tried++;
          if (!move || !legal.some((m) => m.from === move.from && m.to === move.to
                                       && m.clone === move.clone)) bad++;
        }
      }
      return {bad, tried};
    }""")
    check(f"it never offers an illegal move ({illegal['tried']} asked for)", illegal["bad"] == 0,
          f"{illegal['bad']} illegal")

    timing = page.evaluate("""() => {
      const out = {};
      for (const level of ["easy", "normal", "hard"]) {
        let worst = 0;
        for (let g = 0; g < 6; g++) {
          let cells = Ataxx.newBoard();
          for (let k = 0; k < 8 && !Ataxx.isOver(cells); k++) {
            const side = k % 2 ? Ataxx.FOE : Ataxx.YOU;
            const ms = Ataxx.legalMoves(cells, side);
            if (!ms.length) break;
            cells = Ataxx.applyMove(cells, ms[Math.floor(Math.random()*ms.length)], side).cells;
          }
          const t0 = performance.now();
          AtaxxAI.chooseMove(cells, Ataxx.FOE, level);
          worst = Math.max(worst, performance.now() - t0);
        }
        out[level] = Math.round(worst);
      }
      return out;
    }""")
    print(f"      slowest reply: {timing}")
    check("it answers without the game feeling stuck", max(timing.values()) < 1500, str(timing))

    strength = page.evaluate("""([games]) => {
      const play = (a, b) => {
        let cells = Ataxx.newBoard(), side = Ataxx.YOU, passes = 0;
        for (let t = 0; t < 300 && !Ataxx.isOver(cells); t++) {
          const level = side === Ataxx.YOU ? a : b;
          const ms = Ataxx.distinctMoves(cells, side);
          let move = null;
          if (ms.length) {
            move = level === "random"
              ? ms[Math.floor(Math.random() * ms.length)]
              : AtaxxAI.chooseMove(cells, side, level);
          }
          if (!move) { if (++passes >= 2) break; side = 3 - side; continue; }
          passes = 0;
          cells = Ataxx.applyMove(cells, move, side).cells;
          side = 3 - side;
        }
        return Ataxx.winner(cells);
      };
      const tally = (a, b) => {
        const r = {win: 0, loss: 0, draw: 0};
        for (let i = 0; i < games; i++) {
          const w = play(a, b);
          if (w === Ataxx.YOU) r.win++; else if (w === Ataxx.FOE) r.loss++; else r.draw++;
        }
        return r;
      };
      return {vsRandom: tally("normal", "random"), hardVsEasy: tally("hard", "easy")};
    }""", [16])
    print(f"      ふつう vs random: {strength['vsRandom']} | つよい vs よわい: {strength['hardVsEasy']}")
    check("ふつう beats a player picking at random", strength["vsRandom"]["win"] >= 14,
          str(strength["vsRandom"]))
    check("つよい beats よわい more often than not",
          strength["hardVsEasy"]["win"] > strength["hardVsEasy"]["loss"], str(strength["hardVsEasy"]))

    print("\n[4] playing it")
    page.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
    page.reload()
    page.wait_for_timeout(700)
    state = page.evaluate("() => window.__ataxx()")
    move = state["yourMoves"][0]
    page.evaluate("(i) => window.__tap(i)", move["from"])
    page.wait_for_timeout(250)
    marked = page.evaluate("""() => ({
      clone: [...document.querySelectorAll('.square.clone')].map(n => Number(n.dataset.index)),
      jump: [...document.querySelectorAll('.square.jump')].map(n => Number(n.dataset.index)),
    })""")
    want = legal_moves(state["cells"], YOU)
    want_clone = sorted(d for s, d, c in want if s == move["from"] and c)
    want_jump = sorted(d for s, d, c in want if s == move["from"] and not c)
    check("tapping a stone marks exactly the squares it can reach",
          sorted(marked["clone"]) == want_clone and sorted(marked["jump"]) == want_jump,
          f"shown {marked}, expected clone {want_clone} jump {want_jump}")
    page.screenshot(path=f"{SHOTS}/ataxx_picked.png")

    expected = apply_move(state["cells"], move["from"], move["to"], move["clone"], YOU)
    page.evaluate("(i) => window.__tap(i)", move["to"])
    page.wait_for_timeout(260)
    check("the board after your move is what the rules say",
          page.evaluate("() => window.__ataxx().cells") == expected)

    page.wait_for_timeout(2500)
    replied = page.evaluate("() => window.__ataxx()")
    check("the opponent answers and the turn comes back",
          replied["turn"] == YOU and not replied["busy"], f"turn={replied['turn']}")

    # play it out, choosing legal moves from here
    for _ in range(300):
        s = page.evaluate("() => window.__ataxx()")
        if s["over"]:
            break
        if s["turn"] != YOU or s["busy"]:
            page.wait_for_timeout(200)
            continue
        mine = sorted(legal_moves(s["cells"], YOU))
        if not mine:
            page.wait_for_timeout(400)
            continue
        src, dst, _clone = random.Random(len(mine)).choice(mine)
        page.evaluate("(i) => window.__tap(i)", src)
        page.evaluate("(i) => window.__tap(i)", dst)
        page.wait_for_timeout(260)
    final = page.evaluate("() => window.__ataxx()")
    check("a whole game reaches an end", final["over"], str(final["counts"]))
    check("and the page agrees with the rules about the result",
          is_over(final["cells"]) and counts(final["cells"]) == final["counts"],
          str(final["counts"]))
    check("the overlay shows the result",
          page.get_attribute("#overlay", "hidden") is None)
    if page.get_attribute("#overlay", "hidden") is None:
        print("      overlay:", page.inner_text("#overlay-message"), "|",
              page.inner_text("#overlay-sub"))
    recorded = final["record"]
    check("the running record was updated",
          recorded["win"] + recorded["loss"] + recorded["draw"] == 1, str(recorded))
    page.screenshot(path=f"{SHOTS}/ataxx_over.png")

    page.click("#overlay-btn")
    page.wait_for_timeout(500)
    fresh = page.evaluate("() => window.__ataxx()")
    check("a new board starts from two stones each",
          fresh["counts"]["you"] == 2 and fresh["counts"]["foe"] == 2 and not fresh["over"],
          str(fresh["counts"]))
    check("and the record survives", fresh["record"] == recorded, str(fresh["record"]))

    check("no page errors", not [e for e in errors if "ERR_" not in e], str(errors))
    browser.close()

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURES"))
for f in failures:
    print("  -", f)
sys.exit(1 if failures else 0)
