(() => {
  const COLS = 6;
  const ROWS = 12;
  const SPAWN_COL = 2;
  const STORAGE_BEST = "gems-best-score";
  const CLEAR_FLASH_MS = 220;

  const COLORS = ["#ff5a5a", "#ffa94d", "#ffe066", "#63e6be", "#74c0fc"];

  const canvas = document.getElementById("board");
  const ctx = canvas.getContext("2d");
  const scoreEl = document.getElementById("score");
  const bestEl = document.getElementById("best");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlaySubEl = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const nextGemsEl = document.getElementById("next-gems");
  const btnLeft = document.getElementById("btn-left");
  const btnRight = document.getElementById("btn-right");
  const btnRotate = document.getElementById("btn-rotate");
  const btnDrop = document.getElementById("btn-drop");
  const boardWrap = document.querySelector(".board-wrap");

  let cellSize = 0;
  let board = [];
  let piece = null;
  let nextColors = [];
  let score = 0;
  let best = 0;
  try { best = Number(localStorage.getItem(STORAGE_BEST)) || 0; } catch (e) {}

  let gameState = "falling"; // falling | clearing | gameover
  let lastStepTime = 0;
  let dropInterval = 700;
  let clearTimer = 0;
  let matchedSet = new Set();
  let chain = 1;

  function randomColor() {
    return COLORS[Math.floor(Math.random() * COLORS.length)];
  }

  function makeTriplet() {
    return [randomColor(), randomColor(), randomColor()];
  }

  function emptyBoard() {
    return Array.from({ length: ROWS }, () => Array(COLS).fill(null));
  }

  function cellKey(r, c) { return `${r},${c}`; }

  function canOccupy(col, topRow) {
    for (let offset = 0; offset < 3; offset++) {
      const r = topRow + offset;
      if (r < 0) continue;
      if (r >= ROWS) return false;
      if (col < 0 || col >= COLS) return false;
      if (board[r][col]) return false;
    }
    return true;
  }

  function spawnPiece() {
    piece = { col: SPAWN_COL, row: -2, colors: nextColors };
    nextColors = makeTriplet();
    renderNextPreview();
    lastStepTime = performance.now();
    if (!canOccupy(piece.col, piece.row)) {
      endGame();
    }
  }

  function renderNextPreview() {
    nextGemsEl.innerHTML = "";
    for (const c of nextColors) {
      const span = document.createElement("span");
      span.style.background = c;
      nextGemsEl.appendChild(span);
    }
  }

  function updateScoreHud() {
    scoreEl.textContent = String(score);
    if (score > best) {
      best = score;
      try { localStorage.setItem(STORAGE_BEST, String(best)); } catch (e) {}
    }
    bestEl.textContent = String(best);
  }

  function findMatches() {
    const matched = new Set();
    const dirs = [
      [0, 1], [1, 0], [1, 1], [1, -1],
    ];
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const color = board[r][c];
        if (!color) continue;
        for (const [dr, dc] of dirs) {
          const line = [[r, c]];
          let rr = r + dr, cc = c + dc;
          while (rr >= 0 && rr < ROWS && cc >= 0 && cc < COLS && board[rr][cc] === color) {
            line.push([rr, cc]);
            rr += dr; cc += dc;
          }
          if (line.length >= 3) {
            for (const [lr, lc] of line) matched.add(cellKey(lr, lc));
          }
        }
      }
    }
    return matched;
  }

  function applyGravity() {
    for (let c = 0; c < COLS; c++) {
      const colVals = [];
      for (let r = 0; r < ROWS; r++) {
        if (board[r][c]) colVals.push(board[r][c]);
      }
      const newCol = Array(ROWS - colVals.length).fill(null).concat(colVals);
      for (let r = 0; r < ROWS; r++) board[r][c] = newCol[r];
    }
  }

  function lockPiece() {
    for (let offset = 0; offset < 3; offset++) {
      const r = piece.row + offset;
      if (r >= 0 && r < ROWS) {
        board[r][piece.col] = piece.colors[offset];
      }
    }
    piece = null;

    const matches = findMatches();
    if (matches.size > 0) {
      matchedSet = matches;
      gameState = "clearing";
      clearTimer = CLEAR_FLASH_MS;
      chain = 1;
    } else {
      spawnPiece();
      gameState = "falling";
    }
  }

  function resolveClear() {
    const count = matchedSet.size;
    score += count * 10 * chain;
    updateScoreHud();
    for (const key of matchedSet) {
      const [r, c] = key.split(",").map(Number);
      board[r][c] = null;
    }
    matchedSet = new Set();
    applyGravity();

    const nextMatches = findMatches();
    if (nextMatches.size > 0) {
      chain += 1;
      matchedSet = nextMatches;
      clearTimer = CLEAR_FLASH_MS;
    } else {
      spawnPiece();
      gameState = "falling";
    }
  }

  function endGame() {
    gameState = "gameover";
    overlayMessageEl.textContent = "ゲームオーバー";
    overlaySubEl.textContent = `SCORE ${score} / BEST ${best}`;
    overlayBtn.textContent = "もう一度";
    overlayEl.hidden = false;
  }

  function startGame() {
    board = emptyBoard();
    score = 0;
    chain = 1;
    dropInterval = 700;
    matchedSet = new Set();
    overlayEl.hidden = true;
    updateScoreHud();
    nextColors = makeTriplet();
    gameState = "falling";
    spawnPiece();
  }

  function moveLeft() {
    if (gameState !== "falling" || !piece) return;
    if (canOccupy(piece.col - 1, piece.row)) piece.col -= 1;
  }
  function moveRight() {
    if (gameState !== "falling" || !piece) return;
    if (canOccupy(piece.col + 1, piece.row)) piece.col += 1;
  }
  function rotate() {
    if (gameState !== "falling" || !piece) return;
    piece.colors = [piece.colors[2], piece.colors[0], piece.colors[1]];
  }
  function hardDrop() {
    if (gameState !== "falling" || !piece) return;
    while (canOccupy(piece.col, piece.row + 1)) piece.row += 1;
    lockPiece();
  }

  function step(dtMs, now) {
    if (gameState === "falling" && piece) {
      dropInterval = Math.max(180, 700 - Math.floor(score / 150) * 25);
      if (now - lastStepTime >= dropInterval) {
        lastStepTime = now;
        if (canOccupy(piece.col, piece.row + 1)) {
          piece.row += 1;
        } else {
          lockPiece();
        }
      }
    } else if (gameState === "clearing") {
      clearTimer -= dtMs;
      if (clearTimer <= 0) {
        resolveClear();
      }
    }
  }

  function sizeCanvas() {
    const rect = boardWrap.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const availWidth = rect.width;
    const maxHeight = Math.min(window.innerHeight * 0.56, 520);
    cellSize = Math.min(availWidth / COLS, maxHeight / ROWS);
    const width = cellSize * COLS;
    const height = cellSize * ROWS;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function drawGem(cx, cy, radius, color, highlight) {
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fillStyle = highlight ? "#ffffff" : color;
    ctx.fill();
    if (!highlight) {
      ctx.beginPath();
      ctx.arc(cx - radius * 0.3, cy - radius * 0.3, radius * 0.35, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,255,255,0.35)";
      ctx.fill();
    }
  }

  function render(now) {
    const width = cellSize * COLS;
    const height = cellSize * ROWS;
    ctx.clearRect(0, 0, width, height);

    ctx.fillStyle = "rgba(255,255,255,0.03)";
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        if ((r + c) % 2 === 0) {
          ctx.fillRect(c * cellSize, r * cellSize, cellSize, cellSize);
        }
      }
    }

    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const color = board[r][c];
        if (!color) continue;
        const isMatched = gameState === "clearing" && matchedSet.has(cellKey(r, c));
        const flashOn = isMatched && Math.floor(now / 80) % 2 === 0;
        drawGem(c * cellSize + cellSize / 2, r * cellSize + cellSize / 2, cellSize * 0.4, color, flashOn);
      }
    }

    if (gameState === "falling" && piece) {
      const progress = Math.min(1, (now - lastStepTime) / dropInterval);
      const renderRow = piece.row + progress;
      for (let offset = 0; offset < 3; offset++) {
        const r = renderRow + offset;
        if (r < -1) continue;
        drawGem(
          piece.col * cellSize + cellSize / 2,
          r * cellSize + cellSize / 2,
          cellSize * 0.4,
          piece.colors[offset],
          false
        );
      }
    }
  }

  let lastFrameTime = performance.now();
  function loop(now) {
    const dt = Math.min(now - lastFrameTime, 50);
    lastFrameTime = now;
    if (gameState !== "gameover") {
      step(dt, now);
    }
    render(now);
    requestAnimationFrame(loop);
  }

  let repeatTimer = null;
  function bindRepeat(btn, action) {
    function start() {
      action();
      repeatTimer = setInterval(action, 130);
    }
    function stop() {
      clearInterval(repeatTimer);
      repeatTimer = null;
    }
    btn.addEventListener("touchstart", (e) => { e.preventDefault(); start(); }, { passive: false });
    btn.addEventListener("mousedown", start);
    ["touchend", "touchcancel", "mouseup", "mouseleave"].forEach((evt) =>
      btn.addEventListener(evt, stop)
    );
  }

  bindRepeat(btnLeft, moveLeft);
  bindRepeat(btnRight, moveRight);
  btnRotate.addEventListener("click", rotate);
  btnDrop.addEventListener("click", hardDrop);

  window.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { e.preventDefault(); moveLeft(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); moveRight(); }
    else if (e.key === "ArrowUp" || e.key === " ") { e.preventDefault(); rotate(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); hardDrop(); }
  });

  let touchStartX = 0, touchStartY = 0;
  const SWIPE_THRESHOLD = 22;
  canvas.addEventListener("touchstart", (e) => {
    const t = e.changedTouches[0];
    touchStartX = t.clientX;
    touchStartY = t.clientY;
  }, { passive: true });
  canvas.addEventListener("touchend", (e) => {
    const t = e.changedTouches[0];
    const dx = t.clientX - touchStartX;
    const dy = t.clientY - touchStartY;
    if (Math.abs(dx) < SWIPE_THRESHOLD && Math.abs(dy) < SWIPE_THRESHOLD) {
      rotate();
    } else if (Math.abs(dx) > Math.abs(dy)) {
      if (dx > 0) moveRight(); else moveLeft();
    } else if (dy > 0) {
      hardDrop();
    }
  }, { passive: true });

  overlayBtn.addEventListener("click", startGame);

  window.addEventListener("resize", sizeCanvas);

  sizeCanvas();
  startGame();
  requestAnimationFrame(loop);
})();
