const MonsterGen = (() => {
  const TYPES = [
    { name: "ほのお", color: "#ff6b4a" },
    { name: "みず", color: "#4aa8ff" },
    { name: "くさ", color: "#5ad16f" },
    { name: "でんき", color: "#ffd23f" },
    { name: "こおり", color: "#7fe3ff" },
    { name: "やみ", color: "#8a5cff" },
    { name: "はがね", color: "#b9c2cc" },
    { name: "だいち", color: "#c98a4b" },
  ];

  const SYLLABLES = [
    "ガ", "ロ", "ビ", "ネ", "ズ", "ラ", "ト", "ムン", "キ", "ダ",
    "ペ", "ソ", "ワ", "ジ", "ク", "メ", "ル", "ヴォ", "チ", "パ",
    "ボ", "ニ", "ザ", "フォ", "レ",
  ];

  function hashDigits(digits, seed) {
    let h = seed >>> 0;
    for (const d of digits) {
      h = (h * 31 + d) >>> 0;
      h = h % 1000003;
    }
    return h;
  }

  function fromCode(code) {
    const digits = [...code].map((ch) => Number(ch)).filter((n) => !Number.isNaN(n));
    if (digits.length === 0) digits.push(0);

    const hp = 60 + (hashDigits(digits, 7) % 121);
    const atk = 15 + (hashDigits(digits, 13) % 46);
    const def = 10 + (hashDigits(digits, 17) % 41);
    const spd = 5 + (hashDigits(digits, 23) % 31);
    const typeIndex = hashDigits(digits, 29) % TYPES.length;
    const type = TYPES[typeIndex];

    const nameLength = 3 + (hashDigits(digits, 37) % 2);
    let name = "";
    for (let i = 0; i < nameLength; i++) {
      const idx = hashDigits(digits, 41 + i * 5) % SYLLABLES.length;
      name += SYLLABLES[idx];
    }

    return {
      code,
      name,
      type: type.name,
      color: type.color,
      hp,
      maxHp: hp,
      atk,
      def,
      spd,
      visual: {
        spikeCount: hashDigits(digits, 53) % 4,
        eyeCount: 1 + (hashDigits(digits, 59) % 2),
        bodyShape: hashDigits(digits, 61) % 3,   // 0 round, 1 boxy, 2 tall
        hornType: hashDigits(digits, 67) % 3,    // 0 none, 1 horns, 2 antennae
        mouthType: hashDigits(digits, 71) % 3,   // 0 smile, 1 fangs, 2 straight
        pattern: hashDigits(digits, 73) % 3,     // 0 none, 1 belly, 2 spots
      },
    };
  }

  function randomCode() {
    let code = "";
    for (let i = 0; i < 13; i++) code += Math.floor(Math.random() * 10);
    return code;
  }

  // ---------- colour helpers ----------

  function toRgb(hex) {
    const v = hex.replace("#", "");
    return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
  }

  function mix(color, target, t) {
    const [r, g, b] = toRgb(color);
    return `rgb(${Math.round(r + (target[0] - r) * t)}, ${Math.round(g + (target[1] - g) * t)}, ${Math.round(b + (target[2] - b) * t)})`;
  }

  const tint = (color, t) => mix(color, [255, 255, 255], t);
  const shade = (color, t) => mix(color, [16, 10, 14], t);

  // Older saved entries were stored before some of these traits existed, so the
  // look is derived from the barcode itself rather than from what was saved.
  function visualOf(monster) {
    if (monster && typeof monster.code === "string" && monster.code.length) {
      return fromCode(monster.code).visual;
    }
    return Object.assign(
      { spikeCount: 0, eyeCount: 2, bodyShape: 0, hornType: 0, mouthType: 0, pattern: 0 },
      (monster && monster.visual) || {}
    );
  }

  function bodyPath(shape, cx, cy, r) {
    const path = new Path2D();
    if (shape === 0) {
      path.ellipse(cx, cy, r * 1.02, r * 0.94, 0, 0, Math.PI * 2);
    } else if (shape === 1) {
      const w = r * 0.96, h = r * 0.9, k = r * 0.3;
      path.moveTo(cx - w + k, cy - h);
      path.lineTo(cx + w - k, cy - h);
      path.quadraticCurveTo(cx + w, cy - h, cx + w, cy - h + k);
      path.lineTo(cx + w, cy + h - k);
      path.quadraticCurveTo(cx + w, cy + h, cx + w - k, cy + h);
      path.lineTo(cx - w + k, cy + h);
      path.quadraticCurveTo(cx - w, cy + h, cx - w, cy + h - k);
      path.lineTo(cx - w, cy - h + k);
      path.quadraticCurveTo(cx - w, cy - h, cx - w + k, cy - h);
    } else {
      path.ellipse(cx, cy, r * 0.78, r * 1.12, 0, 0, Math.PI * 2);
    }
    path.closePath();
    return path;
  }

  function draw(canvas, monster) {
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const size = canvas.clientWidth || 96;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);

    const v = visualOf(monster);
    const base = monster.color || "#888888";
    const cx = size / 2;
    // Sized so the tallest body with the longest antennae still fits, and the
    // shadow underneath it does not run off the bottom.
    const cy = size * 0.54;
    const r = size * 0.28;
    const body = bodyPath(v.bodyShape, cx, cy, r);
    const half = v.bodyShape === 2 ? r * 1.12 : v.bodyShape === 1 ? r * 0.9 : r * 0.94;

    // the shadow it casts, which is what seats it on the ground
    const floor = cy + half + size * 0.035;
    ctx.save();
    ctx.scale(1, 0.32);
    // The gradient is painted in the space in force when it is used, so it has
    // to be built inside the squash, not before it.
    const flat = floor / 0.32;
    const shadow = ctx.createRadialGradient(cx, flat, size * 0.02, cx, flat, r * 1.05);
    shadow.addColorStop(0, "rgba(0, 0, 0, 0.45)");
    shadow.addColorStop(0.6, "rgba(0, 0, 0, 0.22)");
    shadow.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = shadow;
    ctx.beginPath();
    ctx.arc(cx, flat, r * 1.05, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // feet, tucked behind the body so the silhouette stays readable
    ctx.fillStyle = shade(base, 0.42);
    for (const dx of [-r * 0.5, r * 0.5]) {
      ctx.beginPath();
      ctx.ellipse(cx + dx, cy + half * 0.92, r * 0.3, r * 0.19, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    // horns and spikes, also behind
    if (v.hornType === 1) {
      ctx.fillStyle = tint(base, 0.55);
      for (const dir of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(cx + dir * r * 0.5, cy - half * 0.72);
        ctx.quadraticCurveTo(cx + dir * r * 0.95, cy - half * 1.5, cx + dir * r * 0.5, cy - half * 1.28);
        ctx.closePath();
        ctx.fill();
      }
    } else if (v.hornType === 2) {
      ctx.strokeStyle = shade(base, 0.25);
      ctx.lineWidth = Math.max(1.4, r * 0.09);
      ctx.lineCap = "round";
      for (const dir of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(cx + dir * r * 0.32, cy - half * 0.82);
        ctx.quadraticCurveTo(cx + dir * r * 0.62, cy - half * 1.32, cx + dir * r * 0.42, cy - half * 1.42);
        ctx.stroke();
        ctx.fillStyle = tint(base, 0.6);
        ctx.beginPath();
        ctx.arc(cx + dir * r * 0.42, cy - half * 1.45, r * 0.11, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    for (let i = 0; i < v.spikeCount; i++) {
      const angle = -Math.PI / 2 + (i - (v.spikeCount - 1) / 2) * 0.55;
      const bx = cx + Math.cos(angle) * r * 0.75;
      const by = cy + Math.sin(angle) * half * 0.75;
      const tx = cx + Math.cos(angle) * r * 1.35;
      const ty = cy + Math.sin(angle) * half * 1.42;
      const spike = ctx.createLinearGradient(bx, by, tx, ty);
      spike.addColorStop(0, shade(base, 0.35));
      spike.addColorStop(1, tint(base, 0.45));
      ctx.fillStyle = spike;
      ctx.beginPath();
      ctx.moveTo(bx - r * 0.16, by);
      ctx.lineTo(tx, ty);
      ctx.lineTo(bx + r * 0.16, by);
      ctx.closePath();
      ctx.fill();
    }

    // the body: lit from the upper left, dark towards the far edge
    const lit = ctx.createRadialGradient(
      cx - r * 0.4, cy - half * 0.5, r * 0.08,
      cx, cy, Math.max(r, half) * 1.5
    );
    lit.addColorStop(0, tint(base, 0.52));
    lit.addColorStop(0.42, base);
    lit.addColorStop(1, shade(base, 0.5));
    ctx.fillStyle = lit;
    ctx.fill(body);

    ctx.save();
    ctx.clip(body);

    // contact shadow where the body meets the ground
    const occ = ctx.createLinearGradient(0, cy + half * 0.1, 0, cy + half);
    occ.addColorStop(0, "rgba(0, 0, 0, 0)");
    occ.addColorStop(1, "rgba(0, 0, 0, 0.35)");
    ctx.fillStyle = occ;
    ctx.fillRect(cx - r * 1.4, cy - half, r * 2.8, half * 2);

    // bounce light along the lower right edge: the same outline, nudged up and
    // left, so only the far rim of it survives the clip
    ctx.save();
    ctx.translate(-r * 0.09, -r * 0.1);
    ctx.lineWidth = r * 0.22;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.20)";
    ctx.stroke(body);
    ctx.restore();

    if (v.pattern === 1) {
      ctx.fillStyle = tint(base, 0.42);
      ctx.globalAlpha = 0.85;
      ctx.beginPath();
      ctx.ellipse(cx, cy + half * 0.3, r * 0.52, half * 0.5, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    } else if (v.pattern === 2) {
      ctx.fillStyle = shade(base, 0.3);
      for (const [dx, dy, rad] of [[-0.55, 0.42, 0.2], [0.5, 0.2, 0.15], [0.1, 0.62, 0.17]]) {
        ctx.beginPath();
        ctx.ellipse(cx + r * dx, cy + half * dy, r * rad, r * rad * 0.85, 0, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // specular highlight
    ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
    ctx.beginPath();
    ctx.ellipse(cx - r * 0.42, cy - half * 0.52, r * 0.24, r * 0.15, -0.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.strokeStyle = shade(base, 0.62);
    ctx.lineWidth = Math.max(1, size * 0.018);
    ctx.stroke(body);

    // eyes: a lit sphere rather than a flat disc
    const eyeY = cy - half * 0.18;
    const eyeR = r * (v.eyeCount === 1 ? 0.28 : 0.22);
    const spacing = v.eyeCount === 2 ? r * 0.38 : 0;
    for (let i = 0; i < v.eyeCount; i++) {
      const ex = cx + (i - (v.eyeCount - 1) / 2) * spacing * 2;
      const ball = ctx.createRadialGradient(ex - eyeR * 0.3, eyeY - eyeR * 0.35, eyeR * 0.1, ex, eyeY, eyeR);
      ball.addColorStop(0, "#ffffff");
      ball.addColorStop(1, "#c3ccd8");
      ctx.fillStyle = ball;
      ctx.beginPath();
      ctx.arc(ex, eyeY, eyeR, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "rgba(20, 12, 16, 0.35)";
      ctx.lineWidth = Math.max(0.7, size * 0.008);
      ctx.stroke();

      ctx.fillStyle = "#1c1114";
      ctx.beginPath();
      ctx.arc(ex + eyeR * 0.08, eyeY + eyeR * 0.12, eyeR * 0.48, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "rgba(255, 255, 255, 0.92)";
      ctx.beginPath();
      ctx.arc(ex - eyeR * 0.18, eyeY - eyeR * 0.25, eyeR * 0.2, 0, Math.PI * 2);
      ctx.fill();
    }

    const mouthY = cy + half * 0.34;
    ctx.strokeStyle = shade(base, 0.68);
    ctx.lineWidth = Math.max(1.1, r * 0.075);
    ctx.lineCap = "round";
    if (v.mouthType === 0) {
      ctx.beginPath();
      ctx.arc(cx, mouthY - r * 0.16, r * 0.3, 0.32 * Math.PI, 0.68 * Math.PI);
      ctx.stroke();
    } else if (v.mouthType === 1) {
      ctx.fillStyle = shade(base, 0.72);
      ctx.beginPath();
      ctx.ellipse(cx, mouthY, r * 0.3, r * 0.17, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#fff8f2";
      for (const dx of [-0.16, 0.16]) {
        ctx.beginPath();
        ctx.moveTo(cx + r * dx - r * 0.07, mouthY - r * 0.14);
        ctx.lineTo(cx + r * dx, mouthY + r * 0.06);
        ctx.lineTo(cx + r * dx + r * 0.07, mouthY - r * 0.14);
        ctx.closePath();
        ctx.fill();
      }
    } else {
      ctx.beginPath();
      ctx.moveTo(cx - r * 0.22, mouthY);
      ctx.lineTo(cx + r * 0.22, mouthY);
      ctx.stroke();
    }
  }

  return { fromCode, randomCode, draw, visualOf, TYPES };
})();
