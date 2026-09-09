(() => {
  const STORAGE_PROGRESS = "sokoban-cleared-levels";

  const PLAYER_SVG = `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="7.5" r="4"/><path d="M4 21v-1c0-4.4 3.6-7.5 8-7.5s8 3.1 8 7.5v1H4z"/></svg>`;

  const CONTAINER_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><rect x="2.2" y="6" width="19.6" height="12.5" rx="1.4"/><line x1="6.2" y1="6" x2="6.2" y2="18.5"/><line x1="10.1" y1="6" x2="10.1" y2="18.5"/><line x1="14" y1="6" x2="14" y2="18.5"/><line x1="17.9" y1="6" x2="17.9" y2="18.5"/></svg>`;

  const LEVELS = [
    `
#####
#.$@#
#####
`,
    `
#######
#     #
#  $  #
#  @  #
#.    #
#######
`,
    `
 #####
##   #
#. $ #
#  #@##
#  $  #
#  .  #
#######
`,
    `
########
#  .   #
#  $   #
#  #   #
#. $ @ #
#      #
########
`,
    `
########
#  .   #
#      #
#  $ $ #
#      #
#.  @  #
########
`,
    `
 ########
##  .   #
#  $$   #
# .# ####
#  $  #
#  .@ #
########
`,
    `
########
#.  .  #
#      #
#  $ $ #
#  #   #
#  $ @ #
#     .#
########
`,
    `
 ########
##  .   #
#  $$   #
# .# ####
#  $  #
#  .@ #
#   $ #
#   . #
#######
`,
    `
##########
#.      .#
#  $  $  #
#   ##   #
#  $  $  #
#.  @   .#
##########
`,
    `
#########
#.      #
#  $ $  #
# ##.## #
#  $ $  #
#. #@# .#
#   #   #
#########
`,
  ];

  const boardEl = document.getElementById("board");
  const levelNumEl = document.getElementById("level-num");
  const movesEl = document.getElementById("moves");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlaySubEl = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const undoBtn = document.getElementById("undo-btn");
  const resetBtn = document.getElementById("reset-btn");
  const boardWrap = document.querySelector(".board-wrap");

  let levelIndex = 0;
  let cols = 0;
  let rows = 0;
  let walls = new Set();
  let goals = new Set();
  let boxes = new Set();
  let player = { x: 0, y: 0 };
  let moves = 0;
  let history = [];

  function key(x, y) { return `${x},${y}`; }

  function parseLevel(raw) {
    const lines = raw.replace(/^\n/, "").replace(/\n$/, "").split("\n");
    const width = Math.max(...lines.map((l) => l.length));
    const padded = lines.map((l) => l.padEnd(width, " "));

    const w = new Set();
    const g = new Set();
    const b = new Set();
    let p = null;

    padded.forEach((line, y) => {
      [...line].forEach((ch, x) => {
        if (ch === "#") w.add(key(x, y));
        else if (ch === ".") g.add(key(x, y));
        else if (ch === "$") b.add(key(x, y));
        else if (ch === "*") { g.add(key(x, y)); b.add(key(x, y)); }
        else if (ch === "@") p = { x, y };
        else if (ch === "+") { g.add(key(x, y)); p = { x, y }; }
      });
    });

    return { walls: w, goals: g, boxes: b, player: p, cols: width, rows: padded.length };
  }

  function loadLevel(index) {
    const parsed = parseLevel(LEVELS[index]);
    cols = parsed.cols;
    rows = parsed.rows;
    walls = parsed.walls;
    goals = parsed.goals;
    boxes = new Set(parsed.boxes);
    player = { ...parsed.player };
    moves = 0;
    history = [];
    overlayEl.hidden = true;
    updateHud();
    sizeBoard();
    render();
  }

  function updateHud() {
    levelNumEl.textContent = `${levelIndex + 1}/${LEVELS.length}`;
    movesEl.textContent = String(moves);
  }

  function sizeBoard() {
    const rect = boardWrap.getBoundingClientRect();
    const availWidth = rect.width - 32;
    const maxHeight = Math.min(window.innerHeight * 0.42, 420);
    const cell = Math.floor(Math.min(availWidth / cols, maxHeight / rows));
    boardEl.style.gridTemplateColumns = `repeat(${cols}, ${cell}px)`;
    boardEl.style.gridTemplateRows = `repeat(${rows}, ${cell}px)`;
    boardEl.style.width = `${cell * cols}px`;
    boardEl.style.height = `${cell * rows}px`;
  }

  function render() {
    boardEl.innerHTML = "";
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const k = key(x, y);
        const cell = document.createElement("div");
        if (walls.has(k)) {
          cell.className = "cell wall";
        } else if (goals.has(k)) {
          cell.className = "cell goal";
        } else {
          cell.className = "cell floor";
        }

        if (boxes.has(k)) {
          const box = document.createElement("div");
          box.className = "box" + (goals.has(k) ? " on-goal" : "");
          box.innerHTML = CONTAINER_SVG;
          cell.appendChild(box);
        }

        if (player.x === x && player.y === y) {
          const p = document.createElement("div");
          p.className = "player";
          p.innerHTML = PLAYER_SVG;
          cell.appendChild(p);
        }

        boardEl.appendChild(cell);
      }
    }
  }

  function isWon() {
    if (boxes.size !== goals.size) return false;
    for (const b of boxes) if (!goals.has(b)) return false;
    return true;
  }

  function showCleared() {
    const isLast = levelIndex === LEVELS.length - 1;
    overlayMessageEl.textContent = isLast ? "全レベルクリア！" : "クリア！";
    overlaySubEl.textContent = `${moves} 手でクリア`;
    overlayBtn.textContent = isLast ? "最初から遊ぶ" : "次のレベルへ";
    overlayEl.hidden = false;
    try {
      const cleared = new Set(JSON.parse(localStorage.getItem(STORAGE_PROGRESS) || "[]"));
      cleared.add(levelIndex);
      localStorage.setItem(STORAGE_PROGRESS, JSON.stringify([...cleared]));
    } catch (e) {}
  }

  function move(dir) {
    if (!overlayEl.hidden) return;
    const deltas = { U: [0, -1], D: [0, 1], L: [-1, 0], R: [1, 0] };
    const [dx, dy] = deltas[dir];
    const nx = player.x + dx;
    const ny = player.y + dy;
    const nk = key(nx, ny);

    if (walls.has(nk)) return;

    let nextBoxes = boxes;
    if (boxes.has(nk)) {
      const bx = nx + dx;
      const by = ny + dy;
      const bk = key(bx, by);
      if (walls.has(bk) || boxes.has(bk)) return;
      nextBoxes = new Set(boxes);
      nextBoxes.delete(nk);
      nextBoxes.add(bk);
    }

    history.push({ player: { ...player }, boxes: new Set(boxes), moves });
    player = { x: nx, y: ny };
    boxes = nextBoxes;
    moves += 1;
    updateHud();
    render();

    if (isWon()) {
      setTimeout(showCleared, 150);
    }
  }

  function undo() {
    if (history.length === 0) return;
    const prev = history.pop();
    player = prev.player;
    boxes = prev.boxes;
    moves = prev.moves;
    overlayEl.hidden = true;
    updateHud();
    render();
  }

  document.querySelectorAll(".dpad-btn").forEach((btn) => {
    btn.addEventListener("click", () => move(btn.dataset.dir));
  });

  undoBtn.addEventListener("click", undo);
  resetBtn.addEventListener("click", () => loadLevel(levelIndex));

  overlayBtn.addEventListener("click", () => {
    if (levelIndex === LEVELS.length - 1) {
      loadLevel(0);
    } else {
      levelIndex += 1;
      loadLevel(levelIndex);
    }
  });

  window.addEventListener("keydown", (e) => {
    const map = { ArrowUp: "U", ArrowDown: "D", ArrowLeft: "L", ArrowRight: "R" };
    if (map[e.key]) {
      e.preventDefault();
      move(map[e.key]);
    }
  });

  let touchStartX = 0;
  let touchStartY = 0;
  const SWIPE_THRESHOLD = 20;

  boardEl.addEventListener("touchstart", (e) => {
    const t = e.changedTouches[0];
    touchStartX = t.clientX;
    touchStartY = t.clientY;
  }, { passive: true });

  boardEl.addEventListener("touchend", (e) => {
    const t = e.changedTouches[0];
    const dx = t.clientX - touchStartX;
    const dy = t.clientY - touchStartY;
    if (Math.max(Math.abs(dx), Math.abs(dy)) < SWIPE_THRESHOLD) return;
    if (Math.abs(dx) > Math.abs(dy)) {
      move(dx > 0 ? "R" : "L");
    } else {
      move(dy > 0 ? "D" : "U");
    }
  }, { passive: true });

  window.addEventListener("resize", () => {
    sizeBoard();
    render();
  });

  loadLevel(0);
})();
