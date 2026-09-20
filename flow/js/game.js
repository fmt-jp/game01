(() => {
  const STORAGE_CLEARED = "flow-cleared-count";
  const STORAGE_LEVEL = "flow-level";
  const COLORS = [
    "#ff5a5a", "#4da3ff", "#ffd43b", "#51cf66",
    "#ff922b", "#cc5de8", "#22d3ee",
  ];

  const canvas = document.getElementById("board");
  const ctx = canvas.getContext("2d");
  const boardWrap = document.querySelector(".board-wrap");
  const levelEl = document.getElementById("level");
  const clearedEl = document.getElementById("cleared");
  const pairsStatusEl = document.getElementById("pairs-status");
  const fillStatusEl = document.getElementById("fill-status");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlaySubEl = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const resetBtn = document.getElementById("reset-btn");
  const newBtn = document.getElementById("new-btn");

  let level = 1;
  let cleared = 0;
  try {
    cleared = Number(localStorage.getItem(STORAGE_CLEARED)) || 0;
    level = Math.max(1, Number(localStorage.getItem(STORAGE_LEVEL)) || 1);
  } catch (e) {}

  let size = 5;
  let endpoints = [];
  let paths = [];
  let owner = null;
  let endpointOf = null;
  let activeColor = -1;
  let cellSize = 0;
  let solved = false;

  function total() { return size * size; }

  function rebuildOwner() {
    owner.fill(-1);
    paths.forEach((path, k) => {
      for (const cell of path) owner[cell] = k;
    });
  }

  function loadPuzzle(puzzle) {
    size = puzzle.size;
    endpoints = puzzle.endpoints;
    paths = endpoints.map(() => []);
    owner = new Int8Array(total()).fill(-1);
    endpointOf = new Int8Array(total()).fill(-1);
    endpoints.forEach(([a, b], k) => {
      endpointOf[a] = k;
      endpointOf[b] = k;
    });
    activeColor = -1;
    solved = false;
    overlayEl.hidden = true;
    sizeCanvas();
    updateHud();
    render();
  }

  function newPuzzle(targetLevel) {
    const config = FlowPuzzle.levelConfig(targetLevel);
    let puzzle = FlowPuzzle.generate(config.size, config.colors);
    if (!puzzle) puzzle = FlowPuzzle.generate(5, 4);
    if (!puzzle) return;
    loadPuzzle(puzzle);
  }

  function isAdjacent(a, b) {
    const ra = Math.floor(a / size), ca = a % size;
    const rb = Math.floor(b / size), cb = b % size;
    return Math.abs(ra - rb) + Math.abs(ca - cb) === 1;
  }

  function isComplete(k) {
    const path = paths[k];
    if (path.length < 2) return false;
    const [a, b] = endpoints[k];
    const head = path[0];
    const tail = path[path.length - 1];
    return (head === a && tail === b) || (head === b && tail === a);
  }

  function filledCount() {
    let n = 0;
    for (let i = 0; i < total(); i++) if (owner[i] >= 0) n++;
    return n;
  }

  function completedCount() {
    let n = 0;
    for (let k = 0; k < paths.length; k++) if (isComplete(k)) n++;
    return n;
  }

  function updateHud() {
    levelEl.textContent = String(level);
    clearedEl.textContent = String(cleared);
    pairsStatusEl.textContent = `${completedCount()}/${paths.length}`;
    fillStatusEl.textContent = `${filledCount()}/${total()}`;
  }

  function checkWin() {
    if (solved) return;
    if (completedCount() !== paths.length) return;
    if (filledCount() !== total()) return;
    solved = true;
    activeColor = -1;
    cleared += 1;
    try { localStorage.setItem(STORAGE_CLEARED, String(cleared)); } catch (e) {}
    updateHud();
    overlayMessageEl.textContent = "クリア！";
    overlaySubEl.textContent = `LEVEL ${level} ／ ${size}×${size} をクリア`;
    overlayBtn.textContent = "次のパズルへ";
    overlayEl.hidden = false;
  }

  // ---------- input ----------

  function cellFromEvent(e) {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const c = Math.floor(x / cellSize);
    const r = Math.floor(y / cellSize);
    if (r < 0 || r >= size || c < 0 || c >= size) return -1;
    return r * size + c;
  }

  function startAt(cell) {
    if (solved || cell < 0) return;
    const ep = endpointOf[cell];
    if (ep >= 0) {
      paths[ep] = [cell];
      activeColor = ep;
    } else if (owner[cell] >= 0) {
      const k = owner[cell];
      const idx = paths[k].indexOf(cell);
      if (idx >= 0) paths[k] = paths[k].slice(0, idx + 1);
      activeColor = k;
    } else {
      return;
    }
    rebuildOwner();
    updateHud();
    render();
  }

  function extendTo(cell) {
    const k = activeColor;
    if (k < 0 || cell < 0) return false;
    const path = paths[k];
    const last = path[path.length - 1];
    if (cell === last) return false;
    if (!isAdjacent(cell, last)) return false;

    if (path.length >= 2 && cell === path[path.length - 2]) {
      path.pop();
      rebuildOwner();
      return true;
    }

    const ep = endpointOf[cell];
    if (ep >= 0 && ep !== k) return false;
    if (ep === k && cell === path[0]) return false;
    if (isComplete(k)) return false;

    if (owner[cell] === k) {
      const idx = path.indexOf(cell);
      if (idx >= 0) {
        paths[k] = path.slice(0, idx + 1);
        rebuildOwner();
        return true;
      }
    }

    if (owner[cell] >= 0 && owner[cell] !== k) {
      const other = owner[cell];
      const idx = paths[other].indexOf(cell);
      if (idx > 0) paths[other] = paths[other].slice(0, idx);
      else if (idx === 0) paths[other] = [];
    }

    path.push(cell);
    rebuildOwner();
    return true;
  }

  // Fingers move faster than pointermove events: walk cell by cell toward the target.
  function dragTo(target) {
    if (activeColor < 0 || target < 0) return;
    let changed = false;
    for (let guard = 0; guard < 12; guard++) {
      const path = paths[activeColor];
      const last = path[path.length - 1];
      if (last === target) break;
      const lr = Math.floor(last / size), lc = last % size;
      const tr = Math.floor(target / size), tc = target % size;
      const dr = tr - lr, dc = tc - lc;
      if (dr === 0 && dc === 0) break;
      let next;
      if (Math.abs(dr) >= Math.abs(dc)) next = last + (dr > 0 ? size : -size);
      else next = last + (dc > 0 ? 1 : -1);
      if (!extendTo(next)) break;
      changed = true;
    }
    if (changed) {
      updateHud();
      render();
      checkWin();
    }
  }

  canvas.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    canvas.setPointerCapture(e.pointerId);
    startAt(cellFromEvent(e));
  });

  canvas.addEventListener("pointermove", (e) => {
    if (activeColor < 0) return;
    e.preventDefault();
    dragTo(cellFromEvent(e));
  });

  function endDrag() {
    if (activeColor < 0) return;
    activeColor = -1;
    render();
    checkWin();
  }

  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointercancel", endDrag);

  resetBtn.addEventListener("click", () => {
    if (solved) return;
    paths = endpoints.map(() => []);
    rebuildOwner();
    updateHud();
    render();
  });

  newBtn.addEventListener("click", () => newPuzzle(level));

  overlayBtn.addEventListener("click", () => {
    level += 1;
    try { localStorage.setItem(STORAGE_LEVEL, String(level)); } catch (e) {}
    newPuzzle(level);
  });

  // ---------- rendering ----------

  function sizeCanvas() {
    const rect = boardWrap.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const maxHeight = Math.min(window.innerHeight * 0.52, 460);
    const board = Math.floor(Math.min(rect.width - 8, maxHeight));
    cellSize = board / size;
    canvas.style.width = `${board}px`;
    canvas.style.height = `${board}px`;
    canvas.width = Math.round(board * dpr);
    canvas.height = Math.round(board * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function center(cell) {
    const r = Math.floor(cell / size), c = cell % size;
    return { x: c * cellSize + cellSize / 2, y: r * cellSize + cellSize / 2 };
  }

  function render() {
    const board = cellSize * size;
    ctx.clearRect(0, 0, board, board);

    const gap = Math.max(1, cellSize * 0.04);
    ctx.fillStyle = "rgba(247, 242, 228, 0.05)";
    for (let r = 0; r < size; r++) {
      for (let c = 0; c < size; c++) {
        ctx.fillRect(
          c * cellSize + gap / 2, r * cellSize + gap / 2,
          cellSize - gap, cellSize - gap
        );
      }
    }

    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    paths.forEach((path, k) => {
      if (path.length < 2) return;
      ctx.strokeStyle = COLORS[k % COLORS.length];
      ctx.lineWidth = cellSize * 0.3;
      ctx.globalAlpha = isComplete(k) ? 1 : 0.75;
      ctx.beginPath();
      path.forEach((cell, i) => {
        const p = center(cell);
        if (i === 0) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      });
      ctx.stroke();
      ctx.globalAlpha = 1;
    });

    endpoints.forEach(([a, b], k) => {
      const color = COLORS[k % COLORS.length];
      for (const cell of [a, b]) {
        const p = center(cell);
        ctx.beginPath();
        ctx.arc(p.x, p.y, cellSize * 0.28, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        if (isComplete(k)) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, cellSize * 0.13, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(255,255,255,0.85)";
          ctx.fill();
        }
      }
    });

    if (activeColor >= 0) {
      const path = paths[activeColor];
      if (path.length > 0) {
        const p = center(path[path.length - 1]);
        ctx.beginPath();
        ctx.arc(p.x, p.y, cellSize * 0.2, 0, Math.PI * 2);
        ctx.fillStyle = COLORS[activeColor % COLORS.length];
        ctx.fill();
      }
    }
  }

  window.addEventListener("resize", () => {
    sizeCanvas();
    render();
  });

  newPuzzle(level);
})();
