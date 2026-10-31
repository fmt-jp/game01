(() => {
  const STORAGE_LEVEL = "ataxx-level";
  const STORAGE_RECORD = "ataxx-record";
  const STORAGE_FIRST = "ataxx-first";
  const { YOU, FOE, EMPTY, WALL, SIZE, CELLS } = Ataxx;

  const boardEl = document.getElementById("board");
  const turnEl = document.getElementById("turn");
  const scoreYouEl = document.getElementById("score-you");
  const scoreFoeEl = document.getElementById("score-foe");
  const recordEl = document.getElementById("record");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlaySubEl = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const newBtn = document.getElementById("new-btn");
  const levelsEl = document.getElementById("levels");
  const firstsEl = document.getElementById("firsts");

  let level = "normal";
  let first = YOU;                 // who opens; you, unless it has been changed
  let record = { win: 0, loss: 0, draw: 0 };
  try {
    level = localStorage.getItem(STORAGE_LEVEL) || "normal";
    first = localStorage.getItem(STORAGE_FIRST) === "foe" ? FOE : YOU;
    record = JSON.parse(localStorage.getItem(STORAGE_RECORD) || "null") || record;
  } catch (e) {}
  if (!AtaxxAI.LEVELS[level]) level = "normal";

  let cells = null;
  let squares = [];
  let picked = -1;
  let turn = YOU;
  let busy = false;
  let over = false;
  let timer = null;
  let lastMove = null;        // the move just played, marked on the board

  // The game advances through exactly one pending step. Scheduling a new one
  // cancels whatever was waiting, so a stray tap cannot leave two chains of
  // turns running against each other.
  function later(fn, ms) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => { timer = null; fn(); }, ms);
  }

  function squareSize() {
    const available = boardEl.parentElement.clientWidth - 4;
    const byWidth = Math.floor((available - (SIZE - 1) * 3) / SIZE);
    const byHeight = Math.floor((window.innerHeight * 0.5 - (SIZE - 1) * 3) / SIZE);
    // Never below a comfortable tap target, even if that costs a scroll.
    return Math.max(36, Math.min(54, byWidth, byHeight));
  }

  function buildBoard() {
    const size = squareSize();
    boardEl.style.gridTemplateColumns = `repeat(${SIZE}, ${size}px)`;
    boardEl.innerHTML = "";
    squares = [];
    for (let i = 0; i < CELLS; i++) {
      const node = document.createElement("div");
      node.className = "square";
      node.style.width = `${size}px`;
      node.style.height = `${size}px`;
      node.dataset.index = String(i);
      boardEl.appendChild(node);
      squares.push(node);
    }
    paint();
  }

  function paint(animate) {
    for (let i = 0; i < CELLS; i++) {
      const node = squares[i];
      let classes = "square" + (cells[i] === WALL ? " wall" : "");
      // Leave the last move on the board. Without it a jump looks like a stone
      // teleporting, and a run of moves after a pass looks like one huge one.
      if (lastMove) {
        if (i === lastMove.from && !lastMove.clone) classes += " moved-from";
        if (i === lastMove.to) classes += " moved-to " + (lastMove.side === YOU ? "by-you" : "by-foe");
      }
      node.className = classes;
      const value = cells[i];
      if (value === YOU || value === FOE) {
        let stone = node.firstChild;
        if (!stone) {
          stone = document.createElement("div");
          node.appendChild(stone);
        }
        stone.className = "stone " + (value === YOU ? "you" : "foe");
        if (animate && animate.flipped && animate.flipped.includes(i)) stone.classList.add("flip");
        if (animate && animate.placed === i) stone.classList.add("drop");
      } else if (node.firstChild) {
        node.removeChild(node.firstChild);
      }
    }
    if (picked >= 0) showChoices();
    updateHud();
  }

  function showChoices() {
    squares[picked].classList.add("picked");
    for (const move of Ataxx.legalMoves(cells, YOU)) {
      if (move.from !== picked) continue;
      squares[move.to].classList.add(move.clone ? "clone" : "jump");
    }
  }

  function clearChoices() {
    picked = -1;
    for (const node of squares) node.classList.remove("picked", "clone", "jump");
  }

  function updateHud() {
    const { you, foe } = Ataxx.counts(cells);
    scoreYouEl.textContent = String(you);
    scoreFoeEl.textContent = String(foe);
    recordEl.textContent = `${record.win}-${record.loss}`;
    if (over) return;
    turnEl.textContent = turn === YOU ? "あなたの番" : "あいての番…";
    turnEl.className = "turn " + (turn === YOU ? "you" : "foe");
  }

  function announce(text) {
    turnEl.textContent = text;
    turnEl.className = "turn notice";
  }

  function finish() {
    over = true;
    const { you, foe } = Ataxx.counts(cells);
    const result = Ataxx.winner(cells);
    if (result === YOU) record.win += 1;
    else if (result === FOE) record.loss += 1;
    else record.draw += 1;
    try { localStorage.setItem(STORAGE_RECORD, JSON.stringify(record)); } catch (e) {}
    overlayMessageEl.textContent =
      result === YOU ? "あなたの勝ち！" : result === FOE ? "あいての勝ち" : "引き分け";
    overlaySubEl.textContent = `${you} 対 ${foe}`;
    overlayEl.hidden = false;
    updateHud();
  }

  // One side's move, then hand over. A side with no move passes, which is how
  // the winner ends up filling the rest of the board.
  function advance() {
    if (Ataxx.isOver(cells)) { busy = false; finish(); return; }
    if (Ataxx.legalMoves(cells, turn).length === 0) {
      announce(turn === YOU
        ? "打てる手がありません。あいてが続けて打ちます"
        : "あいては打てないのでパス。もう一度どうぞ");
      turn = turn === YOU ? FOE : YOU;
      busy = true;
      later(() => { if (!over) advance(); }, 1400);
      return;
    }
    if (turn === FOE) {
      busy = true;
      updateHud();
      later(playOpponent, 260);
    } else {
      busy = false;
      updateHud();
    }
  }

  function commit(move, side) {
    const result = Ataxx.applyMove(cells, move, side);
    cells = result.cells;
    clearChoices();
    // Shut the board immediately. Waiting until advance() runs left a window in
    // which a second tap played another move, and the turn order came apart.
    busy = true;
    lastMove = { from: move.from, to: move.to, clone: move.clone, side };
    paint({ placed: move.to, flipped: result.flipped });
    turn = side === YOU ? FOE : YOU;
    later(() => { if (!over) advance(); }, 320);
  }

  function playOpponent() {
    const move = AtaxxAI.chooseMove(cells, FOE, level);
    if (!move) { turn = YOU; advance(); return; }
    commit(move, FOE);
  }

  boardEl.addEventListener("click", (event) => {
    if (busy || over || turn !== YOU) return;
    const node = event.target.closest(".square");
    if (!node) return;
    const i = Number(node.dataset.index);

    if (cells[i] === YOU) {
      clearChoices();
      picked = i;
      showChoices();
      return;
    }
    if (picked < 0) return;
    const move = Ataxx.legalMoves(cells, YOU).find((m) => m.from === picked && m.to === i);
    if (!move) { clearChoices(); return; }
    commit(move, YOU);
  });

  function newGame() {
    if (timer) { clearTimeout(timer); timer = null; }
    cells = Ataxx.newBoard();
    lastMove = null;
    picked = -1;
    turn = first;
    over = false;
    busy = false;
    overlayEl.hidden = true;
    buildBoard();
    advance();
  }

  for (const btn of levelsEl.querySelectorAll(".level-btn")) {
    btn.addEventListener("click", () => {
      level = btn.dataset.level;
      try { localStorage.setItem(STORAGE_LEVEL, level); } catch (e) {}
      for (const b of levelsEl.querySelectorAll(".level-btn")) {
        b.classList.toggle("on", b.dataset.level === level);
      }
      newGame();
    });
    btn.classList.toggle("on", btn.dataset.level === level);
  }

  for (const btn of firstsEl.querySelectorAll(".level-btn")) {
    btn.addEventListener("click", () => {
      first = btn.dataset.first === "foe" ? FOE : YOU;
      try { localStorage.setItem(STORAGE_FIRST, first === FOE ? "foe" : "you"); } catch (e) {}
      for (const b of firstsEl.querySelectorAll(".level-btn")) {
        b.classList.toggle("on", (b.dataset.first === "foe" ? FOE : YOU) === first);
      }
      newGame();
    });
    btn.classList.toggle("on", (btn.dataset.first === "foe" ? FOE : YOU) === first);
  }

  newBtn.addEventListener("click", newGame);
  overlayBtn.addEventListener("click", newGame);
  window.addEventListener("resize", () => { if (cells) buildBoard(); });

  // Read-only snapshot, and a way to play a square, for the automated checks.
  window.__ataxx = () => ({
    cells: Array.from(cells), turn, over, busy, level, first,
    lastMove: lastMove && { ...lastMove },
    record: { ...record },
    counts: Ataxx.counts(cells),
    yourMoves: Ataxx.legalMoves(cells, YOU).map((m) => ({ ...m })),
    picked,
  });
  window.__tap = (i) => {
    squares[i].dispatchEvent(new MouseEvent("click", { bubbles: true }));
  };
  // Lets a check set up a position that is otherwise hard to reach by playing,
  // such as one where a side has nowhere to go and has to pass.
  window.__setBoard = (next, whose) => {
    if (timer) { clearTimeout(timer); timer = null; }
    cells = Int8Array.from(next);
    lastMove = null;
    picked = -1;
    over = false;
    busy = false;
    turn = whose;
    overlayEl.hidden = true;
    buildBoard();
    advance();
  };

  newGame();
})();
