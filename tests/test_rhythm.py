"""Check おとのつぶ: the charts it writes, the timing it judges by, and that a
perfect run really comes out perfect.

The chart rules are applied here from the description rather than read back
from the game, and the judging windows are reimplemented, so the two can
disagree. Timing is taken from the audio clock, which is the one the game plays
to.
"""
import sys
from collections import Counter

from playwright.sync_api import sync_playwright
from _common import CHROMIUM, SHOTS

BASE = "http://localhost:8390"
LANES = 3
failures = []


def check(label, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(f"{label}: {detail}")


def chart_problem(song):
    notes = song["notes"]
    if not notes:
        return "no notes at all"
    if any(n["time"] < 0 or n["time"] > song["length"] for n in notes):
        return "a note falls outside the song"
    # every note sits on the sixteenth-note grid
    for n in notes:
        steps = n["time"] / song["secPerStep"]
        if abs(steps - round(steps)) > 1e-6:
            return f"a note at {n['time']:.4f}s is off the beat grid"
    if any(n["lane"] < 0 or n["lane"] >= LANES for n in notes):
        return "a note is in no lane"
    times = [n["time"] for n in notes]
    if times != sorted(times):
        return "the notes are not in time order"

    # two taps in one lane too close together cannot be played
    last = {}
    for n in notes:
        gap = n["time"] - last.get(n["lane"], -99)
        if gap < 0.16 - 1e-9:
            return f"two notes {gap:.3f}s apart in lane {n['lane']}"
        last[n["lane"]] = n["time"]

    per_lane = Counter(n["lane"] for n in notes)
    if len(per_lane) < LANES or min(per_lane.values()) < len(notes) * 0.18:
        return f"lanes are lopsided: {dict(sorted(per_lane.items()))}"
    if len(notes) / song["length"] < 0.8:
        return f"only {len(notes) / song['length']:.2f} notes a second"

    backing = song["backing"]
    if [b["time"] for b in backing] != sorted(b["time"] for b in backing):
        return "the backing track is out of order"
    if not backing or backing[-1]["time"] < song["length"] * 0.9:
        return "the backing stops before the song does"
    return None


def grade(diff, windows):
    d = abs(diff)
    if d <= windows["PERFECT"]:
        return "perfect"
    if d <= windows["GOOD"]:
        return "good"
    return None


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True,
                              is_mobile=True, device_scale_factor=2)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/rhythm/index.html")
    page.wait_for_timeout(700)

    print("\n[1] the charts it writes")
    songs = page.evaluate("""([levels, per]) => {
      const out = [];
      for (const level of levels) {
        for (let i = 0; i < per; i++) out.push(Song.generate(level));
      }
      return out;
    }""", [[1, 4, 8, 12, 16], 12])
    bad = 0
    for song in songs:
        problem = chart_problem(song)
        if problem:
            bad += 1
            if bad <= 3:
                print(f"      lv{song['level']}: {problem}")
    check(f"all {len(songs)} generated charts are playable", bad == 0, f"{bad} failed")
    for level in (1, 8, 16):
        same = [s for s in songs if s["level"] == level]
        density = sum(len(s["notes"]) / s["length"] for s in same) / len(same)
        secs = sum(s["length"] for s in same) / len(same)
        print(f"      lv{level}: {same[0]['bpm']} bpm, {secs:.0f}s, {density:.2f} notes a second")
    check("the charts get busier as the levels go up",
          sum(len(s["notes"]) / s["length"] for s in songs if s["level"] == 16)
          > sum(len(s["notes"]) / s["length"] for s in songs if s["level"] == 1))
    check("no two songs come out the same",
          len({tuple((n["time"], n["lane"]) for n in s["notes"]) for s in songs}) == len(songs))

    print("\n[2] the judging windows")
    windows = page.evaluate("() => window.__windows")
    print(f"      perfect ±{windows['PERFECT'] * 1000:.0f}ms, good ±{windows['GOOD'] * 1000:.0f}ms")
    probes = []
    for ms in range(-200, 201, 1):
        probes.append(ms / 1000)
    for edge in (windows["PERFECT"], windows["GOOD"]):
        probes += [edge, -edge, edge + 1e-9, -edge - 1e-9]
    got = page.evaluate("(ds) => ds.map((d) => window.__grade(d))", probes)
    wrong = [(d, g, grade(d, windows)) for d, g in zip(probes, got) if g != grade(d, windows)]
    check(f"{len(probes)} offsets graded the same as the rules say", not wrong, str(wrong[:3]))

    print("\n[3] a perfect run")
    page.click("#overlay-btn")
    page.wait_for_timeout(300)
    page.evaluate("() => window.__autoplay(true)")
    state = None
    for _ in range(140):
        page.wait_for_timeout(500)
        state = page.evaluate("() => window.__rhythm()")
        if state["state"] == "done":
            break
    check("the song reaches its end", state["state"] == "done", state["state"])
    total = len(state["notes"])
    print(f"      {total} notes: perfect {state['tally']['perfect']}, "
          f"good {state['tally']['good']}, miss {state['tally']['miss']}")
    check("playing every note on time misses nothing", state["tally"]["miss"] == 0,
          str(state["tally"]))
    check("and they are judged perfect, not merely good",
          state["tally"]["perfect"] >= total * 0.98, str(state["tally"]))
    check("every note was judged",
          sum(state["tally"].values()) == total, f"{sum(state['tally'].values())} of {total}")
    check("the combo ran the whole way", state["bestCombo"] == total,
          f"{state['bestCombo']} of {total}")
    check("a clean run counts as cleared", (state["accuracy"] or 0) >= 0.95,
          str(state["accuracy"]))
    page.screenshot(path=f"{SHOTS}/rhythm_result.png")

    print("\n[4] what was actually scheduled to play")
    scheduled = state["scheduled"]
    check("nothing was scheduled into the past", not [e for e in scheduled if e["late"]],
          f"{len([e for e in scheduled if e['late']])} late of {len(scheduled)}")
    pushed = [e for e in scheduled if e.get("pushed")]
    check("and almost nothing had to be nudged later to stay in the future",
          len(pushed) <= len(scheduled) * 0.02, f"{len(pushed)} of {len(scheduled)} nudged")
    melody = sorted(e["at"] for e in scheduled if e["type"] == "melody")
    backing = sorted(e["at"] for e in scheduled if e["type"] != "melody")
    check("a note was sounded for every note played", len(melody) == total,
          f"{len(melody)} sounds for {total} notes")
    check("the backing played all the way through", len(backing) > 150, str(len(backing)))
    gaps = [round(b - a, 4) for a, b in zip(backing, backing[1:])]
    check("the backing has no silent stretch", max(gaps) < 1.0 if gaps else False,
          f"longest gap {max(gaps) if gaps else '-'}s")

    print("\n[5] the clock, and the offset")
    page.click("#overlay-btn")
    page.wait_for_timeout(2500)
    samples = page.evaluate("""async () => {
      const out = [];
      for (let i = 0; i < 6; i++) {
        const s = window.__rhythm();
        out.push({audio: s.audioTime, wall: performance.now() / 1000,
                  position: s.position, start: s.songStart, offset: s.offsetMs});
        await new Promise(r => setTimeout(r, 400));
      }
      return out;
    }""")
    drift = [(s["audio"] - samples[0]["audio"]) - (s["wall"] - samples[0]["wall"]) for s in samples]
    check("the audio clock keeps real time", max(abs(d) for d in drift) < 0.05,
          f"worst drift {max(abs(d) for d in drift):.3f}s")
    off = samples[-1]
    check("the position it judges by is the audio clock less your offset",
          abs(off["position"] - (off["audio"] - off["start"] - off["offset"] / 1000)) < 0.02,
          str(off))

    before = page.evaluate("() => window.__rhythm().offsetMs")
    page.click("#offset-up")
    page.click("#offset-up")
    page.wait_for_timeout(200)
    check("the offset buttons move it", page.evaluate("() => window.__rhythm().offsetMs") == before + 10,
          str(page.evaluate("() => window.__rhythm().offsetMs")))
    page.reload()
    page.wait_for_timeout(700)
    check("and it is remembered", page.evaluate("() => window.__rhythm().offsetMs") == before + 10,
          str(page.evaluate("() => window.__rhythm().offsetMs")))

    print("\n[6] missing")
    page.click("#overlay-btn")
    page.wait_for_timeout(300)
    start = page.evaluate("() => window.__rhythm()")
    page.wait_for_timeout(6000)
    missed = page.evaluate("() => window.__rhythm()")
    check("notes left alone are counted as missed", missed["tally"]["miss"] > 0,
          str(missed["tally"]))
    check("and the combo is back to nothing", missed["combo"] == 0, str(missed["combo"]))
    stray = page.evaluate("() => window.__tapLane(0)")
    check("a tap with nothing near it is ignored rather than punished",
          stray is None or stray in ("perfect", "good"), str(stray))

    check("no page errors", not [e for e in errors if "ERR_" not in e], str(errors))
    browser.close()

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} FAILURES"))
for f in failures:
    print("  -", f)
sys.exit(1 if failures else 0)
