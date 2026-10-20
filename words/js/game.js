(() => {
  const STORAGE_LEVEL = "words-level";
  const STORAGE_BONUS = "words-bonus";
  const HINTS_PER_PUZZLE = 3;

  const gridEl = document.getElementById("grid");
  const levelEl = document.getElementById("level");
  const foundEl = document.getElementById("found");
  const bonusEl = document.getElementById("bonus");
  const currentEl = document.getElementById("current");
  const wheelEl = document.getElementById("wheel");
  const wheelWrap = document.querySelector(".wheel-wrap");
  const traceCanvas = document.getElementById("trace");
  const traceCtx = traceCanvas.getContext("2d");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlaySubEl = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const shuffleBtn = document.getElementById("shuffle-btn");
  const hintBtn = document.getElementById("hint-btn");
  const hintCountEl = document.getElementById("hint-count");

  let level = 1;
  let bonusTotal = 0;
  try {
    level = Math.max(1, Number(localStorage.getItem(STORAGE_LEVEL)) || 1);
    bonusTotal = Math.max(0, Number(localStorage.getItem(STORAGE_BONUS)) || 0);
  } catch (e) {}

  let puzzle = null;
  let solved = new Set();        // grid words already found
  let bonusFound = new Set();    // extra words found this puzzle
  let hintsLeft = HINTS_PER_PUZZLE;
  let cellNodes = [];            // row-major, null where there is no cell
  let letterNodes = [];
  let selection = [];            // indices into letterNodes
  let pointerId = null;
  let pointerPos = null;
  let cleared = false;

  // ---------- layout ----------

  function buildGrid() {
    const { width, height, cells } = puzzle.grid;
    const available = gridEl.parentElement.clientWidth - 4;
    // The wheel has to share the screen, so the board is capped by height too.
    const byWidth = Math.floor((available - (width - 1) * 3) / width);
    const byHeight = Math.floor((window.innerHeight * 0.3 - (height - 1) * 3) / height);
    const size = Math.max(20, Math.min(46, byWidth, byHeight));
    gridEl.style.gridTemplateColumns = `repeat(${width}, ${size}px)`;
    gridEl.innerHTML = "";
    cellNodes = [];
    for (let r = 0; r < height; r++) {
      const row = [];
      for (let c = 0; c < width; c++) {
        const node = document.createElement("div");
        node.className = cells[r][c] ? "cell" : "cell blank";
        node.style.width = `${size}px`;
        node.style.height = `${size}px`;
        node.style.fontSize = `${Math.round(size * 0.52)}px`;
        node.textContent = cells[r][c] || "";
        gridEl.appendChild(node);
        row.push(cells[r][c] ? node : null);
      }
      cellNodes.push(row);
    }
  }

  function buildWheel() {
    const letters = puzzle.letters;
    const diameter = Math.max(186, Math.min(
      wheelWrap.parentElement.clientWidth - 24, 268, window.innerHeight * 0.36));
    const letterSize = diameter < 220 || letters.length > 6 ? 48 : 54;
    const radius = diameter / 2 - letterSize / 2;

    wheelWrap.style.width = `${diameter}px`;
    wheelWrap.style.height = `${diameter}px`;
    wheelEl.style.width = `${diameter}px`;
    wheelEl.style.height = `${diameter}px`;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    traceCanvas.style.width = `${diameter}px`;
    traceCanvas.style.height = `${diameter}px`;
    traceCanvas.width = Math.round(diameter * dpr);
    traceCanvas.height = Math.round(diameter * dpr);
    traceCtx.setTransform(dpr, 0, 0, dpr, 0, 0);

    wheelEl.innerHTML = "";
    letterNodes = letters.map((ch, i) => {
      const angle = -Math.PI / 2 + (i / letters.length) * Math.PI * 2;
      const x = diameter / 2 + Math.cos(angle) * radius;
      const y = diameter / 2 + Math.sin(angle) * radius;
      const node = document.createElement("div");
      node.className = "letter";
      node.textContent = ch;
      node.style.width = `${letterSize}px`;
      node.style.height = `${letterSize}px`;
      node.style.fontSize = `${Math.round(letterSize * 0.5)}px`;
      node.style.left = `${x - letterSize / 2}px`;
      node.style.top = `${y - letterSize / 2}px`;
      wheelEl.appendChild(node);
      return { node, ch, x, y, r: letterSize / 2 };
    });
    drawTrace();
  }

  function drawTrace() {
    const w = traceCanvas.width / (Math.min(window.devicePixelRatio || 1, 2));
    traceCtx.clearRect(0, 0, w, w);
    if (selection.length === 0) return;
    traceCtx.strokeStyle = "rgba(232, 121, 249, 0.85)";
    traceCtx.lineWidth = 6;
    traceCtx.lineCap = "round";
    traceCtx.lineJoin = "round";
    traceCtx.beginPath();
    selection.forEach((idx, i) => {
      const p = letterNodes[idx];
      if (i === 0) traceCtx.moveTo(p.x, p.y);
      else traceCtx.lineTo(p.x, p.y);
    });
    if (pointerPos) traceCtx.lineTo(pointerPos.x, pointerPos.y);
    traceCtx.stroke();
  }

  // ---------- state ----------

  function currentWord() {
    return selection.map((i) => letterNodes[i].ch).join("");
  }

  function updateHud() {
    levelEl.textContent = String(level);
    foundEl.textContent = `${solved.size}/${puzzle.entries.length}`;
    bonusEl.textContent = String(bonusTotal);
    hintCountEl.textContent = ` ${hintsLeft}`;
    hintBtn.disabled = hintsLeft === 0 || cleared;
  }

  function revealWord(word, hinted) {
    for (const entry of puzzle.entries) {
      if (entry.word !== word) continue;
      for (let i = 0; i < word.length; i++) {
        const r = entry.row + (entry.dir === "down" ? i : 0);
        const c = entry.col + (entry.dir === "across" ? i : 0);
        const node = cellNodes[r][c];
        if (!node || node.classList.contains("open")) continue;
        node.classList.add("open", "pop");
        if (hinted) node.classList.add("hinted");
        setTimeout(() => node.classList.remove("pop"), 340);
      }
    }
  }

  function flash(text, kind) {
    currentEl.textContent = text;
    currentEl.className = `current ${kind}`;
    setTimeout(() => {
      if (selection.length === 0) {
        currentEl.innerHTML = "&nbsp;";
        currentEl.className = "current";
      }
    }, 650);
  }

  function submit() {
    const word = currentWord();
    selection = [];
    for (const l of letterNodes) l.node.classList.remove("on");
    drawTrace();
    if (word.length < 2) {
      currentEl.innerHTML = "&nbsp;";
      currentEl.className = "current";
      return;
    }

    const inGrid = puzzle.entries.some((e) => e.word === word);
    if (inGrid && !solved.has(word)) {
      solved.add(word);
      revealWord(word, false);
      flash(word, "good");
      updateHud();
      if (solved.size === puzzle.entries.length) finish();
      return;
    }
    if (inGrid) { flash(word, "good"); return; }

    if (WordDict.has(word) && !bonusFound.has(word)) {
      bonusFound.add(word);
      bonusTotal += 1;
      try { localStorage.setItem(STORAGE_BONUS, String(bonusTotal)); } catch (e) {}
      flash(`${word} ＋ボーナス`, "bonus");
      updateHud();
      return;
    }
    flash(word, bonusFound.has(word) ? "bonus" : "bad");
  }

  function finish() {
    cleared = true;
    overlayMessageEl.textContent = "ぜんぶ みつけた！";
    const extra = bonusFound.size ? `／ ボーナス ${bonusFound.size}語` : "";
    overlaySubEl.textContent = `${puzzle.base} の ${puzzle.entries.length}語 ${extra}`;
    overlayEl.hidden = false;
    updateHud();
  }

  function newPuzzle(targetLevel) {
    const made = WordPuzzle.generate(targetLevel);
    if (!made) return;                       // generator gave up; keep the board
    puzzle = made;
    solved = new Set();
    bonusFound = new Set();
    hintsLeft = HINTS_PER_PUZZLE;
    selection = [];
    cleared = false;
    overlayEl.hidden = true;
    currentEl.innerHTML = "&nbsp;";
    currentEl.className = "current";
    buildGrid();
    buildWheel();
    updateHud();
  }

  // ---------- input ----------

  function localPoint(event) {
    const rect = wheelWrap.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }

  function hitLetter(point) {
    for (let i = 0; i < letterNodes.length; i++) {
      const l = letterNodes[i];
      if (Math.hypot(l.x - point.x, l.y - point.y) <= l.r * 0.95) return i;
    }
    return -1;
  }

  function extend(index) {
    if (index === -1) return;
    const at = selection.indexOf(index);
    if (at !== -1) {
      // dragging back over an earlier letter undoes everything after it
      if (at === selection.length - 2) {
        const dropped = selection.pop();
        letterNodes[dropped].node.classList.remove("on");
      }
      return;
    }
    selection.push(index);
    letterNodes[index].node.classList.add("on");
  }

  wheelWrap.addEventListener("pointerdown", (event) => {
    if (cleared || pointerId !== null) return;
    const point = localPoint(event);
    const hit = hitLetter(point);
    if (hit === -1) return;
    event.preventDefault();
    pointerId = event.pointerId;
    wheelWrap.setPointerCapture(pointerId);
    selection = [];
    extend(hit);
    pointerPos = point;
    currentEl.className = "current";
    currentEl.textContent = currentWord();
    drawTrace();
  });

  wheelWrap.addEventListener("pointermove", (event) => {
    if (event.pointerId !== pointerId) return;
    pointerPos = localPoint(event);
    extend(hitLetter(pointerPos));
    currentEl.textContent = currentWord();
    drawTrace();
  });

  function endPointer(event) {
    if (event.pointerId !== pointerId) return;
    pointerId = null;
    pointerPos = null;
    submit();
  }
  wheelWrap.addEventListener("pointerup", endPointer);
  wheelWrap.addEventListener("pointercancel", endPointer);

  shuffleBtn.addEventListener("click", () => {
    if (!puzzle) return;
    for (let i = puzzle.letters.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [puzzle.letters[i], puzzle.letters[j]] = [puzzle.letters[j], puzzle.letters[i]];
    }
    selection = [];
    buildWheel();
  });

  hintBtn.addEventListener("click", () => {
    if (hintsLeft === 0 || cleared) return;
    const pending = puzzle.entries.filter((e) => !solved.has(e.word));
    if (pending.length === 0) return;
    // open a single cell of the shortest unsolved word
    pending.sort((a, b) => a.word.length - b.word.length);
    const entry = pending[0];
    for (let i = 0; i < entry.word.length; i++) {
      const r = entry.row + (entry.dir === "down" ? i : 0);
      const c = entry.col + (entry.dir === "across" ? i : 0);
      const node = cellNodes[r][c];
      if (node && !node.classList.contains("open")) {
        node.classList.add("open", "hinted", "pop");
        setTimeout(() => node.classList.remove("pop"), 340);
        hintsLeft -= 1;
        updateHud();
        return;
      }
    }
  });

  overlayBtn.addEventListener("click", () => {
    level += 1;
    try { localStorage.setItem(STORAGE_LEVEL, String(level)); } catch (e) {}
    newPuzzle(level);
  });

  window.addEventListener("resize", () => {
    if (!puzzle) return;
    buildGrid();
    buildWheel();
    for (const word of solved) revealWord(word, false);
  });

  // Read-only snapshot for the automated checks.
  window.__words = () => ({
    level, base: puzzle.base, letters: puzzle.letters.slice(),
    entries: puzzle.entries.map((e) => ({ ...e })),
    bonusWords: puzzle.bonus.slice(),
    solved: [...solved], bonusFound: [...bonusFound], bonusTotal,
    hintsLeft, cleared,
    grid: puzzle.grid.cells.map((row) => row.slice()),
    openCells: cellNodes.map((row) => row.map((n) => (n && n.classList.contains("open") ? 1 : 0))),
  });
  window.__spell = (word) => {
    // drive the wheel the way a finger would: pick each letter in turn
    selection = [];
    for (const ch of word) {
      const idx = letterNodes.findIndex((l, i) => l.ch === ch && !selection.includes(i));
      if (idx === -1) { selection = []; return false; }
      extend(idx);
    }
    submit();
    return true;
  };

  newPuzzle(level);
})();
