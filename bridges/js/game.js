/* はしわたし -- the islands on screen.
 *
 * puzzle.js decides what a board is and what counts as an answer; this file
 * draws it, takes the drags, and keeps the level and the clock.
 */
(() => {
  "use strict";

  const canvas = document.getElementById("board");
  const ctx = canvas.getContext("2d");
  const levelEl = document.getElementById("level");
  const leftEl = document.getElementById("left");
  const timerEl = document.getElementById("timer");
  const noticeEl = document.getElementById("notice");
  const overlay = document.getElementById("overlay");
  const overlayMsg = document.getElementById("overlay-message");
  const overlaySub = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const hintBtn = document.getElementById("hint-btn");
  const hintLeftEl = document.getElementById("hint-left");
  const undoBtn = document.getElementById("undo-btn");
  const clearBtn = document.getElementById("clear-btn");
  const newBtn = document.getElementById("new-btn");

  const HINTS = 3;

  let puzzle = null;
  let counts = [];
  let history = [];
  let level = 1;
  let hints = HINTS;
  let picked = null;
  let dragTo = null;
  let cell = 40;
  let pad = 0;
  let startedAt = 0;
  let solved = false;
  let timers = [];

  // A timer must not outlive the board it was set on.
  function later(fn, ms) {
    const id = setTimeout(() => { timers = timers.filter((t) => t !== id); fn(); }, ms);
    timers.push(id);
    return id;
  }
  function stopTimers() { timers.forEach(clearTimeout); timers = []; }

  function readStore(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch (err) {
      return fallback;
    }
  }
  function writeStore(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (err) { /* private mode */ }
  }

  /* ---- where things are ------------------------------------------- */

  function size() {
    const wrap = canvas.parentElement;
    const availW = Math.max(200, wrap.clientWidth);
    const availH = Math.max(230, window.innerHeight - 300);
    cell = Math.max(26, Math.floor(Math.min(availW / puzzle.w, availH / puzzle.h)));
    pad = Math.round(cell * 0.1);
    const w = puzzle.w * cell + pad * 2;
    const h = puzzle.h * cell + pad * 2;
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  const atX = (c) => pad + c * cell + cell / 2;
  const atY = (r) => pad + r * cell + cell / 2;

  function used(i) {
    let n = 0;
    puzzle.edges.forEach((e, k) => { if (e.a === i || e.b === i) n += counts[k]; });
    return n;
  }

  function edgeBetween(a, b) {
    return puzzle.edges.findIndex((e) => (e.a === a && e.b === b) || (e.a === b && e.b === a));
  }

  /* ---- drawing ------------------------------------------------------ */

  function draw() {
    const w = Number(canvas.style.width.replace("px", ""));
    const h = Number(canvas.style.height.replace("px", ""));
    ctx.clearRect(0, 0, w, h);

    ctx.fillStyle = "#0e1726";
    ctx.fillRect(0, 0, w, h);

    // the water, faintly ruled so a straight line is easy to aim along
    ctx.strokeStyle = "rgba(233, 238, 246, 0.045)";
    ctx.lineWidth = 1;
    for (let c = 0; c <= puzzle.w; c += 1) {
      ctx.beginPath();
      ctx.moveTo(pad + c * cell, pad);
      ctx.lineTo(pad + c * cell, h - pad);
      ctx.stroke();
    }
    for (let r = 0; r <= puzzle.h; r += 1) {
      ctx.beginPath();
      ctx.moveTo(pad, pad + r * cell);
      ctx.lineTo(w - pad, pad + r * cell);
      ctx.stroke();
    }

    const gap = Math.max(3, Math.round(cell * 0.11));
    ctx.lineCap = "round";
    puzzle.edges.forEach((e, i) => {
      if (!counts[i]) return;
      const A = puzzle.islands[e.a], B = puzzle.islands[e.b];
      const flat = A.r === B.r;
      const offsets = counts[i] === 1 ? [0] : [-gap, gap];
      ctx.strokeStyle = "#9ab4de";
      ctx.lineWidth = Math.max(2, Math.round(cell * 0.07));
      for (const off of offsets) {
        ctx.beginPath();
        ctx.moveTo(atX(A.c) + (flat ? 0 : off), atY(A.r) + (flat ? off : 0));
        ctx.lineTo(atX(B.c) + (flat ? 0 : off), atY(B.r) + (flat ? off : 0));
        ctx.stroke();
      }
    });

    // the bridge being dragged out right now
    if (picked !== null && dragTo) {
      const A = puzzle.islands[picked];
      ctx.strokeStyle = "rgba(255, 207, 107, 0.55)";
      ctx.lineWidth = Math.max(2, Math.round(cell * 0.06));
      ctx.setLineDash([4, 5]);
      ctx.beginPath();
      ctx.moveTo(atX(A.c), atY(A.r));
      ctx.lineTo(dragTo.x, dragTo.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    const radius = cell * 0.36;
    puzzle.islands.forEach((is, i) => {
      const have = used(i);
      const full = have === is.need;
      const over = have > is.need;
      const x = atX(is.c), y = atY(is.r);

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = over ? "#3b1b22" : full ? "#9ab4de" : "#1b2740";
      ctx.fill();
      ctx.lineWidth = picked === i ? 3.5 : 2;
      ctx.strokeStyle = picked === i ? "#ffcf6b" : over ? "#ff6b6b" : full ? "#9ab4de" : "#6f8cb8";
      ctx.stroke();

      ctx.fillStyle = over ? "#ff6b6b" : full ? "#0b1220" : "#e9eef6";
      ctx.font = `800 ${Math.round(radius * 1.15)}px "JetBrains Mono", ui-monospace, monospace`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(is.need), x, y + 1);
    });
  }

  /* ---- the state of play --------------------------------------------- */

  function stillToDo() {
    return puzzle.islands.filter((is, i) => used(i) !== is.need).length;
  }

  function update() {
    const left = stillToDo();
    levelEl.textContent = String(level);
    leftEl.textContent = String(left);
    leftEl.classList.toggle("done", left === 0);
    undoBtn.disabled = history.length === 0;
    hintBtn.disabled = hints === 0 || solved;
    hintLeftEl.textContent = String(hints);
    if (!solved) {
      const joined = Puzzle.connected(puzzle.islands, puzzle.edges, counts);
      noticeEl.textContent = left === 0 && !joined
        ? "数字は合っていますが、島が離れています"
        : "";
    }
    draw();
    if (!solved && left === 0 && Puzzle.connected(puzzle.islands, puzzle.edges, counts)) finish();
  }

  function setEdge(i, value, remember) {
    if (counts[i] === value) return;
    if (remember !== false) history.push([i, counts[i]]);
    counts[i] = value;
  }

  // A bridge may not be laid across one that is already there.
  function blockedBy(i) {
    return (Puzzle.crossesOf(puzzle.islands, puzzle.edges)[i] || []).some((x) => counts[x] > 0);
  }

  function toggle(a, b) {
    const i = edgeBetween(a, b);
    if (i < 0) return false;
    const next = (counts[i] + 1) % 3;
    if (next > 0 && blockedBy(i)) {
      noticeEl.textContent = "橋どうしは交差できません";
      later(() => { if (noticeEl.textContent === "橋どうしは交差できません") update(); }, 1600);
      return false;
    }
    setEdge(i, next);
    update();
    return true;
  }

  function finish() {
    solved = true;
    picked = null;
    const took = Math.max(0, Math.round((Date.now() - startedAt) / 1000));
    const bests = readStore("bridges-best", {});
    const best = bests[level] === undefined ? took : Math.min(bests[level], took);
    bests[level] = best;
    writeStore("bridges-best", bests);
    writeStore("bridges-level", level + 1);
    noticeEl.textContent = "";
    overlayMsg.textContent = "ぜんぶつながった！";
    overlaySub.innerHTML = `${puzzle.islands.length}島 / ${clock(took)}<br>ベスト ${clock(best)}`;
    overlay.hidden = false;
    draw();
  }

  function clock(total) {
    return Math.floor(total / 60) + ":" + String(total % 60).padStart(2, "0");
  }

  /* ---- input ---------------------------------------------------------- */

  function islandAt(x, y) {
    let best = -1, near = cell * 0.75;
    puzzle.islands.forEach((is, i) => {
      const d = Math.hypot(atX(is.c) - x, atY(is.r) - y);
      if (d < near) { near = d; best = i; }
    });
    return best;
  }

  function spot(event) {
    const rect = canvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }

  canvas.addEventListener("pointerdown", (event) => {
    if (solved) return;
    const at = spot(event);
    const i = islandAt(at.x, at.y);
    if (i < 0) { picked = null; update(); return; }
    if (picked !== null && picked !== i && toggle(picked, i)) {
      picked = null;
      return;
    }
    picked = picked === i ? null : i;
    dragTo = null;
    canvas.setPointerCapture(event.pointerId);
    update();
  });

  canvas.addEventListener("pointermove", (event) => {
    if (picked === null || solved) return;
    dragTo = spot(event);
    draw();
  });

  function release(event) {
    if (picked === null || solved) { dragTo = null; return; }
    const at = dragTo || spot(event);
    const i = islandAt(at.x, at.y);
    dragTo = null;
    if (i >= 0 && i !== picked) {
      toggle(picked, i);
      picked = null;
    }
    update();
  }
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", () => { dragTo = null; draw(); });

  /* ---- the buttons ------------------------------------------------------ */

  undoBtn.addEventListener("click", () => {
    const last = history.pop();
    if (!last) return;
    counts[last[0]] = last[1];
    picked = null;
    update();
  });

  clearBtn.addEventListener("click", () => {
    counts = counts.map(() => 0);
    history = [];
    picked = null;
    update();
  });

  hintBtn.addEventListener("click", () => {
    if (hints === 0 || solved) return;
    const wrong = puzzle.edges
      .map((e, i) => i)
      .filter((i) => counts[i] !== puzzle.answer[i]);
    if (!wrong.length) return;
    hints -= 1;
    const i = wrong[Math.floor(Math.random() * wrong.length)];
    // clear whatever crosses it first, or the right bridge cannot be laid
    Puzzle.crossesOf(puzzle.islands, puzzle.edges)[i].forEach((x) => {
      if (counts[x] > 0 && puzzle.answer[i] > 0) setEdge(x, 0);
    });
    setEdge(i, puzzle.answer[i]);
    picked = null;
    update();
  });

  newBtn.addEventListener("click", () => start(level));
  overlayBtn.addEventListener("click", () => start(level + 1));
  window.addEventListener("resize", () => { if (puzzle) { size(); draw(); } });

  /* ---- levels ------------------------------------------------------------ */

  function start(next) {
    stopTimers();
    level = Math.max(1, next);
    const made = Puzzle.generate(level);
    if (!made) return;
    puzzle = made;
    counts = puzzle.edges.map(() => 0);
    history = [];
    hints = HINTS;
    picked = null;
    dragTo = null;
    solved = false;
    startedAt = Date.now();
    overlay.hidden = true;
    noticeEl.textContent = "";
    size();
    update();
  }

  setInterval(() => {
    if (puzzle && !solved) {
      timerEl.textContent = clock(Math.max(0, Math.round((Date.now() - startedAt) / 1000)));
    }
  }, 500);

  // Read-only snapshot and a few handles for the automated checks.
  window.__bridges = () => ({
    level, solved, hints, left: stillToDo(),
    w: puzzle.w, h: puzzle.h,
    notice: noticeEl.textContent,
    islands: puzzle.islands.map((is, i) => ({ r: is.r, c: is.c, need: is.need, have: used(i) })),
    edges: puzzle.edges.map((e, i) => ({ a: e.a, b: e.b, dir: e.dir, n: counts[i], answer: puzzle.answer[i] })),
    connected: Puzzle.connected(puzzle.islands, puzzle.edges, counts),
  });
  window.__toggle = (a, b) => toggle(a, b);
  window.__start = start;
  // what the game would call a tap at a point on the canvas, and how big an
  // island is drawn, so a check can aim where a finger would
  window.__islandAt = (x, y) => islandAt(x, y);
  window.__metrics = () => ({ cell, pad, radius: cell * 0.36, reach: cell * 0.75 });
  window.__spotOf = (i) => {
    const rect = canvas.getBoundingClientRect();
    return { x: rect.left + atX(puzzle.islands[i].c), y: rect.top + atY(puzzle.islands[i].r) };
  };

  start(readStore("bridges-level", 1));
})();
