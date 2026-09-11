(() => {
  const SIZE = 4;
  const STORAGE_BEST = "fifteen-best-time";
  const GAP = 8;

  const boardEl = document.getElementById("board");
  const movesEl = document.getElementById("moves");
  const timerEl = document.getElementById("timer");
  const bestEl = document.getElementById("best");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlaySubEl = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const shuffleBtn = document.getElementById("shuffle-btn");

  let tiles = []; // index = position (0..15), value = tile number (1-15) or 0 for blank
  let blankPos = SIZE * SIZE - 1;
  let moves = 0;
  let startTime = null;
  let timerId = null;
  let elapsedMs = 0;
  let best = null;
  try {
    const saved = localStorage.getItem(STORAGE_BEST);
    best = saved ? Number(saved) : null;
  } catch (e) {}

  function pos(r, c) { return r * SIZE + c; }
  function rowOf(p) { return Math.floor(p / SIZE); }
  function colOf(p) { return p % SIZE; }

  function solvedTiles() {
    const arr = [];
    for (let i = 1; i < SIZE * SIZE; i++) arr.push(i);
    arr.push(0);
    return arr;
  }

  function isSolved() {
    const solved = solvedTiles();
    return tiles.every((v, i) => v === solved[i]);
  }

  function neighbors(p) {
    const r = rowOf(p), c = colOf(p);
    const result = [];
    if (r > 0) result.push(pos(r - 1, c));
    if (r < SIZE - 1) result.push(pos(r + 1, c));
    if (c > 0) result.push(pos(r, c - 1));
    if (c < SIZE - 1) result.push(pos(r, c + 1));
    return result;
  }

  function shuffle() {
    tiles = solvedTiles();
    blankPos = tiles.indexOf(0);
    let lastPos = -1;
    const iterations = 250 + Math.floor(Math.random() * 100);
    for (let i = 0; i < iterations; i++) {
      const opts = neighbors(blankPos).filter((n) => n !== lastPos);
      const next = opts[Math.floor(Math.random() * opts.length)];
      tiles[blankPos] = tiles[next];
      tiles[next] = 0;
      lastPos = blankPos;
      blankPos = next;
    }
    if (isSolved()) {
      shuffle();
      return;
    }
    moves = 0;
    elapsedMs = 0;
    startTime = null;
    stopTimer();
    updateHud();
    overlayEl.hidden = true;
    render();
  }

  function updateHud() {
    movesEl.textContent = String(moves);
    bestEl.textContent = best != null ? formatTime(best) : "--:--";
  }

  function formatTime(ms) {
    const totalSec = Math.floor(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  function startTimer() {
    if (timerId) return;
    startTime = performance.now() - elapsedMs;
    timerId = setInterval(() => {
      elapsedMs = performance.now() - startTime;
      timerEl.textContent = formatTime(elapsedMs);
    }, 250);
  }

  function stopTimer() {
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
    timerEl.textContent = formatTime(elapsedMs);
  }

  function cellMetrics() {
    const rect = boardEl.getBoundingClientRect();
    const cell = (rect.width - GAP * (SIZE - 1)) / SIZE;
    return { cell, rect };
  }

  function render() {
    const { cell } = cellMetrics();
    boardEl.innerHTML = "";
    for (let p = 0; p < SIZE * SIZE; p++) {
      const value = tiles[p];
      if (value === 0) continue;
      const r = rowOf(p), c = colOf(p);
      const el = document.createElement("div");
      el.className = "tile";
      el.textContent = String(value);
      el.style.width = `${cell}px`;
      el.style.height = `${cell}px`;
      el.style.left = `${c * (cell + GAP)}px`;
      el.style.top = `${r * (cell + GAP)}px`;
      el.dataset.pos = String(p);
      boardEl.appendChild(el);
    }
  }

  function tryMove(p) {
    if (!overlayEl.hidden) return;
    if (!neighbors(blankPos).includes(p)) return;

    if (moves === 0 && startTime === null) {
      startTimer();
    }

    tiles[blankPos] = tiles[p];
    tiles[p] = 0;
    blankPos = p;
    moves += 1;
    updateHud();
    render();

    if (isSolved()) {
      stopTimer();
      const isNewBest = best == null || elapsedMs < best;
      if (isNewBest) {
        best = elapsedMs;
        try { localStorage.setItem(STORAGE_BEST, String(best)); } catch (e) {}
      }
      overlayMessageEl.textContent = "クリア！";
      overlaySubEl.textContent = `${moves} 手 / ${formatTime(elapsedMs)}${isNewBest ? "（ベスト更新！）" : ""}`;
      overlayBtn.textContent = "もう一度シャッフル";
      updateHud();
      overlayEl.hidden = false;
    }
  }

  boardEl.addEventListener("click", (e) => {
    const tile = e.target.closest(".tile");
    if (!tile) return;
    tryMove(Number(tile.dataset.pos));
  });

  window.addEventListener("keydown", (e) => {
    const map = { ArrowUp: [1, 0], ArrowDown: [-1, 0], ArrowLeft: [0, 1], ArrowRight: [0, -1] };
    if (!map[e.key]) return;
    e.preventDefault();
    const [dr, dc] = map[e.key];
    const r = rowOf(blankPos) + dr;
    const c = colOf(blankPos) + dc;
    if (r < 0 || r >= SIZE || c < 0 || c >= SIZE) return;
    tryMove(pos(r, c));
  });

  shuffleBtn.addEventListener("click", shuffle);
  overlayBtn.addEventListener("click", shuffle);

  window.addEventListener("resize", render);

  shuffle();
})();
