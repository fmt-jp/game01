(() => {
  const STORAGE_PROGRESS = "picross-cleared-puzzles";

  const PUZZLES = [
    [
      "00100",
      "00100",
      "11111",
      "00100",
      "00100",
    ],
    [
      "01010",
      "11111",
      "11111",
      "01110",
      "00100",
    ],
    [
      "00011000",
      "00111100",
      "01111110",
      "11111111",
      "11000011",
      "11000011",
      "11011011",
      "11011011",
    ],
    [
      "10000001",
      "11000011",
      "01111110",
      "01011010",
      "01111110",
      "01100110",
      "01111110",
      "00000000",
    ],
    [
      "0000110000",
      "0001111000",
      "0011111100",
      "0111111110",
      "1111111111",
      "0001100000",
      "0001100000",
      "0001100000",
      "0001110000",
      "0000000000",
    ],
  ];

  const boardEl = document.getElementById("board");
  const boardWrap = document.querySelector(".board-wrap");
  const levelNumEl = document.getElementById("level-num");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlayBtn = document.getElementById("overlay-btn");
  const resetBtn = document.getElementById("reset-btn");
  const modeBtns = document.querySelectorAll(".mode-btn");

  let puzzleIndex = 0;
  let bitmap = [];
  let rows = 0;
  let cols = 0;
  let rowClues = [];
  let colClues = [];
  let state = [];
  let mode = "fill";
  let solved = false;

  function computeClue(cells) {
    const runs = [];
    let count = 0;
    for (const v of cells) {
      if (v) {
        count++;
      } else if (count) {
        runs.push(count);
        count = 0;
      }
    }
    if (count) runs.push(count);
    return runs.length ? runs : [0];
  }

  function loadPuzzle(index) {
    bitmap = PUZZLES[index];
    rows = bitmap.length;
    cols = bitmap[0].length;
    rowClues = bitmap.map((row) => computeClue([...row].map((ch) => ch === "1" ? 1 : 0)));
    colClues = [];
    for (let c = 0; c < cols; c++) {
      const colCells = [];
      for (let r = 0; r < rows; r++) colCells.push(bitmap[r][c] === "1" ? 1 : 0);
      colClues.push(computeClue(colCells));
    }
    state = Array.from({ length: rows }, () => Array(cols).fill(0));
    solved = false;
    overlayEl.hidden = true;
    levelNumEl.textContent = `${index + 1}/${PUZZLES.length}`;
    sizeBoard();
    render();
  }

  function maxClueLines(clues) {
    return Math.max(...clues.map((c) => c.length));
  }

  function sizeBoard() {
    const rect = boardWrap.getBoundingClientRect();
    const availWidth = rect.width - 4;
    const maxHeight = Math.min(window.innerHeight * 0.5, 460);

    const rowClueRatio = Math.max(1.6, maxClueLines(rowClues) * 1.05);
    const colClueRatio = Math.max(1.3, maxClueLines(colClues) * 0.62);

    const cell = Math.floor(Math.min(
      availWidth / (cols + rowClueRatio),
      maxHeight / (rows + colClueRatio)
    ));

    const clueColWidth = Math.round(cell * rowClueRatio);
    const clueRowHeight = Math.round(cell * colClueRatio);

    boardEl.style.gridTemplateColumns = `${clueColWidth}px repeat(${cols}, ${cell}px)`;
    boardEl.style.gridTemplateRows = `${clueRowHeight}px repeat(${rows}, ${cell}px)`;
    boardEl.dataset.cell = cell;
  }

  function lineIsDone(cells, clue) {
    const fillOnly = cells.map((v) => (v === 1 ? 1 : 0));
    const runs = computeClue(fillOnly);
    return runs.length === clue.length && runs.every((v, i) => v === clue[i]);
  }

  function render() {
    boardEl.innerHTML = "";

    const corner = document.createElement("div");
    corner.className = "corner cell-base";
    corner.style.gridColumn = "1";
    corner.style.gridRow = "1";
    boardEl.appendChild(corner);

    for (let c = 0; c < cols; c++) {
      const colCells = state.map((row) => row[c]);
      const done = lineIsDone(colCells, colClues[c]);
      const el = document.createElement("div");
      el.className = "clue-col cell-base" + (done ? " done" : "");
      el.style.gridColumn = String(c + 2);
      el.style.gridRow = "1";
      el.innerHTML = colClues[c].map((n) => `<span>${n}</span>`).join("");
      boardEl.appendChild(el);
    }

    for (let r = 0; r < rows; r++) {
      const done = lineIsDone(state[r], rowClues[r]);
      const el = document.createElement("div");
      el.className = "clue-row cell-base" + (done ? " done" : "");
      el.style.gridColumn = "1";
      el.style.gridRow = String(r + 2);
      el.innerHTML = rowClues[r].map((n) => `<span>${n}</span>`).join("");
      boardEl.appendChild(el);
    }

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const el = document.createElement("div");
        const v = state[r][c];
        el.className = "cell" + (v === 1 ? " fill" : v === 2 ? " mark" : "");
        el.style.gridColumn = String(c + 2);
        el.style.gridRow = String(r + 2);
        el.dataset.row = String(r);
        el.dataset.col = String(c);
        boardEl.appendChild(el);
      }
    }
  }

  function checkWin() {
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const filled = state[r][c] === 1;
        const shouldFill = bitmap[r][c] === "1";
        if (filled !== shouldFill) return false;
      }
    }
    return true;
  }

  function toggleCell(r, c) {
    if (solved) return;
    const modeValue = mode === "fill" ? 1 : 2;
    state[r][c] = state[r][c] === modeValue ? 0 : modeValue;
    render();

    if (checkWin()) {
      solved = true;
      const isLast = puzzleIndex === PUZZLES.length - 1;
      overlayMessageEl.textContent = isLast ? "全パズルクリア！" : "できた！";
      overlayBtn.textContent = isLast ? "最初から遊ぶ" : "次のパズルへ";
      overlayEl.hidden = false;
      try {
        const cleared = new Set(JSON.parse(localStorage.getItem(STORAGE_PROGRESS) || "[]"));
        cleared.add(puzzleIndex);
        localStorage.setItem(STORAGE_PROGRESS, JSON.stringify([...cleared]));
      } catch (e) {}
    }
  }

  boardEl.addEventListener("click", (e) => {
    const cell = e.target.closest(".cell");
    if (!cell) return;
    toggleCell(Number(cell.dataset.row), Number(cell.dataset.col));
  });

  modeBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      mode = btn.dataset.mode;
      modeBtns.forEach((b) => b.classList.toggle("active", b === btn));
    });
  });

  resetBtn.addEventListener("click", () => {
    state = Array.from({ length: rows }, () => Array(cols).fill(0));
    solved = false;
    overlayEl.hidden = true;
    render();
  });

  overlayBtn.addEventListener("click", () => {
    if (puzzleIndex === PUZZLES.length - 1) {
      puzzleIndex = 0;
    } else {
      puzzleIndex += 1;
    }
    loadPuzzle(puzzleIndex);
  });

  window.addEventListener("resize", () => {
    sizeBoard();
    render();
  });

  loadPuzzle(0);
})();
