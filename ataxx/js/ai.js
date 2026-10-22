// Alpha-beta search over the move list, deepened until its time is up so the
// opponent answers at the same speed on any phone.
const AtaxxAI = (() => {
  const { CELLS, SIZE, EMPTY, YOU, FOE } = Ataxx;
  const WIN = 100000;

  // Edges and corners are worth holding: a stone there has fewer neighbours, so
  // fewer squares an opponent can land on to take it.
  const PLACE = new Int8Array(CELLS);
  for (let i = 0; i < CELLS; i++) {
    const [r, c] = Ataxx.rc(i);
    const edge = r === 0 || c === 0 || r === SIZE - 1 || c === SIZE - 1;
    const corner = (r === 0 || r === SIZE - 1) && (c === 0 || c === SIZE - 1);
    PLACE[i] = corner ? 5 : edge ? 2 : 1;
  }

  const LEVELS = {
    easy: { maxDepth: 1, budget: 60, blunder: 0.35 },
    normal: { maxDepth: 3, budget: 220, blunder: 0.08 },
    hard: { maxDepth: 6, budget: 550, blunder: 0 },
  };

  const other = (side) => (side === YOU ? FOE : YOU);

  function evaluate(cells, side) {
    const foe = other(side);
    let material = 0, place = 0;
    for (let i = 0; i < CELLS; i++) {
      if (cells[i] === side) { material++; place += PLACE[i]; }
      else if (cells[i] === foe) { material--; place -= PLACE[i]; }
    }
    const mobility = Ataxx.distinctMoves(cells, side).length
      - Ataxx.distinctMoves(cells, foe).length;
    return material * 14 + place * 2 + mobility;
  }

  function flipsFor(cells, move, side) {
    const foe = other(side);
    let n = 0;
    for (const i of Ataxx.NEIGHBOURS[move.to]) if (cells[i] === foe) n++;
    return n;
  }

  // Try the loudest moves first so the window closes early.
  function ordered(cells, side) {
    return Ataxx.distinctMoves(cells, side)
      .map((m) => ({ m, score: flipsFor(cells, m, side) * 2 + (m.clone ? 1 : 0) }))
      .sort((a, b) => b.score - a.score)
      .map((x) => x.m);
  }

  function terminalScore(cells, side) {
    const { you, foe } = Ataxx.counts(cells);
    const mine = side === YOU ? you : foe;
    const theirs = side === YOU ? foe : you;
    if (mine === theirs) return 0;
    return mine > theirs ? WIN + (mine - theirs) : -WIN - (theirs - mine);
  }

  function search(cells, side, depth, alpha, beta, deadline, state) {
    state.nodes++;
    if (Ataxx.isOver(cells)) return terminalScore(cells, side);
    if (depth === 0) return evaluate(cells, side);
    if ((state.nodes & 255) === 0 && performance.now() > deadline) {
      state.ranOut = true;
      return evaluate(cells, side);
    }

    const moves = ordered(cells, side);
    if (moves.length === 0) {
      // no move: pass, and the other side carries on
      return -search(cells, other(side), depth - 1, -beta, -alpha, deadline, state);
    }

    let best = -Infinity;
    for (const move of moves) {
      const next = Ataxx.applyMove(cells, move, side).cells;
      const score = -search(next, other(side), depth - 1, -beta, -alpha, deadline, state);
      if (score > best) best = score;
      if (best > alpha) alpha = best;
      if (alpha >= beta) break;
      if (state.ranOut) break;
    }
    return best;
  }

  function chooseMove(cells, side, levelName) {
    const level = LEVELS[levelName] || LEVELS.normal;
    const moves = ordered(cells, side);
    if (moves.length === 0) return null;
    if (moves.length === 1) return moves[0];

    // A weak opponent should lose in a way that still looks like playing, so it
    // picks a decent-but-not-best move rather than flailing.
    if (level.blunder > 0 && Math.random() < level.blunder) {
      const pick = Math.min(moves.length - 1, 1 + Math.floor(Math.random() * 3));
      return moves[pick];
    }

    const deadline = performance.now() + level.budget;
    const state = { nodes: 0, ranOut: false };
    let best = moves[0];

    for (let depth = 1; depth <= level.maxDepth; depth++) {
      let localBest = null, localScore = -Infinity;
      let alpha = -Infinity;
      for (const move of moves) {
        const next = Ataxx.applyMove(cells, move, side).cells;
        const score = -search(next, other(side), depth - 1, -Infinity, -alpha, deadline, state);
        if (score > localScore) { localScore = score; localBest = move; }
        if (score > alpha) alpha = score;
        if (state.ranOut) break;
      }
      if (localBest && !state.ranOut) best = localBest;
      if (state.ranOut || Math.abs(localScore) > WIN) break;
    }
    return best;
  }

  return { chooseMove, evaluate, ordered, LEVELS, PLACE };
})();

if (typeof window !== "undefined") window.AtaxxAI = AtaxxAI;
