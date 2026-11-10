/* かさねとり -- the pile, on screen.
 *
 * Board.js decides what a pile is and what may be taken from it; this file
 * puts it on the page, takes the taps, and keeps the level and the clock.
 */
(() => {
  "use strict";

  const boardEl = document.getElementById("board");
  const wrapEl = boardEl.parentElement;
  const levelEl = document.getElementById("level");
  const leftEl = document.getElementById("left");
  const openEl = document.getElementById("open");
  const overlay = document.getElementById("overlay");
  const overlayMsg = document.getElementById("overlay-message");
  const overlaySub = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const hintBtn = document.getElementById("hint-btn");
  const hintLeftEl = document.getElementById("hint-left");
  const undoBtn = document.getElementById("undo-btn");
  const restackBtn = document.getElementById("restack-btn");
  const newBtn = document.getElementById("new-btn");

  const HINTS = 3;
  const OFFSET = 0.12;    // how far each layer is shifted, as a share of a tile
  const RATIO = 1.34;     // a tile is taller than it is wide, as a real one is

  let board = null;
  let alive = new Set();
  let nodes = [];
  let picked = null;
  let history = [];
  let level = 1;
  let hints = HINTS;
  let restacks = 0;
  let startedAt = 0;
  let cleared = false;
  let timers = [];

  /* A timer must not outlive the pile it was set on. Clearing a pile sets one
   * going to raise the overlay; without this, starting the next pile inside
   * that moment let the old timer land on the new one and freeze it. */
  function later(fn, ms) {
    const id = setTimeout(() => {
      timers = timers.filter((t) => t !== id);
      fn();
    }, ms);
    timers.push(id);
    return id;
  }
  function stopTimers() {
    timers.forEach(clearTimeout);
    timers = [];
  }

  /* ---- what is kept between visits --------------------------------- */

  function readStore(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch (err) {
      return fallback;
    }
  }
  function writeStore(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (err) {
      /* private mode: the game is still playable, it just forgets */
    }
  }

  /* ---- sizing ------------------------------------------------------ */

  function layerCount() {
    return board ? Math.max(...board.tiles.map((t) => t.z)) + 1 : 1;
  }

  function metrics() {
    const layers = layerCount();
    const availW = Math.max(200, wrapEl.clientWidth);
    // Leave room for the masthead, the hint line and the buttons, so the pile
    // is on screen in one piece rather than half of it below the fold.
    const availH = Math.max(230, window.innerHeight - 300);
    let tw = availW / (board.w + (layers - 1) * OFFSET);
    let th = tw * RATIO;
    const needH = board.d * th + (layers - 1) * th * OFFSET;
    if (needH > availH) {
      th = availH / (board.d + (layers - 1) * OFFSET);
      tw = th / RATIO;
    }
    tw = Math.max(36, Math.floor(tw));
    th = Math.floor(tw * RATIO);
    return { tw, th, offX: Math.round(tw * OFFSET), offY: Math.round(th * OFFSET), layers };
  }

  function place() {
    if (!board) return;
    const m = metrics();
    boardEl.style.width = (board.w * m.tw + (m.layers - 1) * m.offX) + "px";
    boardEl.style.height = (board.d * m.th + (m.layers - 1) * m.offY) + "px";
    board.tiles.forEach((t, i) => {
      const node = nodes[i];
      node.style.width = m.tw + "px";
      node.style.height = m.th + "px";
      node.style.left = (t.x * m.tw + (m.layers - 1 - t.z) * m.offX) + "px";
      node.style.top = (t.y * m.th + (m.layers - 1 - t.z) * m.offY) + "px";
      node.style.zIndex = String(t.z * 100 + t.y);
    });
  }

  /* ---- the pile on the page ---------------------------------------- */

  function build() {
    boardEl.innerHTML = "";
    nodes = board.tiles.map((t, i) => {
      const node = document.createElement("button");
      node.className = "tile";
      node.type = "button";
      node.dataset.i = String(i);
      node.dataset.kind = t.kind;
      node.setAttribute("aria-label", Faces.name(t.kind));
      node.innerHTML = Faces.svg(t.kind);
      boardEl.appendChild(node);
      return node;
    });
    place();
  }

  function paint() {
    const free = new Set(Board.freeList(board.tiles, alive));
    board.tiles.forEach((t, i) => {
      const node = nodes[i];
      if (!alive.has(i)) {
        node.hidden = true;
        return;
      }
      node.hidden = false;
      node.classList.toggle("free", free.has(i));
      node.classList.toggle("locked", !free.has(i));
      node.classList.toggle("picked", picked === i);
    });
    const open = Board.pairs(board.tiles, alive).length;
    levelEl.textContent = String(level);
    leftEl.textContent = String(alive.size);
    openEl.textContent = String(open);
    openEl.classList.toggle("none", open === 0 && alive.size > 0);
    restackBtn.classList.toggle("urge", open === 0 && alive.size > 0);
    undoBtn.disabled = history.length === 0;
    hintBtn.disabled = hints === 0 || open === 0;
    hintLeftEl.textContent = String(hints);
  }

  /* ---- playing ------------------------------------------------------ */

  function isFree(i) {
    return Board.freeList(board.tiles, alive).includes(i);
  }

  function tap(i) {
    if (cleared || !alive.has(i) || !isFree(i)) return;
    if (picked === i) {
      picked = null;
      paint();
      return;
    }
    if (picked !== null && board.tiles[picked].kind === board.tiles[i].kind) {
      take(picked, i);
      return;
    }
    picked = i;
    paint();
  }

  function take(a, b) {
    alive.delete(a);
    alive.delete(b);
    history.push([a, b]);
    picked = null;
    [a, b].forEach((i) => {
      const node = nodes[i];
      node.classList.remove("picked", "free");
      node.classList.add("going");
      later(() => { node.classList.remove("going"); }, 240);
    });
    later(paint, 180);
    if (alive.size === 0) later(finish, 260);
  }

  function undo() {
    const last = history.pop();
    if (!last) return;
    last.forEach((i) => alive.add(i));
    picked = null;
    paint();
  }

  function hint() {
    const options = Board.pairs(board.tiles, alive);
    if (!options.length || hints === 0) return;
    hints -= 1;
    const [a, b] = options[Math.floor(Math.random() * options.length)];
    [a, b].forEach((i) => {
      nodes[i].classList.remove("hinted");
      void nodes[i].offsetWidth;          // restart the animation
      nodes[i].classList.add("hinted");
      later(() => nodes[i].classList.remove("hinted"), 1900);
    });
    paint();
  }

  function restack() {
    if (!alive.size) return;
    if (!Board.restack(board.tiles, alive)) return;
    restacks += 1;
    picked = null;
    history = [];                      // the old pile is gone; nothing to go back to
    board.tiles.forEach((t, i) => {
      nodes[i].dataset.kind = t.kind;
      nodes[i].innerHTML = Faces.svg(t.kind);
      nodes[i].setAttribute("aria-label", Faces.name(t.kind));
    });
    paint();
  }

  /* ---- levels -------------------------------------------------------- */

  function seconds() {
    return Math.max(0, Math.round((Date.now() - startedAt) / 1000));
  }
  function clock(total) {
    return Math.floor(total / 60) + ":" + String(total % 60).padStart(2, "0");
  }

  function finish() {
    cleared = true;
    const took = seconds();
    const bests = readStore("tiles-best", {});
    const prev = bests[level];
    const best = prev === undefined ? took : Math.min(prev, took);
    bests[level] = best;
    writeStore("tiles-best", bests);
    writeStore("tiles-level", level + 1);
    overlayMsg.textContent = "取り切った！";
    overlaySub.innerHTML = `${board.tiles.length}枚 / ${clock(took)}<br>ベスト ${clock(best)}` +
      (restacks ? `<br>つみなおし ${restacks}回` : "");
    overlayBtn.textContent = "次の山へ";
    overlay.hidden = false;
  }

  function start(next) {
    stopTimers();
    level = Math.max(1, next);
    const dealt = Board.deal(level);
    if (!dealt) return;
    board = dealt;
    alive = new Set(board.tiles.keys());
    picked = null;
    history = [];
    hints = HINTS;
    restacks = 0;
    cleared = false;
    startedAt = Date.now();
    overlay.hidden = true;
    build();
    paint();
  }

  /* ---- wiring --------------------------------------------------------- */

  boardEl.addEventListener("click", (event) => {
    const node = event.target.closest(".tile");
    if (!node) return;
    tap(Number(node.dataset.i));
  });

  hintBtn.addEventListener("click", hint);
  undoBtn.addEventListener("click", undo);
  restackBtn.addEventListener("click", restack);
  newBtn.addEventListener("click", () => start(level));
  overlayBtn.addEventListener("click", () => start(level + 1));
  window.addEventListener("resize", place);

  // Read-only snapshot and a few handles for the automated checks.
  window.__tiles = () => ({
    level, left: alive.size, open: Board.pairs(board.tiles, alive).length,
    picked, cleared, hints, restacks, seconds: seconds(),
    width: board.w, depth: board.d, layers: layerCount(),
    free: Board.freeList(board.tiles, alive).slice().sort((a, b) => a - b),
    tiles: board.tiles.map((t, i) => ({ x: t.x, y: t.y, z: t.z, kind: t.kind, alive: alive.has(i) })),
    solution: board.solution.map(([a, b]) => [a, b]),
  });
  window.__pairs = () => Board.pairs(board.tiles, alive);
  window.__tap = tap;
  window.__start = start;
  window.__undo = undo;
  window.__restack = restack;

  start(readStore("tiles-level", 1));
})();
