// Steers the game by dispatching real key events at its own input handlers and
// watching the published state snapshot, the same loop a player closes by eye.
window.__drive = (() => {
  const peek = () => window.__maze3d();

  function blockPath(maze, fromB, toB) {
    const { cols, rows, blocks } = maze;
    const prev = new Map([[fromB, -1]]);
    const queue = [fromB];
    for (let head = 0; head < queue.length; head++) {
      const b = queue[head];
      if (b === toB) break;
      const bx = b % cols, by = Math.floor(b / cols);
      for (const [dx, dy] of [[0, -1], [1, 0], [0, 1], [-1, 0]]) {
        const nx = bx + dx, ny = by + dy;
        if (nx < 0 || ny < 0 || nx >= cols || ny >= rows) continue;
        const nb = ny * cols + nx;
        if (blocks[nb] === 1 || prev.has(nb)) continue;
        prev.set(nb, b);
        queue.push(nb);
      }
    }
    if (!prev.has(toB)) return null;
    const path = [];
    for (let b = toB; b !== -1; b = prev.get(b)) path.push(b);
    return path.reverse();
  }

  const frame = () => new Promise((r) => requestAnimationFrame(r));
  const norm = (a) => {
    while (a > Math.PI) a -= 2 * Math.PI;
    while (a < -Math.PI) a += 2 * Math.PI;
    return a;
  };

  return async function drive(targetCell, timeoutMs = 45000, autoDescend = true) {
    const press = (code, down) =>
      window.dispatchEvent(new KeyboardEvent(down ? "keydown" : "keyup", { code, bubbles: true }));
    let held = null;
    const setKey = (code) => {
      if (held === code) return;
      if (held) press(held, false);
      held = code;
      if (code) press(code, true);
    };

    const t0 = performance.now();
    let lastX = 0, lastY = 0, stuck = 0, climbed = 0;
    while (performance.now() - t0 < timeoutMs) {
      const s = peek();
      if (s.state === "lookout") {
        // A tower on the way is not a failure; note it and climb back down.
        setKey(null);
        climbed++;
        if (!autoDescend) return { reason: "lookout", climbed, ...s };
        document.getElementById("descend-btn").click();
        await frame();
        continue;
      }
      if (s.state !== "playing") { setKey(null); return { reason: s.state, climbed, ...s }; }
      const cols = s.maze.cols;
      const tcx = targetCell % s.maze.w, tcy = Math.floor(targetCell / s.maze.w);
      const toB = (tcy * 2 + 1) * cols + (tcx * 2 + 1);
      // Arrive at the middle of the cell, where whatever is standing there is.
      if (Math.hypot(s.x - (tcx * 2 + 1.5), s.y - (tcy * 2 + 1.5)) < 0.3) {
        setKey(null);
        return { reason: "arrived", climbed, ...s };
      }
      const fromB = Math.floor(s.y) * cols + Math.floor(s.x);
      let wx, wy;
      if (fromB === toB) {
        // Already in the right block, just not yet at the middle of it.
        wx = tcx * 2 + 1.5;
        wy = tcy * 2 + 1.5;
      } else {
        const path = blockPath(s.maze, fromB, toB);
        if (!path || path.length < 2) { setKey(null); return { reason: "no route", ...s }; }
        const next = path[1];
        wx = (next % cols) + 0.5;
        wy = Math.floor(next / cols) + 0.5;
      }
      const diff = norm(Math.atan2(wy - s.y, wx - s.x) - s.angle);
      setKey(Math.abs(diff) > 0.1 ? (diff > 0 ? "ArrowRight" : "ArrowLeft") : "ArrowUp");

      if (Math.hypot(s.x - lastX, s.y - lastY) < 0.004) stuck++; else stuck = 0;
      lastX = s.x; lastY = s.y;
      if (stuck > 90) { setKey(null); return { reason: "stuck", climbed, ...s }; }
      await frame();
    }
    setKey(null);
    return { reason: "timeout", climbed, ...peek() };
  };
})();
