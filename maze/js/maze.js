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

  function levelConfig(level) {
    if (level <= 2) return { w: 9, h: 9 };
    if (level <= 4) return { w: 11, h: 11 };
    if (level <= 6) return { w: 13, h: 13 };
    return { w: 15, h: 15 };
  }

  return {
    N, E, S, W, DIRS, DX, DY, OPPOSITE,
    generate, distances, openNeighbors, neighborInDir, stepCell, levelConfig,
  };
})();

if (typeof window !== "undefined") window.MazeGen = MazeGen;
