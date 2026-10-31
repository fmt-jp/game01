(() => {
  const STORAGE_LEVEL = "rhythm-level";
  const STORAGE_OFFSET = "rhythm-offset";
  const PERFECT = 0.06;        // seconds either side
  const GOOD = 0.13;
  const APPROACH = 1.35;       // seconds a note is visible before the line
  const LANES = Song.LANES;

  const canvas = document.getElementById("stage");
  const ctx = canvas.getContext("2d");
  const stageWrap = document.querySelector(".stage-wrap");
  const levelEl = document.getElementById("level");
  const comboEl = document.getElementById("combo");
  const accuracyEl = document.getElementById("accuracy");
  const judgeEl = document.getElementById("judge");
  const overlayEl = document.getElementById("overlay");
  const overlayMessageEl = document.getElementById("overlay-message");
  const overlaySubEl = document.getElementById("overlay-sub");
  const overlayBtn = document.getElementById("overlay-btn");
  const offsetValueEl = document.getElementById("offset-value");

  let level = 1;
  let offsetMs = 0;
  let offsetTouched = false;
  try {
    level = Math.max(1, Number(localStorage.getItem(STORAGE_LEVEL)) || 1);
    const saved = localStorage.getItem(STORAGE_OFFSET);
    if (saved !== null) { offsetMs = Number(saved) || 0; offsetTouched = true; }
  } catch (e) {}

  let audio = null;
  let song = null;
  let notes = [];
  let state = "idle";          // idle | playing | done
  let tally = { perfect: 0, good: 0, miss: 0 };
  let combo = 0, bestCombo = 0, score = 0;
  let laneFlash = new Array(LANES).fill(0);
  let autoplay = false;
  let width = 0, height = 0, lineY = 0;

  // ---------- judging, kept pure so it can be checked on its own ----------

  function grade(diff) {
    const d = Math.abs(diff);
    if (d <= PERFECT) return "perfect";
    if (d <= GOOD) return "good";
    return null;
  }

  function position() {
    return audio ? audio.position() - offsetMs / 1000 : 0;
  }

  function accuracy() {
    const total = tally.perfect + tally.good + tally.miss;
    if (total === 0) return null;
    return (tally.perfect + tally.good * 0.6) / total;
  }

  function updateHud() {
    levelEl.textContent = String(level);
    comboEl.textContent = String(combo);
    const acc = accuracy();
    accuracyEl.textContent = acc === null ? "--%" : `${Math.round(acc * 100)}%`;
    offsetValueEl.textContent = `${offsetMs > 0 ? "+" : ""}${offsetMs}ms`;
  }

  function flashJudge(kind) {
    judgeEl.textContent = { perfect: "PERFECT", good: "GOOD", miss: "MISS" }[kind];
    judgeEl.className = `judge ${kind}`;
    void judgeEl.offsetWidth;
    judgeEl.classList.add("show");
  }

  function tapLane(lane) {
    if (state !== "playing") return null;
    const at = position();
    let best = null, bestDiff = Infinity;
    for (const note of notes) {
      if (note.judged || note.lane !== lane) continue;
      const diff = note.time - at;
      if (Math.abs(diff) < Math.abs(bestDiff)) { bestDiff = diff; best = note; }
    }
    laneFlash[lane] = 1;
    const kind = best ? grade(bestDiff) : null;
    if (!best || !kind) return null;      // a tap with nothing near it is ignored
    best.judged = kind;
    tally[kind] += 1;
    combo += 1;
    bestCombo = Math.max(bestCombo, combo);
    score += kind === "perfect" ? 100 + Math.min(combo, 60) : 50;
    audio.hit(best.midi, kind === "perfect" ? 1 : 0.75);
    flashJudge(kind);
    updateHud();
    return kind;
  }

  function sweepMisses(at) {
    for (const note of notes) {
      if (note.judged || note.time + GOOD >= at) continue;
      note.judged = "miss";
      tally.miss += 1;
      combo = 0;
      flashJudge("miss");
      updateHud();
    }
  }

  // ---------- drawing ----------

  function sizeStage() {
    const rect = stageWrap.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = rect.width;
    height = Math.round(Math.min(window.innerHeight * 0.46, 420));
    canvas.style.height = `${height}px`;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    lineY = height - 72;
  }

  function render() {
    const at = position();
    const laneWidth = width / LANES;
    const pxPerSecond = lineY / APPROACH;

    ctx.clearRect(0, 0, width, height);

    for (let lane = 0; lane < LANES; lane++) {
      const x = lane * laneWidth;
      ctx.fillStyle = lane % 2 ? "rgba(236, 234, 248, 0.035)" : "rgba(236, 234, 248, 0.015)";
      ctx.fillRect(x, 0, laneWidth, height);
      if (laneFlash[lane] > 0) {
        ctx.fillStyle = `rgba(129, 140, 248, ${0.26 * laneFlash[lane]})`;
        ctx.fillRect(x, 0, laneWidth, height);
        laneFlash[lane] = Math.max(0, laneFlash[lane] - 0.08);
      }
      ctx.strokeStyle = "rgba(236, 234, 248, 0.08)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x + 0.5, 0);
      ctx.lineTo(x + 0.5, height);
      ctx.stroke();
    }

    // the line you play on
    ctx.strokeStyle = "rgba(129, 140, 248, 0.85)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, lineY);
    ctx.lineTo(width, lineY);
    ctx.stroke();
    for (let lane = 0; lane < LANES; lane++) {
      ctx.strokeStyle = "rgba(129, 140, 248, 0.35)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(lane * laneWidth + laneWidth / 2, lineY, 20, 0, Math.PI * 2);
      ctx.stroke();
    }

    for (const note of notes) {
      if (note.judged && note.judged !== "miss") continue;
      const dt = note.time - at;
      if (dt > APPROACH || dt < -0.35) continue;
      const y = lineY - dt * pxPerSecond;
      const cx = note.lane * laneWidth + laneWidth / 2;
      const radius = Math.min(22, laneWidth * 0.3);
      ctx.globalAlpha = note.judged === "miss" ? 0.25 : 1;
      const grad = ctx.createRadialGradient(cx - radius * 0.3, y - radius * 0.35, radius * 0.1,
                                            cx, y, radius);
      grad.addColorStop(0, "#c7ccff");
      grad.addColorStop(1, "#6b76e8");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, y, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    if (state === "playing" && at < 0) {
      ctx.fillStyle = "rgba(236, 234, 248, 0.75)";
      ctx.font = "700 28px " + getComputedStyle(document.body).fontFamily;
      ctx.textAlign = "center";
      ctx.fillText(String(Math.ceil(-at)), width / 2, height / 2);
    }
  }

  function loop() {
    if (state === "playing") {
      const at = position();
      if (autoplay) {
        for (const note of notes) {
          if (!note.judged && note.time <= at) tapLane(note.lane);
        }
      }
      sweepMisses(at);
      if (at > song.length + 1.2) finish();
    }
    render();
    requestAnimationFrame(loop);
  }

  // ---------- flow ----------

  function finish() {
    state = "done";
    audio.stop();
    const acc = accuracy() || 0;
    const rank = acc >= 0.95 ? "S" : acc >= 0.88 ? "A" : acc >= 0.75 ? "B" : "C";
    const cleared = acc >= 0.85;
    overlayMessageEl.textContent = `${rank}　${Math.round(acc * 100)}%`;
    overlaySubEl.innerHTML =
      `PERFECT ${tally.perfect} ／ GOOD ${tally.good} ／ MISS ${tally.miss}<br>` +
      `最大コンボ ${bestCombo}　スコア ${score}` +
      (cleared ? "<br>クリア！つぎのレベルへ" : "<br>せいど85%でクリアです");
    overlayBtn.textContent = cleared ? "つぎのレベル" : "もういちど";
    overlayEl.hidden = false;
    if (cleared) {
      level += 1;
      try { localStorage.setItem(STORAGE_LEVEL, String(level)); } catch (e) {}
    }
    updateHud();
  }

  async function startRound() {
    if (!audio) {
      audio = RhythmAudio.create();
      if (!offsetTouched) {
        offsetMs = Math.round(audio.latency() * 1000);
        offsetTouched = true;
      }
    }
    await audio.unlock();
    song = Song.generate(level);
    notes = song.notes.map((n) => ({ ...n, judged: null }));
    tally = { perfect: 0, good: 0, miss: 0 };
    combo = 0; bestCombo = 0; score = 0;
    state = "playing";
    overlayEl.hidden = true;
    sizeStage();
    audio.start(song);
    updateHud();
  }

  // ---------- input ----------

  canvas.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const lane = Math.max(0, Math.min(LANES - 1,
      Math.floor(((event.clientX - rect.left) / rect.width) * LANES)));
    tapLane(lane);
  });

  window.addEventListener("keydown", (event) => {
    const lane = { KeyA: 0, KeyS: 1, KeyD: 2, ArrowLeft: 0, ArrowDown: 1, ArrowRight: 2 }[event.code];
    if (lane === undefined) return;
    event.preventDefault();
    tapLane(lane);
  });

  overlayBtn.addEventListener("click", startRound);

  function setOffset(ms) {
    offsetMs = Math.max(-250, Math.min(250, ms));
    offsetTouched = true;
    try { localStorage.setItem(STORAGE_OFFSET, String(offsetMs)); } catch (e) {}
    updateHud();
  }
  document.getElementById("offset-down").addEventListener("click", () => setOffset(offsetMs - 5));
  document.getElementById("offset-up").addEventListener("click", () => setOffset(offsetMs + 5));
  document.getElementById("offset-auto").addEventListener("click", () => {
    if (!audio) audio = RhythmAudio.create();
    setOffset(Math.round(audio.latency() * 1000));
  });

  window.addEventListener("resize", sizeStage);

  // Read-only snapshot and a few handles for the automated checks.
  window.__rhythm = () => ({
    state, level, offsetMs, combo, bestCombo, score, tally,
    accuracy: accuracy(), position: position(),
    audioTime: audio ? audio.now() : null,
    songStart: audio ? audio.songStart() : null,
    length: song ? song.length : null,
    notes: notes.map((n) => ({ time: n.time, lane: n.lane, midi: n.midi, judged: n.judged })),
    scheduled: audio ? audio.scheduled.slice() : [],
  });
  window.__grade = grade;
  window.__tapLane = tapLane;
  window.__autoplay = (on) => { autoplay = on; };
  window.__windows = { PERFECT, GOOD, APPROACH };

  sizeStage();
  updateHud();
  requestAnimationFrame(loop);
})();
