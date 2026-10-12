"""Measure check 4 (flattening stretch) and check 3 (stuffed shape) for 6, 8 and 12 gores.

Run from engine/:  uv run python tools/gore_comparison.py
Shapes: a 6 in ball, and the head of the test-only bear kit (tests/kits.py) at 12 in tall.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from kits import bear  # noqa: E402

from plush.geometry.assemble import assemble  # noqa: E402
from plush.panels import gore_panels  # noqa: E402
from plush.parts import RoundedSolid, parse_kit  # noqa: E402
from plush.settings import load_settings  # noqa: E402
from plush.stuffing import stuff  # noqa: E402


def main() -> None:
    s = load_settings()
    ball = RoundedSolid(kind="rounded_solid", id="ball", name="Ball", colour="#000000",
                        width=0.5, height=0.5, depth=0.5)
    kit = parse_kit(json.dumps(bear()))
    placed = assemble(kit, 12.0)
    head = next(p for p in kit.parts if p.id == "head")
    print(f"Limits: flattening stretch {s.max_flatten_stretch:.0%}; stuffed deviation mean "
          f"{s.stuffed_mean_deviation:.0%}, worst {s.stuffed_max_deviation:.0%} (of the part's largest size)")
    print("shape | gores | flattening stretch (check 4) | stuffed mean / worst (check 3) | passes 3 / 4")
    shapes = (("ball, 6.00 in across", ball, 12.0),
              (f"bear head, {placed['head'].mesh.extents.max():.2f} in across", head, placed["head"].scale_in))
    for label, part, scale in shapes:
        for n in (6, 8, 12):
            panels = gore_panels(part, scale, n)
            flat = max(p.max_stretch for p in panels)
            r = stuff(panels, s.stuffed_mean_deviation, s.stuffed_max_deviation)
            p3 = r.mean_deviation <= s.stuffed_mean_deviation and r.worst_deviation <= s.stuffed_max_deviation
            print(f"{label} | {n} | {flat:.2%} | {r.mean_deviation:.2%} / {r.worst_deviation:.2%} | "
                  f"{'yes' if p3 else 'no'} / {'yes' if flat <= s.max_flatten_stretch else 'no'}", flush=True)


if __name__ == "__main__":
    main()
