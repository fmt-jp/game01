// The world the player walks through: a block grid, the landmarks placed on it,
// and the two bits of geometry the renderer and the physics both need — a ray
// cast against the walls, and a move resolved against them.
const Maze3D = (() => {
  const DIRS = [[0, -1], [1, 0], [0, 1], [-1, 0]];
  const RADIUS = 0.27;

  // Cells sit on odd block coordinates, the wall between two cells on the even
  // one in between. The raycaster wants to walk blocks, the maze rules want to
  // talk about cells, so both views share one array.
  function isWall(maze, bx, by) {
    if (bx < 0 || by < 0 || bx >= maze.cols || by >= maze.rows) return true;
    return maze.blocks[by * maze.cols + bx] === 1;
  }

  function cellOpen(maze, cx, cy, dx, dy) {
    return !isWall(maze, cx * 2 + 1 + dx, cy * 2 + 1 + dy);
  }

  function cellCenter(maze, cell) {
    return {
      x: (cell % maze.w) * 2 + 1.5,
      y: Math.floor(cell / maze.w) * 2 + 1.5,
    };
  }

  // Only the cell's own block counts: the even blocks are the passages between
  // cells, and standing in one is being on the way to a cell, not in it.
  function cellAt(maze, x, y) {
    const bx = Math.floor(x), by = Math.floor(y);
    if (bx % 2 === 0 || by % 2 === 0) return -1;
    const cx = (bx - 1) / 2, cy = (by - 1) / 2;
    if (cx < 0 || cy < 0 || cx >= maze.w || cy >= maze.h) return -1;
    return cy * maze.w + cx;
  }

  function carve(w, h) {
    const cols = w * 2 + 1;
    const rows = h * 2 + 1;
    const blocks = new Uint8Array(cols * rows).fill(1);
    const visited = new Uint8Array(w * h);
    const stack = [0];
    visited[0] = 1;
    blocks[1 * cols + 1] = 0;

    while (stack.length) {
      const cell = stack[stack.length - 1];
      const cx = cell % w;
      const cy = Math.floor(cell / w);
      const options = [];
      for (const [dx, dy] of DIRS) {
        const nx = cx + dx, ny = cy + dy;
        if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
        if (visited[ny * w + nx]) continue;
        options.push([nx, ny, dx, dy]);
      }
      if (options.length === 0) {
        stack.pop();
        continue;
      }
      const [nx, ny, dx, dy] = options[Math.floor(Math.random() * options.length)];
      blocks[(cy * 2 + 1 + dy) * cols + (cx * 2 + 1 + dx)] = 0;
      blocks[(ny * 2 + 1) * cols + (nx * 2 + 1)] = 0;
      visited[ny * w + nx] = 1;
      stack.push(ny * w + nx);
    }
    return { w, h, cols, rows, blocks, loops: 0 };
  }

  function deadEndCells(maze) {
    const out = [];
    for (let cell = 0; cell < maze.w * maze.h; cell++) {
      const cx = cell % maze.w, cy = Math.floor(cell / maze.w);
      let open = 0;
      for (const [dx, dy] of DIRS) if (cellOpen(maze, cx, cy, dx, dy)) open++;
      if (open === 1) out.push(cell);
    }
    return out;
  }

  // A real giant maze is not a tidy tree. Opening a few extra gaps gives it
  // loops, which is also what stops the keep-your-right-hand-on-the-wall trick
  // from walking you straight to the exit.
  function braid(maze, rate) {
    for (const cell of deadEndCells(maze)) {
      if (Math.random() > rate) continue;
      const cx = cell % maze.w, cy = Math.floor(cell / maze.w);
      const options = DIRS.filter(([dx, dy]) => {
        const nx = cx + dx, ny = cy + dy;
        if (nx < 0 || ny < 0 || nx >= maze.w || ny >= maze.h) return false;
        return !cellOpen(maze, cx, cy, dx, dy);
      });
      if (options.length === 0) continue;
      const [dx, dy] = options[Math.floor(Math.random() * options.length)];
      maze.blocks[(cy * 2 + 1 + dy) * maze.cols + (cx * 2 + 1 + dx)] = 0;
      maze.loops += 1;
    }
  }

  function cellDistances(maze, from) {
    const dist = new Int32Array(maze.w * maze.h).fill(-1);
    dist[from] = 0;
    const queue = [from];
    for (let head = 0; head < queue.length; head++) {
      const cell = queue[head];
      const cx = cell % maze.w, cy = Math.floor(cell / maze.w);
      for (const [dx, dy] of DIRS) {
        const nx = cx + dx, ny = cy + dy;
        if (nx < 0 || ny < 0 || nx >= maze.w || ny >= maze.h) continue;
        if (!cellOpen(maze, cx, cy, dx, dy)) continue;
        const nb = ny * maze.w + nx;
        if (dist[nb] === -1) {
          dist[nb] = dist[cell] + 1;
          queue.push(nb);
        }
      }
    }
    return dist;
  }

  // Greedy farthest-point placement: each landmark lands as far as it can from
  // the entrance, the exit and everything already placed.
  function spreadPick(maze, count, candidates, anchors) {
    const taken = new Set(anchors);
    let spread = null;
    for (const anchor of anchors) {
      const d = cellDistances(maze, anchor);
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
      const d = cellDistances(maze, best);
      for (let j = 0; j < spread.length; j++) spread[j] = Math.min(spread[j], d[j]);
    }
    return picked;
  }

  function landmarks(maze, config) {
    const start = 0;
    const fromStart = cellDistances(maze, start);
    let goal = 0;
    for (let i = 0; i < fromStart.length; i++) {
      if (fromStart[i] > fromStart[goal]) goal = i;
    }
    const all = [];
    for (let cell = 0; cell < maze.w * maze.h; cell++) {
      if (cell !== start && cell !== goal) all.push(cell);
    }
    const stamps = spreadPick(maze, config.stamps, all, [start, goal]);

    // Towers belong mid-journey: far enough in to be worth the climb, not so
    // far that you are already at the exit when you find one.
    const far = fromStart[goal];
    const taken = new Set([start, goal, ...stamps]);
    const midway = all.filter((cell) => !taken.has(cell)
      && fromStart[cell] >= far * 0.3 && fromStart[cell] <= far * 0.8);
    const towers = spreadPick(maze, config.towers,
      midway.length >= config.towers ? midway : all, [start, goal, ...stamps]);

    return { start, goal, stamps, towers, goalDistance: far };
  }

  function levelConfig(level) {
    if (level <= 2) return { w: 7, h: 7, stamps: 3, towers: 1, braid: 0.3 };
    if (level <= 4) return { w: 9, h: 9, stamps: 3, towers: 1, braid: 0.35 };
    if (level <= 6) return { w: 11, h: 11, stamps: 4, towers: 2, braid: 0.35 };
    return { w: 13, h: 13, stamps: 4, towers: 2, braid: 0.4 };
  }

  function generate(level) {
    const config = levelConfig(level);
    const maze = carve(config.w, config.h);
    braid(maze, config.braid);
    return { maze, config, marks: landmarks(maze, config) };
  }

  // ---------- geometry shared by the renderer and the physics ----------

  // The player is a square that must not overlap a wall block; testing the two
  // axes separately is what lets you slide along a wall instead of sticking.
  function overlapsWall(maze, x, y, radius) {
    const minX = Math.floor(x - radius), maxX = Math.floor(x + radius);
    const minY = Math.floor(y - radius), maxY = Math.floor(y + radius);
    for (let by = minY; by <= maxY; by++) {
      for (let bx = minX; bx <= maxX; bx++) {
        if (isWall(maze, bx, by)) return true;
      }
    }
    return false;
  }

  function resolveMove(maze, x, y, dx, dy, radius = RADIUS) {
    let nx = x, ny = y;
    if (!overlapsWall(maze, x + dx, y, radius)) nx = x + dx;
    if (!overlapsWall(maze, nx, y + dy, radius)) ny = y + dy;
    return { x: nx, y: ny };
  }

  // Digital differential analysis: step from grid line to grid line, so the
  // first wall hit is exact rather than sampled.
  function castRay(maze, px, py, rdx, rdy) {
    let bx = Math.floor(px), by = Math.floor(py);
    const deltaX = rdx === 0 ? Infinity : Math.abs(1 / rdx);
    const deltaY = rdy === 0 ? Infinity : Math.abs(1 / rdy);
    let stepX, stepY, sideX, sideY;
    if (rdx < 0) { stepX = -1; sideX = (px - bx) * deltaX; }
    else { stepX = 1; sideX = (bx + 1 - px) * deltaX; }
    if (rdy < 0) { stepY = -1; sideY = (py - by) * deltaY; }
    else { stepY = 1; sideY = (by + 1 - py) * deltaY; }

    let side = 0;
    for (let guard = 0; guard < 512; guard++) {
      if (sideX < sideY) { sideX += deltaX; bx += stepX; side = 0; }
      else { sideY += deltaY; by += stepY; side = 1; }
      if (isWall(maze, bx, by)) break;
    }
    const dist = side === 0 ? sideX - deltaX : sideY - deltaY;
    const hit = side === 0 ? py + dist * rdy : px + dist * rdx;
    return { dist, side, texX: hit - Math.floor(hit), bx, by };
  }

  return {
    DIRS, RADIUS,
    generate, levelConfig, carve, braid, landmarks, cellDistances, deadEndCells,
    isWall, cellOpen, cellCenter, cellAt, overlapsWall, resolveMove, castRay,
  };
})();

if (typeof window !== "undefined") window.Maze3D = Maze3D;
