(() => {
  const STORAGE_LEVEL = "maze-level";
  const STEP_MS = 55;
  const SIGHT_DEPTH = 2;

  const canvas = document.getElementById("board");
  const ctx = canvas.getContext("2d");
  const boardWrap = document.querySelector(".board-wrap");
  const levelEl = document.getElementById("level");
  const timerEl = document.getElementById("timer");
  const bestEl = document.getElementById("best");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlaySubEl = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const newBtn = document.getElementById("new-btn");

  const { N, E, S, W, DIRS, OPPOSITE } = MazeGen;

  let level = 1;
  try { level = Math.max(1, Number(localStorage.getItem(STORAGE_LEVEL)) || 1); } catch (e) {}

  let maze = null;
  let pos = 0;
  let explored = null;
  let visible = new Set();
  let walkQueue = [];
  let walkTimer = 0;
  let steps = 0;
  let startTime = null;
  let elapsedMs = 0;
  let solved = false;
  let cellPx = 0;
  let bestMs = null;

  function bestKey() { return `maze-best-${maze.w}x${maze.h}`; }

  function loadBest() {
    try {
      const raw = localStorage.getItem(bestKey());
      return raw ? Number(raw) : null;
    } catch (e) { return null; }
  }

  function formatTime(ms) {
    const sec = Math.floor(ms / 1000);
    return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
  }

  function reveal() {
    visible = new Set([pos]);
    let frontier = [pos];
    for (let depth = 0; depth < SIGHT_DEPTH; depth++) {
      const next = [];
      for (const cell of frontier) {
        for (const nb of MazeGen.openNeighbors(maze, cell)) {
          if (!visible.has(nb)) { visible.add(nb); next.push(nb); }
        }
      }
      frontier = next;
    }
    // Straight corridors are visible all the way to the wall that ends them.
    for (const dir of DIRS) {
      let cell = pos;
      for (let i = 0; i < maze.w + maze.h; i++) {
        const next = MazeGen.neighborInDir(maze, cell, dir);
        if (next === -1) break;
        visible.add(next);
        cell = next;
      }
    }
    for (const cell of visible) explored[cell] = 1;
  }

  // Walk in `dir` until the corridor forks or ends, following bends along the way.
  function runPath(dir) {
    const path = [];
    let cell = pos;
    let heading = dir;
    for (let i = 0; i < maze.w * maze.h; i++) {
      const next = MazeGen.neighborInDir(maze, cell, heading);
      if (next === -1) break;
      path.push(next);
      cell = next;
      if (cell === maze.goal) break;
      const back = OPPOSITE[heading];
      const exits = DIRS.filter((d) => d !== back && (maze.cells[cell] & d));
      if (exits.length !== 1) break;
      heading = exits[0];
    }
    return path;
  }

  function move(dir) {
    if (solved || walkQueue.length > 0) return;
    const path = runPath(dir);
    if (path.length === 0) return;
    if (startTime === null) startTime = performance.now();
    walkQueue = path;
    walkTimer = 0;
  }

  function advanceWalk(dt) {
    if (walkQueue.length === 0) return;
    walkTimer += dt;
    while (walkTimer >= STEP_MS && walkQueue.length > 0) {
      walkTimer -= STEP_MS;
      pos = walkQueue.shift();
      steps += 1;
      reveal();
      if (pos === maze.goal) {
        walkQueue = [];
        finish();
        return;
      }
    }
  }

  function finish() {
    solved = true;
    elapsedMs = startTime === null ? 0 : performance.now() - startTime;
    const isBest = bestMs === null || elapsedMs < bestMs;
    if (isBest) {
      bestMs = Math.round(elapsedMs);
      try { localStorage.setItem(bestKey(), String(bestMs)); } catch (e) {}
    }
    updateHud();
    overlayMessageEl.textContent = "ゴール！";
    overlaySubEl.textContent =
      `${maze.w}×${maze.h} ／ ${formatTime(elapsedMs)} ／ ${steps}歩${isBest ? "（ベスト更新！）" : ""}`;
    overlayEl.hidden = false;
  }

  function updateHud() {
    levelEl.textContent = String(level);
    const running = startTime !== null && !solved ? performance.now() - startTime : elapsedMs;
    timerEl.textContent = formatTime(running);
    bestEl.textContent = bestMs === null ? "--:--" : formatTime(bestMs);
  }

  function newMaze(targetLevel) {
    const config = MazeGen.levelConfig(targetLevel);
    maze = MazeGen.generate(config.w, config.h);
    pos = maze.start;
    explored = new Uint8Array(maze.w * maze.h);
    walkQueue = [];
    walkTimer = 0;
    steps = 0;
    startTime = null;
    elapsedMs = 0;
    solved = false;
    overlayEl.hidden = true;
    bestMs = loadBest();
    reveal();
    sizeCanvas();
    updateHud();
  }

  // ---------- rendering ----------

  function sizeCanvas() {
    const rect = boardWrap.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const maxHeight = Math.min(window.innerHeight * 0.5, 460);
    const board = Math.floor(Math.min(rect.width - 8, maxHeight));
    cellPx = board / maze.w;
    const height = cellPx * maze.h;
    canvas.style.width = `${board}px`;
    canvas.style.height = `${height}px`;
    canvas.width = Math.round(board * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function cellRect(cell) {
    const x = (cell % maze.w) * cellPx;
    const y = Math.floor(cell / maze.w) * cellPx;
    return { x, y };
  }

  function render() {
    const width = cellPx * maze.w;
    const height = cellPx * maze.h;
    ctx.clearRect(0, 0, width, height);

    for (let cell = 0; cell < maze.w * maze.h; cell++) {
      const { x, y } = cellRect(cell);
      const lit = visible.has(cell);
      ctx.fillStyle = lit ? "#24354f" : explored[cell] ? "#16233c" : "#0d1526";
      ctx.fillRect(x, y, cellPx, cellPx);
    }

    // faint outline so the size of the maze reads even before it is explored
    ctx.strokeStyle = "rgba(148, 169, 201, 0.18)";
    ctx.lineWidth = Math.max(1, cellPx * 0.07);
    ctx.strokeRect(ctx.lineWidth / 2, ctx.lineWidth / 2, width - ctx.lineWidth, height - ctx.lineWidth);

    ctx.strokeStyle = "rgba(148, 169, 201, 0.55)";
    ctx.lineWidth = Math.max(1.5, cellPx * 0.11);
    ctx.lineCap = "round";
    ctx.beginPath();
    for (let cell = 0; cell < maze.w * maze.h; cell++) {
      if (!explored[cell] && !visible.has(cell)) continue;
      const { x, y } = cellRect(cell);
      const open = maze.cells[cell];
      if (!(open & N)) { ctx.moveTo(x, y); ctx.lineTo(x + cellPx, y); }
      if (!(open & S)) { ctx.moveTo(x, y + cellPx); ctx.lineTo(x + cellPx, y + cellPx); }
      if (!(open & W)) { ctx.moveTo(x, y); ctx.lineTo(x, y + cellPx); }
      if (!(open & E)) { ctx.moveTo(x + cellPx, y); ctx.lineTo(x + cellPx, y + cellPx); }
    }
    ctx.stroke();

    // exit: always shown so the player knows which way to head
    const goal = cellRect(maze.goal);
    const gx = goal.x + cellPx / 2, gy = goal.y + cellPx / 2;
    const pulse = 0.6 + 0.4 * Math.sin(performance.now() / 350);
    ctx.globalAlpha = explored[maze.goal] ? 1 : 0.55;
    ctx.fillStyle = "#ffcf6b";
    ctx.beginPath();
    ctx.moveTo(gx, gy - cellPx * 0.3);
    ctx.lineTo(gx + cellPx * 0.3, gy);
    ctx.lineTo(gx, gy + cellPx * 0.3);
    ctx.lineTo(gx - cellPx * 0.3, gy);
    ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = 0.25 * pulse;
    ctx.beginPath();
    ctx.arc(gx, gy, cellPx * 0.75, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;

    // player torch
    const p = cellRect(pos);
    const px = p.x + cellPx / 2, py = p.y + cellPx / 2;
    const glow = ctx.createRadialGradient(px, py, cellPx * 0.2, px, py, cellPx * 2.4);
    glow.addColorStop(0, "rgba(255, 233, 180, 0.30)");
    glow.addColorStop(1, "rgba(255, 233, 180, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(px - cellPx * 2.4, py - cellPx * 2.4, cellPx * 4.8, cellPx * 4.8);

    ctx.fillStyle = "#38bdf8";
    ctx.beginPath();
    ctx.arc(px, py, cellPx * 0.26, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.beginPath();
    ctx.arc(px, py, cellPx * 0.1, 0, Math.PI * 2);
    ctx.fill();
  }

  let lastFrame = performance.now();
  function loop(now) {
    const dt = Math.min(now - lastFrame, 100);
    lastFrame = now;
    advanceWalk(dt);
    if (!solved && startTime !== null) updateHud();
    render();
    requestAnimationFrame(loop);
  }

  // ---------- input ----------

  document.getElementById("btn-up").addEventListener("click", () => move(N));
  document.getElementById("btn-down").addEventListener("click", () => move(S));
  document.getElementById("btn-left").addEventListener("click", () => move(W));
  document.getElementById("btn-right").addEventListener("click", () => move(E));

  window.addEventListener("keydown", (e) => {
    const map = { ArrowUp: N, ArrowDown: S, ArrowLeft: W, ArrowRight: E };
    if (!map[e.key]) return;
    e.preventDefault();
    move(map[e.key]);
  });

  let touchStartX = 0, touchStartY = 0;
  const SWIPE_THRESHOLD = 20;
  canvas.addEventListener("touchstart", (e) => {
    const t = e.changedTouches[0];
    touchStartX = t.clientX;
    touchStartY = t.clientY;
  }, { passive: true });
  canvas.addEventListener("touchend", (e) => {
    const t = e.changedTouches[0];
    const dx = t.clientX - touchStartX;
    const dy = t.clientY - touchStartY;
    if (Math.max(Math.abs(dx), Math.abs(dy)) < SWIPE_THRESHOLD) return;
    if (Math.abs(dx) > Math.abs(dy)) move(dx > 0 ? E : W);
    else move(dy > 0 ? S : N);
  }, { passive: true });

  newBtn.addEventListener("click", () => newMaze(level));

  overlayBtn.addEventListener("click", () => {
    level += 1;
    try { localStorage.setItem(STORAGE_LEVEL, String(level)); } catch (e) {}
    newMaze(level);
  });

  window.addEventListener("resize", () => {
    sizeCanvas();
    render();
  });

  newMaze(level);
  requestAnimationFrame(loop);
})();
