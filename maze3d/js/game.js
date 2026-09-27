(() => {
  const STORAGE_LEVEL = "maze3d-level";
  const MOVE_SPEED = 2.7;          // blocks per second
  const TURN_SPEED = 2.4;          // radians per second on the buttons
  const LOOK_SENS = 0.0055;        // radians per pixel dragged
  const STAMP_REACH = 0.6;
  const STAMP_COLORS = ["#ff5a5a", "#4da3ff", "#ffcf6b", "#4ade80"];

  const canvas = document.getElementById("view");
  const viewWrap = document.querySelector(".view-wrap");
  const mapCanvas = document.getElementById("map");
  const levelEl = document.getElementById("level");
  const timerEl = document.getElementById("timer");
  const bestEl = document.getElementById("best");
  const slotsEl = document.getElementById("stamp-slots");
  const toastEl = document.getElementById("toast");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlaySubEl = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const lookoutEl = document.getElementById("lookout");
  const descendBtn = document.getElementById("descend-btn");
  const joystickEl = document.getElementById("joystick");
  const knobEl = document.getElementById("knob");
  const newBtn = document.getElementById("new-btn");

  const view = MazeView.create(canvas);

  let level = 1;
  try { level = Math.max(1, Number(localStorage.getItem(STORAGE_LEVEL)) || 1); } catch (e) {}

  let maze = null;
  let marks = null;
  let stamps = [];
  let towers = [];
  let goalPos = { x: 0, y: 0 };
  let camera = { x: 1.5, y: 1.5, angle: 0, bob: 0 };
  let state = "playing";           // playing | lookout | cleared
  let startTime = null;
  let elapsedMs = 0;
  let bestMs = null;
  let bobPhase = 0;
  let towerLock = -1;              // the tower you are standing on, so it fires once
  let toastTimer = 0;

  const input = { forward: 0, strafe: 0, turn: 0, dragTurn: 0 };
  const held = new Set();

  function bestKey() { return `maze3d-best-${maze.w}x${maze.h}`; }

  function loadBest() {
    try {
      const raw = localStorage.getItem(bestKey());
      return raw ? Number(raw) : null;
    } catch (e) { return null; }
  }

  function formatTime(ms) {
    const sec = Math.floor(ms / 1000);
    return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
  }

  function stampsLeft() { return stamps.filter((s) => !s.taken).length; }

  function toast(text) {
    toastEl.textContent = text;
    toastEl.hidden = false;
    toastTimer = 1600;
  }

  function buildStampCard() {
    slotsEl.innerHTML = "";
    for (const stamp of stamps) {
      const slot = document.createElement("span");
      slot.className = "stamp-slot";
      slot.style.setProperty("--slot", stamp.color);
      slotsEl.appendChild(slot);
      stamp.el = slot;
    }
  }

  function updateHud() {
    levelEl.textContent = String(level);
    const running = startTime !== null && state !== "cleared"
      ? performance.now() - startTime : elapsedMs;
    timerEl.textContent = formatTime(running);
    bestEl.textContent = bestMs === null ? "--:--" : formatTime(bestMs);
    for (const stamp of stamps) stamp.el.classList.toggle("on", stamp.taken);
  }

  function newMaze(targetLevel) {
    const world = Maze3D.generate(targetLevel);
    maze = world.maze;
    marks = world.marks;

    stamps = marks.stamps.map((cell, i) => {
      const center = Maze3D.cellCenter(maze, cell);
      return { cell, x: center.x, y: center.y, color: STAMP_COLORS[i % STAMP_COLORS.length], taken: false };
    });
    towers = marks.towers.map((cell) => ({ cell, ...Maze3D.cellCenter(maze, cell) }));
    goalPos = Maze3D.cellCenter(maze, marks.goal);

    const start = Maze3D.cellCenter(maze, marks.start);
    // Face whichever way you can actually walk, so the first frame is not a wall.
    let angle = 0;
    for (const [dx, dy] of Maze3D.DIRS) {
      if (!Maze3D.isWall(maze, Math.floor(start.x) + dx, Math.floor(start.y) + dy)) {
        angle = Math.atan2(dy, dx);
        break;
      }
    }
    camera = { x: start.x, y: start.y, angle, bob: 0 };

    state = "playing";
    startTime = null;
    elapsedMs = 0;
    towerLock = -1;
    bestMs = loadBest();
    overlayEl.hidden = true;
    lookoutEl.hidden = true;
    toastEl.hidden = true;
    buildStampCard();
    sizeView();
    updateHud();
  }

  function sprites() {
    const out = [];
    for (const stamp of stamps) {
      if (stamp.taken) continue;
      out.push({ x: stamp.x, y: stamp.y, tex: view.stampTex(stamp.color), height: 1.05 });
    }
    for (const tower of towers) {
      out.push({ x: tower.x, y: tower.y, tex: view.textures.tower, height: 1.9 });
    }
    out.push({
      x: goalPos.x, y: goalPos.y, height: 1.5,
      tex: stampsLeft() === 0 ? view.textures.gateOpen : view.textures.gateShut,
    });
    return out;
  }

  // ---------- simulation ----------

  function step(dt) {
    if (state !== "playing") return;

    const turn = input.turn * TURN_SPEED * dt + input.dragTurn;
    input.dragTurn = 0;
    if (turn !== 0) {
      camera.angle += turn;
      if (startTime === null) startTime = performance.now();
    }

    const forward = input.forward, strafe = input.strafe;
    if (forward !== 0 || strafe !== 0) {
      if (startTime === null) startTime = performance.now();
      const speed = MOVE_SPEED * dt;
      const dirX = Math.cos(camera.angle), dirY = Math.sin(camera.angle);
      const dx = dirX * forward * speed - dirY * strafe * speed;
      const dy = dirY * forward * speed + dirX * strafe * speed;
      const moved = Maze3D.resolveMove(maze, camera.x, camera.y, dx, dy);
      camera.x = moved.x;
      camera.y = moved.y;
      bobPhase += dt * 9.5 * Math.min(1, Math.hypot(forward, strafe));
      camera.bob = Math.sin(bobPhase) * 0.007;
    } else {
      camera.bob *= 0.85;
    }

    for (const stamp of stamps) {
      if (stamp.taken) continue;
      if (Math.hypot(stamp.x - camera.x, stamp.y - camera.y) > STAMP_REACH) continue;
      stamp.taken = true;
      const left = stampsLeft();
      toast(left === 0 ? "スタンプ コンプリート！ゴールへ" : `スタンプ ${stamps.length - left}/${stamps.length}`);
    }

    const cell = Maze3D.cellAt(maze, camera.x, camera.y);
    const tower = towers.find((t) => t.cell === cell);
    if (tower && towerLock !== cell) {
      towerLock = cell;
      climb();
      return;
    }
    if (!tower) towerLock = -1;

    if (cell === marks.goal) {
      if (stampsLeft() === 0) finish();
      else if (toastTimer <= 0) toast(`スタンプがあと${stampsLeft()}つ`);
    }
  }

  function finish() {
    state = "cleared";
    elapsedMs = startTime === null ? 0 : performance.now() - startTime;
    const isBest = bestMs === null || elapsedMs < bestMs;
    if (isBest) {
      bestMs = Math.round(elapsedMs);
      try { localStorage.setItem(bestKey(), String(bestMs)); } catch (e) {}
    }
    updateHud();
    overlayMessageEl.textContent = "ゴール！";
    overlaySubEl.textContent =
      `${maze.w}×${maze.h} ／ ${formatTime(elapsedMs)}${isBest ? " ／ ベスト更新！" : ""}`;
    overlayEl.hidden = false;
    clearInput();
  }

  function climb() {
    state = "lookout";
    clearInput();
    drawMap();
    lookoutEl.hidden = false;
  }

  function descend() {
    lookoutEl.hidden = true;
    state = "playing";
  }

  // ---------- the view from the tower ----------

  function drawMap() {
    // Leave room for the caption above and the button below, or the way down
    // ends up off-screen.
    const size = Math.max(140, Math.min(
      viewWrap.clientWidth - 36, viewWrap.clientHeight - 112, 320));
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    mapCanvas.style.width = `${size}px`;
    mapCanvas.style.height = `${size}px`;
    mapCanvas.width = Math.round(size * dpr);
    mapCanvas.height = Math.round(size * dpr);
    const g = mapCanvas.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);

    const px = size / Math.max(maze.cols, maze.rows);
    const offX = (size - px * maze.cols) / 2;
    const offY = (size - px * maze.rows) / 2;

    g.fillStyle = "#e7dcc4";
    g.fillRect(0, 0, size, size);
    g.fillStyle = "#6b4f32";
    for (let by = 0; by < maze.rows; by++) {
      for (let bx = 0; bx < maze.cols; bx++) {
        if (Maze3D.isWall(maze, bx, by)) {
          g.fillRect(offX + bx * px, offY + by * px, px + 0.5, px + 0.5);
        }
      }
    }

    const dot = (wx, wy, color, r) => {
      g.fillStyle = color;
      g.beginPath();
      g.arc(offX + wx * px, offY + wy * px, r, 0, Math.PI * 2);
      g.fill();
    };

    for (const stamp of stamps) {
      if (!stamp.taken) dot(stamp.x, stamp.y, stamp.color, px * 0.55);
    }
    for (const tower of towers) dot(tower.x, tower.y, "#3f8f6f", px * 0.45);

    g.fillStyle = stampsLeft() === 0 ? "#e8a33f" : "#9a8c78";
    g.fillRect(offX + (goalPos.x - 0.7) * px, offY + (goalPos.y - 0.7) * px, px * 1.4, px * 1.4);

    // you, and which way you are facing
    const cx = offX + camera.x * px, cy = offY + camera.y * px;
    g.fillStyle = "#1f6fd0";
    g.beginPath();
    g.moveTo(cx + Math.cos(camera.angle) * px * 1.1, cy + Math.sin(camera.angle) * px * 1.1);
    g.lineTo(cx + Math.cos(camera.angle + 2.5) * px * 0.75, cy + Math.sin(camera.angle + 2.5) * px * 0.75);
    g.lineTo(cx + Math.cos(camera.angle - 2.5) * px * 0.75, cy + Math.sin(camera.angle - 2.5) * px * 0.75);
    g.closePath();
    g.fill();
  }

  // ---------- layout ----------

  function sizeView() {
    const wrapWidth = viewWrap.clientWidth;
    const height = Math.round(Math.min(window.innerHeight * 0.46, 360));
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    view.resize(wrapWidth, height, dpr);
  }

  // ---------- input ----------

  function clearInput() {
    input.forward = 0;
    input.strafe = 0;
    input.turn = 0;
    input.dragTurn = 0;
    held.clear();
    joystickEl.hidden = true;
  }

  const KEYS = {
    ArrowUp: "forward", KeyW: "forward",
    ArrowDown: "back", KeyS: "back",
    ArrowLeft: "left", KeyA: "strafeLeft",
    ArrowRight: "right", KeyD: "strafeRight",
  };

  function applyHeld() {
    input.forward = (held.has("forward") ? 1 : 0) - (held.has("back") ? 1 : 0);
    input.turn = (held.has("right") ? 1 : 0) - (held.has("left") ? 1 : 0);
    input.strafe = (held.has("strafeRight") ? 1 : 0) - (held.has("strafeLeft") ? 1 : 0);
  }

  window.addEventListener("keydown", (e) => {
    const action = KEYS[e.code];
    if (!action) return;
    e.preventDefault();
    held.add(action);
    applyHeld();
  });

  window.addEventListener("keyup", (e) => {
    const action = KEYS[e.code];
    if (!action) return;
    held.delete(action);
    applyHeld();
  });

  // Hold-to-move buttons for people who would rather not drag.
  for (const [id, action] of [["btn-forward", "forward"], ["btn-back", "back"],
                              ["btn-left", "left"], ["btn-right", "right"]]) {
    const el = document.getElementById(id);
    const press = (e) => { e.preventDefault(); held.add(action); applyHeld(); };
    const release = () => { held.delete(action); applyHeld(); };
    el.addEventListener("pointerdown", press);
    el.addEventListener("pointerup", release);
    el.addEventListener("pointercancel", release);
    el.addEventListener("pointerleave", release);
  }

  // Left half of the view is a thumb stick, right half turns the view.
  let stick = null;   // {id, ox, oy}
  let look = null;    // {id, lastX}
  const STICK_RANGE = 46;

  canvas.addEventListener("touchstart", (e) => {
    const rect = canvas.getBoundingClientRect();
    for (const touch of e.changedTouches) {
      const localX = touch.clientX - rect.left;
      if (localX < rect.width / 2 && stick === null) {
        stick = { id: touch.identifier, ox: touch.clientX, oy: touch.clientY };
        joystickEl.hidden = false;
        joystickEl.style.left = `${localX}px`;
        joystickEl.style.top = `${touch.clientY - rect.top}px`;
        knobEl.style.transform = "translate(-50%, -50%)";
      } else if (localX >= rect.width / 2 && look === null) {
        look = { id: touch.identifier, lastX: touch.clientX };
      }
    }
  }, { passive: true });

  canvas.addEventListener("touchmove", (e) => {
    for (const touch of e.changedTouches) {
      if (stick && touch.identifier === stick.id) {
        const dx = touch.clientX - stick.ox;
        const dy = touch.clientY - stick.oy;
        const len = Math.hypot(dx, dy) || 1;
        const clamped = Math.min(len, STICK_RANGE) / len;
        input.forward = -(dy * clamped) / STICK_RANGE;
        input.strafe = (dx * clamped) / STICK_RANGE;
        knobEl.style.transform =
          `translate(calc(-50% + ${dx * clamped}px), calc(-50% + ${dy * clamped}px))`;
      } else if (look && touch.identifier === look.id) {
        input.dragTurn += (touch.clientX - look.lastX) * LOOK_SENS;
        look.lastX = touch.clientX;
      }
    }
  }, { passive: true });

  function endTouch(e) {
    for (const touch of e.changedTouches) {
      if (stick && touch.identifier === stick.id) {
        stick = null;
        input.forward = 0;
        input.strafe = 0;
        joystickEl.hidden = true;
      }
      if (look && touch.identifier === look.id) look = null;
    }
  }
  canvas.addEventListener("touchend", endTouch, { passive: true });
  canvas.addEventListener("touchcancel", endTouch, { passive: true });

  descendBtn.addEventListener("click", descend);
  newBtn.addEventListener("click", () => newMaze(level));
  overlayBtn.addEventListener("click", () => {
    level += 1;
    try { localStorage.setItem(STORAGE_LEVEL, String(level)); } catch (e) {}
    newMaze(level);
  });

  window.addEventListener("resize", () => {
    sizeView();
    if (state === "lookout") drawMap();
  });

  // ---------- loop ----------

  let lastFrame = performance.now();
  function loop(now) {
    const dt = Math.min(0.05, (now - lastFrame) / 1000);
    lastFrame = now;
    step(dt);
    if (toastTimer > 0) {
      toastTimer -= dt * 1000;
      if (toastTimer <= 0) toastEl.hidden = true;
    }
    if (state !== "lookout") view.draw({ maze, camera, sprites: sprites() });
    if (state === "playing" && startTime !== null) updateHud();
    requestAnimationFrame(loop);
  }

  // Read-only snapshot for the automated checks; nothing in the game reads it.
  window.__maze3d = () => ({
    x: camera.x, y: camera.y, angle: camera.angle, state, level,
    cell: Maze3D.cellAt(maze, camera.x, camera.y),
    goal: marks.goal, stampsLeft: stampsLeft(),
    stamps: stamps.map((s) => ({ cell: s.cell, taken: s.taken })),
    towers: towers.map((t) => t.cell),
    maze: { w: maze.w, h: maze.h, cols: maze.cols, rows: maze.rows, blocks: Array.from(maze.blocks) },
  });

  newMaze(level);
  requestAnimationFrame(loop);
})();
