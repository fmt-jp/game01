/* はしわたし -- the islands, the bridges between them, and the one answer.
 *
 * A puzzle is built answer-first: islands are dropped one at a time, each one
 * reached by a bridge from an island already placed, so the finished thing is
 * connected by construction. The numbers are then read off that answer. What
 * makes it a puzzle rather than a drawing is the last step: the same solver
 * the game ships with counts the answers, and a board is only handed out when
 * the count is exactly one.
 */
const Puzzle = (() => {
  "use strict";

  const DIRS = [[0, 1], [0, -1], [1, 0], [-1, 0]];

  function spec(level) {
    const n = Math.max(1, level);
    return {
      w: Math.min(7, 4 + Math.ceil(n / 3)),
      h: Math.min(9, 5 + Math.ceil(n / 2)),
      islands: Math.min(24, 6 + Math.floor((n - 1) * 1.4)),
      // how often a link is a double bridge; more doubles read as harder
      doubles: Math.min(0.5, 0.18 + n * 0.025),
      // how many boards to make and sift through, keeping the knottiest
      tries: Math.min(6, 1 + Math.floor(n / 3)),
      // extra bridges tried on top of the tree, each kept only if the
      // board still has exactly one answer
      extras: Math.min(10, Math.floor(n / 2)),
    };
  }

  /* ---- the board as a thing to reason about ------------------------ */

  // Two islands are joined by a possible bridge when they are in the same row
  // or column with nothing but water between them.
  function edgesOf(islands) {
    const at = new Map(islands.map((is, i) => [is.r + "," + is.c, i]));
    // The walk needs a far edge to stop at, or looking right from the
    // rightmost island runs off down the number line for ever.
    const lastR = Math.max(...islands.map((is) => is.r));
    const lastC = Math.max(...islands.map((is) => is.c));
    const edges = [];
    islands.forEach((is, i) => {
      for (const [dr, dc] of [[0, 1], [1, 0]]) {
        let r = is.r + dr, c = is.c + dc;
        while (r <= lastR && c <= lastC) {
          const hit = at.get(r + "," + c);
          if (hit !== undefined) {
            edges.push({ a: i, b: hit, dir: dr ? "v" : "h" });
            break;
          }
          r += dr;
          c += dc;
        }
      }
    });
    return edges;
  }

  function crossesOf(islands, edges) {
    const span = edges.map((e) => {
      const A = islands[e.a], B = islands[e.b];
      return {
        dir: e.dir,
        r1: Math.min(A.r, B.r), r2: Math.max(A.r, B.r),
        c1: Math.min(A.c, B.c), c2: Math.max(A.c, B.c),
      };
    });
    const out = edges.map(() => []);
    for (let i = 0; i < edges.length; i += 1) {
      for (let j = i + 1; j < edges.length; j += 1) {
        const p = span[i], q = span[j];
        if (p.dir === q.dir) continue;
        const h = p.dir === "h" ? p : q;
        const v = p.dir === "h" ? q : p;
        if (v.c1 > h.c1 && v.c1 < h.c2 && h.r1 > v.r1 && h.r1 < v.r2) {
          out[i].push(j);
          out[j].push(i);
        }
      }
    }
    return out;
  }

  function incidence(islands, edges) {
    const out = islands.map(() => []);
    edges.forEach((e, i) => {
      out[e.a].push(i);
      out[e.b].push(i);
    });
    return out;
  }

  function connected(islands, edges, counts) {
    const near = islands.map(() => []);
    edges.forEach((e, i) => {
      if (counts[i] > 0) {
        near[e.a].push(e.b);
        near[e.b].push(e.a);
      }
    });
    const seen = new Array(islands.length).fill(false);
    const stack = [0];
    seen[0] = true;
    let n = 1;
    while (stack.length) {
      for (const next of near[stack.pop()]) {
        if (!seen[next]) { seen[next] = true; n += 1; stack.push(next); }
      }
    }
    return n === islands.length;
  }

  /* ---- the solver -------------------------------------------------- */

  // Count the ways to finish the board, stopping at `limit`. Islands are
  // filled in most-constrained first, and every way of spreading an island's
  // remaining bridges over its free edges is tried in turn.
  // How much searching the last solve took. A board that falls out in a few
  // steps is one a person can reason straight through; one that takes many is
  // a board where the solver had to try something and back out of it. It is
  // the only measure of hard here, so it is what the levels are chosen by.
  let steps = 0;

  function solve(islands, edges, limit) {
    const stop = limit || 2;
    steps = 0;
    const cross = crossesOf(islands, edges);
    const inc = incidence(islands, edges);
    const counts = new Array(edges.length).fill(-1);
    const found = [];

    const other = (e, i) => (edges[e].a === i ? edges[e].b : edges[e].a);

    function room(e, i) {
      // how much could still be put on edge e, from island i's side
      if (counts[e] >= 0) return counts[e];
      if (cross[e].some((x) => counts[x] > 0)) return 0;
      const far = other(e, i);
      let used = 0;
      for (const f of inc[far]) if (counts[f] > 0) used += counts[f];
      return Math.min(2, islands[far].need - used);
    }

    function ways(i) {
      let used = 0;
      const free = [];
      for (const e of inc[i]) {
        if (counts[e] >= 0) used += counts[e];
        else free.push(e);
      }
      const need = islands[i].need - used;
      if (need < 0) return null;
      const caps = free.map((e) => room(e, i));
      if (caps.reduce((a, b) => a + b, 0) < need) return null;
      const out = [];
      (function walk(n, left, picked) {
        if (out.length > 64) return;              // a wide island: leave it
        if (n === free.length) {
          if (left === 0) out.push(picked.slice());
          return;
        }
        const most = Math.min(caps[n], left);
        for (let k = 0; k <= most; k += 1) {
          picked.push(k);
          walk(n + 1, left - k, picked);
          picked.pop();
        }
      })(0, need, []);
      return { free, out };
    }

    function search() {
      steps += 1;
      let pick = -1, best = null;
      for (let i = 0; i < islands.length; i += 1) {
        if (inc[i].every((e) => counts[e] >= 0)) continue;
        const w = ways(i);
        if (w === null) return;                    // this island cannot be met
        if (best === null || w.out.length < best.out.length) {
          best = w;
          pick = i;
          if (w.out.length <= 1) break;
        }
      }
      if (pick === -1) {
        // Every island, not just the ones the search stopped at: an island
        // whose bridges were all settled by its neighbours is never picked,
        // so its own number has to be checked here, or an arrangement that
        // leaves it short would be counted as an answer.
        const ends = new Array(islands.length).fill(0);
        edges.forEach((e, n) => { ends[e.a] += counts[n]; ends[e.b] += counts[n]; });
        if (ends.every((n, i) => n === islands[i].need)
            && connected(islands, edges, counts)) {
          found.push(counts.slice());
        }
        return;
      }
      for (const option of best.out) {
        if (found.length >= stop) return;
        best.free.forEach((e, n) => { counts[e] = option[n]; });
        if (sane()) search();
        best.free.forEach((e) => { counts[e] = -1; });
      }
    }

    // Cheap pruning: no bridge may cross one that is already there, and every
    // island must still be able to reach every other over edges that are not
    // yet ruled out.
    function sane() {
      for (let e = 0; e < edges.length; e += 1) {
        if (counts[e] > 0 && cross[e].some((x) => counts[x] > 0)) return false;
      }
      const maybe = counts.map((c) => (c === -1 ? 1 : c));
      return connected(islands, edges, maybe);
    }

    search();
    return found;
  }

  /* ---- building one ------------------------------------------------ */

  function shuffle(list, rand) {
    for (let i = list.length - 1; i > 0; i -= 1) {
      const j = Math.floor(rand() * (i + 1));
      [list[i], list[j]] = [list[j], list[i]];
    }
    return list;
  }

  // Which bridges cross which is decided by where the islands are, so a pair
  // of cells is enough to ask the question.
  function cuts(A, B, C, D) {
    const flat = A.r === B.r;
    if ((C.r === D.r) === flat) return false;
    const h = flat ? { r: A.r, c1: Math.min(A.c, B.c), c2: Math.max(A.c, B.c) }
                   : { r: C.r, c1: Math.min(C.c, D.c), c2: Math.max(C.c, D.c) };
    const v = flat ? { c: C.c, r1: Math.min(C.r, D.r), r2: Math.max(C.r, D.r) }
                   : { c: A.c, r1: Math.min(A.r, B.r), r2: Math.max(A.r, B.r) };
    return v.c > h.c1 && v.c < h.c2 && h.r > v.r1 && h.r < v.r2;
  }

  // Grow a tree of islands: every island after the first arrives on the end of
  // one bridge from an island already there. A tree is connected by
  // construction and, being thin, is far likelier to have only one answer
  // than a dense tangle is -- so the extras come later, one at a time, and
  // only if they leave the answer alone.
  function grow(s, rand) {
    const at = new Map();
    const islands = [];
    const drawn = [];                       // {a, b, n} in the order laid

    const put = (r, c) => {
      at.set(r + "," + c, islands.length);
      islands.push({ r, c, need: 0 });
      return islands.length - 1;
    };
    put(Math.floor(rand() * s.h), Math.floor(rand() * s.w));

    const degree = (i) => drawn.reduce((n, l) => n + (l.a === i || l.b === i ? l.n : 0), 0);

    // nothing may sit on a bridge, and no bridge may cut another
    const onBridge = (r, c) => drawn.some(({ a, b }) => {
      const A = islands[a], B = islands[b];
      if (A.r === B.r) return r === A.r && c > Math.min(A.c, B.c) && c < Math.max(A.c, B.c);
      return c === A.c && r > Math.min(A.r, B.r) && r < Math.max(A.r, B.r);
    });
    const wouldCut = (A, B) => drawn.some(({ a, b }) => cuts(A, B, islands[a], islands[b]));

    let guard = 0;
    while (islands.length < s.islands && guard < 1200) {
      guard += 1;
      const from = Math.floor(rand() * islands.length);
      const A = islands[from];
      const [dr, dc] = DIRS[Math.floor(rand() * 4)];
      const reach = 2 + Math.floor(rand() * 3);
      const r = A.r + dr * reach, c = A.c + dc * reach;
      if (r < 0 || c < 0 || r >= s.h || c >= s.w) continue;
      if (at.has(r + "," + c) || onBridge(r, c)) continue;
      // Islands may not sit side by side: a bridge needs water to span, and
      // two touching islands would draw as one blob with a line inside it.
      if (DIRS.some(([ar, ac]) => at.has((r + ar) + "," + (c + ac)))) continue;
      const span = rand() < s.doubles ? 2 : 1;
      if (degree(from) + span > 8) continue;
      // the water between has to be empty, and the crossing clear
      let clear = true;
      for (let k = 1; k < reach; k += 1) {
        if (at.has((A.r + dr * k) + "," + (A.c + dc * k))) { clear = false; break; }
      }
      if (!clear || wouldCut(A, { r, c })) continue;
      drawn.push({ a: from, b: put(r, c), n: span });
    }
    if (islands.length < Math.max(4, s.islands - 3)) return null;
    return { islands, drawn };
  }

  // Read the clues off a set of bridges.
  function clue(islands, edges, counts) {
    islands.forEach((is) => { is.need = 0; });
    edges.forEach((e, i) => {
      islands[e.a].need += counts[i];
      islands[e.b].need += counts[i];
    });
  }

  function generate(level, rand) {
    const r = rand || Math.random;
    const s = spec(level);
    let keep = null;
    for (let round = 0; round < s.tries; round += 1) {
      const made = one(s, level, r);
      if (!made) continue;
      if (!keep || made.steps > keep.steps) keep = made;
    }
    return keep;
  }

  function one(s, level, r) {
    for (let attempt = 0; attempt < 140; attempt += 1) {
      const grown = grow(s, r);
      if (!grown) continue;
      const { islands } = grown;
      const edges = edgesOf(islands);
      const index = new Map(edges.map((e, i) => [Math.min(e.a, e.b) + "," + Math.max(e.a, e.b), i]));
      const counts = new Array(edges.length).fill(0);
      for (const l of grown.drawn) counts[index.get(Math.min(l.a, l.b) + "," + Math.max(l.a, l.b))] = l.n;
      clue(islands, edges, counts);
      if (solve(islands, edges, 2).length !== 1) continue;

      // Thicken it, keeping only what leaves the answer alone. Each kept
      // bridge makes the board busier to read without making it guesswork.
      const cross = crossesOf(islands, edges);
      let added = 0;
      for (const i of shuffle([...edges.keys()], r)) {
        if (added >= s.extras) break;
        if (counts[i] >= 2) continue;
        if (counts[i] === 0 && cross[i].some((x) => counts[x] > 0)) continue;
        if (islands[edges[i].a].need >= 8 || islands[edges[i].b].need >= 8) continue;
        counts[i] += 1;
        clue(islands, edges, counts);
        if (solve(islands, edges, 2).length === 1) {
          added += 1;
        } else {
          counts[i] -= 1;
          clue(islands, edges, counts);
        }
      }
      solve(islands, edges, 2);
      return { level, w: s.w, h: s.h, islands, edges, answer: counts.slice(), steps };
    }
    return null;
  }

  return { spec, generate, solve, edgesOf, crossesOf, incidence, connected };
})();
