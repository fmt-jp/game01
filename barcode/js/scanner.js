/* Reading a barcode off a camera frame, without anything from outside.
 *
 * This replaces the one library the collection used to fetch from a CDN. It
 * reads EAN-13, UPC-A (which is EAN-13 with a leading zero) and EAN-8 --
 * between them, what is printed on a packet in a shop.
 *
 * The method is the usual one for a one-dimensional code. Take a horizontal
 * line of pixels; turn it into a list of run lengths of dark and light; find
 * the start guard, three runs of the same width; then read the digits four
 * runs at a time, scaling each digit by its own total so that a code that
 * widens across the frame still reads. The check digit at the end has to
 * agree, which is what keeps a misread from becoming a monster.
 */
const Scanner = (() => {
  "use strict";

  // Each digit is seven modules, written here as the four run lengths it
  // makes: light, dark, light, dark on the left half; dark, light, dark,
  // light on the right.
  const LEFT_ODD = {
    "3211": 0, "2221": 1, "2122": 2, "1411": 3, "1132": 4,
    "1231": 5, "1114": 6, "1312": 7, "1213": 8, "3112": 9,
  };
  const LEFT_EVEN = {
    "1123": 0, "1222": 1, "2212": 2, "1141": 3, "2311": 4,
    "1321": 5, "4111": 6, "2131": 7, "3121": 8, "2113": 9,
  };
  // The right half is the left-odd set with dark and light swapped, which
  // leaves the run lengths alone, so the same table reads it.
  const RIGHT = LEFT_ODD;

  // Which of the first six digits are written in the even set says what the
  // thirteenth digit -- the one with no bars of its own -- must be.
  const PARITY = {
    "000000": 0, "001011": 1, "001101": 2, "001110": 3, "010011": 4,
    "011001": 5, "011100": 6, "010101": 7, "010110": 8, "011010": 9,
  };

  function checksum(digits) {
    // Odd positions count three times, counting from the right.
    let sum = 0;
    for (let i = 0; i < digits.length - 1; i += 1) {
      const fromRight = digits.length - 2 - i;
      sum += digits[i] * (fromRight % 2 === 0 ? 3 : 1);
    }
    return (10 - (sum % 10)) % 10;
  }

  /* ---- a line of pixels, as runs ---------------------------------- */

  // Light and dark are decided against the neighbourhood, not the whole line.
  // One threshold for the line only works under even light; a packet held at
  // an angle is bright at one end and the dark end then reads as all bars.
  // So: compare each pixel with the average of the window around it.
  function runsOf(row, window, biasShare) {
    const n = row.length;
    let low = 255, high = 0;
    for (const v of row) {
      if (v < low) low = v;
      if (v > high) high = v;
    }
    if (high - low < 24) return null;              // nothing but flat grey

    const dark = new Uint8Array(n);
    if (!window) {
      // One threshold for the whole line, halfway between its darkest and
      // its lightest. Blunt, but it holds a blurred code together, where a
      // local average follows the blur into the middle of a wide bar and
      // splits it.
      const mid = (low + high) / 2;
      for (let i = 0; i < n; i += 1) dark[i] = row[i] < mid ? 1 : 0;
      return toRuns(dark, n);
    }

    const sums = new Float64Array(n + 1);
    for (let i = 0; i < n; i += 1) sums[i + 1] = sums[i] + row[i];
    const half = Math.max(6, Math.round(window));
    // How far below its neighbourhood a pixel has to sit to count as a
    // bar. A blurred code barely dips at all, so this has to be tried low as
    // well as high.
    const bias = Math.max(1, (high - low) * (biasShare === undefined ? 0.06 : biasShare));

    for (let i = 0; i < n; i += 1) {
      const from = Math.max(0, i - half);
      const to = Math.min(n, i + half + 1);
      const mean = (sums[to] - sums[from]) / (to - from);
      dark[i] = row[i] < mean - bias ? 1 : 0;
    }

    return toRuns(dark, n);
  }

  function toRuns(dark, n) {
    const runs = [];
    let on = dark[0];
    let start = 0;
    for (let i = 1; i < n; i += 1) {
      if (dark[i] !== on) {
        runs.push({ dark: !!on, length: i - start });
        on = dark[i];
        start = i;
      }
    }
    runs.push({ dark: !!on, length: n - start });
    return runs;
  }

  // How far a set of runs is from a pattern, once both are scaled to the
  // same total. Returns null when it is too far off to be that pattern.
  function widths(runs, at, count, modules) {
    let total = 0;
    for (let i = 0; i < count; i += 1) {
      if (!runs[at + i]) return null;
      total += runs[at + i].length;
    }
    const unit = total / modules;
    if (unit < 0.6) return null;
    const out = [];
    for (let i = 0; i < count; i += 1) {
      const n = Math.round(runs[at + i].length / unit);
      if (n < 1 || n > 4) return null;
      // Allow a third of a module of slop in any one run.
      if (Math.abs(runs[at + i].length / unit - n) > 0.38) return null;
      out.push(n);
    }
    return out;
  }

  function isGuard(runs, at, count) {
    const w = widths(runs, at, count, count);
    return w !== null && w.every((n) => n === 1);
  }

  function readDigits(runs, at, howMany, tables) {
    const digits = [];
    const parity = [];
    let cursor = at;
    for (let n = 0; n < howMany; n += 1) {
      const w = widths(runs, cursor, 4, 7);
      if (!w) return null;
      const key = w.join("");
      let found = null;
      for (let t = 0; t < tables.length; t += 1) {
        if (key in tables[t]) {
          found = { digit: tables[t][key], table: t };
          break;
        }
      }
      if (!found) return null;
      digits.push(found.digit);
      parity.push(found.table);
      cursor += 4;
    }
    return { digits, parity, cursor };
  }

  function readEAN13(runs, at) {
    if (!runs[at].dark || !isGuard(runs, at, 3)) return null;
    const left = readDigits(runs, at + 3, 6, [LEFT_ODD, LEFT_EVEN]);
    if (!left) return null;
    if (!isGuard(runs, left.cursor, 5)) return null;
    const right = readDigits(runs, left.cursor + 5, 6, [RIGHT]);
    if (!right) return null;
    if (!isGuard(runs, right.cursor, 3)) return null;

    const first = PARITY[left.parity.join("")];
    if (first === undefined) return null;
    const digits = [first, ...left.digits, ...right.digits];
    if (checksum(digits) !== digits[12]) return null;
    return digits.join("");
  }

  function readEAN8(runs, at) {
    if (!runs[at].dark || !isGuard(runs, at, 3)) return null;
    const left = readDigits(runs, at + 3, 4, [LEFT_ODD]);
    if (!left) return null;
    if (!isGuard(runs, left.cursor, 5)) return null;
    const right = readDigits(runs, left.cursor + 5, 4, [RIGHT]);
    if (!right) return null;
    if (!isGuard(runs, right.cursor, 3)) return null;
    const digits = [...left.digits, ...right.digits];
    if (checksum(digits) !== digits[7]) return null;
    return digits.join("");
  }

  // Average each pixel with its neighbours. A frame that is both soft and
  // grainy -- which is most of them, indoors, at arm's length -- breaks into
  // specks under any threshold until the grain is taken out first.
  function smoothed(row, reach) {
    const n = row.length;
    const out = new Uint8Array(n);
    const sums = new Float64Array(n + 1);
    for (let i = 0; i < n; i += 1) sums[i + 1] = sums[i] + row[i];
    for (let i = 0; i < n; i += 1) {
      const from = Math.max(0, i - reach);
      const to = Math.min(n, i + reach + 1);
      out[i] = (sums[to] - sums[from]) / (to - from);
    }
    return out;
  }

  function readLine(row) {
    for (const reach of [0, 1, 2, 4]) {
      const got = readPass(reach ? smoothed(row, reach) : row);
      if (got) return got;
    }
    return null;
  }

  function readPass(row) {
    // A narrow window follows the light closely but smears the widest bars
    // into the background; a wide one is the other way about. Try a few.
    const windows = [0, Math.round(row.length / 30), Math.round(row.length / 12), 8];
    for (const window of windows) {
     for (const biasShare of [0.06, 0.015]) {
      const runs = runsOf(row, window, biasShare);
      if (!runs || runs.length < 30) continue;
      const both = [runs, runs.slice().reverse()];   // a code held upside down
      for (const list of both) {
        for (let at = 0; at < list.length - 28; at += 1) {
          if (!list[at].dark) continue;
          const thirteen = readEAN13(list, at);
          if (thirteen) return thirteen;
          const eight = readEAN8(list, at);
          if (eight) return eight;
        }
      }
     }
    }
    return null;
  }

  /* ---- a whole frame ------------------------------------------------ */

  // Read across a band of lines through the middle of the picture. A code
  // only has to come out of one of them, and the check digit says whether it
  // really did.
  function decode(data, width, height, options) {
    const opts = options || {};
    const lines = opts.lines || 24;
    const top = Math.floor(height * (opts.band === undefined ? 0.15 : opts.band));
    const bottom = height - top;
    const row = new Uint8Array(width);
    for (let n = 0; n < lines; n += 1) {
      const y = Math.round(top + ((bottom - top) * n) / Math.max(1, lines - 1));
      if (y < 0 || y >= height) continue;
      let at = y * width * 4;
      for (let x = 0; x < width; x += 1, at += 4) {
        // Green carries most of the luminance and costs one lookup.
        row[x] = (data[at] * 77 + data[at + 1] * 151 + data[at + 2] * 28) >> 8;
      }
      const got = readLine(row);
      if (got) return got;
    }
    return null;
  }

  function decodeCanvas(canvas, options) {
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
    return decode(image.data, canvas.width, canvas.height, options);
  }

  return { decode, decodeCanvas, checksum, readLine };
})();
