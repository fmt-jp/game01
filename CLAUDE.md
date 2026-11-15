# ポケットアーケード

A collection of mobile browser games, published with GitHub Pages at
https://fmt-jp.github.io/game01/ and installable as a PWA.

`index.html` at the root is the hub that links to every game. Each game lives in
its own directory and is self-contained.

## What is here

Fifteen games, all on `main` and live. Service worker at `pocket-arcade-v17`;
the whole site, every game included, works offline once visited.

| Directory | Name | Kind | Worth knowing |
|---|---|---|---|
| `2048/` | 2048 | slide | a bot plays it, to show 2048 is actually reachable |
| `stack/` | つみあげ | one-handed action | tap to drop, timing based |
| `sokoban/` | そうこばん | box pushing | 10 levels, each proven solvable by BFS |
| `picross/` | おえかきロジック | nonogram | only boards with a unique solution are used |
| `fifteen/` | 15パズル | slide | random every time, parity-checked as solvable |
| `gems/` | 宝石パズル | falling blocks | Columns-like, real time |
| `barcode/` | バーコードモンスター | camera | own EAN-13/8 reader; a product barcode makes a monster |
| `flow/` | ラインつなぎ | line drawing | generated, with a solution guaranteed to exist |
| `maze/` | めいろ探検 | 2D maze | keys gate the exit, lantern fuel drains per step |
| `maze3d/` | きょだい迷路 | 3D first person | own raycaster with floor casting, stamp rally, tower |
| `words/` | ことばの輪 | word puzzle | trace a kana wheel to fill a generated crossword |
| `ataxx/` | ふえる石 | board game vs AI | clone or jump, converting what you land beside |
| `rhythm/` | おとのつぶ | rhythm | song and chart both generated; WebAudio synthesis only |
| `tiles/` | かさねとり | mahjong solitaire | the pile is dealt by taking an empty one apart |
| `bridges/` | はしわたし | hashiwokakero | built answer-first, kept only when the answer is the only one |

## Ground rules

- **No build step, no framework, no bundler.** Plain HTML, CSS and JavaScript,
  served as-is. A change must be visible by reloading the page.
- **No runtime dependencies** beyond Google Fonts. Nothing else is fetched at
  runtime, from anywhere. Anything a game needs, it draws or computes itself --
  including reading a barcode off the camera, which `barcode/js/scanner.js`
  does from the EAN tables rather than from a library.
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
  teal, violet, blue, pink, green, crimson, amber, sky, timber, orchid, lime,
  indigo, jade, mist (a pale desaturated blue — the first one picked for its
  lightness rather than its hue).
  A new game picks a new one and uses it for its own page and for its hub card.
  Fifteen in, the hues are used up: a new one now differs by lightness or
  by how washed out it is, the way mist does.
- The same page furniture in the same order: masthead with score boxes, a 遊び方
  one-liner, the board, the controls, then a 遊び方 section at the bottom.
- The hub is not one list: it is three shelves side by side, snapped, with a
  sticky tab row. A card's description is clamped to two lines, so write one
  that fits in about 25 characters rather than relying on the ellipsis.
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
   - add a hub card to `index.html` (accent colour, preview icon, description)
     **inside the right shelf** — the hub is three swipeable shelves,
     そろえる / かんがえる / うごかす, with a tab each,
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

**Every check decides for itself** and exits non-zero when something is wrong,
so a green `tests/run.sh` means what it says. `_common.py` holds the shared
`check` / `note` / `head` / `finish` helpers a new check should use. Where a
measurement is noisy, assert on the steadier figure behind it and print the
noisy one: a check that fails one run in ten is worse than no check at all.

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

`run.sh` picks whichever interpreter has playwright installed; the system
`python3` often does not, and a missing import otherwise looks like a broken
check rather than a setup gap.

## Outstanding work

Nothing here is a known bug — the games all work. These are the things a next
session would most usefully pick up, roughly in that order.

1. **`maze3d/`'s towers are only visible in line of sight.** The depth buffer
   is per column, so a tower's roof cannot be seen over a fence that is nearer
   than it — you walk round a corner and it appears. Sprites would need a
   per-pixel depth test, or towers their own pass drawn before the walls.
2. **`barcode/`'s 図鑑 is read-only.** You cannot pick a monster from it to
   fight with; only the one just scanned can battle.
3. **The shelves are hand-sorted.** Each game sits on そろえる, かんがえる or
   うごかす because a person put it there, and a few are arguable (`gems/` is
   real time but is shelved with the matching games, `ataxx/` is a board game
   among the thinking ones). Past twenty games a shelf will want splitting,
   and nothing stops a shelf growing past a screenful.
4. **`words/` draws its base words from a finite pool** — roughly 1,400 five and
   six kana words survive the variety rule — so the boards are generated but not
   literally endless. Building the wheel from a letter set rather than a single
   word would widen it, at the cost of the promise that one answer uses every
   letter.
5. **`rhythm/`'s latency offset cannot be measured for the player.** The initial
   value comes from `AudioContext.outputLatency`, which is wrong on plenty of
   phones, and the ズレ調整 buttons leave it to the player to find by feel. A
   calibration round — tap along to a bare metronome, take the median of the
   errors — would set it properly.
6. **`bridges/` runs out of room at level 12.** The board caps at 7 by 9 with
   24 islands, because a phone cannot show more and still leave an island big
   enough to tap, so the search depth stops climbing there. A harder board
   would have to come from the shape of the clues rather than the size.
7. **`tiles/` stacks on an aligned grid.** Real 上海 layouts offset tiles by
   half a width, which is prettier and makes the free rule harder (a half-gap
   is not enough to slide through). The pile is a mirrored height map instead,
   which looks built but means every layout is a mound. Half-offsets would
   want the free rule and the Python checker rewritten together.

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
- A `for...of` over a `Set` visits entries added while it runs. Expanding a set
  of cells in place therefore floods the whole board; iterate a snapshot.
- Anything that hands the turn over on a timer must close the input at the
  moment the move is made, not when the timer fires. `ataxx/` let a second tap
  in during that gap, which started a second chain of scheduled turns and had
  the opponent moving twice in a row. Checks that only play politely, one move
  at a time, will not see it.
- A look-ahead audio scheduler walks its event list in time order and stops at
  the first event still in the future, so an unsorted list silences everything
  after the first late entry. `rhythm/` built its backing track bar by bar and
  queued one event in total until the list was sorted.
- `AudioContext.currentTime` advances in blocks of 128 samples, about 3ms. A
  sound asked for any sooner than that may already be in the past by the time
  it is wired up, and anything in the past plays at once, as a click. Schedule
  with a cushion (`rhythm/` uses 15ms) and clamp a late event forward rather
  than scheduling it behind the clock.
- A timer must not outlive the board it was set on. `tiles/` raised its
  "cleared" overlay on a timer, so starting the next pile inside that moment
  let the old timer land on the new pile and freeze it. Clearing a game's
  pending timers where the game is set up is the fix; the ataxx entry above is
  the same mistake wearing different clothes.
- Measuring an element with a screenshot measures whatever is painted over it
  too. A check that read the brightness of a buried tile was really reading
  the tile standing on it, and reported a 17-point difference where the real
  one was 97. Measure something nothing covers, or crop to the part that shows.
- Scanning along a row from an island needs a far edge to stop at. Looking
  rightwards from the rightmost island in `bridges/` ran off down the number
  line and hung the page, with nothing in the console to say why. Any walk
  outward from a cell wants both ends bounded.
- Setting a game's state right after a call that may have ended the game wipes
  the ending out. `gems/` ran `spawnPiece(); gameState = "falling";` in two
  places, and spawnPiece is exactly where a full column is noticed, so the
  board froze instead of finishing: nothing placeable, nothing scored, no
  overlay to start again from. Set the state first, then call.
- A synthetic `KeyboardEvent` reaches a handler only through the field that
  handler reads. `maze3d/` switches on `e.code`, so an event built with `key`
  alone is dropped in silence and the check appears to drive a player who
  never moves. Set both.
- Reading a barcode wants two thresholds, not one. A single level for the
  whole line loses a packet lit from one side; a local average follows a
  blurred bar into its own middle and splits it. `barcode/` tries the plain
  one first and local windows after, over a few strengths of smoothing.
