const MazeGen = (() => {
  const N = 1, E = 2, S = 4, W = 8;
  const DIRS = [N, E, S, W];
  const DX = { [N]: 0, [E]: 1, [S]: 0, [W]: -1 };
  const DY = { [N]: -1, [E]: 0, [S]: 1, [W]: 0 };
  const OPPOSITE = { [N]: S, [E]: W, [S]: N, [W]: E };

  function stepCell(cell, dir, w) {
    const x = (cell % w) + DX[dir];
    const y = Math.floor(cell / w) + DY[dir];
    return { x, y, cell: y * w + x };
  }

  function inside(x, y, w, h) {
    return x >= 0 && x < w && y >= 0 && y < h;
  }

  function openNeighbors(maze, cell) {
    const out = [];
    for (const dir of DIRS) {
      if (maze.cells[cell] & dir) out.push(stepCell(cell, dir, maze.w).cell);
    }
    return out;
  }

  function neighborInDir(maze, cell, dir) {
    if (!(maze.cells[cell] & dir)) return -1;
    return stepCell(cell, dir, maze.w).cell;
  }

  // Distance in cells from `from` to every reachable cell (-1 when unreachable).
  function distances(maze, from) {
    const dist = new Int32Array(maze.w * maze.h).fill(-1);
    dist[from] = 0;
    const queue = [from];
    for (let head = 0; head < queue.length; head++) {
      const cell = queue[head];
      for (const nb of openNeighbors(maze, cell)) {
        if (dist[nb] === -1) {
          dist[nb] = dist[cell] + 1;
          queue.push(nb);
        }
      }
    }
    return dist;
  }

  // Recursive-backtracker maze: one winding corridor system, no loops,
  // every cell reachable.
  function generate(w, h) {
    const cells = new Uint8Array(w * h);
    const visited = new Uint8Array(w * h);
    const start = 0;
    const stack = [start];
    visited[start] = 1;

    while (stack.length) {
      const cell = stack[stack.length - 1];
      const x = cell % w, y = Math.floor(cell / w);
      const options = [];
      for (const dir of DIRS) {
        const nx = x + DX[dir], ny = y + DY[dir];
        if (!inside(nx, ny, w, h)) continue;
        if (visited[ny * w + nx]) continue;
        options.push(dir);
      }
      if (options.length === 0) {
        stack.pop();
        continue;
      }
      const dir = options[Math.floor(Math.random() * options.length)];
      const next = stepCell(cell, dir, w).cell;
      cells[cell] |= dir;
      cells[next] |= OPPOSITE[dir];
      visited[next] = 1;
      stack.push(next);
    }

    const maze = { w, h, cells, start, goal: start };
    // Put the exit as far from the entrance as the maze allows.
    const dist = distances(maze, start);
    let goal = start;
    for (let i = 0; i < dist.length; i++) {
      if (dist[i] > dist[goal]) goal = i;
    }
    maze.goal = goal;
    maze.goalDistance = dist[goal];
    return maze;
  }

  function deadEnds(maze) {
    const out = [];
    for (let cell = 0; cell < maze.w * maze.h; cell++) {
      let openings = 0;
      for (const dir of DIRS) if (maze.cells[cell] & dir) openings++;
      if (openings === 1) out.push(cell);
    }
    return out;
  }

  // Greedy farthest-point placement: each new item lands as far as possible
  // from the entrance, the exit and everything placed before it.
  function spreadPick(maze, count, candidates, anchors) {
    const taken = new Set(anchors);
    let spread = null;
    for (const anchor of anchors) {
      const d = distances(maze, anchor);
      if (spread === null) spread = Array.from(d);
      else for (let i = 0; i < spread.length; i++) spread[i] = Math.min(spread[i], d[i]);
    }
    const picked = [];
    for (let i = 0; i < count; i++) {
      let best = -1;
      for (const cell of candidates) {
        if (taken.has(cell)) continue;
        if (best === -1 || spread[cell] > spread[best]) best = cell;
      }
      if (best === -1) break;
      picked.push(best);
      taken.add(best);
      const d = distances(maze, best);
      for (let j = 0; j < spread.length; j++) spread[j] = Math.min(spread[j], d[j]);
    }
    return picked;
  }

  // Shortest walk that collects every key and then reaches the exit.
  function routeLength(maze, keys, goal) {
    const fromStart = distances(maze, maze.start);
    const fromKey = keys.map((k) => distances(maze, k));
    const fromGoal = distances(maze, goal);

    let best = Infinity;
    const order = keys.map((_, i) => i);
    const permute = (arr, prefix = []) => {
      if (arr.length === 0) {
        let length = fromStart[keys[prefix[0]]];
        for (let i = 0; i < prefix.length - 1; i++) {
          length += fromKey[prefix[i]][keys[prefix[i + 1]]];
        }
        length += fromGoal[keys[prefix[prefix.length - 1]]];
        best = Math.min(best, length);
        return;
      }
      for (let i = 0; i < arr.length; i++) {
        permute([...arr.slice(0, i), ...arr.slice(i + 1)], [...prefix, arr[i]]);
      }
    };
    if (keys.length === 0) return fromGoal[maze.start];
    permute(order);
    return best;
  }

  function placeItems(maze, keyCount, oilCount) {
    const total = maze.w * maze.h;
    const all = [];
    for (let cell = 0; cell < total; cell++) {
      if (cell !== maze.start && cell !== maze.goal) all.push(cell);
    }
    const keys = spreadPick(maze, keyCount, all, [maze.start, maze.goal]);

    const used = new Set([maze.start, maze.goal, ...keys]);
    // Oil sits in dead ends where possible, so fetching it is a real detour.
    const pockets = deadEnds(maze).filter((cell) => !used.has(cell));
    const oils = spreadPick(maze, oilCount, pockets.length >= oilCount ? pockets : all,
      [maze.start, maze.goal, ...keys]);

    return { keys, oils };
  }

  function levelConfig(level) {
    if (level <= 2) return { w: 9, h: 9, keys: 3 };
    if (level <= 4) return { w: 11, h: 11, keys: 3 };
    if (level <= 6) return { w: 13, h: 13, keys: 4 };
    return { w: 15, h: 15, keys: 4 };
  }

  // One can per 24 cells, never fewer than four, so even the small mazes have
  // somewhere to go when the lantern runs low.
  function oilCountFor(maze) {
    return Math.max(4, Math.round((maze.w * maze.h) / 24));
  }

  // Everything is measured against the perfect route: the lantern starts with a
  // third more fuel than that route costs, and the cans together bring the
  // maze's whole supply to a little over three times it. Exploring blind is
  // affordable, wandering is not, and bigger mazes stay the harder ones because
  // they need proportionally more walking to uncover.
  function fuelPlan(maze, keys) {
    const optimal = routeLength(maze, keys, maze.goal);
    const oilCount = oilCountFor(maze);
    const startFuel = Math.round(optimal * 1.35);
    return {
      optimal,
      oilCount,
      startFuel,
      oilValue: Math.max(1, Math.round((optimal * 3.2 - startFuel) / oilCount)),
    };
  }

  return {
    N, E, S, W, DIRS, DX, DY, OPPOSITE,
    generate, distances, openNeighbors, neighborInDir, stepCell, levelConfig,
    deadEnds, placeItems, routeLength, oilCountFor, fuelPlan,
  };
})();

if (typeof window !== "undefined") window.MazeGen = MazeGen;
