# Part-Kit Plush Pattern Generator: Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task by task.

**Goal:** Build version 1 as approved in `docs/plans/2026-10-12-part-kit-plush-design.md`. The user uploads a picture, the app reads it into a part kit, the owner edits and approves a 3D part model, and the app produces true-scale panels that pass seven automatic checks, a US Letter PDF and written directions.

**Architecture:**
- A Python package `engine/plush` holds the part-kit format, geometry, flattening, the stuffing simulation, the checks, the PDF writer and the single OpenRouter vision call.
- The engine is served by FastAPI on 127.0.0.1 only.
- The existing Angular shell becomes the editor, with three.js for the 3D view. Its Express/SSR server is removed.
- Each project is a folder on disk under `projects/`, which git ignores.

**Tech stack:**
- Python 3.13, managed with uv 0.7.12.
- numpy, scipy, shapely, trimesh, libigl (flattening), reportlab (PDF writing), pypdf (PDF reading), pydantic, FastAPI and uvicorn, httpx, pytest.
- Angular 21, three.js and vitest.

All Python packages were installed and imported on this Mac (M4 Pro, Python 3.13.9) on 2026-10-12. The versions were numpy 2.5.4, scipy 1.18.1, shapely 2.2.0, trimesh 5.1.1, libigl 2.6.3 (`igl.lscm` and `igl.ARAP` present), reportlab 5.0.1, pydantic 2.14.1 and pytest 9.1.1.

---

## Rules for whoever executes this plan

1. **Real data only.**
   - No mocks, stubs, placeholder outputs or simulated API responses unless the owner approves them first.
   - Engine tests use mathematical shapes with exact known answers.
   - Validation tests use hand-written part kits that exist only in test files (approval gate G1).
2. **No model IDs in code.** The vision model comes from the `PLUSH_VISION_MODEL` environment variable, and the owner chooses it (gate G3).
3. **Commit after every task.** At the end of every phase, update `docs/PROGRESS.md` with the exact test counts (passed, failed, skipped) and commit it.
4. **Two-fix rule.** If the same failure survives two fix attempts, stop patching. List the plausible causes, add logging that would confirm the likeliest ones, then fix. Record the error, cause and fix in `ERROR_LOG.md` at the repo root.
5. **Report honestly.** Report only results backed by a command's output from the session. Give no time estimates.
6. **Bind locally.** Every server binds to 127.0.0.1.

## Approval gates (owner input needed)

| Gate | When | What the owner decides |
|---|---|---|
| G1 | Before Phase 1 | Allow hand-written part kits as **test-only** inputs (`engine/tests/`, never loaded by the app). |
| G2 | Before Phase 3 | Approve or change each starting value in `engine/settings.toml`, then set `approved_by_owner = true`. |
| G3 | Start of Phase 8 | Choose the vision model from OpenRouter's current list. |
| G4 | Phase 8 | Supply real character pictures for the live reading test, and approve sending them to OpenRouter and the chosen provider. |
| G5 | Phase 10 | Approve the final end-to-end run with a real picture (it sends the picture to the hosted model). |

**Proposed starting values for G2.** None of these has been validated by sewing.

| Setting | Proposed | Meaning |
|---|---|---|
| `seam_allowance_in` | 0.25 | Margin between the cut line and the stitch line |
| `min_turnable_width_in` | 0.625 | Narrowest stitched width that can still be turned right side out |
| `fabric_width_in` | 44.0 | Fabric width used for the cutting layout |
| `notch_spacing_in` | 2.0 | Largest gap between notches along a seam |
| `seam_length_diff_in` | 0.03125 (1/32 in) | Check 1: largest allowed difference between the two sides of a seam |
| `max_flatten_stretch` | 0.03 | Check 4: largest allowed edge stretch when a panel is flattened |
| `stuffed_mean_deviation` | 0.03 | Check 3: average distance from the target, as a fraction of the part's largest dimension |
| `stuffed_max_deviation` | 0.08 | Check 3: worst-point distance from the target, as the same fraction |
| `test_square_in` | 2.0 | Side of the PDF test square |
| `tile_overlap_in` | 0.5 | Overlap between tiled PDF pages |

## Level of detail

- **Phases 0 and 1** contain complete code. They were dry-run on 2026-10-12 in a scratch copy: 2 tests passed after Phase 0, 9 after Task 1.1, and 16 after Task 1.2.
- **Phases 2 to 10** list the tasks, files, the tests with their exact assertions, and acceptance commands. Each starts with a "Task N.0: expand" step, which turns the phase into the same step-level, code-complete form before any code is written. That expansion is committed and reviewed first. The numerical details (meshing resolution, simulation solver settings) depend on what the earlier phases measure, so writing that code now would be guesswork.

**Expected cumulative engine test counts (default run, live tests excluded):**

| End of phase | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| Tests | 2 | 16 | 29 | 42 | 48 | 59 | 74 | 83 | 85 |

If a phase's expansion changes its test count, update this table in the same commit.

---

## Phase 0: Python engine skeleton

### Task 0.1: Ignore engine build files and project data

**Files:**
- Modify: `.gitignore` (append at the end)

**Step 1: Append these lines to `.gitignore`**

```gitignore

# Python engine
engine/.venv/
__pycache__/
.pytest_cache/

# Project folders (pictures, kits, patterns) stay on this Mac
/projects/
```

**Step 2: Check the ignore rules**

Run: `git check-ignore -v engine/.venv/pyvenv.cfg engine/plush/__pycache__/settings.cpython-313.pyc engine/.pytest_cache/README.md projects/x`
Expected: four lines, each naming `.gitignore`. Use paths inside the folders: patterns ending in `/` match only directories, so a bare path to a folder that doesn't exist yet prints nothing. This was corrected during execution on 2026-10-12.

**Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore Python engine build files and local project folders"
```

### Task 0.2: Package, settings file and settings loader

**Files:**
- Create: `engine/pyproject.toml`
- Create: `engine/settings.toml`
- Create: `engine/plush/__init__.py`
- Create: `engine/plush/settings.py`
- Test: `engine/tests/test_settings.py`

**Step 1: Create `engine/pyproject.toml`**

```toml
[project]
name = "plush-engine"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
  "numpy>=2.5",
  "scipy>=1.18",
  "shapely>=2.2",
  "trimesh>=5.1",
  "libigl>=2.6",
  "reportlab>=5.0",
  "pypdf>=6.20",
  "fastapi>=0.143",
  "uvicorn>=0.54",
  "pydantic>=2.14",
  "httpx>=0.28",
]

[dependency-groups]
dev = ["pytest>=9.1"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["plush"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["live: calls the hosted vision model; run only with the owner's approval"]
addopts = "-m 'not live'"
```

**Step 2: Create `engine/settings.toml`**

```toml
# Pattern settings and check tolerances (US Letter, inches).
# Starting values PROPOSED 2026-10-12; none has been validated by sewing.
# Set approved_by_owner = true only after the owner approves each value.

[status]
approved_by_owner = false

[pattern]
seam_allowance_in = 0.25
min_turnable_width_in = 0.625
fabric_width_in = 44.0
notch_spacing_in = 2.0

[tolerances]
seam_length_diff_in = 0.03125
max_flatten_stretch = 0.03
stuffed_mean_deviation = 0.03
stuffed_max_deviation = 0.08

[pdf]
test_square_in = 2.0
tile_overlap_in = 0.5
```

**Step 3: Create `engine/plush/__init__.py`**

```python
"""Plush pattern engine: part kit -> panels -> checks -> PDF."""
```

**Step 4: Write the failing test `engine/tests/test_settings.py`**

```python
import pytest

from plush.settings import SETTINGS_PATH, load_settings


def test_settings_file_loads_with_positive_values():
    s = load_settings()
    assert s.approved_by_owner is False  # flips only after owner approval
    for name in (
        "seam_allowance_in", "min_turnable_width_in", "fabric_width_in",
        "notch_spacing_in", "seam_length_diff_in", "max_flatten_stretch",
        "stuffed_mean_deviation", "stuffed_max_deviation",
        "test_square_in", "tile_overlap_in",
    ):
        assert getattr(s, name) > 0, name


def test_missing_key_is_reported_by_name(tmp_path):
    text = SETTINGS_PATH.read_text().replace("fabric_width_in = 44.0\n", "")
    broken = tmp_path / "settings.toml"
    broken.write_text(text)
    with pytest.raises(KeyError, match="fabric_width_in"):
        load_settings(broken)
```

Gate G2 later changes `approved_by_owner` to `true`. Update the first assertion in that same commit.

**Step 5: Install and run the test to confirm it fails**

Run: `cd engine && uv sync && uv run pytest -q`
Expected: a collection error, `ModuleNotFoundError: No module named 'plush.settings'`.

**Step 6: Write `engine/plush/settings.py`**

```python
"""Pattern settings and check tolerances, read from engine/settings.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.toml"


@dataclass(frozen=True)
class Settings:
    approved_by_owner: bool
    seam_allowance_in: float
    min_turnable_width_in: float
    fabric_width_in: float
    notch_spacing_in: float
    seam_length_diff_in: float
    max_flatten_stretch: float
    stuffed_mean_deviation: float
    stuffed_max_deviation: float
    test_square_in: float
    tile_overlap_in: float


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Read settings; a missing key raises KeyError naming it."""
    with path.open("rb") as f:
        raw = tomllib.load(f)
    pattern, tol, pdf = raw["pattern"], raw["tolerances"], raw["pdf"]
    return Settings(
        approved_by_owner=bool(raw["status"]["approved_by_owner"]),
        seam_allowance_in=float(pattern["seam_allowance_in"]),
        min_turnable_width_in=float(pattern["min_turnable_width_in"]),
        fabric_width_in=float(pattern["fabric_width_in"]),
        notch_spacing_in=float(pattern["notch_spacing_in"]),
        seam_length_diff_in=float(tol["seam_length_diff_in"]),
        max_flatten_stretch=float(tol["max_flatten_stretch"]),
        stuffed_mean_deviation=float(tol["stuffed_mean_deviation"]),
        stuffed_max_deviation=float(tol["stuffed_max_deviation"]),
        test_square_in=float(pdf["test_square_in"]),
        tile_overlap_in=float(pdf["tile_overlap_in"]),
    )
```

**Step 7: Run the tests**

Run: `cd engine && uv run pytest -q`
Expected: `2 passed`

**Step 8: Commit (including the lock file)**

```bash
git add engine/pyproject.toml engine/uv.lock engine/settings.toml engine/plush/__init__.py engine/plush/settings.py engine/tests/test_settings.py
git commit -m "feat(engine): add Python engine package and settings loader"
```

### Task 0.3: Record Phase 0

Update `docs/PROGRESS.md`: add "Phase 0 done: engine tests 2 passed, 0 failed, 0 skipped" with the date, then commit it.

---

## Phase 1: The part-kit format

**Gate G1 applies before starting.**

### Task 1.1: Part kinds, fixed lists and JSON Schema

**Files:**
- Create: `engine/plush/parts.py`
- Test: `engine/tests/test_parts.py`

**Step 1: Write the failing tests `engine/tests/test_parts.py`**

```python
"""Validation rules for the part kit.

The kits below are hand-written inputs that exercise each rule. They live
only in this test file and are never loaded by the app.
"""

import copy
import json

import pytest
from pydantic import ValidationError

from plush.parts import Kit, kit_json_schema, parse_kit

BODY = {"kind": "rounded_solid", "id": "body", "name": "Body", "colour": "#C8A27A",
        "width": 0.5, "height": 0.55, "depth": 0.45, "flat_bottom": True}

BEAR = {
    "character_name": "Rule-check bear",
    "parts": [
        BODY,
        {"kind": "rounded_solid", "id": "head", "name": "Head", "colour": "#C8A27A",
         "width": 0.45, "height": 0.4, "depth": 0.4,
         "attach": {"parent": "body", "azimuth_deg": 0, "elevation_deg": 90}},
        {"kind": "flat_part", "id": "ear", "name": "Ear", "colour": "#C8A27A", "pair": True,
         "outline": "round", "width": 0.12, "height": 0.12, "inner_colour": "#F2D0D9",
         "attach": {"parent": "head", "azimuth_deg": 50, "elevation_deg": 60}},
        {"kind": "limb", "id": "arm", "name": "Arm", "colour": "#C8A27A", "pair": True,
         "length": 0.25, "start_thickness": 0.12, "end_thickness": 0.1, "end_shape": "round",
         "attach": {"parent": "body", "azimuth_deg": 80, "elevation_deg": 30, "pitch_deg": -40}},
        {"kind": "surface_feature", "id": "eye", "name": "Eye", "colour": "#1A1A1A", "pair": True,
         "shape": "circle", "method": "safety_eye", "width": 0.04, "height": 0.04,
         "attach": {"parent": "head", "azimuth_deg": 20, "elevation_deg": 10}},
    ],
}


def bear():
    return copy.deepcopy(BEAR)


def part(kit, part_id):
    return next(p for p in kit["parts"] if p["id"] == part_id)


def test_minimal_kit_with_only_a_body_is_valid():
    kit = parse_kit(json.dumps({"character_name": "Blob", "parts": [BODY]}))
    assert kit.parts[0].kind == "rounded_solid"


def test_bear_kit_is_valid():
    kit = parse_kit(json.dumps(bear()))
    assert [p.id for p in kit.parts] == ["body", "head", "ear", "arm", "eye"]


def test_rejects_unknown_part_kind():
    kit = bear()
    part(kit, "arm")["kind"] = "tentacle"
    with pytest.raises(ValidationError):
        parse_kit(json.dumps(kit))


def test_rejects_value_outside_fixed_list():
    kit = bear()
    part(kit, "arm")["end_shape"] = "claw"
    with pytest.raises(ValidationError, match="end_shape"):
        parse_kit(json.dumps(kit))


def test_rejects_unexpected_field():
    kit = bear()
    part(kit, "head")["sparkle"] = True
    with pytest.raises(ValidationError, match="sparkle"):
        parse_kit(json.dumps(kit))


def test_rejects_bad_colour():
    kit = bear()
    part(kit, "body")["colour"] = "brown"
    with pytest.raises(ValidationError, match="colour"):
        parse_kit(json.dumps(kit))


def test_json_schema_carries_the_fixed_lists():
    schema = json.dumps(kit_json_schema())
    for value in ("flat_sole", "long_oval", "safety_eye", "rounded_solid", "surface_feature"):
        assert f'"{value}"' in schema
    assert Kit.model_json_schema()["additionalProperties"] is False
```

**Step 2: Run to confirm it fails**

Run: `cd engine && uv run pytest -q`
Expected: a collection error, `ModuleNotFoundError: No module named 'plush.parts'`.

**Step 3: Write `engine/plush/parts.py`**

```python
"""The part kit: the fixed vocabulary every character is built from.

Sizes are fractions of the finished height, so changing the height
rescales the whole character. The vision model must return exactly this
format; anything else is rejected by parse_kit, never guessed or repaired.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Fraction = Annotated[float, Field(gt=0, le=2)]
Colour = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
PartId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")]


class EndShape(StrEnum):
    ROUND = "round"
    FLAT_SOLE = "flat_sole"
    POINT = "point"


class Outline(StrEnum):
    ROUND = "round"
    POINTED = "pointed"
    LONG_OVAL = "long_oval"
    LEAF = "leaf"


class FeatureShape(StrEnum):
    CIRCLE = "circle"
    OVAL = "oval"
    TRIANGLE = "triangle"
    LINE = "line"


class FeatureMethod(StrEnum):
    EMBROIDERY = "embroidery"
    APPLIQUE = "applique"
    SAFETY_EYE = "safety_eye"


class Attachment(BaseModel):
    """Where a part sits on its parent, as a direction from the parent's centre."""

    model_config = ConfigDict(extra="forbid")
    parent: PartId
    azimuth_deg: Annotated[float, Field(ge=-180, le=180)]  # 0 = front, +90 = character's left
    elevation_deg: Annotated[float, Field(ge=-90, le=90)]  # +90 = top
    yaw_deg: Annotated[float, Field(ge=-90, le=90)] = 0.0
    pitch_deg: Annotated[float, Field(ge=-90, le=90)] = 0.0


class _PartBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: PartId
    name: Annotated[str, Field(min_length=1, max_length=60)]
    colour: Colour
    # pair = this part plus its mirror image across the centre line (left/right twins)
    pair: bool = False


class RoundedSolid(_PartBase):
    kind: Literal["rounded_solid"]
    width: Fraction
    height: Fraction
    depth: Fraction
    taper: Annotated[float, Field(ge=-0.5, le=0.5)] = 0.0  # + = wider at the bottom
    flat_bottom: bool = False
    attach: Attachment | None = None  # None only for the root body


class Limb(_PartBase):
    kind: Literal["limb"]
    length: Fraction
    start_thickness: Fraction
    end_thickness: Fraction
    bend_deg: Annotated[float, Field(ge=0, le=120)] = 0.0
    end_shape: EndShape
    attach: Attachment


class FlatPart(_PartBase):
    kind: Literal["flat_part"]
    outline: Outline
    width: Fraction
    height: Fraction
    puffiness: Annotated[float, Field(ge=0, le=1)] = 0.2
    cupping: Annotated[float, Field(ge=0, le=1)] = 0.0
    inner_colour: Colour | None = None
    attach: Attachment


class SurfaceFeature(_PartBase):
    kind: Literal["surface_feature"]
    shape: FeatureShape
    method: FeatureMethod
    width: Fraction
    height: Fraction
    attach: Attachment


Part = Annotated[RoundedSolid | Limb | FlatPart | SurfaceFeature, Field(discriminator="kind")]


class Kit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    character_name: Annotated[str, Field(min_length=1, max_length=80)]
    parts: Annotated[list[Part], Field(min_length=1)]


def parse_kit(raw: str | bytes) -> Kit:
    """Validate a kit from JSON. Raises pydantic.ValidationError on any problem."""
    return Kit.model_validate_json(raw)


def kit_json_schema() -> dict:
    """JSON Schema sent to the vision model as its required output format."""
    return Kit.model_json_schema()
```

**Step 4: Run the tests**

Run: `cd engine && uv run pytest -q`
Expected: `9 passed`

**Step 5: Commit**

```bash
git add engine/plush/parts.py engine/tests/test_parts.py
git commit -m "feat(engine): add part-kit format with fixed lists and JSON Schema"
```

### Task 1.2: Structure rules (one root, valid parents, no loops, pairs off the centre line)

**Files:**
- Modify: `engine/plush/parts.py` (the import line, and the `Kit` class)
- Test: `engine/tests/test_parts.py` (append)

**Step 1: Append the failing tests to `engine/tests/test_parts.py`**

```python
def test_rejects_two_roots():
    kit = bear()
    del part(kit, "head")["attach"]
    with pytest.raises(ValidationError, match="exactly one root part"):
        parse_kit(json.dumps(kit))


def test_rejects_paired_root():
    kit = bear()
    part(kit, "body")["pair"] = True
    with pytest.raises(ValidationError, match="cannot be a pair"):
        parse_kit(json.dumps(kit))


def test_rejects_unknown_parent():
    kit = bear()
    part(kit, "ear")["attach"]["parent"] = "hat"
    with pytest.raises(ValidationError, match="unknown part 'hat'"):
        parse_kit(json.dumps(kit))


def test_rejects_duplicate_ids():
    kit = bear()
    part(kit, "arm")["id"] = "ear"
    with pytest.raises(ValidationError, match="duplicate part ids"):
        parse_kit(json.dumps(kit))


def test_rejects_attaching_to_a_surface_feature():
    kit = bear()
    part(kit, "ear")["attach"]["parent"] = "eye"
    with pytest.raises(ValidationError, match="cannot attach to surface feature"):
        parse_kit(json.dumps(kit))


def test_rejects_paired_part_on_centre_line():
    kit = bear()
    part(kit, "ear")["attach"]["azimuth_deg"] = 0
    with pytest.raises(ValidationError, match="off the centre line"):
        parse_kit(json.dumps(kit))


def test_rejects_attachment_loop():
    kit = bear()
    part(kit, "head")["attach"]["parent"] = "arm"
    part(kit, "arm")["attach"]["parent"] = "head"
    with pytest.raises(ValidationError, match="attachment loop"):
        parse_kit(json.dumps(kit))
```

**Step 2: Run to confirm the new tests fail**

Run: `cd engine && uv run pytest -q`
Expected: `7 failed, 9 passed`. Each new test fails with "DID NOT RAISE".

**Step 3: Add the structure rules to `engine/plush/parts.py`**

Change the import line to:

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator
```

Add this method inside `class Kit`, below the `parts` field:

```python
    @model_validator(mode="after")
    def _check_structure(self) -> Kit:
        ids = [p.id for p in self.parts]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate part ids: {dupes}")

        roots = [p for p in self.parts if p.attach is None]
        if len(roots) != 1:
            raise ValueError(f"exactly one root part is required, found {len(roots)}")
        if roots[0].pair:
            raise ValueError(f"root part {roots[0].id!r} cannot be a pair")

        by_id = {p.id: p for p in self.parts}
        for p in self.parts:
            if p.attach is None:
                continue
            parent = by_id.get(p.attach.parent)
            if parent is None:
                raise ValueError(f"part {p.id!r} attaches to unknown part {p.attach.parent!r}")
            if parent.kind == "surface_feature":
                raise ValueError(f"part {p.id!r} cannot attach to surface feature {parent.id!r}")
            if p.pair and not 1 <= abs(p.attach.azimuth_deg) <= 179:
                raise ValueError(f"paired part {p.id!r} must sit off the centre line")

        for p in self.parts:
            seen: set[str] = set()
            cur = p
            while cur.attach is not None:
                if cur.id in seen:
                    raise ValueError(f"attachment loop involving part {p.id!r}")
                seen.add(cur.id)
                cur = by_id[cur.attach.parent]
        return self
```

**Step 4: Run the tests**

Run: `cd engine && uv run pytest -q`
Expected: `16 passed`

**Step 5: Commit, and record Phase 1 in `docs/PROGRESS.md`**

```bash
git add engine/plush/parts.py engine/tests/test_parts.py docs/PROGRESS.md
git commit -m "feat(engine): enforce part-kit structure rules"
```

---

## Phase 2: Part geometry at finished size

**Task 2.0: Expand.** Expand this phase to step-level form with complete code, as in Phases 0 and 1. Commit the expansion before writing any code.

The rule-check bear from `test_parts.py` moves into a shared test module, `engine/tests/kits.py`, which is still test-only. All meshes are `trimesh.Trimesh` objects in inches. The axes are x = the character's left, y = up, z = front.

**Task 2.1: `engine/plush/geometry/rounded_solid.py`**

Function: `rounded_solid_mesh(part, scale_in) -> Trimesh`. 4 tests in `engine/tests/test_geometry.py`:
- With equal width, height and depth and `taper=0`, the mesh volume is within 1% of 4/3·π·r³.
- The bounding box equals (width, height, depth) × `scale_in`, within 0.5%.
- With `taper=0.3`, the widest cross-section is below the centre.
- With `flat_bottom=True`, at least 3 vertices lie within 1e-6 in of the lowest y, and their convex hull has area greater than 0.

**Task 2.2: `engine/plush/geometry/limb.py`**

Function: `limb_mesh(part, scale_in) -> Trimesh`. The mesh is open at the start, where the limb is sewn to its parent. 3 tests:
- A straight limb with equal end thicknesses and `flat_sole` has side area within 1% of π·d·L.
- A limb with `bend_deg=60` has a centreline length of `length × scale_in`, within 0.5%.
- With `end_shape=point`, the end radius is below 1e-6.

**Task 2.3: `engine/plush/geometry/flat_part.py`**

Functions: `outline_polygon(part, scale_in) -> shapely.Polygon` and `flat_part_mesh(...)`. 3 tests:
- The round outline's area is within 1% of π·w·h/4.
- All four outlines produce valid polygons (`is_valid`).
- With `puffiness=0`, the mesh thickness is no more than 0.01 in.

**Task 2.4: `engine/plush/geometry/assemble.py`**

Function: `assemble(kit, finished_height_in) -> dict[str, Trimesh]`. Pairs are expanded into `<id>_left` and `<id>_right`. 3 tests:
- The two meshes of a pair mirror each other across x = 0, within 1e-9.
- Each child's attachment point lies within 0.01 in of its parent's surface.
- The assembled bear's bounding-box height equals `finished_height_in`, within 1e-6. Assembly scales uniformly to make this exact.

**Acceptance:** `cd engine && uv run pytest -q` reports 29 passed. Record the count in PROGRESS.md and commit.

## Phase 3: Panels, flattening and seams

**Gate G2 applies before starting.** Then **Task 3.0: Expand.**

**Task 3.1: `engine/plush/flatten.py`**

Function: `flatten(mesh) -> FlatPanel` using `igl.lscm(V, F, b, bc)`, followed by a least-squares scale fit to the 3D edge lengths and an optional `igl.ARAP` refinement. The result reports the maximum and mean edge stretch. 3 tests:
- A cylinder of radius 1 and length 3, cut along one line, flattens to a rectangle. The width equals the mesh's cross-section perimeter within 0.1%, the height is 3 within 0.1%, and the maximum stretch is below 1e-3.
- A flat input stays the same, with stretch below 1e-9.
- The stretch statistics are present and are 0 or more.

**Task 3.2: `engine/plush/panels.py` (constructions)** — 4 tests:
- A sphere built with n gores gives n panels whose flattened areas are equal within 0.5%.
- An elongated rounded solid gets side panels plus a gusset (3 panels).
- A `flat_sole` limb gives a wrapped panel plus a sole; `round` and `point` limbs get no sole.
- A flat part gives two mirror-image pieces, plus an inner piece when `inner_colour` is set.

**Task 3.3: `engine/plush/seams.py`** — 4 tests:
- Every seam has exactly two sides.
- After equalising, the two sides of each seam differ by no more than `seam_length_diff_in`.
- Both sides of a seam have the same number of notches, with no gap larger than `notch_spacing_in`.
- Each closed part has exactly one stuffing gap.

**Task 3.4: Adaptive panel count** — 2 tests:
- For a sphere, the engine picks the smallest n whose stretch is within `max_flatten_stretch`, and n − 1 exceeds the limit.
- If the cap of 12 gores still can't meet the limit, the engine raises an error naming the part.

**Acceptance:** 42 passed.

## Phase 4: Stuffing correction

**Task 4.0: Expand.**

**Task 4.1: `engine/plush/inflate.py`**

Simulate sewn panels as a low-stretch membrane under internal pressure, by minimising energy with `scipy.optimize`. 3 tests:
- **Mylar balloon reference.** Two discs of radius a = 3 in, sewn at the rim, must inflate to:
  - a rim radius r = a / 1.3110287771, within 3%;
  - a thickness τ = 2 × 0.5990701173 × r, within 3%.

  The constants come from Wikipedia, "Mylar balloon (geometry)", citing Paulsen (1994), *American Mathematical Monthly* 101(10):953–958. Check them against that page before writing the test.
- No edge is longer than its rest length by more than 0.5%.
- A mirror-symmetric input gives a result that is symmetric within 1e-3 in.

**Task 4.2: Correction loop.** Repeat simulate → compare with target → adjust panel outlines. 3 tests:
- For a sphere with 6 gores, the final mean and maximum deviations are within the `stuffed_*` tolerances.
- The final deviation is lower than the starting deviation.
- If the loop hasn't converged when it reaches the iteration cap, the result is returned with `converged=False` and the measured values. It is never raised silently.

**Acceptance:** 48 passed.

## Phase 5: Finishing and checks 1, 3, 4 and 5

**Task 5.0: Expand.**

**Task 5.1: `engine/plush/allowance.py`** — a true outward offset with shapely `buffer`. 3 tests:
- A 2 × 2 in stitch square with a 0.25 in allowance and a mitre join gives a cut polygon of area exactly 2.5², within 1e-9.
- A circle of radius 1 gives a cut area within 0.5% of π·1.25².
- Every point on the cut line is at least `allowance − 1e-6` from the stitch line.

**Task 5.2: Labels and arrows** — 2 tests:
- The label contains the name, the cut count and the mirror flag.
- A limb panel's grain arrow is parallel to the limb axis.

**Task 5.3: `engine/plush/checks.py`.** Checks 1, 3, 4 and 5 each return `CheckResult(name, passed, measured, limit, where)`. 6 tests, one pass case and one fail case for each of checks 1, 4 and 5:
- Shortening one seam side by 0.1 in makes check 1 fail and name the seam.
- Forcing 2 gores on the head makes check 4 fail.
- An arm thinner than `min_turnable_width_in` makes check 5 fail and name the arm.

Check 3 is covered by Task 4.2.

**Acceptance:** 59 passed.

## Phase 6: Outputs, and checks 2 and 6

**Task 6.0: Expand.**

**Task 6.1: `engine/plush/pdf.py`** (reportlab, Letter 612 × 792 pt, tiled with overlap). Check 2 is `check_true_scale(pdf_path, pattern)`, which reads the PDF's drawing operations with pypdf. 5 tests:
- The test square measures exactly 144 × 144 pt.
- Each piece's outline, reassembled across tiles, matches the engine's outline × 72 within 0.01 pt.
- Every page is 612 × 792.
- The page map lists every tile.
- A PDF deliberately drawn at 0.97 scale fails check 2.

**Task 6.2: `engine/plush/layout.py`** (packing pieces on the fabric with the fur running one way) — 4 tests:
- Every piece fits within the fabric width.
- No two pieces overlap (intersection area below 1e-9).
- No piece is rotated, and mirrored pieces are flipped.
- The fabric length is reported for each colour.

**Task 6.3: `engine/plush/directions.py` and check 6** — 4 tests:
- Every piece appears in exactly one cut step.
- Every seam appears in exactly one sew step.
- Removing a step makes check 6 fail and name what's missing.
- Feature steps come before the seams that close the part.

**Task 6.4: Materials** — 1 test: the stuffed volume equals the inflated mesh's `trimesh` volume, in cubic inches.

**Task 6.5: Unapproved settings** — 1 test: while `approved_by_owner = false`, page 1 says "Tolerance settings not yet approved by owner".

**Acceptance:** 74 passed.

## Phase 7: Projects, versions, check 7 and the local service

**Task 7.0: Expand.**

**Task 7.1: `engine/plush/projects.py`.** The folder layout is `projects/<slug>/` containing `picture.*`, `kit-v<n>.json`, `approved.json`, `pattern/`, `report.json` and `pattern.pdf`. The version ID is the sha256 of the canonical kit JSON plus the finished height. 4 tests (using `tmp_path`):
- Creating a project stores the picture.
- Drafts are saved as numbered versions.
- Approving records the version ID.
- Check 7: building from a draft that changed since approval is refused, and the pattern carries the approved version ID.

**Task 7.2: `engine/plush/server.py`** (FastAPI, run with `uv run uvicorn plush.server:app --host 127.0.0.1 --port 8765`). 5 tests, using FastAPI's in-process `TestClient` against the real app:
- Starting without `OPENROUTER_API_KEY` or `PLUSH_VISION_MODEL` raises an error that names them.
- An invalid kit sent with PUT gets a 422 containing the validation message.
- POST `/mesh` returns meshes for the bear.
- POST `/pattern` on an unapproved project gets a 409.
- The full flow (approve → pattern) returns a report with 7 checks. A PDF is served only when all 7 pass; otherwise the response is 409 listing the failing checks.

**Task 7.3: Measure.** Time POST `/mesh` for the bear on this Mac and record the measured number in PROGRESS.md. The owner judges whether editing feels responsive. Only if it doesn't, propose a TypeScript port of the geometry with a parity test, and ask before building it.

**Acceptance:** 83 passed.

## Phase 8: Reading the picture (hosted vision model)

**Task 8.0: Gate G3.**
1. Fetch `https://openrouter.ai/api/v1/models`.
2. List the models that accept image input and support `structured_outputs` or `response_format`.
3. The owner picks one. It is stored in `.env` as `PLUSH_VISION_MODEL` and never written into code.

Then expand this phase.

**Task 8.1: `engine/plush/vision.py`.** `build_request(picture_bytes, mime, model)` is a pure function. `read_picture(...)` calls OpenRouter with httpx and parses the reply with `parse_kit`. On any failure it raises `ReadError` with the reason. There is never a fallback kit. 2 offline tests:
- `build_request` includes the kit JSON Schema and the image as a data URL.
- With `HTTPS_PROXY=http://127.0.0.1:9` set through `monkeypatch.setenv`, `read_picture` raises `ReadError` mentioning the network. This runs the real code path, with outbound traffic blocked.

**Task 8.2: Live test (gate G4)**, marked `@pytest.mark.live`. It reads the owner's pictures from `projects/_live_pictures/`, which git ignores, and asserts that each returns a valid `Kit`. It records the model ID and the measured response times in PROGRESS.md.
- Run: `cd engine && uv run pytest -m live -q`, only with approval.
- Live tests are not counted in the default totals.

**Acceptance:** 85 passed in the default run, with the live results recorded separately.

## Phase 9: Angular front end

**Task 9.0: Expand.**

**Task 9.1: Remove the old server code.**
- Delete `src/server.ts`, `src/main.server.ts`, `src/app/app.config.server.ts` and `src/app/app.routes.server.ts`.
- Remove `server`, `outputMode` and `ssr` from `angular.json`.
- Remove `express`, `@angular/ssr`, `@angular/platform-server`, `@google/genai` and `@types/express` from `package.json`.
- Add `proxy.conf.json` mapping `/api` to `http://127.0.0.1:8765`.
- Change the `dev` script to `ng serve --host=127.0.0.1 --port=3000 --proxy-config proxy.conf.json`.

Acceptance:
- `npx ng build` succeeds.
- `grep -rnE "localStorage|@google/genai|express" src package.json` returns nothing.

**Task 9.2: `src/app/api.ts`.** Every call checks `response.ok`, and error responses become messages shown on screen. 2 tests: a non-OK `Response` maps to the server's error message; an OK response passes its JSON through.

**Task 9.3: `src/app/editor-state.ts`** (pure TypeScript) — 4 tests:
- Editing a pair changes both copies.
- Unlinking a pair gives two parts with mirrored azimuths.
- Approving freezes the version; editing afterwards creates a new draft and marks the approval as out of date.
- A limb thinner than `min_turnable_width_in` raises the too-small warning.

**Task 9.4: Viewer component** (three.js). It shows meshes from `/mesh`, overlays the picture in a front orthographic view, and lets the owner pick parts. 1 test: the component is created, and the overlay can be toggled.

**Task 9.5: Screens.** Upload, Read (with error states), Shape, Pattern (a table of the 7 checks) and Output (PDF download and directions). 2 tests: the checks table renders 7 rows from a `report.json` produced by the real engine; the Output screen is unavailable until all checks pass.

**Acceptance:** `npx ng test --watch=false` reports 10 passed: the existing smoke test plus 9 new. The owner then walks through the screens in the browser.

## Phase 10: Documentation and the end-to-end run

**Task 10.1:**
- Rewrite `README.md`: how to set up `.env` (`OPENROUTER_API_KEY`, `PLUSH_VISION_MODEL`), how to start both servers, and how to run the tests.
- Replace the contents of `handoff.md` with a pointer to `docs/PROGRESS.md` and the design. The old text stays in git history (commit `2aa1874`).

**Task 10.2 (gate G5): End-to-end run** with one real picture: upload → read → edit → approve → pattern (all 7 checks pass) → PDF. Record each check's measured values in PROGRESS.md.

**Task 10.3:** Final PROGRESS.md entry: exact engine and Angular test counts, open items, and anything skipped.
