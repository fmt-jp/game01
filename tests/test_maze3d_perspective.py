"""A straight wall must project to a straight edge, in the right place.

Perspective maps 3D straight lines to 2D straight lines, always. So the top of
a long straight corridor wall has to come out as a straight line of pixels --
and at a position the projection formula predicts exactly:

    depth(x)  = d / (tan(fov/2) * |cameraX|)        d = distance to the wall
    unit(x)   = W / (2 * tan(fov/2) * depth)        pixels per world unit
    top_y(x)  = horizon - (wallHeight - eye) * unit

This renders the corridor through the real renderer, reads the wall/sky
boundary out of the pixels, and checks it against both.
"""
import sys
from playwright.sync_api import sync_playwright
from _common import CHROMIUM

W, H = 420, 300
HALF_WIDTH = 1.5          # camera sits this far from each corridor wall

RENDER = """
([W, H]) => {
  // A corridor 21 blocks long and 3 wide, so the top of the wall stays on
  // screen instead of running off it.
  const cols = 21, rows = 5;
  const blocks = new Uint8Array(cols * rows).fill(0);
  for (let bx = 0; bx < cols; bx++) { blocks[bx] = 1; blocks[4 * cols + bx] = 1; }
  for (let by = 1; by <= 3; by++) { blocks[by * cols] = 1; blocks[by * cols + cols - 1] = 1; }
  const maze = {w: 10, h: 2, cols, rows, blocks};

  const canvas = document.createElement("canvas");
  const view = MazeView.create(canvas);
  view.resize(W, H, 1);
  view.draw({maze, camera: {x: 2.5, y: 2.5, angle: 0, bob: 0}, sprites: []});

  const g = canvas.getContext("2d");
  const data = g.getImageData(0, 0, canvas.width, canvas.height).data;
  const edge = [];
  for (let x = 0; x < canvas.width; x++) {
    let found = -1;
    for (let y = 0; y < canvas.height; y++) {
      const i = (y * canvas.width + x) * 4;
      const r = data[i], gg = data[i + 1], b = data[i + 2];
      if (r > gg + 8 && gg > b + 8) { found = y; break; }   // wood: warm, r > g > b
    }
    edge.push(found);
  }
  return {edge, fov: MazeView.FOV, wallH: MazeView.WALL_H, eye: MazeView.EYE};
}
"""

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROMIUM)
    p = b.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("http://localhost:8390/maze3d/index.html")
    p.wait_for_timeout(600)
    res = p.evaluate(RENDER, [W, H])
    if errs:
        print("page errors:", errs)
    b.close()

import math
edge = res["edge"]
T = math.tan(res["fov"] / 2)
rise = res["wallH"] - res["eye"]

rows = []
for x, y in enumerate(edge):
    camera_x = (2 * (x + 0.5)) / W - 1
    if abs(camera_x) < 0.25:      # near the middle the ray reaches the far end instead
        continue
    if y <= 1:                    # edge ran off the top: nothing to measure
        continue
    depth = HALF_WIDTH / (T * abs(camera_x))
    unit = W / (2 * T * depth)
    rows.append((x, y, H / 2 - rise * unit))

print(f"columns measured: {len(rows)}")
worst_abs = max(abs(y - want) for _, y, want in rows)
print(f"worst gap from the projection formula: {worst_abs:.2f} px")

left = [(x, y) for x, y, _ in rows if x < W / 2]
right = [(x, y) for x, y, _ in rows if x >= W / 2]


def bend(points):
    n = len(points)
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    den = sum((p[0] - mx) ** 2 for p in points)
    slope = sum((p[0] - mx) * (p[1] - my) for p in points) / den
    return max(abs(y - (slope * (x - mx) + my)) for x, y in points)


bl, br = bend(left), bend(right)
print(f"bend away from a straight line: left {bl:.2f} px, right {br:.2f} px")

ok = worst_abs <= 1.5 and max(bl, br) <= 1.5
print("\n" + ("STRAIGHT, and where the maths says it should be"
              if ok else "WRONG: the wall does not project where it should"))
sys.exit(0 if ok else 1)
