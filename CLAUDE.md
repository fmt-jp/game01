# ポケットアーケード

A collection of mobile browser games, published with GitHub Pages at
https://fmt-jp.github.io/game01/ and installable as a PWA.

`index.html` at the root is the hub that links to every game. Each game lives in
its own directory and is self-contained.

## What is here

Ten games, all on `main` and live. Service worker at `pocket-arcade-v9`; the
whole site, every game included, works offline once visited.

| Directory | Name | Kind | Worth knowing |
|---|---|---|---|
| `2048/` | 2048 | slide | a bot plays it, to show 2048 is actually reachable |
| `stack/` | つみあげ | one-handed action | tap to drop, timing based |
| `sokoban/` | そうこばん | box pushing | 10 levels, each proven solvable by BFS |
| `picross/` | おえかきロジック | nonogram | only boards with a unique solution are used |
| `fifteen/` | 15パズル | slide | random every time, parity-checked as solvable |
| `gems/` | 宝石パズル | falling blocks | Columns-like, real time |
| `barcode/` | バーコードモンスター | camera | a product barcode makes a monster; battles; a 図鑑 |
| `flow/` | ラインつなぎ | line drawing | generated, with a solution guaranteed to exist |
| `maze/` | めいろ探検 | 2D maze | keys gate the exit, lantern fuel drains per step |
| `maze3d/` | きょだい迷路 | 3D first person | own raycaster, stamp rally, lookout tower |

## Ground rules

- **No build step, no framework, no bundler.** Plain HTML, CSS and JavaScript,
  served as-is. A change must be visible by reloading the page.
- **No runtime dependencies** beyond Google Fonts. (One exception is documented
  under *Known limitations*.) Anything a game needs, it draws or computes
  itself.
- **Everything is generated.** No fixed level lists that run out: mazes,
  puzzles, monsters and boards are produced from a seed or a barcode, and are
  checked to be solvable before they reach the player.
- **One file layout per game**: `<name>/index.html`, `<name>/css/style.css`,
  `<name>/js/*.js`. Splitting the JavaScript is by role — generation, rendering
  and game state in separate files once a game grows past a few hundred lines.

## House style

Shared across every game, so the collection reads as one thing:

- Fonts: Zen Maru Gothic (display), Noto Sans JP (body), JetBrains Mono
  (numerals), all from Google Fonts.
- A dark ground, with **one accent colour per game**. Taken so far: ember, gold,
  teal, violet, blue, pink, green, crimson, amber, sky, timber. A new game picks
  a new one and uses it for its own page and for its hub card.
- The same page furniture in the same order: masthead with score boxes, a 遊び方
  one-liner, the board, the controls, then a 遊び方 section at the bottom.
- Real-time games render to a canvas scaled by `devicePixelRatio`; grid games
  use CSS grid or DOM nodes.
- Progress goes in `localStorage`, always wrapped in `try`/`catch` — it throws
  in private mode.

## Adding a game

1. Branch: `claude/<name>-game`.
2. Build it in `<name>/`, following the layout and house style above.
3. Write the checks (see below) and get them passing.
4. Publish a preview and get it approved before merging.
5. Merge to `main`, then in the same pass:
   - add a hub card to `index.html` (accent colour, preview icon, description),
   - add every new file to `APP_SHELL` in `sw.js`,
   - **bump `CACHE_NAME` in `sw.js`**.
6. Push `main`.

**Bumping `CACHE_NAME` is not optional, for any change to any game.** The
service worker serves the cached copy first, so a phone that has already
installed the site will keep running the old code until the cache name changes.

## Checking the work

Under `tests/`. Run them with `tests/run.sh` (serves the site on :8390 and runs
every check), or `tests/run.sh maze3d` for one game. Each check prints its own
results and exits non-zero on failure.

Most of these print their findings for a person to read rather than asserting;
`tests/README.md` says which ones decide for themselves, and *Outstanding work*
below treats fixing that as the first job. A new check should assert from the
start.

The approach that has actually caught bugs here: **generate in the browser,
verify from outside it.**

- The game produces something (a maze, a puzzle, a ray, a monster) and hands it
  out through `page.evaluate`.
- A checker written separately, in Python, decides whether it is correct — a BFS
  or A* solver, a nonogram solver, a brute-force ray marcher, a flood fill.
  Writing the check from the rules rather than from the implementation is the
  point; a check that mirrors the code cannot find a disagreement.
- Then the real UI is driven with real input events, and the outcome is asserted
  from outside. If the game's rules and the checker's rules disagree, the
  planned moves stop working and the check fails.
- Where behaviour is visual, measure the pixels: a straight wall must project to
  a straight edge, a shaded body must show a luminance gradient, nothing may
  touch the edge of its canvas.

Seed `Math.random` before the page loads to reproduce a specific board. Anything
drawn at load time (textures, scenery) must therefore use its own generator, not
`Math.random`, or seeding the page shifts the game's own sequence.

## Outstanding work

Nothing here is a known bug — the games all work. These are the things a next
session would most usefully pick up, roughly in that order.

1. **Fifteen of the eighteen checks cannot fail.** They print findings a person
   read at the time instead of asserting. `tests/README.md` names them. Until
   they are converted, a green `tests/run.sh` means "nothing crashed" for those
   games. Worth doing one game at a time.
2. **`barcode/` depends on a CDN.** It loads ZXing as a fallback for browsers
   without `BarcodeDetector` (notably iOS Safari), which is the only external
   dependency in the repository and means scanning does not work offline on
   those browsers. Vendoring the library would fix it; documenting it as a
   limitation is the cheaper alternative.
3. **`maze3d/` has no floor texture**, so in open spaces there is little sense
   of movement — the walls carry it alone. Floor casting at reduced resolution
   would work without costing the frame budget. Also, a tower is only visible in
   line of sight: the depth buffer is per column, so its roof cannot be seen
   over a fence.
4. **`barcode/`'s 図鑑 is read-only.** You cannot pick a monster from it to
   fight with; only the one just scanned can battle.
5. **The hub is ten cards long** and only grows. Sorting, grouping or a filter
   will be wanted before long.

## Pitfalls already hit here

- A class rule that sets `display` beats the user-agent rule for `[hidden]`
  (equal specificity, later in the cascade). Every container that is hidden with
  the attribute needs its own `.x[hidden] { display: none; }`. This has bitten
  four separate games.
- `touch-action: none` on `body` stops the page scrolling, which hides the 遊び方
  section on a phone. Put it on the board element only.
- `body { display: flex }` defaults to `align-items: stretch`, which gives the
  page a viewport-height box and squashes an aspect-ratio board. Use
  `flex-start`.
- A canvas that has never been painted produces a `captureStream()` that never
  becomes ready, so `video.play()` hangs. Paint something first when mocking a
  camera in a test.
