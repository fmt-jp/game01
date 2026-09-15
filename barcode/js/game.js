(() => {
  const STORAGE_DEX = "barcode-monster-dex";
  const MAX_DEX = 30;

  const screens = {
    home: document.getElementById("screen-home"),
    scan: document.getElementById("screen-scan"),
    result: document.getElementById("screen-result"),
    battle: document.getElementById("screen-battle"),
  };

  const scanMainBtn = document.getElementById("scan-main-btn");
  const scanCancelBtn = document.getElementById("scan-cancel-btn");
  const scanVideo = document.getElementById("scan-video");
  const scanStatus = document.getElementById("scan-status");

  const resultCard = document.getElementById("result-card");
  const battleRandomBtn = document.getElementById("battle-random-btn");
  const battleScanBtn = document.getElementById("battle-scan-btn");
  const resultBackBtn = document.getElementById("result-back-btn");

  const fighterAEl = document.getElementById("fighter-a");
  const fighterBEl = document.getElementById("fighter-b");
  const battleLogEl = document.getElementById("battle-log");
  const battleResultEl = document.getElementById("battle-result");
  const battleAgainBtn = document.getElementById("battle-again-btn");

  const dexWrap = document.getElementById("dex-wrap");
  const dexList = document.getElementById("dex-list");
  const dexCount = document.getElementById("dex-count");

  let currentMonster = null;
  let mediaStream = null;
  let zxingReader = null;
  let detectRAF = null;
  let scanMode = "new"; // "new" | "opponent"

  function showScreen(name) {
    for (const key in screens) {
      screens[key].hidden = key !== name;
    }
  }

  function loadDex() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_DEX) || "[]");
    } catch (e) {
      return [];
    }
  }

  function saveDex(list) {
    try {
      localStorage.setItem(STORAGE_DEX, JSON.stringify(list.slice(0, MAX_DEX)));
    } catch (e) {}
  }

  function addToDex(monster) {
    const list = loadDex();
    const existingIdx = list.findIndex((m) => m.code === monster.code);
    if (existingIdx !== -1) list.splice(existingIdx, 1);
    list.unshift({
      code: monster.code, name: monster.name, type: monster.type, color: monster.color,
      hp: monster.maxHp, atk: monster.atk, def: monster.def, spd: monster.spd, visual: monster.visual,
    });
    saveDex(list);
    renderDex();
  }

  function renderDex() {
    const list = loadDex();
    dexWrap.hidden = list.length === 0;
    dexCount.textContent = list.length ? `(${list.length})` : "";
    dexList.innerHTML = "";
    for (const m of list) {
      const item = document.createElement("div");
      item.className = "dex-item";
      const canvas = document.createElement("canvas");
      item.appendChild(canvas);
      const name = document.createElement("div");
      name.className = "dex-name";
      name.textContent = m.name;
      item.appendChild(name);
      const type = document.createElement("div");
      type.className = "dex-type";
      type.textContent = m.type;
      item.appendChild(type);
      dexList.appendChild(item);
      requestAnimationFrame(() => MonsterGen.draw(canvas, { ...m, maxHp: m.hp }));
    }
  }

  function renderMonsterCard(container, monster) {
    container.innerHTML = "";
    const canvas = document.createElement("canvas");
    container.appendChild(canvas);

    const name = document.createElement("div");
    name.className = "m-name";
    name.textContent = monster.name;
    container.appendChild(name);

    const type = document.createElement("div");
    type.className = "m-type";
    type.textContent = monster.type + "タイプ";
    container.appendChild(type);

    const code = document.createElement("div");
    code.className = "m-code";
    code.textContent = monster.code;
    container.appendChild(code);

    const stats = document.createElement("div");
    stats.className = "m-stats";
    const statDefs = [
      ["HP", monster.hp ?? monster.maxHp, 180],
      ["こうげき", monster.atk, 60],
      ["ぼうぎょ", monster.def, 50],
      ["すばやさ", monster.spd, 35],
    ];
    for (const [label, value, max] of statDefs) {
      const row = document.createElement("div");
      row.className = "stat-row";
      const l = document.createElement("span");
      l.className = "stat-label";
      l.textContent = label;
      const bar = document.createElement("div");
      bar.className = "stat-bar";
      const fill = document.createElement("span");
      fill.style.width = `${Math.min(100, (value / max) * 100)}%`;
      bar.appendChild(fill);
      const v = document.createElement("span");
      v.className = "stat-value";
      v.textContent = value;
      row.appendChild(l);
      row.appendChild(bar);
      row.appendChild(v);
      stats.appendChild(row);
    }
    container.appendChild(stats);

    requestAnimationFrame(() => MonsterGen.draw(canvas, monster));
  }

  // ---------- Scanning ----------

  async function startScan(mode) {
    scanMode = mode;
    showScreen("scan");
    scanStatus.textContent = "カメラを起動しています…";

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
    } catch (e) {
      scanStatus.textContent = "カメラを使用できませんでした。権限を確認してください。";
      return;
    }

    scanVideo.srcObject = mediaStream;
    await scanVideo.play();
    scanStatus.textContent = "バーコードを枠内に写してください";

    if ("BarcodeDetector" in window) {
      startNativeDetection();
    } else {
      startZXingDetection();
    }
  }

  function startNativeDetection() {
    const detector = new BarcodeDetector({
      formats: ["ean_13", "ean_8", "upc_a", "upc_e"],
    });
    const tick = async () => {
      if (!mediaStream) return;
      try {
        const codes = await detector.detect(scanVideo);
        if (codes.length > 0) {
          onCodeDetected(codes[0].rawValue);
          return;
        }
      } catch (e) {
        // ignore transient detection errors
      }
      detectRAF = requestAnimationFrame(tick);
    };
    detectRAF = requestAnimationFrame(tick);
  }

  function startZXingDetection() {
    if (typeof ZXing === "undefined") {
      scanStatus.textContent = "バーコード読み取り機能を読み込めませんでした。通信環境を確認してください。";
      return;
    }
    const hints = new Map();
    const formats = [
      ZXing.BarcodeFormat.EAN_13,
      ZXing.BarcodeFormat.EAN_8,
      ZXing.BarcodeFormat.UPC_A,
      ZXing.BarcodeFormat.UPC_E,
    ];
    hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, formats);
    zxingReader = new ZXing.BrowserMultiFormatReader(hints);
    zxingReader.decodeFromVideoElement(scanVideo, (result, err) => {
      if (result) {
        onCodeDetected(result.getText());
      }
    });
  }

  function stopScan() {
    if (detectRAF) {
      cancelAnimationFrame(detectRAF);
      detectRAF = null;
    }
    if (zxingReader) {
      try { zxingReader.reset(); } catch (e) {}
      zxingReader = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
      mediaStream = null;
    }
    scanVideo.srcObject = null;
  }

  function onCodeDetected(code) {
    stopScan();
    const monster = MonsterGen.fromCode(code);
    if (scanMode === "new") {
      currentMonster = monster;
      addToDex(monster);
      renderMonsterCard(resultCard, monster);
      showScreen("result");
    } else if (scanMode === "opponent") {
      const opponent = monster;
      addToDex(opponent);
      startBattle(currentMonster, opponent);
    }
  }

  scanMainBtn.addEventListener("click", () => startScan("new"));
  battleScanBtn.addEventListener("click", () => startScan("opponent"));
  scanCancelBtn.addEventListener("click", () => {
    stopScan();
    showScreen(currentMonster ? "result" : "home");
  });

  battleRandomBtn.addEventListener("click", () => {
    const rndCode = MonsterGen.randomCode();
    const opponent = MonsterGen.fromCode(rndCode);
    startBattle(currentMonster, opponent);
  });

  resultBackBtn.addEventListener("click", () => {
    showScreen("home");
    renderDex();
  });

  battleAgainBtn.addEventListener("click", () => {
    showScreen("home");
    renderDex();
  });

  // ---------- Battle ----------

  function startBattle(a, b) {
    const fighterA = { ...a, hp: a.maxHp ?? a.hp };
    const fighterB = { ...b, hp: b.maxHp ?? b.hp };
    showScreen("battle");
    battleLogEl.innerHTML = "";
    battleResultEl.hidden = true;
    battleAgainBtn.hidden = true;

    renderFighter(fighterAEl, fighterA);
    renderFighter(fighterBEl, fighterB);

    const events = simulateBattle(fighterA, fighterB);
    playBattleEvents(events, fighterA, fighterB);
  }

  function renderFighter(container, fighter) {
    container.innerHTML = "";
    const canvas = document.createElement("canvas");
    container.appendChild(canvas);
    const name = document.createElement("div");
    name.className = "f-name";
    name.textContent = fighter.name;
    container.appendChild(name);
    const hpBar = document.createElement("div");
    hpBar.className = "hp-bar";
    const hpFill = document.createElement("span");
    hpFill.style.width = "100%";
    hpBar.appendChild(hpFill);
    container.appendChild(hpBar);
    const hpText = document.createElement("div");
    hpText.className = "hp-text";
    hpText.textContent = `${fighter.hp}/${fighter.maxHp ?? fighter.hp}`;
    container.appendChild(hpText);
    container._hpFill = hpFill;
    container._hpText = hpText;
    container._maxHp = fighter.maxHp ?? fighter.hp;
    requestAnimationFrame(() => MonsterGen.draw(canvas, fighter));
  }

  function simulateBattle(a, b) {
    const events = [];
    let hpA = a.hp, hpB = b.hp;
    let [first, second, firstEl, secondEl] = a.spd >= b.spd
      ? [a, b, "A", "B"]
      : [b, a, "B", "A"];

    events.push({ type: "start", text: `${a.spd >= b.spd ? a.name : b.name} が先制！` });

    let round = 0;
    while (hpA > 0 && hpB > 0 && round < 40) {
      round++;
      for (const [attacker, defenderName, side] of [
        [first, second, firstEl],
        [second, first, secondEl],
      ]) {
        const variance = 0.8 + Math.random() * 0.4;
        const raw = Math.max(1, Math.round((attacker.atk - defenderName.def * 0.5) * variance));
        if (side === "A") {
          hpB = Math.max(0, hpB - raw);
        } else {
          hpA = Math.max(0, hpA - raw);
        }
        events.push({
          type: "attack",
          text: `${attacker.name} の こうげき！ ${defenderName.name} に ${raw} のダメージ！`,
          hpA, hpB,
        });
        if (hpA <= 0 || hpB <= 0) break;
      }
    }

    const winner = hpA > 0 ? a.name : hpB > 0 ? b.name : "引き分け";
    events.push({ type: "end", text: `${winner} の勝利！`, winner });
    return events;
  }

  function playBattleEvents(events, a, b) {
    let i = 0;
    function step() {
      if (i >= events.length) return;
      const ev = events[i];
      i++;
      const p = document.createElement("p");
      p.textContent = ev.text;
      battleLogEl.appendChild(p);
      battleLogEl.scrollTop = battleLogEl.scrollHeight;

      if (ev.type === "attack") {
        const pctA = Math.max(0, (ev.hpA / fighterAEl._maxHp) * 100);
        const pctB = Math.max(0, (ev.hpB / fighterBEl._maxHp) * 100);
        fighterAEl._hpFill.style.width = `${pctA}%`;
        fighterAEl._hpText.textContent = `${ev.hpA}/${fighterAEl._maxHp}`;
        fighterBEl._hpFill.style.width = `${pctB}%`;
        fighterBEl._hpText.textContent = `${ev.hpB}/${fighterBEl._maxHp}`;
      }
      if (ev.type === "end") {
        battleResultEl.hidden = false;
        battleResultEl.textContent = ev.text;
        battleAgainBtn.hidden = false;
        return;
      }
      setTimeout(step, ev.type === "start" ? 500 : 650);
    }
    step();
  }

  renderDex();
  showScreen("home");
})();
