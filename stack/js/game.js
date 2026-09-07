(() => {
  const STORAGE_BEST = "stack-tower-best-score";
  const BLOCK_HEIGHT = 34;
  const VISIBLE_ROWS = 9;
  const PERFECT_TOLERANCE = 6;
  const BASE_SPEED = 2.4;
  const MAX_SPEED = 6.5;
  const SPEED_GAIN = 0.12;

  const canvas = document.getElementById("stage");
  const ctx = canvas.getContext("2d");
  const scoreEl = document.getElementById("score");
  const bestEl = document.getElementById("best");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlayScoreEl = document.getElementById("overlay-score");
  const overlayBtn = document.getElementById("overlay-btn");
  const tapHintEl = document.getElementById("tap-hint");
  const stageWrap = document.querySelector(".stage-wrap");

  let dpr = 1;
  let cssWidth = 0;
  let cssHeight = 0;

  let stack = [];
  let mover = null;
  let debris = [];
  let particles = [];
  let score = 0;
  let best = 0;
  try { best = Number(localStorage.getItem(STORAGE_BEST)) || 0; } catch (e) {}
  let status = "ready";
  let popup = null;
  let rafId = null;

  function resize() {
    const rect = stageWrap.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    cssWidth = rect.width;
    cssHeight = rect.height;
    canvas.width = Math.round(cssWidth * dpr);
    canvas.height = Math.round(cssHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function blockColor(row) {
    const hue = (168 + row * 10) % 360;
    return `hsl(${hue}, 62%, ${row % 2 === 0 ? 58 : 52}%)`;
  }

  function baseWidth() {
    return cssWidth * 0.62;
  }

  function cameraWorldOffset() {
    return Math.max(0, (stack.length - VISIBLE_ROWS) * BLOCK_HEIGHT);
  }

  function screenBottomY(worldTop) {
    const bottomMargin = 28;
    return cssHeight - bottomMargin - (worldTop - cameraWorldOffset());
  }

  function spawnMover() {
    const row = stack.length;
    const prev = stack[stack.length - 1];
    const width = prev.width;
    const fromLeft = row % 2 === 0;
    const speed = Math.min(BASE_SPEED + score * SPEED_GAIN, MAX_SPEED);
    mover = {
      row,
      width,
      x: fromLeft ? -width * 0.4 : cssWidth - width * 0.6,
      dir: fromLeft ? 1 : -1,
      speed,
    };
  }

  function startGame() {
    stack = [{ x: (cssWidth - baseWidth()) / 2, width: baseWidth(), row: 0 }];
    debris = [];
    particles = [];
    score = 0;
    status = "playing";
    popup = null;
    overlayEl.hidden = true;
    tapHintEl.hidden = true;
    updateScore();
    spawnMover();
  }

  function updateScore() {
    scoreEl.textContent = String(score);
    if (score > best) {
      best = score;
      try { localStorage.setItem(STORAGE_BEST, String(best)); } catch (e) {}
    }
    bestEl.textContent = String(best);
  }

  function drop() {
    if (status === "ready") { startGame(); return; }
    if (status === "gameover") { startGame(); return; }
    if (status !== "playing" || !mover) return;

    const below = stack[stack.length - 1];
    const moverLeft = mover.x;
    const moverRight = mover.x + mover.width;
    const belowLeft = below.x;
    const belowRight = below.x + below.width;

    const overlapLeft = Math.max(moverLeft, belowLeft);
    const overlapRight = Math.min(moverRight, belowRight);
    const overlapWidth = overlapRight - overlapLeft;

    if (overlapWidth <= 0) {
      endGame();
      return;
    }

    const isPerfect = Math.abs(overlapWidth - mover.width) <= PERFECT_TOLERANCE
      && Math.abs(overlapWidth - below.width) <= PERFECT_TOLERANCE;

    let placedX = overlapLeft;
    let placedWidth = overlapWidth;

    if (isPerfect) {
      placedX = below.x;
      placedWidth = below.width;
      score += 2;
      popup = { text: "PERFECT", life: 0.7, maxLife: 0.7 };
    } else {
      score += 1;
      if (moverLeft < belowLeft) {
        debris.push(makeDebris(moverLeft, overlapLeft - moverLeft, mover.row));
      } else if (moverRight > belowRight) {
        debris.push(makeDebris(overlapRight, moverRight - overlapRight, mover.row));
      }
    }

    stack.push({ x: placedX, width: placedWidth, row: mover.row });
    spawnBurst(placedX + placedWidth / 2, screenBottomY(mover.row * BLOCK_HEIGHT) - BLOCK_HEIGHT / 2);
    updateScore();
    spawnMover();
  }

  function makeDebris(x, width, row) {
    return {
      x,
      width,
      y: screenBottomY(row * BLOCK_HEIGHT) - BLOCK_HEIGHT,
      vy: 1.5,
      vx: (x + width / 2 < cssWidth / 2 ? -1 : 1) * 1.2,
      rotation: 0,
      vr: (Math.random() - 0.5) * 0.2,
      opacity: 1,
      row,
    };
  }

  function spawnBurst(x, y) {
    for (let i = 0; i < 8; i++) {
      const angle = (Math.PI * 2 * i) / 8;
      particles.push({
        x, y,
        vx: Math.cos(angle) * (1 + Math.random()),
        vy: Math.sin(angle) * (1 + Math.random()) - 1,
        life: 0.4,
        maxLife: 0.4,
      });
    }
  }

  function endGame() {
    status = "gameover";
    mover = null;
    overlayMessageEl.textContent = "ゲームオーバー";
    overlayScoreEl.innerHTML = `SCORE <strong>${score}</strong> &nbsp;/&nbsp; BEST <strong>${best}</strong>`;
    overlayBtn.textContent = "もう一度";
    overlayEl.hidden = false;
  }

  function update(dt) {
    if (status === "playing" && mover) {
      mover.x += mover.dir * mover.speed;
      const minX = -mover.width * 0.5;
      const maxX = cssWidth - mover.width * 0.5;
      if (mover.x <= minX) { mover.x = minX; mover.dir = 1; }
      if (mover.x >= maxX) { mover.x = maxX; mover.dir = -1; }
    }

    for (let i = debris.length - 1; i >= 0; i--) {
      const d = debris[i];
      d.vy += 0.35;
      d.y += d.vy;
      d.x += d.vx;
      d.rotation += d.vr;
      d.opacity -= 0.018;
      if (d.opacity <= 0 || d.y > cssHeight + 60) debris.splice(i, 1);
    }

    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.vy += 0.12;
      p.x += p.vx;
      p.y += p.vy;
      p.life -= dt;
      if (p.life <= 0) particles.splice(i, 1);
    }

    if (popup) {
      popup.life -= dt;
      if (popup.life <= 0) popup = null;
    }
  }

  function drawBlock(x, worldTop, width, row) {
    const bottom = screenBottomY(worldTop);
    const top = bottom - BLOCK_HEIGHT;
    if (bottom < -10 || top > cssHeight + 10) return;
    ctx.fillStyle = blockColor(row);
    ctx.fillRect(x, top, width, BLOCK_HEIGHT);
    ctx.fillStyle = "rgba(255,255,255,0.14)";
    ctx.fillRect(x, top, width, 4);
    ctx.fillStyle = "rgba(0,0,0,0.16)";
    ctx.fillRect(x, bottom - 3, width, 3);
  }

  function render() {
    ctx.clearRect(0, 0, cssWidth, cssHeight);

    for (const block of stack) {
      drawBlock(block.x, block.row * BLOCK_HEIGHT, block.width, block.row);
    }

    for (const d of debris) {
      ctx.save();
      ctx.globalAlpha = Math.max(d.opacity, 0);
      ctx.translate(d.x + d.width / 2, d.y + BLOCK_HEIGHT / 2);
      ctx.rotate(d.rotation);
      ctx.fillStyle = blockColor(d.row);
      ctx.fillRect(-d.width / 2, -BLOCK_HEIGHT / 2, d.width, BLOCK_HEIGHT);
      ctx.restore();
    }

    if (mover && status === "playing") {
      drawBlock(mover.x, mover.row * BLOCK_HEIGHT, mover.width, mover.row);
    }

    for (const p of particles) {
      ctx.globalAlpha = Math.max(p.life / p.maxLife, 0);
      ctx.fillStyle = "#ffcf6b";
      ctx.beginPath();
      ctx.arc(p.x, p.y, 2.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    if (popup) {
      const t = popup.life / popup.maxLife;
      ctx.save();
      ctx.globalAlpha = Math.min(t * 1.6, 1);
      ctx.fillStyle = "#ffcf6b";
      ctx.font = "800 22px 'Zen Maru Gothic', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(popup.text, cssWidth / 2, cssHeight * 0.32 - (1 - t) * 20);
      ctx.restore();
    }
  }

  let lastTime = performance.now();
  function loop(now) {
    const dt = Math.min((now - lastTime) / 1000, 0.05);
    lastTime = now;
    update(dt);
    render();
    rafId = requestAnimationFrame(loop);
  }

  function handleTap(e) {
    e.preventDefault();
    drop();
  }

  stageWrap.addEventListener("touchstart", handleTap, { passive: false });
  stageWrap.addEventListener("mousedown", handleTap);

  window.addEventListener("keydown", (e) => {
    if (e.code === "Space" || e.key === "ArrowUp") {
      e.preventDefault();
      drop();
    }
  });

  overlayBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    startGame();
  });

  window.addEventListener("resize", () => {
    const wasPlaying = status === "playing";
    resize();
    if (!wasPlaying) render();
  });

  resize();
  render();
  rafId = requestAnimationFrame(loop);
})();
