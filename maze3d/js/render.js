// First-person view of the block grid, drawn with a raycaster: one ray per
// screen column, nearest wall wins, sprites afterwards against the depth those
// rays leave behind.
const MazeView = (() => {
  const FOV = (72 * Math.PI) / 180;
  const HALF_FOV_TAN = Math.tan(FOV / 2);
  const WALL_H = 1.6;   // walls are taller than the corridor is wide, as they are in the real thing
  const EYE = 0.8;
  const MAX_COLUMNS = 420;
  const FOG_START = 3.5;
  const FOG_FULL = 18;

  // Textures must not touch Math.random: the tests seed it to reproduce a maze,
  // and drawing the scenery would shift the sequence out from under them.
  function rng(seed) {
    let state = seed >>> 0;
    return () => {
      state = (state * 1664525 + 1013904223) >>> 0;
      return state / 4294967296;
    };
  }

  function makeCanvas(w, h) {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    return c;
  }

  function woodTexture() {
    const W = 128, H = 256, planks = 8;
    const c = makeCanvas(W, H);
    const g = c.getContext("2d");
    const rand = rng(0x5eed);
    const plankH = H / planks;
    for (let i = 0; i < planks; i++) {
      const tone = 96 + Math.floor(rand() * 24);
      g.fillStyle = `rgb(${tone + 32}, ${tone}, ${Math.floor(tone * 0.66)})`;
      g.fillRect(0, i * plankH, W, plankH);
      // grain
      for (let s = 0; s < 40; s++) {
        const y = i * plankH + rand() * plankH;
        g.strokeStyle = `rgba(70, 38, 14, ${0.05 + rand() * 0.1})`;
        g.lineWidth = 1;
        g.beginPath();
        g.moveTo(rand() * W, y);
        g.lineTo(rand() * W, y + (rand() - 0.5) * 2);
        g.stroke();
      }
      g.fillStyle = "rgba(42, 26, 12, 0.6)";
      g.fillRect(0, (i + 1) * plankH - 3, W, 3);
    }
    // upright posts, so corners read as built rather than painted
    for (const x of [3, W - 15]) {
      g.fillStyle = "rgba(86, 58, 30, 0.5)";
      g.fillRect(x, 0, 12, H);
    }
    const shade = g.createLinearGradient(0, 0, 0, H);
    shade.addColorStop(0, "rgba(255, 246, 225, 0.12)");
    shade.addColorStop(0.45, "rgba(0, 0, 0, 0)");
    shade.addColorStop(1, "rgba(18, 12, 4, 0.42)");
    g.fillStyle = shade;
    g.fillRect(0, 0, W, H);
    return c;
  }

  function stampTexture(color) {
    const W = 48, H = 80;
    const c = makeCanvas(W, H);
    const g = c.getContext("2d");
    g.fillStyle = "#7a5230";
    g.fillRect(W / 2 - 4, 28, 8, H - 28);
    g.fillStyle = "#f3ece0";
    g.fillRect(6, 6, W - 12, 30);
    g.fillStyle = color;
    g.fillRect(9, 9, W - 18, 24);
    g.fillStyle = "#f3ece0";
    g.font = "bold 17px sans-serif";
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText("★", W / 2, 22);
    g.strokeStyle = "rgba(40, 24, 10, 0.6)";
    g.lineWidth = 2;
    g.strokeRect(6, 6, W - 12, 30);
    return c;
  }

  function gateTexture(open) {
    const W = 96, H = 96;
    const c = makeCanvas(W, H);
    const g = c.getContext("2d");

    // posts and lintel
    g.fillStyle = open ? "#c9832f" : "#6b5946";
    g.fillRect(4, 12, 13, H - 12);
    g.fillRect(W - 17, 12, 13, H - 12);
    g.fillStyle = open ? "#e8a33f" : "#5d4c3b";
    g.fillRect(0, 4, W, 18);
    g.fillStyle = open ? "#2a1a06" : "#cdc4b7";
    g.font = "bold 15px sans-serif";
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText("ゴール", W / 2, 14);

    if (open) {
      // the way through, lit
      const glow = g.createLinearGradient(0, 22, 0, H);
      glow.addColorStop(0, "rgba(255, 224, 150, 0.30)");
      glow.addColorStop(1, "rgba(255, 224, 150, 0.04)");
      g.fillStyle = glow;
      g.fillRect(17, 22, W - 34, H - 22);
    } else {
      // boarded over, thick enough to read from down the corridor
      for (let i = 0; i < 5; i++) {
        const y = 26 + i * 14;
        g.fillStyle = i % 2 ? "#7a6853" : "#6d5c49";
        g.fillRect(17, y, W - 34, 11);
        g.fillStyle = "rgba(30, 22, 14, 0.45)";
        g.fillRect(17, y + 11, W - 34, 3);
      }
      g.strokeStyle = "rgba(38, 28, 18, 0.7)";
      g.lineWidth = 6;
      g.beginPath();
      g.moveTo(20, 28);
      g.lineTo(W - 20, H - 6);
      g.moveTo(W - 20, 28);
      g.lineTo(20, H - 6);
      g.stroke();
    }
    return c;
  }

  function towerTexture() {
    const W = 64, H = 112;
    const c = makeCanvas(W, H);
    const g = c.getContext("2d");
    g.fillStyle = "#8a6238";
    g.fillRect(10, 20, 8, H - 20);
    g.fillRect(W - 18, 20, 8, H - 20);
    g.fillStyle = "#a07444";
    for (let i = 0; i < 6; i++) g.fillRect(14, 34 + i * 13, W - 28, 5);
    g.fillStyle = "#c08a4e";
    g.fillRect(4, 14, W - 8, 8);
    g.fillStyle = "#3f8f6f";
    g.beginPath();
    g.moveTo(4, 14);
    g.lineTo(W / 2, 0);
    g.lineTo(W - 4, 14);
    g.closePath();
    g.fill();
    return c;
  }

  // A 360-degree strip of hills and trees. Scrolling it with the camera gives
  // the one thing a maze corridor never does: something to take a bearing from.
  function skylineTexture(width, height) {
    const c = makeCanvas(width, height);
    const g = c.getContext("2d");
    const rand = rng(0x1cea);
    const far = g.createLinearGradient(0, 0, 0, height);
    far.addColorStop(0, "#7fa8c9");
    far.addColorStop(1, "#9dbfd8");
    g.fillStyle = far;
    g.fillRect(0, 0, width, height);

    g.fillStyle = "#5f7f96";
    g.beginPath();
    g.moveTo(0, height);
    for (let x = 0; x <= width; x += 40) {
      const peak = height * (0.45 + rand() * 0.4);
      g.lineTo(x, peak);
    }
    g.lineTo(width, height);
    g.closePath();
    g.fill();

    g.fillStyle = "#3f6b52";
    for (let x = -10; x < width + 10; x += 14 + rand() * 16) {
      const treeH = height * (0.30 + rand() * 0.26);
      const treeW = treeH * 0.55;
      g.beginPath();
      g.moveTo(x, height);
      g.lineTo(x + treeW / 2, height - treeH);
      g.lineTo(x + treeW, height);
      g.closePath();
      g.fill();
    }
    return c;
  }

  function create(canvas) {
    const ctx = canvas.getContext("2d", { alpha: false });
    const textures = {
      wall: woodTexture(),
      gateShut: gateTexture(false),
      gateOpen: gateTexture(true),
      tower: towerTexture(),
      stamps: {},
    };
    const state = { w: 0, h: 0, step: 1, columns: 0, depth: null, skyline: null, ringW: 0 };

    function stampTex(color) {
      if (!textures.stamps[color]) textures.stamps[color] = stampTexture(color);
      return textures.stamps[color];
    }

    function resize(cssW, cssH, dpr) {
      canvas.style.width = `${cssW}px`;
      canvas.style.height = `${cssH}px`;
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
      state.w = canvas.width;
      state.h = canvas.height;
      state.step = Math.max(1, Math.ceil(state.w / MAX_COLUMNS));
      state.columns = Math.ceil(state.w / state.step);
      state.depth = new Float32Array(state.columns);
      state.ringW = Math.round((2 * Math.PI * state.w) / FOV);
      state.skyline = skylineTexture(state.ringW, Math.round(state.h * 0.3));
      ctx.imageSmoothingEnabled = true;
    }

    function drawBackground(camera, horizon) {
      const { w, h } = state;
      const sky = ctx.createLinearGradient(0, 0, 0, horizon);
      sky.addColorStop(0, "#3c7fb8");
      sky.addColorStop(1, "#bcd9ea");
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, w, Math.max(0, horizon));

      if (state.skyline) {
        const band = state.skyline.height;
        let offset = -((camera.angle / (2 * Math.PI)) * state.ringW) % state.ringW;
        if (offset > 0) offset -= state.ringW;
        const top = horizon - band;
        ctx.drawImage(state.skyline, offset, top);
        ctx.drawImage(state.skyline, offset + state.ringW, top);
      }

      const ground = ctx.createLinearGradient(0, horizon, 0, h);
      ground.addColorStop(0, "#4a7c45");
      ground.addColorStop(0.35, "#3d6b3a");
      ground.addColorStop(1, "#2c4f2c");
      ctx.fillStyle = ground;
      ctx.fillRect(0, horizon, w, h - horizon);
    }

    function fogAlpha(dist) {
      if (dist <= FOG_START) return 0;
      return Math.min(1, (dist - FOG_START) / (FOG_FULL - FOG_START)) * 0.45;
    }

    function drawWalls(maze, camera, horizon) {
      const { w, h, step, columns, depth } = state;
      const dirX = Math.cos(camera.angle), dirY = Math.sin(camera.angle);
      const planeX = -dirY * HALF_FOV_TAN, planeY = dirX * HALF_FOV_TAN;
      const tex = textures.wall;

      for (let i = 0; i < columns; i++) {
        const x = i * step;
        const cameraX = (2 * (x + step / 2)) / w - 1;
        const rdx = dirX + planeX * cameraX;
        const rdy = dirY + planeY * cameraX;
        const hit = Maze3D.castRay(maze, camera.x, camera.y, rdx, rdy);
        // Distance along the view axis, not to the eye: using the eye distance
        // is what bows straight walls into a fisheye.
        const perp = Math.max(0.0001, hit.dist * (dirX * rdx + dirY * rdy) / (rdx * rdx + rdy * rdy));
        depth[i] = perp;

        // Pixels per world unit: the width spans 2*tan(FOV/2) units at this
        // distance, and pixels are square, so the same scale works vertically.
        const unit = w / (2 * HALF_FOV_TAN * perp);
        const bottom = horizon + EYE * unit;
        const top = bottom - WALL_H * unit;
        const texX = Math.min(tex.width - 1, Math.floor(hit.texX * tex.width));
        ctx.drawImage(tex, texX, 0, 1, tex.height, x, top, step, bottom - top);

        const shade = fogAlpha(perp) + (hit.side === 1 ? 0.18 : 0);
        if (shade > 0.003) {
          ctx.fillStyle = `rgba(178, 205, 226, ${Math.min(0.72, shade)})`;
          ctx.fillRect(x, top, step, bottom - top);
        }
      }
    }

    function drawSprites(sprites, camera, horizon) {
      const { w, h, step, columns, depth } = state;
      const dirX = Math.cos(camera.angle), dirY = Math.sin(camera.angle);
      const planeX = -dirY * HALF_FOV_TAN, planeY = dirX * HALF_FOV_TAN;
      const invDet = 1 / (planeX * dirY - dirX * planeY);

      const ordered = sprites
        .map((s) => ({ s, d: (s.x - camera.x) ** 2 + (s.y - camera.y) ** 2 }))
        .sort((a, b) => b.d - a.d);

      for (const { s } of ordered) {
        const dx = s.x - camera.x, dy = s.y - camera.y;
        const camXs = invDet * (dirY * dx - dirX * dy);
        const depthY = invDet * (-planeY * dx + planeX * dy);
        if (depthY <= 0.12) continue;
        // Walking onto a landmark would otherwise fill the screen with one
        // blown-up slice of it, so it fades out as you close the last step.
        const nearFade = Math.min(1, Math.max(0, (depthY - 0.45) / 0.55));
        if (nearFade <= 0) continue;

        const unit = w / (2 * HALF_FOV_TAN * depthY);
        const screenX = (w / 2) * (1 + camXs / depthY);
        const tex = s.tex;
        const spriteH = s.height * unit;
        const spriteW = spriteH * (tex.width / tex.height);
        const bottom = horizon + EYE * unit;
        const top = bottom - spriteH;
        const left = screenX - spriteW / 2;

        const startX = Math.max(0, Math.floor(left));
        const endX = Math.min(w, Math.ceil(left + spriteW));
        if (endX <= startX) continue;

        // Distance haze: fading the sprite lets the background bleed through,
        // which reads as air between you and it.
        ctx.globalAlpha = (1 - fogAlpha(depthY) * 0.85) * nearFade;

        // Walk the columns, batching the visible ones so a near sprite is a few
        // draws instead of hundreds.
        let runStart = -1;
        for (let x = startX; x <= endX; x++) {
          const visible = x < endX
            && depth[Math.min(columns - 1, Math.floor(x / step))] > depthY;
          if (visible && runStart === -1) runStart = x;
          if (!visible && runStart !== -1) {
            const u0 = ((runStart - left) / spriteW) * tex.width;
            const u1 = ((x - left) / spriteW) * tex.width;
            ctx.drawImage(tex, u0, 0, Math.max(0.5, u1 - u0), tex.height,
              runStart, top, x - runStart, spriteH);
            runStart = -1;
          }
        }
        ctx.globalAlpha = 1;

      }
    }

    // A compass is the only instrument in here, and it is what makes the view
    // from a tower worth memorising.
    function drawCompass(camera) {
      const { w, h } = state;
      const scale = h / 220;
      const barH = 22 * scale;
      ctx.fillStyle = "rgba(14, 22, 32, 0.45)";
      ctx.fillRect(0, 0, w, barH);
      ctx.font = `bold ${Math.round(12 * scale)}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const marks = [["北", -Math.PI / 2], ["東", 0], ["南", Math.PI / 2], ["西", Math.PI]];
      for (const [label, angle] of marks) {
        let rel = angle - camera.angle;
        while (rel > Math.PI) rel -= 2 * Math.PI;
        while (rel < -Math.PI) rel += 2 * Math.PI;
        if (Math.abs(rel) > FOV / 2) continue;
        const x = (w / 2) * (1 + Math.tan(rel) / HALF_FOV_TAN);
        ctx.fillStyle = label === "北" ? "#ffd166" : "rgba(255,255,255,0.8)";
        ctx.fillText(label, x, barH / 2);
      }
      ctx.fillStyle = "rgba(255,255,255,0.55)";
      ctx.fillRect(w / 2 - 1, barH, 2, 5 * scale);
    }

    function draw(scene) {
      const { maze, camera, sprites } = scene;
      const horizon = state.h / 2 + (camera.bob || 0) * state.h;
      drawBackground(camera, horizon);
      drawWalls(maze, camera, horizon);
      drawSprites(sprites, camera, horizon);
      drawCompass(camera);
    }

    return { resize, draw, textures, stampTex, state };
  }

  return { create, FOV, WALL_H, EYE };
})();

if (typeof window !== "undefined") window.MazeView = MazeView;
