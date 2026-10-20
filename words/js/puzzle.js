// Builds one puzzle: a wheel of kana taken from a single base word, every
// dictionary word spellable from them, and a crossword those words interlock
// into. Words that will not fit the grid become bonus words.
const WordPuzzle = (() => {
  const MAX_GRID = 9;

  const SMALL = new Set(["ゃ", "ゅ", "ょ", "っ", "ぁ", "ぃ", "ぅ", "ぇ", "ぉ", "ー"]);

  // Base words of five and six kana are mixed at the higher levels so the pool
  // of possible boards stays wide; a six-kana base alone is only a couple of
  // hundred words once the variety rule below has had its say.
  function levelConfig(level) {
    if (level <= 3) return { baseLengths: [5], minWords: 5, maxWords: 9, distinct: 4 };
    if (level <= 10) return { baseLengths: [5, 6], minWords: 6, maxWords: 12, distinct: 4 };
    return { baseLengths: [6, 5], minWords: 7, maxWords: 15, distinct: 4 };
  }

  // A base like しょうじょう fills the wheel with ょ and う and every answer ends
  // up looking the same. Insist on variety in the letters themselves.
  function usableBase(word, config) {
    if (new Set(word).size < config.distinct) return false;
    let small = 0;
    for (const ch of word) if (SMALL.has(ch)) small++;
    return small <= 1;
  }

  function shuffled(list) {
    const out = list.slice();
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  }

  const key = (r, c) => `${r},${c}`;

  // A word fits when every cell it needs is empty or already holds that same
  // kana, its two ends stay clear, and none of the letters it writes brushes
  // against a word running the other way. That last rule is what stops the
  // grid from quietly spelling something nobody chose.
  function canPlace(cells, word, row, col, dir) {
    const dr = dir === "down" ? 1 : 0;
    const dc = dir === "across" ? 1 : 0;
    let crossings = 0;

    if (cells.has(key(row - dr, col - dc))) return null;
    if (cells.has(key(row + dr * word.length, col + dc * word.length))) return null;

    for (let i = 0; i < word.length; i++) {
      const r = row + dr * i, c = col + dc * i;
      const here = cells.get(key(r, c));
      if (here !== undefined) {
        if (here !== word[i]) return null;
        crossings++;
        continue;
      }
      // empty cell: its perpendicular neighbours must be empty too
      const sideA = key(r + dc, c + dr);
      const sideB = key(r - dc, c - dr);
      if (cells.has(sideA) || cells.has(sideB)) return null;
    }
    return crossings;
  }

  function bounds(cells, extra) {
    let minR = Infinity, maxR = -Infinity, minC = Infinity, maxC = -Infinity;
    const visit = (r, c) => {
      if (r < minR) minR = r;
      if (r > maxR) maxR = r;
      if (c < minC) minC = c;
      if (c > maxC) maxC = c;
    };
    for (const k of cells.keys()) {
      const [r, c] = k.split(",").map(Number);
      visit(r, c);
    }
    if (extra) for (const [r, c] of extra) visit(r, c);
    return { minR, maxR, minC, maxC, height: maxR - minR + 1, width: maxC - minC + 1 };
  }

  function layout(words) {
    const ordered = words.slice().sort((a, b) => b.length - a.length || a.localeCompare(b));
    const cells = new Map();
    const entries = [];
    const unplaced = [];

    const write = (word, row, col, dir) => {
      const dr = dir === "down" ? 1 : 0;
      const dc = dir === "across" ? 1 : 0;
      for (let i = 0; i < word.length; i++) {
        cells.set(key(row + dr * i, col + dc * i), word[i]);
      }
      entries.push({ word, row, col, dir });
    };

    write(ordered[0], 0, 0, "across");

    for (const word of ordered.slice(1)) {
      let best = null;
      for (const entry of entries) {
        const edr = entry.dir === "down" ? 1 : 0;
        const edc = entry.dir === "across" ? 1 : 0;
        const dir = entry.dir === "across" ? "down" : "across";
        const dr = dir === "down" ? 1 : 0;
        const dc = dir === "across" ? 1 : 0;

        for (let i = 0; i < entry.word.length; i++) {
          const r = entry.row + edr * i, c = entry.col + edc * i;
          for (let j = 0; j < word.length; j++) {
            if (word[j] !== entry.word[i]) continue;
            const row = r - dr * j, col = c - dc * j;
            if (canPlace(cells, word, row, col, dir) === null) continue;
            const span = bounds(cells, [
              [row, col], [row + dr * (word.length - 1), col + dc * (word.length - 1)],
            ]);
            if (span.width > MAX_GRID || span.height > MAX_GRID) continue;
            const score = span.width * span.height + Math.abs(span.width - span.height);
            if (!best || score < best.score) best = { score, word, row, col, dir };
          }
        }
      }
      if (best) write(best.word, best.row, best.col, best.dir);
      else unplaced.push(word);
    }

    const span = bounds(cells);
    const grid = {
      width: span.width,
      height: span.height,
      // row-major, "" where there is no cell
      cells: Array.from({ length: span.height }, (_, r) =>
        Array.from({ length: span.width }, (_, c) => cells.get(key(r + span.minR, c + span.minC)) || "")),
    };
    const placed = entries.map((e) => ({
      word: e.word, row: e.row - span.minR, col: e.col - span.minC, dir: e.dir,
    }));
    return { grid, entries: placed, unplaced };
  }

  function generate(level) {
    const config = levelConfig(level);

    for (let attempt = 0; attempt < 500; attempt++) {
      const length = config.baseLengths[Math.floor(Math.random() * config.baseLengths.length)];
      const pool = WordDict.byLength[length];
      const base = pool[Math.floor(Math.random() * pool.length)];
      if (!usableBase(base, config)) continue;
      const words = WordDict.formableFrom(base, length);
      if (words.length < config.minWords || words.length > config.maxWords) continue;

      const built = layout(words);
      // Most of the words have to make it into the grid, or the board stops
      // being the puzzle and becomes a hint sheet.
      if (built.entries.length < Math.max(4, Math.ceil(words.length * 0.6))) continue;

      return {
        base,
        letters: shuffled([...base]),
        grid: built.grid,
        entries: built.entries,
        bonus: built.unplaced,
        attempts: attempt + 1,
      };
    }
    return null;
  }

  return { generate, layout, levelConfig, usableBase, canPlace, MAX_GRID };
})();

if (typeof window !== "undefined") window.WordPuzzle = WordPuzzle;
