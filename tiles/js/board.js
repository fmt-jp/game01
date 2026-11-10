/* The pile: its shape, the rule for what can be taken, and the deal.
 *
 * Tiles sit on an aligned grid -- integer (x, y) in tile widths, z for the
 * layer -- so the classic rule stays plain: a tile can be taken when nothing
 * rests on it and one of its two sides is clear. Nothing is half-offset, so
 * there is no "is a half-tile gap enough to slide through" to argue about.
 *
 * Every pile is dealt by taking an empty one apart in reverse: repeatedly pick
 * two tiles that are free right now, write them down as a pair and lift them
 * off. Played forward, that list of pairs is a solution, so a pile is never
 * handed out unless it can be finished.
 */
const Board = (() => {
  "use strict";

  const MAX_W = 7;   // wider than this and a tile is too small to hit on a phone
  const MAX_D = 6;
  const MAX_Z = 4;

  function spec(level) {
    const n = Math.max(1, level);
    return {
      w: Math.min(MAX_W, 5 + Math.floor((n - 1) / 3)),
      d: Math.min(MAX_D, 4 + Math.floor((n - 1) / 4)),
      maxZ: Math.min(MAX_Z, 2 + Math.floor((n - 1) / 3)),
      target: Math.min(72, 24 + (n - 1) * 4),
      // How far the faces are spread. At 1 as many faces as possible appear
      // only twice: each tile has exactly one partner, so there is nothing to
      // choose and nothing to get wrong. At 0 every face is on the pile four
      // times, as in a real set -- and then picking the wrong one of the two
      // partners is what buries the pile. Measured, not assumed: careless
      // play clears a four-of-a-kind pile about 70% of the time and a
      // two-of-a-kind one about 94%, so the spread narrows as levels rise.
      variety: Math.min(1, Math.max(0, (10 - n) / 9)),
    };
  }

  const key = (x, y, z) => x + "," + y + "," + z;

  /* ---- the rule ---------------------------------------------------- */

  // An index for (x,y,z) -> tile index, over the tiles still on the pile.
  function occupancy(tiles, alive) {
    const at = new Map();
    alive.forEach((i) => at.set(key(tiles[i].x, tiles[i].y, tiles[i].z), i));
    return at;
  }

  function freeWith(tiles, at, i) {
    const t = tiles[i];
    if (at.has(key(t.x, t.y, t.z + 1))) return false;
    return !at.has(key(t.x - 1, t.y, t.z)) || !at.has(key(t.x + 1, t.y, t.z));
  }

  function freeList(tiles, alive) {
    const at = occupancy(tiles, alive);
    return [...alive].filter((i) => freeWith(tiles, at, i));
  }

  // Every pair that could be taken right now.
  function pairs(tiles, alive) {
    const free = freeList(tiles, alive);
    const out = [];
    for (let a = 0; a < free.length; a += 1) {
      for (let b = a + 1; b < free.length; b += 1) {
        if (tiles[free[a]].kind === tiles[free[b]].kind) out.push([free[a], free[b]]);
      }
    }
    return out;
  }

  /* ---- the shape --------------------------------------------------- */

  function shuffle(list, rand) {
    for (let i = list.length - 1; i > 0; i -= 1) {
      const j = Math.floor(rand() * (i + 1));
      [list[i], list[j]] = [list[j], list[i]];
    }
    return list;
  }

  // A height map, mirrored down the middle so the pile looks built rather
  // than scattered. heights[y][x] is how many tiles are stacked on that cell.
  function heights(s, rand) {
    const half = Math.ceil(s.w / 2);
    const h = Array.from({ length: s.d }, () => new Array(s.w).fill(0));
    const put = (x, y, v) => {
      h[y][x] = v;
      h[y][s.w - 1 - x] = v;
    };

    // a base layer with the corners nibbled away
    for (let y = 0; y < s.d; y += 1) {
      for (let x = 0; x < half; x += 1) {
        const corner = (x === 0 && (y === 0 || y === s.d - 1));
        put(x, y, corner && rand() < 0.75 ? 0 : 1);
      }
    }

    // then raise the middle: mounds pull the stack up where it looks best
    const cx = (s.w - 1) / 2, cy = (s.d - 1) / 2;
    let count = h.flat().reduce((a, b) => a + b, 0);
    let guard = 0;
    while (count < s.target && guard < 4000) {
      guard += 1;
      const x = Math.floor(rand() * half);
      const y = Math.floor(rand() * s.d);
      if (h[y][x] === 0 || h[y][x] >= s.maxZ) continue;
      // nearer the middle, likelier to grow
      const far = Math.hypot(x - cx, y - cy) / Math.hypot(cx + 0.5, cy + 0.5);
      if (rand() > 1 - far * 0.85) continue;
      const mirrored = x !== s.w - 1 - x;
      put(x, y, h[y][x] + 1);
      count += mirrored ? 2 : 1;
    }

    // an odd number of tiles cannot be paired off: fix it on the centre column
    if (count % 2 === 1) {
      const mid = (s.w - 1) / 2;
      if (Number.isInteger(mid)) {
        const ys = shuffle([...Array(s.d).keys()], rand);
        for (const y of ys) {
          if (h[y][mid] > 0 && h[y][mid] < s.maxZ) { h[y][mid] += 1; count += 1; break; }
          if (h[y][mid] > 1) { h[y][mid] -= 1; count -= 1; break; }
        }
      }
      if (count % 2 === 1) return null;
    }
    return count >= 8 ? h : null;
  }

  function tilesFrom(h, s) {
    const out = [];
    for (let y = 0; y < s.d; y += 1) {
      for (let x = 0; x < s.w; x += 1) {
        for (let z = 0; z < h[y][x]; z += 1) out.push({ x, y, z, kind: null });
      }
    }
    return out;
  }

  /* ---- the deal ---------------------------------------------------- */

  // Take the full pile apart, two free tiles at a time. The list that comes
  // back is a removal order that works, which is what makes the pile solvable.
  function peel(tiles, alive, rand) {
    const left = new Set(alive);
    const order = [];
    while (left.size) {
      const free = shuffle(freeList(tiles, left), rand);
      if (free.length < 2) return null;
      const a = free[0], b = free[1];
      left.delete(a);
      left.delete(b);
      order.push([a, b]);
    }
    return order;
  }

  // Hand out a face to every pair. `variety` picks how many different faces
  // get used: the fewest is one face per two pairs (four of a kind, as in a
  // real set), the most is one face per pair, capped by how many faces exist.
  function kindsFor(pairCount, variety, rand) {
    const least = Math.ceil(pairCount / 2);
    const most = Math.min(Faces.KINDS.length, pairCount);
    const want = Math.max(least, Math.min(most, Math.round(least + (most - least) * variety)));
    const pool = shuffle(Faces.KINDS.slice(), rand).slice(0, want);
    const twice = pairCount - want;          // faces that fill two pairs
    const slots = [];
    pool.forEach((kind, i) => {
      slots.push(kind);
      if (i < twice) slots.push(kind);
    });
    return shuffle(slots, rand);
  }

  function deal(level, rand) {
    const r = rand || Math.random;
    const s = spec(level);
    for (let attempt = 0; attempt < 60; attempt += 1) {
      const h = heights(s, r);
      if (!h) continue;
      const tiles = tilesFrom(h, s);
      const alive = [...tiles.keys()];
      const order = peel(tiles, alive, r);
      if (!order) continue;
      const slots = kindsFor(order.length, s.variety, r);
      order.forEach(([a, b], i) => { tiles[a].kind = slots[i]; tiles[b].kind = slots[i]; });
      // A pile that opens with almost nothing to take reads as broken even
      // though it is solvable. Ask for a few choices on the first move.
      if (pairs(tiles, new Set(alive)).length < 3) continue;
      return { level, w: s.w, d: s.d, layers: s.maxZ, tiles, solution: order };
    }
    return null;
  }

  /* ---- stacking the rest again ------------------------------------- */

  // When nothing can be taken, the faces still on the pile are dealt again
  // over the same places. Every face is left in an even number, because tiles
  // only ever leave in matching pairs, so they always pair off -- and the deal
  // goes back through peel(), so what is left is solvable again.
  function restack(tiles, alive, rand) {
    const r = rand || Math.random;
    const bag = [...alive].map((i) => tiles[i].kind).sort();
    for (let attempt = 0; attempt < 60; attempt += 1) {
      const order = peel(tiles, alive, r);
      if (!order) continue;
      const slots = [];
      for (let i = 0; i < bag.length; i += 2) slots.push(bag[i]);
      shuffle(slots, r);
      order.forEach(([a, b], i) => { tiles[a].kind = slots[i]; tiles[b].kind = slots[i]; });
      if (pairs(tiles, new Set(alive)).length > 0) return true;
    }
    return false;
  }

  return { spec, deal, restack, freeList, pairs, peel, MAX_W, MAX_D, MAX_Z };
})();
