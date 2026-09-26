(() => {
  const STORAGE_LEVEL = "maze-level";
  const STEP_MS = 55;

  const canvas = document.getElementById("board");
  const ctx = canvas.getContext("2d");
  const boardWrap = document.querySelector(".board-wrap");
  const levelEl = document.getElementById("level");
  const timerEl = document.getElementById("timer");
  const bestEl = document.getElementById("best");
  const keyStatusEl = document.getElementById("key-status");
  const fuelStatusEl = document.getElementById("fuel-status");
  const fuelFillEl = document.getElementById("fuel-fill");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlaySubEl = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const overlayAltBtn = document.getElementById("overlay-alt-btn");
  const newBtn = document.getElementById("new-btn");

  const { N, E, S, W, DIRS, OPPOSITE } = MazeGen;

  let level = 1;
  try { level = Math.max(1, Number(localStorage.getItem(STORAGE_LEVEL)) || 1); } catch (e) {}

  let maze = null;
  let pos = 0;
  let explored = null;
  let visible = new Set();
  let seenItems = new Set();
  let keys = [];
  let oils = [];
  let keysLeft = new Set();
  let oilsLeft = new Set();
  let fuel = 0;
  let maxFuel = 0;
  let oilValue = 0;
  let walkQueue = [];
  let walkTimer = 0;
  let steps = 0;
  let startTime = null;
  let elapsedMs = 0;
  let state = "playing"; // playing | cleared | burnout
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

  function fuelRatio() { return maxFuel === 0 ? 0 : fuel / maxFuel; }

  // The dying lantern closes in on you: less reach, shorter line of sight.
  function sightLimits() {
    const ratio = fuelRatio();
    if (ratio <= 0.12) return { depth: 0, corridor: 2 };
    if (ratio <= 0.3) return { depth: 1, corridor: 6 };
    return { depth: 2, corridor: maze.w + maze.h };
  }

  function reveal() {
    const limits = sightLimits();
    visible = new Set([pos]);
    let frontier = [pos];
    for (let depth = 0; depth < limits.depth; depth++) {
      const next = [];
      for (const cell of frontier) {
        for (const nb of MazeGen.openNeighbors(maze, cell)) {
          if (!visible.has(nb)) { visible.add(nb); next.push(nb); }
        }
      }
      frontier = next;
    }
    for (const dir of DIRS) {
      let cell = pos;
      for (let i = 0; i < limits.corridor; i++) {
        const next = MazeGen.neighborInDir(maze, cell, dir);
        if (next === -1) break;
        visible.add(next);
        cell = next;
      }
    }
    for (const cell of visible) {
      explored[cell] = 1;
      if (keysLeft.has(cell) || oilsLeft.has(cell)) seenItems.add(cell);
    }
  }

  function runPath(dir) {
    const path = [];
    let cell = pos;
    let heading = dir;
    for (let i = 0; i < maze.w * maze.h; i++) {
      const next = MazeGen.neighborInDir(maze, cell, heading);
      if (next === -1) break;
      path.push(next);
      cell = next;
      // stop on anything worth stopping for
      if (cell === maze.goal && keysLeft.size === 0) break;
      if (keysLeft.has(cell) || oilsLeft.has(cell)) break;
      const back = OPPOSITE[heading];
      const exits = DIRS.filter((d) => d !== back && (maze.cells[cell] & d));
      if (exits.length !== 1) break;
      heading = exits[0];
    }
    return path;
  }

  function move(dir) {
    if (state !== "playing" || walkQueue.length > 0) return;
    const path = runPath(dir);
    if (path.length === 0) return;
    if (startTime === null) startTime = performance.now();
    walkQueue = path;
    walkTimer = 0;
  }

  function advanceWalk(dt) {
    if (walkQueue.length === 0 || state !== "playing") return;
    walkTimer += dt;
    while (walkTimer >= STEP_MS && walkQueue.length > 0) {
      walkTimer -= STEP_MS;
      pos = walkQueue.shift();
      steps += 1;
      fuel -= 1;

      if (keysLeft.has(pos)) {
        keysLeft.delete(pos);
        seenItems.delete(pos);
      }
      if (oilsLeft.has(pos)) {
        oilsLeft.delete(pos);
        seenItems.delete(pos);
        fuel = Math.min(maxFuel, fuel + oilValue);
      }

      reveal();

      if (pos === maze.goal && keysLeft.size === 0) {
        walkQueue = [];
        finish();
        return;
      }
      if (fuel <= 0) {
        fuel = 0;
        walkQueue = [];
        burnout();
        return;
      }
    }
  }

  function finish() {
    state = "cleared";
    elapsedMs = startTime === null ? 0 : performance.now() - startTime;
    const isBest = bestMs === null || elapsedMs < bestMs;
    if (isBest) {
      bestMs = Math.round(elapsedMs);
      try { localStorage.setItem(bestKey(), String(bestMs)); } catch (e) {}
    }
    updateHud();
    overlayMessageEl.textContent = "だっしゅつ成功！";
    overlaySubEl.textContent =
      `${maze.w}×${maze.h} ／ ${formatTime(elapsedMs)} ／ ${steps}歩${isBest ? "（ベスト更新！）" : ""}`;
    overlayBtn.textContent = "次の迷路へ";
    overlayAltBtn.hidden = true;
    overlayEl.hidden = false;
  }

  function burnout() {
    state = "burnout";
    elapsedMs = startTime === null ? 0 : performance.now() - startTime;
    updateHud();
    overlayMessageEl.textContent = "明かりが消えた…";
    overlaySubEl.textContent = `鍵 ${keys.length - keysLeft.size}/${keys.length} ／ ${steps}歩`;
    overlayBtn.textContent = "同じ迷路をやり直す";
    overlayAltBtn.hidden = false;
    overlayEl.hidden = false;
  }

  function updateHud() {
    levelEl.textContent = String(level);
    const running = startTime !== null && state === "playing" ? performance.now() - startTime : elapsedMs;
    timerEl.textContent = formatTime(running);
    bestEl.textContent = bestMs === null ? "--:--" : formatTime(bestMs);
    keyStatusEl.textContent = `${keys.length - keysLeft.size}/${keys.length}`;
    fuelStatusEl.textContent = String(Math.max(0, fuel));
    const ratio = Math.max(0, Math.min(1, fuelRatio()));
    fuelFillEl.style.width = `${ratio * 100}%`;
    fuelFillEl.style.background = ratio <= 0.12 ? "#ff5a5a" : ratio <= 0.3 ? "#ffb020" : "#38bdf8";
  }

  function resetRun() {
    pos = maze.start;
    keysLeft = new Set(keys);
    oilsLeft = new Set(oils);
    // You keep the map you drew, so you keep what you saw lying on it: a retry
    // is a second attempt with a plan, not the same blind walk again.
    seenItems = new Set();
    for (const cell of [...keys, ...oils]) {
      if (explored[cell]) seenItems.add(cell);
    }
    fuel = maxFuel;
    walkQueue = [];
    walkTimer = 0;
    steps = 0;
    startTime = null;
    elapsedMs = 0;
    state = "playing";
    overlayEl.hidden = true;
    reveal();
    updateHud();
  }

  function newMaze(targetLevel) {
    const config = MazeGen.levelConfig(targetLevel);
    maze = MazeGen.generate(config.w, config.h);
    const items = MazeGen.placeItems(maze, config.keys, MazeGen.oilCountFor(maze));
    keys = items.keys;
    oils = items.oils;
    const budget = MazeGen.fuelPlan(maze, keys);
    maxFuel = budget.startFuel;
    oilValue = budget.oilValue;
    explored = new Uint8Array(maze.w * maze.h);
    seenItems = new Set();
    bestMs = loadBest();
    resetRun();
    sizeCanvas();
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
    return {
      x: (cell % maze.w) * cellPx,
      y: Math.floor(cell / maze.w) * cellPx,
    };
  }

  function drawKey(cx, cy, alpha) {
    ctx.globalAlpha = alpha;
    ctx.fillStyle = "#ffd76b";
    ctx.beginPath();
    ctx.arc(cx - cellPx * 0.1, cy, cellPx * 0.13, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillRect(cx - cellPx * 0.02, cy - cellPx * 0.045, cellPx * 0.26, cellPx * 0.09);
    ctx.fillRect(cx + cellPx * 0.16, cy, cellPx * 0.05, cellPx * 0.12);
    ctx.globalAlpha = 1;
  }

  function drawOil(cx, cy, alpha) {
    ctx.globalAlpha = alpha;
    ctx.fillStyle = "#ff9f43";
    ctx.beginPath();
    ctx.moveTo(cx, cy - cellPx * 0.22);
    ctx.quadraticCurveTo(cx + cellPx * 0.2, cy + cellPx * 0.06, cx, cy + cellPx * 0.2);
    ctx.quadraticCurveTo(cx - cellPx * 0.2, cy + cellPx * 0.06, cx, cy - cellPx * 0.22);
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  function render() {
    const width = cellPx * maze.w;
    const height = cellPx * maze.h;
    ctx.clearRect(0, 0, width, height);

    for (let cell = 0; cell < maze.w * maze.h; cell++) {
      const { x, y } = cellRect(cell);
      ctx.fillStyle = visible.has(cell) ? "#24354f" : explored[cell] ? "#16233c" : "#0d1526";
      ctx.fillRect(x, y, cellPx, cellPx);
    }

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

    // exit: dim while locked, lit once every key is in hand
    const goal = cellRect(maze.goal);
    const gx = goal.x + cellPx / 2, gy = goal.y + cellPx / 2;
    const unlocked = keysLeft.size === 0;
    const pulse = 0.6 + 0.4 * Math.sin(performance.now() / 350);
    ctx.globalAlpha = unlocked ? 1 : 0.4;
    ctx.fillStyle = unlocked ? "#ffcf6b" : "#7d8ba3";
    ctx.beginPath();
    ctx.moveTo(gx, gy - cellPx * 0.3);
    ctx.lineTo(gx + cellPx * 0.3, gy);
    ctx.lineTo(gx, gy + cellPx * 0.3);
    ctx.lineTo(gx - cellPx * 0.3, gy);
    ctx.closePath();
    ctx.fill();
    if (unlocked) {
      ctx.globalAlpha = 0.25 * pulse;
      ctx.beginPath();
      ctx.arc(gx, gy, cellPx * 0.75, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // items: bright where the lantern reaches, remembered elsewhere
    for (const cell of keysLeft) {
      if (!seenItems.has(cell)) continue;
      const { x, y } = cellRect(cell);
      drawKey(x + cellPx / 2, y + cellPx / 2, visible.has(cell) ? 1 : 0.45);
    }
    for (const cell of oilsLeft) {
      if (!seenItems.has(cell)) continue;
      const { x, y } = cellRect(cell);
      drawOil(x + cellPx / 2, y + cellPx / 2, visible.has(cell) ? 1 : 0.45);
    }

    const p = cellRect(pos);
    const px = p.x + cellPx / 2, py = p.y + cellPx / 2;
    const reach = cellPx * (1.2 + 1.2 * Math.max(0.15, fuelRatio()));
    const glow = ctx.createRadialGradient(px, py, cellPx * 0.2, px, py, reach);
    glow.addColorStop(0, "rgba(255, 233, 180, 0.30)");
    glow.addColorStop(1, "rgba(255, 233, 180, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(px - reach, py - reach, reach * 2, reach * 2);

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
    if (state === "playing" && startTime !== null) updateHud();
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
    if (state === "burnout") {
      resetRun();   // same maze, map you uncovered is kept
      return;
    }
    level += 1;
    try { localStorage.setItem(STORAGE_LEVEL, String(level)); } catch (e) {}
    newMaze(level);
  });

  overlayAltBtn.addEventListener("click", () => newMaze(level));

  window.addEventListener("resize", () => {
    sizeCanvas();
    render();
  });

  newMaze(level);
  requestAnimationFrame(loop);
})();
