(() => {
  const SIZE = 4;
  const WIN_VALUE = 2048;
  const STORAGE_BEST = "2048-best-score";

  const boardEl = document.getElementById("board");
  const tilesEl = document.getElementById("tiles");
  const gridBgEl = document.getElementById("grid-bg");
  const scoreEl = document.getElementById("score");
  const bestEl = document.getElementById("best");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlayBtn = document.getElementById("overlay-btn");
  const newGameBtn = document.getElementById("new-game-btn");

  let grid = [];
  let score = 0;
  let best = Number(localStorage.getItem(STORAGE_BEST)) || 0;
  let tileIdCounter = 0;
  let hasWon = false;
  let isGameOver = false;

  for (let i = 0; i < SIZE * SIZE; i++) {
    const cell = document.createElement("div");
    cell.className = "cell";
    gridBgEl.appendChild(cell);
  }

  function createTile(value, row, col) {
    return { id: tileIdCounter++, value, row, col, isNew: true, mergedFrom: null };
  }

  function emptyGrid() {
    return Array.from({ length: SIZE }, () => Array(SIZE).fill(null));
  }

  function getEmptyCells() {
    const cells = [];
    for (let r = 0; r < SIZE; r++) {
      for (let c = 0; c < SIZE; c++) {
        if (!grid[r][c]) cells.push({ r, c });
      }
    }
    return cells;
  }

  function addRandomTile() {
    const empties = getEmptyCells();
    if (empties.length === 0) return;
    const { r, c } = empties[Math.floor(Math.random() * empties.length)];
    const value = Math.random() < 0.9 ? 2 : 4;
    grid[r][c] = createTile(value, r, c);
  }

  function startGame() {
    grid = emptyGrid();
    score = 0;
    hasWon = false;
    isGameOver = false;
    overlayEl.hidden = true;
    addRandomTile();
    addRandomTile();
    updateScore();
    render(true);
  }

  function updateScore() {
    scoreEl.textContent = String(score);
    if (score > best) {
      best = score;
      localStorage.setItem(STORAGE_BEST, String(best));
    }
    bestEl.textContent = String(best);
  }

  function cellMetrics() {
    const rect = tilesEl.getBoundingClientRect();
    const gap = 12;
    const cellSize = (rect.width - gap * (SIZE - 1)) / SIZE;
    return { cellSize, gap };
  }

  function render(immediate) {
    const { cellSize, gap } = cellMetrics();
    tilesEl.innerHTML = "";
    for (let r = 0; r < SIZE; r++) {
      for (let c = 0; c < SIZE; c++) {
        const tile = grid[r][c];
        if (!tile) continue;
        const el = document.createElement("div");
        el.className = "tile";
        el.dataset.value = tile.value > WIN_VALUE ? "super" : String(tile.value);
        if (tile.value > WIN_VALUE) el.dataset.super = "1";
        el.textContent = String(tile.value);
        el.style.width = `${cellSize}px`;
        el.style.height = `${cellSize}px`;
        el.style.left = `${tile.col * (cellSize + gap)}px`;
        el.style.top = `${tile.row * (cellSize + gap)}px`;
        if (!immediate && tile.isNew) el.classList.add("spawn");
        if (!immediate && tile.mergedFrom) el.classList.add("merged");
        tilesEl.appendChild(el);
      }
    }
  }

  function cloneGridValues() {
    return grid.map((row) => row.map((tile) => (tile ? tile.value : 0)));
  }

  function gridsEqual(a, b) {
    for (let r = 0; r < SIZE; r++) {
      for (let c = 0; c < SIZE; c++) {
        if (a[r][c] !== b[r][c]) return false;
      }
    }
    return true;
  }

  function slideAndMergeLine(line) {
    const values = line.filter((t) => t !== null);
    const merged = [];
    let gained = 0;

    for (let i = 0; i < values.length; i++) {
      if (i < values.length - 1 && values[i].value === values[i + 1].value) {
        const newValue = values[i].value * 2;
        const mergedTile = createTile(newValue, 0, 0);
        mergedTile.mergedFrom = [values[i], values[i + 1]];
        mergedTile.isNew = false;
        gained += newValue;
        merged.push(mergedTile);
        i++;
      } else {
        values[i].isNew = false;
        values[i].mergedFrom = null;
        merged.push(values[i]);
      }
    }

    while (merged.length < SIZE) merged.push(null);
    return { merged, gained };
  }

  function move(direction) {
    if (isGameOver) return;
    const before = cloneGridValues();
    let gained = 0;

    const getLine = (i, reverse) => {
      const line = [];
      for (let j = 0; j < SIZE; j++) {
        const idx = reverse ? SIZE - 1 - j : j;
        line.push(direction === "left" || direction === "right" ? grid[i][idx] : grid[idx][i]);
      }
      return line;
    };

    const setLine = (i, line, reverse) => {
      for (let j = 0; j < SIZE; j++) {
        const idx = reverse ? SIZE - 1 - j : j;
        const tile = line[j];
        if (tile) {
          if (direction === "left" || direction === "right") {
            tile.row = i;
            tile.col = idx;
            grid[i][idx] = tile;
          } else {
            tile.row = idx;
            tile.col = i;
            grid[idx][i] = tile;
          }
        } else {
          if (direction === "left" || direction === "right") {
            grid[i][idx] = null;
          } else {
            grid[idx][i] = null;
          }
        }
      }
    };

    const reverse = direction === "right" || direction === "down";

    for (let i = 0; i < SIZE; i++) {
      const line = getLine(i, reverse);
      const { merged, gained: lineGain } = slideAndMergeLine(line);
      gained += lineGain;
      setLine(i, merged, reverse);
    }

    const after = cloneGridValues();
    if (gridsEqual(before, after)) return;

    score += gained;
    updateScore();
    addRandomTile();
    render(false);

    const maxTile = Math.max(...after.flat());
    if (!hasWon && maxTile >= WIN_VALUE) {
      hasWon = true;
      showOverlay("やった！2048達成！", true);
    } else if (!canMove()) {
      isGameOver = true;
      showOverlay("ゲームオーバー", false);
    }
  }

  function canMove() {
    if (getEmptyCells().length > 0) return true;
    for (let r = 0; r < SIZE; r++) {
      for (let c = 0; c < SIZE; c++) {
        const value = grid[r][c].value;
        if (c < SIZE - 1 && grid[r][c + 1].value === value) return true;
        if (r < SIZE - 1 && grid[r + 1][c].value === value) return true;
      }
    }
    return false;
  }

  function showOverlay(message, isWin) {
    overlayMessageEl.textContent = message;
    overlayBtn.textContent = isWin ? "続ける / もう一度" : "もう一度";
    overlayEl.hidden = false;
    if (isWin) {
      overlayBtn.onclick = () => {
        overlayEl.hidden = true;
      };
    } else {
      overlayBtn.onclick = startGame;
    }
  }

  newGameBtn.addEventListener("click", startGame);

  window.addEventListener("keydown", (e) => {
    const map = {
      ArrowLeft: "left",
      ArrowRight: "right",
      ArrowUp: "up",
      ArrowDown: "down",
    };
    if (map[e.key]) {
      e.preventDefault();
      move(map[e.key]);
    }
  });

  let touchStartX = 0;
  let touchStartY = 0;
  const SWIPE_THRESHOLD = 24;

  boardEl.addEventListener(
    "touchstart",
    (e) => {
      const t = e.changedTouches[0];
      touchStartX = t.clientX;
      touchStartY = t.clientY;
    },
    { passive: true }
  );

  boardEl.addEventListener(
    "touchend",
    (e) => {
      const t = e.changedTouches[0];
      const dx = t.clientX - touchStartX;
      const dy = t.clientY - touchStartY;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < SWIPE_THRESHOLD) return;
      if (Math.abs(dx) > Math.abs(dy)) {
        move(dx > 0 ? "right" : "left");
      } else {
        move(dy > 0 ? "down" : "up");
      }
    },
    { passive: true }
  );

  window.addEventListener("resize", () => render(true));

  bestEl.textContent = String(best);
  startGame();
})();
