/* The tile faces, drawn rather than fetched.
 *
 * The collection has no runtime dependencies, so every pip, stick and frame
 * here is SVG this file writes. Only the three suits' numerals and the honour
 * characters are text, and those are glyphs the page fonts carry.
 */
const Faces = (() => {
  "use strict";

  const INK = "#1b2434";
  const RED = "#c0392b";
  const GREEN = "#1f8f63";
  const BLUE = "#2f6fd0";

  // Where the pips sit, on the 60x80 face. Each entry is [x, y, radius].
  const DOTS = {
    1: [[30, 40, 14]],
    2: [[30, 26, 11], [30, 54, 11]],
    3: [[17, 23, 10], [30, 40, 10], [43, 57, 10]],
    4: [[20, 27, 10], [40, 27, 10], [20, 53, 10], [40, 53, 10]],
    5: [[19, 25, 9.5], [41, 25, 9.5], [30, 40, 9.5], [19, 55, 9.5], [41, 55, 9.5]],
    6: [[20, 22, 9], [40, 22, 9], [20, 40, 9], [40, 40, 9], [20, 58, 9], [40, 58, 9]],
    7: [[16, 19, 8.5], [30, 19, 8.5], [44, 19, 8.5],
        [20, 42, 8.5], [40, 42, 8.5], [20, 61, 8.5], [40, 61, 8.5]],
    8: [[20, 17, 7.8], [40, 17, 7.8], [20, 33, 7.8], [40, 33, 7.8],
        [20, 49, 7.8], [40, 49, 7.8], [20, 65, 7.8], [40, 65, 7.8]],
    9: [[16, 22, 8], [30, 22, 8], [44, 22, 8],
        [16, 40, 8], [30, 40, 8], [44, 40, 8],
        [16, 58, 8], [30, 58, 8], [44, 58, 8]],
  };

  // A colour per count, so 4 and 6 are told apart at a glance on a phone.
  const DOT_INK = { 1: BLUE, 2: GREEN, 3: RED, 4: BLUE, 5: RED, 6: GREEN, 7: RED, 8: BLUE, 9: GREEN };

  // The bamboo. Each count gets its own stick size: drawn to one size they
  // come out as dashes on a phone, and a stick that reads as two dots makes
  // six and three the same tile at a glance.
  const STICKS = {
    2: { w: 11, h: 26, at: [[30, 25], [30, 55]] },
    3: { w: 10, h: 23, at: [[30, 20], [19, 55], [41, 55]] },
    4: { w: 10, h: 22, at: [[19, 24], [41, 24], [19, 56], [41, 56]] },
    5: { w: 9, h: 20, at: [[18, 22], [42, 22], [30, 40], [18, 58], [42, 58]] },
    6: { w: 9, h: 19, at: [[19, 21], [41, 21], [19, 40], [41, 40], [19, 59], [41, 59]] },
    7: { w: 8, h: 17, at: [[30, 15], [19, 34], [41, 34], [19, 52], [41, 52], [19, 70], [41, 70]] },
    8: { w: 8, h: 16, at: [[19, 17], [41, 17], [19, 34], [41, 34], [19, 51], [41, 51], [19, 68], [41, 68]] },
    9: { w: 7.5, h: 16, at: [[15, 21], [30, 21], [45, 21], [15, 40], [30, 40], [45, 40], [15, 59], [30, 59], [45, 59]] },
  };
  // The traditional odd ones out: the middle of five and the crown of seven.
  const STICK_RED = { 5: [2], 7: [0] };

  const NUMERAL = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"];

  function pip(x, y, r, colour) {
    return `<circle cx="${x}" cy="${y}" r="${r}" fill="${colour}"/>` +
           `<circle cx="${x}" cy="${y}" r="${(r * 0.46).toFixed(2)}" fill="#fdf7e8"/>`;
  }

  // One length of bamboo: a solid bar, with the joints cut in as thin notches
  // at the ends rather than a band across the middle.
  function stick(x, y, w, h, colour) {
    const r = Math.min(w / 2, 4);
    return `<rect x="${(x - w / 2).toFixed(2)}" y="${(y - h / 2).toFixed(2)}" ` +
           `width="${w.toFixed(2)}" height="${h.toFixed(2)}" rx="${r.toFixed(2)}" fill="${colour}"/>` +
           `<rect x="${(x - w / 2).toFixed(2)}" y="${(y - h / 2 + h * 0.22).toFixed(2)}" ` +
           `width="${w.toFixed(2)}" height="1.1" fill="#fdf7e8" fill-opacity="0.55"/>` +
           `<rect x="${(x - w / 2).toFixed(2)}" y="${(y + h / 2 - h * 0.22).toFixed(2)}" ` +
           `width="${w.toFixed(2)}" height="1.1" fill="#fdf7e8" fill-opacity="0.55"/>`;
  }

  function text(body, y, size, colour, weight) {
    return `<text x="30" y="${y}" text-anchor="middle" font-size="${size}" ` +
           `font-family="Zen Maru Gothic, Noto Sans JP, serif" font-weight="${weight || 700}" ` +
           `fill="${colour}">${body}</text>`;
  }

  // The one of bamboo: a single stalk with a pair of leaves, so it reads as
  // bamboo at a glance and is never mistaken for a count of something.
  function stalk() {
    return stick(30, 44, 13, 38, GREEN) +
           `<path d="M29 26 C20 24 13 18 11 10 C20 9 27 13 29 21 Z" fill="${GREEN}"/>` +
           `<path d="M31 26 C40 24 47 18 49 10 C40 9 33 13 31 21 Z" fill="${RED}"/>` +
           `<circle cx="30" cy="22" r="2.6" fill="${RED}"/>`;
  }

  const DRAW = {};
  for (let n = 1; n <= 9; n += 1) {
    DRAW["p" + n] = () => DOTS[n].map(([x, y, r]) => pip(x, y, r, DOT_INK[n])).join("");
    DRAW["s" + n] = () => {
      if (n === 1) return stalk();
      const red = STICK_RED[n] || [];
      const g = STICKS[n];
      return g.at.map(([x, y], i) => stick(x, y, g.w, g.h, red.includes(i) ? RED : GREEN)).join("");
    };
    DRAW["m" + n] = () => text(NUMERAL[n], 36, 30, INK) + text("萬", 68, 26, RED);
  }
  DRAW.we = () => text("東", 56, 42, INK);
  DRAW.ws = () => text("南", 56, 42, INK);
  DRAW.ww = () => text("西", 56, 42, INK);
  DRAW.wn = () => text("北", 56, 42, INK);
  DRAW.dr = () => text("中", 56, 42, RED);
  DRAW.dg = () => text("發", 56, 42, GREEN);
  // The white dragon is a frame and nothing else, as it is on a real tile.
  DRAW.dw = () => `<rect x="12" y="16" width="36" height="48" rx="4" fill="none" stroke="${BLUE}" stroke-width="3"/>` +
                  `<path d="M18 22 L42 58" stroke="${BLUE}" stroke-width="2.4" stroke-linecap="round"/>`;

  const KINDS = Object.keys(DRAW);

  const NAMES = {
    we: "東", ws: "南", ww: "西", wn: "北", dr: "中", dg: "發", dw: "白",
  };
  function name(kind) {
    if (NAMES[kind]) return NAMES[kind];
    const n = Number(kind.slice(1));
    return NUMERAL[n] + { p: "筒", s: "索", m: "萬" }[kind[0]];
  }

  function svg(kind) {
    return `<svg viewBox="0 0 60 80" aria-hidden="true">${DRAW[kind]()}</svg>`;
  }

  return { KINDS, svg, name };
})();
