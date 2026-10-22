// The whole game in one place: a 7x7 board, moves that either clone a stone to
// a neighbouring square or jump it two squares, and the conversion of every
// enemy stone touching where it landed.
const Ataxx = (() => {
  const SIZE = 7;
  const EMPTY = 0, YOU = 1, FOE = 2, WALL = 3;
  const CELLS = SIZE * SIZE;

  const rc = (i) => [Math.floor(i / SIZE), i % SIZE];
  const idx = (r, c) => r * SIZE + c;
  const inside = (r, c) => r >= 0 && c >= 0 && r < SIZE && c < SIZE;

  // Neighbours (the squares a clone reaches, and the squares that convert) and
  // the ring beyond them (the squares a jump reaches), worked out once.
  const NEIGHBOURS = [];
  const JUMPS = [];
  for (let i = 0; i < CELLS; i++) {
    const [r, c] = rc(i);
    const near = [], far = [];
    for (let dr = -2; dr <= 2; dr++) {
      for (let dc = -2; dc <= 2; dc++) {
        if (dr === 0 && dc === 0) continue;
        const nr = r + dr, nc = c + dc;
        if (!inside(nr, nc)) continue;
        const reach = Math.max(Math.abs(dr), Math.abs(dc));
        (reach === 1 ? near : far).push(idx(nr, nc));
      }
    }
    NEIGHBOURS.push(near);
    JUMPS.push(far);
  }

  const START = {
    [YOU]: [0, CELLS - 1],
    [FOE]: [SIZE - 1, CELLS - SIZE],
  };

  function emptyBoard() {
    const cells = new Int8Array(CELLS);
    for (const side of [YOU, FOE]) for (const i of START[side]) cells[i] = Number(side);
    return cells;
  }

  // Walls come in pairs placed opposite each other, so neither side is handed a
  // better board.
  function addWalls(cells, pairs) {
    const taken = new Set([...START[YOU], ...START[FOE]]);
    // Snapshot first: a for-of over a Set visits whatever is added while it
    // runs, so expanding in place would flood the whole board.
    for (const i of [...taken]) for (const n of NEIGHBOURS[i]) taken.add(n);
    const candidates = [];
    for (let i = 0; i < CELLS; i++) if (!taken.has(i)) candidates.push(i);

    let placed = 0;
    for (let guard = 0; guard < 200 && placed < pairs; guard++) {
      const i = candidates[Math.floor(Math.random() * candidates.length)];
      const mirror = CELLS - 1 - i;
      if (i === mirror || cells[i] !== EMPTY || cells[mirror] !== EMPTY) continue;
      cells[i] = WALL;
      cells[mirror] = WALL;
      placed += 1;
    }
    return placed;
  }

  function newBoard(level) {
    const pairs = level === "wide" ? 0 : 1 + Math.floor(Math.random() * 3);
    for (let attempt = 0; attempt < 40; attempt++) {
      const cells = emptyBoard();
      addWalls(cells, pairs);
      if (legalMoves(cells, YOU).length && legalMoves(cells, FOE).length) return cells;
    }
    return emptyBoard();
  }

  // Every (from, to) a side can play. Clones from different stones to the same
  // square are listed separately because the board shows them that way; the
  // search collapses them itself, since the result is identical.
  function legalMoves(cells, side) {
    const out = [];
    for (let from = 0; from < CELLS; from++) {
      if (cells[from] !== side) continue;
      for (const to of NEIGHBOURS[from]) {
        if (cells[to] === EMPTY) out.push({ from, to, clone: true });
      }
      for (const to of JUMPS[from]) {
        if (cells[to] === EMPTY) out.push({ from, to, clone: false });
      }
    }
    return out;
  }

  // The search only needs one representative per outcome: a clone is decided
  // entirely by where it lands.
  function distinctMoves(cells, side) {
    const seen = new Set();
    const out = [];
    for (const move of legalMoves(cells, side)) {
      const key = move.clone ? `c${move.to}` : `j${move.from},${move.to}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(move);
    }
    return out;
  }

  function applyMove(cells, move, side) {
    const next = Int8Array.from(cells);
    if (!move.clone) next[move.from] = EMPTY;
    next[move.to] = side;
    const flipped = [];
    const foe = side === YOU ? FOE : YOU;
    for (const n of NEIGHBOURS[move.to]) {
      if (next[n] === foe) {
        next[n] = side;
        flipped.push(n);
      }
    }
    return { cells: next, flipped };
  }

  function counts(cells) {
    let you = 0, foe = 0, empty = 0;
    for (let i = 0; i < CELLS; i++) {
      if (cells[i] === YOU) you++;
      else if (cells[i] === FOE) foe++;
      else if (cells[i] === EMPTY) empty++;
    }
    return { you, foe, empty };
  }

  // Over when nobody can move, or one side has been wiped out. A side with no
  // move but stones still on the board simply passes, which is what lets the
  // other side fill the space.
  function isOver(cells) {
    const { you, foe, empty } = counts(cells);
    if (you === 0 || foe === 0 || empty === 0) return true;
    return legalMoves(cells, YOU).length === 0 && legalMoves(cells, FOE).length === 0;
  }

  function winner(cells) {
    const { you, foe } = counts(cells);
    return you === foe ? 0 : you > foe ? YOU : FOE;
  }

  return {
    SIZE, CELLS, EMPTY, YOU, FOE, WALL, NEIGHBOURS, JUMPS, START,
    emptyBoard, newBoard, addWalls, legalMoves, distinctMoves, applyMove,
    counts, isOver, winner, rc, idx,
  };
})();

if (typeof window !== "undefined") window.Ataxx = Ataxx;
