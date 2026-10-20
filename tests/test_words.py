"""Check ことばの輪: the word list, the puzzles it generates, and playing one.

The generator is checked from outside the browser. For each puzzle the page
hands over, this works out independently which dictionary words the wheel can
spell, and insists the puzzle names exactly those — then reads the grid back
cell by cell and insists every run of letters in it is one of them. A crossword
that quietly spells something nobody chose fails here.
"""
import pathlib
import re
import sys
from collections import Counter, deque

from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

BASE = "http://localhost:8390"
ROOT = pathlib.Path(__file__).resolve().parent.parent
HIRAGANA = set(chr(c) for c in range(0x3041, 0x3097))
failures = []


def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(f"{label}: {detail}")


def load_dictionary():
    """Parse the word list straight out of the shipped file."""
    text = (ROOT / "words" / "js" / "dict.js").read_text(encoding="utf-8")
    by_len = {}
    for m in re.finditer(r'^    (\d+): "(.*)",$', text, re.M):
        by_len[int(m.group(1))] = m.group(2).split(" ")
    return by_len


def formable(words, letters, max_length):
    pool = Counter(letters)
    return {w for w in words if len(w) <= max_length and not (Counter(w) - pool)}


def runs_in_grid(cells):
    """Every maximal horizontal or vertical run of two or more letters."""
    height, width = len(cells), len(cells[0])
    found = []
    for r in range(height):
        c = 0
        while c < width:
            if cells[r][c]:
                start = c
                while c < width and cells[r][c]:
                    c += 1
                if c - start >= 2:
                    found.append(("across", r, start, "".join(cells[r][start:c])))
            else:
                c += 1
    for c in range(width):
        r = 0
        while r < height:
            if cells[r][c]:
                start = r
                while r < height and cells[r][c]:
                    r += 1
                if r - start >= 2:
                    found.append(("down", start, c, "".join(cells[k][c] for k in range(start, r))))
            else:
                r += 1
    return found


def connected(cells):
    filled = {(r, c) for r, row in enumerate(cells) for c, ch in enumerate(row) if ch}
    if not filled:
        return False
    start = next(iter(filled))
    seen = {start}
    queue = deque([start])
    while queue:
        r, c = queue.popleft()
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if (nr, nc) in filled and (nr, nc) not in seen:
                seen.add((nr, nc))
                queue.append((nr, nc))
    return seen == filled


def puzzle_problem(p, words_by_len, all_words):
    letters = p["letters"]
    base = p["base"]
    grid_words = [e["word"] for e in p["entries"]]
    every = grid_words + p["bonus"]

    if Counter(letters) != Counter(base):
        return f"wheel {''.join(letters)} is not the letters of {base}"
    if base not in grid_words:
        return f"the base word {base} is not in the grid"
    if len(set(every)) != len(every):
        return "a word appears twice"

    expected = formable(all_words, letters, len(base))
    if set(every) != expected:
        missing = expected - set(every)
        extra = set(every) - expected
        return f"word set differs: missing {sorted(missing)[:4]}, extra {sorted(extra)[:4]}"

    cells = p["grid"]
    if len(cells) > 9 or len(cells[0]) > 9:
        return f"grid is {len(cells[0])}x{len(cells)}, too big for a phone"
    if not connected(cells):
        return "the grid is in more than one piece"

    # each entry really sits where it says it does
    for e in p["entries"]:
        for i, ch in enumerate(e["word"]):
            r = e["row"] + (i if e["dir"] == "down" else 0)
            c = e["col"] + (i if e["dir"] == "across" else 0)
            if not (0 <= r < len(cells) and 0 <= c < len(cells[0])) or cells[r][c] != ch:
                return f"{e['word']} is not at {e['row']},{e['col']} {e['dir']}"

    # and nothing else is spelled out by accident
    placed = {(e["dir"], e["row"], e["col"], e["word"]) for e in p["entries"]}
    for run in runs_in_grid(cells):
        if run not in placed:
            return f"the grid also spells {run[3]} ({run[0]} at {run[1]},{run[2]})"
    if len(runs_in_grid(cells)) != len(p["entries"]):
        return "a listed word is missing from the grid"
    return None


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True,
                              is_mobile=True, device_scale_factor=2)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/words/index.html")
    page.wait_for_timeout(800)

    print("\n[1] the word list")
    by_len = load_dictionary()
    all_words = [w for ws in by_len.values() for w in ws]
    check("the page loaded the same list this check parsed",
          page.evaluate("() => WordDict.size") == len(set(all_words)),
          f"page {page.evaluate('() => WordDict.size')} vs file {len(set(all_words))}")
    check("no duplicates", len(all_words) == len(set(all_words)),
          f"{len(all_words) - len(set(all_words))} repeated")
    bad = [w for w in all_words if not (3 <= len(w) <= 6) or any(ch not in HIRAGANA for ch in w)]
    check("every word is 3 to 6 hiragana", not bad, str(bad[:5]))
    print(f"      {len(all_words)} words: " +
          ", ".join(f"{n} kana {len(by_len[n])}" for n in sorted(by_len)))

    print("\n[2] generated puzzles")
    batch = page.evaluate("""([levels, per]) => {
      const out = [];
      const t0 = performance.now();
      for (const level of levels) {
        for (let i = 0; i < per; i++) {
          const p = WordPuzzle.generate(level);
          if (!p) { out.push(null); continue; }
          out.push({level, base: p.base, letters: p.letters, bonus: p.bonus,
                    entries: p.entries, grid: p.grid.cells, attempts: p.attempts});
        }
      }
      return {out, ms: performance.now() - t0};
    }""", [[1, 4, 8, 14], 40])
    puzzles = batch["out"]
    check("every call produced a puzzle", all(p for p in puzzles),
          f"{sum(1 for p in puzzles if not p)} gave up")
    bad = 0
    for p in puzzles:
        if not p:
            continue
        problem = puzzle_problem(p, by_len, all_words)
        if problem:
            bad += 1
            if bad <= 3:
                print(f"      lv{p['level']} {p['base']}: {problem}")
    check(f"all {len(puzzles)} puzzles are sound", bad == 0, f"{bad} failed")
    good = [p for p in puzzles if p]
    print(f"      {batch['ms'] / len(puzzles):.1f} ms per puzzle, "
          f"{len({p['base'] for p in good})} distinct base words out of {len(good)}")
    for level in (1, 4, 8, 14):
        same = [p for p in good if p["level"] == level]
        words = sum(len(p["entries"]) for p in same) / len(same)
        side = max(max(len(p["grid"]), len(p["grid"][0])) for p in same)
        print(f"      lv{level}: {words:.1f} words per grid, largest grid side {side}")
    check("puzzles are built fast enough to feel instant",
          batch["ms"] / len(puzzles) < 60, f"{batch['ms'] / len(puzzles):.1f} ms")

    print("\n[3] playing one through the wheel")
    state = page.evaluate("() => window.__words()")
    target = [e["word"] for e in state["entries"]]
    print(f"      base {state['base']}, wheel {''.join(state['letters'])}, {len(target)} words")
    check("nothing is revealed at the start",
          sum(sum(row) for row in state["openCells"]) == 0)

    page.evaluate("(w) => window.__spell(w)", target[0])
    page.wait_for_timeout(400)
    after = page.evaluate("() => window.__words()")
    check("spelling a grid word opens its cells",
          after["solved"] == [target[0]]
          and sum(sum(row) for row in after["openCells"]) == len(target[0]),
          f"solved={after['solved']}")
    check("the counter follows", page.inner_text("#found").strip() == f"1/{len(target)}",
          page.inner_text("#found"))

    # a word the wheel can spell that is not in the grid counts as a bonus
    if state["bonusWords"]:
        before = page.evaluate("() => window.__words().bonusTotal")
        page.evaluate("(w) => window.__spell(w)", state["bonusWords"][0])
        page.wait_for_timeout(300)
        check("a word outside the grid counts as a bonus",
              page.evaluate("() => window.__words().bonusTotal") == before + 1)

    # nonsense is rejected
    before = page.evaluate("() => window.__words()")
    page.evaluate("(w) => window.__spell(w)", "".join(state["letters"][:2]) * 1)
    page.wait_for_timeout(250)
    now = page.evaluate("() => window.__words()")
    check("a non-word changes nothing",
          now["solved"] == before["solved"] and now["bonusTotal"] == before["bonusTotal"])

    page.screenshot(path=f"{SHOTS}/words_mid.png")
    for word in target[1:]:
        page.evaluate("(w) => window.__spell(w)", word)
        page.wait_for_timeout(120)
    page.wait_for_timeout(400)
    done = page.evaluate("() => window.__words()")
    check("finding every word clears the puzzle", done["cleared"]
          and page.get_attribute("#overlay", "hidden") is None, str(done["solved"]))
    check("every cell of the grid is open",
          sum(sum(row) for row in done["openCells"])
          == sum(1 for row in done["grid"] for ch in row if ch))
    if page.get_attribute("#overlay", "hidden") is None:
        print("      overlay:", page.inner_text("#overlay-message"), "|",
              page.inner_text("#overlay-sub"))
    page.screenshot(path=f"{SHOTS}/words_cleared.png")

    page.click("#overlay-btn")
    page.wait_for_timeout(500)
    nxt = page.evaluate("() => window.__words()")
    check("the next puzzle starts at level 2", nxt["level"] == 2 and not nxt["cleared"],
          str(nxt["level"]))
    check("and it is a different board", nxt["base"] != state["base"] or nxt["entries"] != state["entries"])

    print("\n[4] hints")
    before = page.evaluate("() => window.__words()")
    page.click("#hint-btn")
    page.wait_for_timeout(300)
    after = page.evaluate("() => window.__words()")
    check("a hint opens exactly one cell",
          sum(sum(r) for r in after["openCells"]) == sum(sum(r) for r in before["openCells"]) + 1,
          f"{sum(sum(r) for r in before['openCells'])} -> {sum(sum(r) for r in after['openCells'])}")
    check("and costs one", after["hintsLeft"] == before["hintsLeft"] - 1)
    for _ in range(5):
        if page.get_attribute("#hint-btn", "disabled") is not None:
            break
        page.click("#hint-btn")
        page.wait_for_timeout(150)
    check("hints run out and the button goes dead",
          page.evaluate("() => window.__words().hintsLeft") == 0
          and page.get_attribute("#hint-btn", "disabled") is not None)

    print("\n[5] shuffle keeps the puzzle")
    before = page.evaluate("() => window.__words()")
    page.click("#shuffle-btn")
    page.wait_for_timeout(300)
    after = page.evaluate("() => window.__words()")
    check("the same letters, possibly reordered",
          sorted(after["letters"]) == sorted(before["letters"])
          and after["entries"] == before["entries"])
    check("and nothing already found is lost", after["solved"] == before["solved"])

    check("no page errors", not [e for e in errors if "ERR_" not in e], str(errors))
    browser.close()

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURES"))
for f in failures:
    print("  -", f)
sys.exit(1 if failures else 0)
