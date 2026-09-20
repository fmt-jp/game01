const FlowPuzzle = (() => {
  function neighbors(idx, size) {
    const r = Math.floor(idx / size);
    const c = idx % size;
    const out = [];
    if (r > 0) out.push(idx - size);
    if (r < size - 1) out.push(idx + size);
    if (c > 0) out.push(idx - 1);
    if (c < size - 1) out.push(idx + 1);
    return out;
  }

  function shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  // A random path that visits every cell exactly once (randomised DFS with
  // Warnsdorff ordering; backtracks when the unvisited cells would split).
  function hamiltonianPath(size, attempts = 30) {
    const total = size * size;

    // Checkerboard parity: when the cell count is odd, one colour has one more
    // cell than the other, so a covering path can only start on that colour.
    // Starting anywhere else is provably impossible and just burns the budget.
    const starts = [];
    for (let cell = 0; cell < total; cell++) {
      const parity = (Math.floor(cell / size) + (cell % size)) % 2;
      if (total % 2 === 0 || parity === 0) starts.push(cell);
    }

    for (let attempt = 0; attempt < attempts; attempt++) {
      const visited = new Uint8Array(total);
      const path = [];
      let steps = 0;
      const budget = 60000;

      const freeDegree = (idx) => {
        let n = 0;
        for (const nb of neighbors(idx, size)) if (!visited[nb]) n++;
        return n;
      };

      const remainingConnected = (cur) => {
        const remaining = total - path.length;
        if (remaining === 0) return true;
        let seed = -1;
        for (const nb of neighbors(cur, size)) {
          if (!visited[nb]) { seed = nb; break; }
        }
        if (seed === -1) return false;
        const seen = new Uint8Array(total);
        const stack = [seed];
        seen[seed] = 1;
        let count = 0;
        while (stack.length) {
          const cell = stack.pop();
          count++;
          for (const nb of neighbors(cell, size)) {
            if (!visited[nb] && !seen[nb]) {
              seen[nb] = 1;
              stack.push(nb);
            }
          }
        }
        return count === remaining;
      };

      const walk = (cur) => {
        if (path.length === total) return true;
        if (steps++ > budget) return false;
        const cands = shuffle(neighbors(cur, size).filter((n) => !visited[n]));
        cands.sort((a, b) => freeDegree(a) - freeDegree(b));
        for (const next of cands) {
          visited[next] = 1;
          path.push(next);
          if (remainingConnected(next) && walk(next)) return true;
          visited[next] = 0;
          path.pop();
        }
        return false;
      };

      const start = starts[Math.floor(Math.random() * starts.length)];
      visited[start] = 1;
      path.push(start);
      if (walk(start)) return path;
    }
    return null;
  }

  // Slice the covering path into `count` segments; each becomes one colour.
  function cutIntoSegments(path, count, minLen, maxLen) {
    const total = path.length;
    if (total < count * minLen) return null;

    for (let tries = 0; tries < 400; tries++) {
      const cuts = new Set();
      while (cuts.size < count - 1) {
        cuts.add(1 + Math.floor(Math.random() * (total - 1)));
      }
      const bounds = [0, ...[...cuts].sort((a, b) => a - b), total];
      let ok = true;
      for (let i = 0; i < bounds.length - 1; i++) {
        const len = bounds[i + 1] - bounds[i];
        if (len < minLen || len > maxLen) { ok = false; break; }
      }
      if (!ok) continue;
      const segments = [];
      for (let i = 0; i < bounds.length - 1; i++) {
        segments.push(path.slice(bounds[i], bounds[i + 1]));
      }
      return segments;
    }
    return null;
  }

  function levelConfig(level) {
    if (level <= 3) return { size: 5, colors: 4 };
    if (level <= 6) return { size: 6, colors: 5 };
    if (level <= 10) return { size: 7, colors: 5 };
    return { size: 7, colors: 6 };
  }

  function generate(size, colorCount) {
    const total = size * size;
    const minLen = 3;
    const maxLen = Math.max(minLen + 2, Math.ceil((total / colorCount) * 1.9));

    for (let attempt = 0; attempt < 25; attempt++) {
      const path = hamiltonianPath(size);
      if (!path) continue;
      const segments = cutIntoSegments(path, colorCount, minLen, maxLen);
      if (!segments) continue;
      return {
        size,
        endpoints: segments.map((seg) => [seg[0], seg[seg.length - 1]]),
        solution: segments,
      };
    }
    return null;
  }

  return { generate, levelConfig, neighbors };
})();

if (typeof window !== "undefined") window.FlowPuzzle = FlowPuzzle;
