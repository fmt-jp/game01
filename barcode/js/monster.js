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

    const spikeCount = hashDigits(digits, 53) % 4;
    const eyeCount = 1 + (hashDigits(digits, 59) % 2);
    const bodyShape = hashDigits(digits, 61) % 3; // 0: round, 1: squarish, 2: tall

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
      visual: { spikeCount, eyeCount, bodyShape },
    };
  }

  function randomCode() {
    let code = "";
    for (let i = 0; i < 13; i++) code += Math.floor(Math.random() * 10);
    return code;
  }

  function draw(canvas, monster) {
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const size = canvas.clientWidth || 96;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);

    const { spikeCount, eyeCount, bodyShape } = monster.visual;
    const cx = size / 2;
    const cy = size / 2 + size * 0.06;
    const r = size * 0.34;

    ctx.fillStyle = monster.color;

    ctx.beginPath();
    if (bodyShape === 0) {
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
    } else if (bodyShape === 1) {
      const s = r * 1.15;
      ctx.moveTo(cx - s, cy - s * 0.7);
      ctx.lineTo(cx + s, cy - s * 0.7);
      ctx.lineTo(cx + s, cy + s);
      ctx.lineTo(cx - s, cy + s);
      ctx.closePath();
    } else {
      ctx.ellipse(cx, cy, r * 0.8, r * 1.25, 0, 0, Math.PI * 2);
    }
    ctx.fill();

    for (let i = 0; i < spikeCount; i++) {
      const angle = (-Math.PI / 2) + (i - (spikeCount - 1) / 2) * 0.5;
      const bx = cx + Math.cos(angle) * r * 0.7;
      const by = cy + Math.sin(angle) * r * 0.7;
      const tx = cx + Math.cos(angle) * r * 1.5;
      const ty = cy + Math.sin(angle) * r * 1.5;
      ctx.beginPath();
      ctx.moveTo(bx - 5, by);
      ctx.lineTo(tx, ty);
      ctx.lineTo(bx + 5, by);
      ctx.closePath();
      ctx.fill();
    }

    const eyeY = cy - r * 0.15;
    const eyeSpacing = eyeCount === 2 ? r * 0.4 : 0;
    for (let i = 0; i < eyeCount; i++) {
      const ex = cx + (i - (eyeCount - 1) / 2) * eyeSpacing * 2;
      ctx.beginPath();
      ctx.arc(ex, eyeY, r * 0.18, 0, Math.PI * 2);
      ctx.fillStyle = "#fff";
      ctx.fill();
      ctx.beginPath();
      ctx.arc(ex, eyeY + r * 0.03, r * 0.09, 0, Math.PI * 2);
      ctx.fillStyle = "#1c1114";
      ctx.fill();
    }
  }

  return { fromCode, randomCode, draw, TYPES };
})();
