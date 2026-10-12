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
| Tests | 2 | 16 | 35 | 48 | 54 | 65 | 80 | 89 | 91 |

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

**Task 2.0: Expand. Done 2026-10-12.** Developed and run in a scratch copy first: 35 passed.

Changes from the phase outline, found while expanding:
- **New dependency `rtree`.** trimesh's ray casting and closest-point functions need it. Version 1.4.1 was installed and checked on this Mac.
- **`assemble` returns more than meshes.** It returns `dict[str, Placed]`: mesh, rotation, the anchor point on the parent, and the parent's name. Later phases need the anchor and parent for attachment notches.
- **Two new kit rules, with a test each.**
  - Part ids may not end in `_left` or `_right`, because pairs use those endings.
  - A paired part must hang from a symmetric part: one on the centre line, not turned, and not itself paired. Mirroring is only correct there.
- **Kit checks run in a set order:** known parents, then loop detection, then the pair rules. This is so the symmetry walk can never loop forever.
- **Normals are blended from the triangle's corners.** Attachment uses this smooth normal instead of the hit triangle's face normal. A ray that lands exactly on a vertex otherwise tilts the child (this showed as a mirrored ear 0.022 in off the head).
- **One test file per module,** so each task's tests can fail first on their own.

The axes are x = the character's left, y = up and z = front. Units are inches.

### Task 2.1: Add `rtree`; move the test kits into `tests/kits.py`

**Files:**
- Modify: `engine/pyproject.toml` and `engine/uv.lock` (through `uv add`)
- Create: `engine/tests/kits.py`
- Modify: `engine/tests/test_parts.py` (import the kits instead of defining them)

**Step 1:** Run `cd engine && uv add rtree`.
Expected: `pyproject.toml` gains `"rtree>=1.4.1"`.

**Step 2: Create `engine/tests/kits.py`**

```python
"""Hand-written part kits used only by the tests (approved as test-only inputs, gate G1).

They exercise validation and geometry rules; the app never loads them.
"""

import copy

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


def bear() -> dict:
    return copy.deepcopy(BEAR)


def part(kit: dict, part_id: str) -> dict:
    return next(p for p in kit["parts"] if p["id"] == part_id)
```

**Step 3: Replace `engine/tests/test_parts.py` with**

```python
"""Validation rules for the part kit (test kits live in tests/kits.py)."""

import json

import pytest
from pydantic import ValidationError

from plush.parts import Kit, kit_json_schema, parse_kit

from kits import BODY, bear, part

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

**Step 4:** Run `cd engine && uv run pytest -q`.
Expected: `16 passed`, the same as before.

**Step 5:** Commit: `git add engine/pyproject.toml engine/uv.lock engine/tests/kits.py engine/tests/test_parts.py && git commit -m "test(engine): share test kits; add rtree for mesh queries"`

### Task 2.2: Kit rules for reserved id endings and symmetric pairs

**Files:** modify `engine/plush/parts.py`; test `engine/tests/test_parts.py` (append).

**Step 1: Append these tests to `engine/tests/test_parts.py`**

```python
def test_rejects_pair_on_a_part_that_is_not_symmetric():
    kit = bear()
    kit["parts"].append(
        {"kind": "limb", "id": "claw", "name": "Claw", "colour": "#FFFFFF", "pair": True,
         "length": 0.03, "start_thickness": 0.02, "end_thickness": 0.01, "end_shape": "point",
         "attach": {"parent": "arm", "azimuth_deg": 30, "elevation_deg": 0}})
    with pytest.raises(ValidationError, match="must attach to a symmetric part"):
        parse_kit(json.dumps(kit))


def test_rejects_ids_ending_in_left_or_right():
    kit = bear()
    part(kit, "head")["id"] = "head_left"
    for p in kit["parts"]:
        if p.get("attach", {}).get("parent") == "head":
            p["attach"]["parent"] = "head_left"
    with pytest.raises(ValidationError, match="may not end in _left or _right"):
        parse_kit(json.dumps(kit))
```

**Step 2:** Run `cd engine && uv run pytest -q`.
Expected: `2 failed, 16 passed`. Both fail with "DID NOT RAISE".

**Step 3: In `engine/plush/parts.py`, replace the whole `_check_structure` method of `Kit` with**

```python
    @model_validator(mode="after")
    def _check_structure(self) -> Kit:
        ids = [p.id for p in self.parts]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate part ids: {dupes}")
        reserved = sorted(i for i in ids if i.endswith(("_left", "_right")))
        if reserved:
            raise ValueError(f"part ids may not end in _left or _right (used for pairs): {reserved}")

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

        for p in self.parts:
            seen: set[str] = set()
            cur = p
            while cur.attach is not None:
                if cur.id in seen:
                    raise ValueError(f"attachment loop involving part {p.id!r}")
                seen.add(cur.id)
                cur = by_id[cur.attach.parent]

        for p in self.parts:
            if not p.pair:
                continue
            if not 1 <= abs(p.attach.azimuth_deg) <= 179:
                raise ValueError(f"paired part {p.id!r} must sit off the centre line")
            if not _is_symmetric(by_id[p.attach.parent], by_id):
                raise ValueError(
                    f"paired part {p.id!r} must attach to a symmetric part "
                    "(one on the centre line, not turned, and not itself paired)"
                )
        return self
```

**and add this function directly above `parse_kit`:**

```python
def _is_symmetric(part, by_id) -> bool:
    """True if the part and all its ancestors sit on the centre line, unturned and unpaired.

    Left/right twins are mirrored across the centre plane, which is only
    correct when everything they hang from is itself mirror-symmetric.
    """
    while part.attach is not None:
        if part.pair or part.attach.yaw_deg != 0 or abs(part.attach.azimuth_deg) not in (0, 180):
            return False
        part = by_id[part.attach.parent]
    return True
```

**Step 4:** Run `cd engine && uv run pytest -q`.
Expected: `18 passed`.

**Step 5:** Commit: `git add engine/plush/parts.py engine/tests/test_parts.py && git commit -m "feat(engine): reserve _left/_right ids; pairs must hang from symmetric parts"`

### Task 2.3: Rounded solids

**Files:**
- Create: `engine/plush/geometry/__init__.py` and `engine/plush/geometry/rounded_solid.py`
- Test: `engine/tests/test_rounded_solid.py`

**Step 1: Write the failing test file `engine/tests/test_rounded_solid.py`**

```python
import numpy as np
import pytest
import shapely

from plush.geometry.rounded_solid import rounded_solid_mesh
from plush.parts import RoundedSolid

SCALE = 10.0  # inches per unit of finished height


def solid(**kw):
    base = {"kind": "rounded_solid", "id": "s", "name": "S", "colour": "#000000",
            "width": 0.5, "height": 0.5, "depth": 0.5}
    return RoundedSolid(**{**base, **kw})


def test_round_solid_volume_matches_sphere():
    mesh = rounded_solid_mesh(solid(), SCALE)
    r = 0.25 * SCALE
    assert mesh.volume == pytest.approx(4 / 3 * np.pi * r**3, rel=0.01)


def test_rounded_solid_bounding_box_matches_size():
    mesh = rounded_solid_mesh(solid(width=0.4, height=0.6, depth=0.3, taper=0.3, flat_bottom=True), SCALE)
    assert mesh.extents == pytest.approx([4.0, 6.0, 3.0], rel=0.005)


def test_taper_puts_widest_section_below_centre():
    mesh = rounded_solid_mesh(solid(taper=0.3), SCALE)
    widest = mesh.vertices[np.argmax(np.abs(mesh.vertices[:, 0]))]
    assert widest[1] < 0


def test_flat_bottom_has_flat_base():
    v = rounded_solid_mesh(solid(flat_bottom=True), SCALE).vertices
    base = v[v[:, 1] < v[:, 1].min() + 1e-6]
    assert len(base) >= 3
    assert shapely.MultiPoint(base[:, [0, 2]]).convex_hull.area > 0
```

**Step 2:** Run `cd engine && uv run pytest -q`.
Expected: a collection error, `ModuleNotFoundError: No module named 'plush.geometry'`.

**Step 3: Create `engine/plush/geometry/__init__.py`**

```python
"""3D shapes for each part kind, in inches. Axes: x = character's left, y = up, z = front."""
```

**and `engine/plush/geometry/rounded_solid.py`**

```python
"""Rounded solids (body, head, muzzle): a deformed sphere at finished size."""

from __future__ import annotations

import numpy as np
import trimesh

from plush.parts import RoundedSolid

SUBDIVISIONS = 4  # icosphere with 2562 vertices
FLAT_BOTTOM_CUT = 0.85  # unit-sphere depth at which a flat bottom is cut


def rounded_solid_mesh(part: RoundedSolid, scale_in: float) -> trimesh.Trimesh:
    """Mesh centred on its bounding box, sized exactly width x height x depth."""
    unit = trimesh.creation.icosphere(subdivisions=SUBDIVISIONS, radius=1.0)
    v = unit.vertices.copy()
    if part.flat_bottom:
        v[:, 1] = np.maximum(v[:, 1], -FLAT_BOTTOM_CUT)
    # +taper widens the lower half and narrows the upper half
    v[:, [0, 2]] *= (1.0 - part.taper * v[:, 1])[:, None]
    size = np.array([part.width, part.height, part.depth]) * scale_in
    lo, hi = v.min(axis=0), v.max(axis=0)
    v = (v - (lo + hi) / 2) / (hi - lo) * size
    return trimesh.Trimesh(vertices=v, faces=unit.faces, process=False)
```

**Step 4:** Run `cd engine && uv run pytest -q`.
Expected: `22 passed`.

**Step 5:** Commit: `git add engine/plush/geometry engine/tests/test_rounded_solid.py && git commit -m "feat(engine): rounded-solid geometry"`

### Task 2.4: Limbs

**Files:** create `engine/plush/geometry/limb.py`; test `engine/tests/test_limb.py`.

**Step 1: Write the failing test file `engine/tests/test_limb.py`**

```python
import numpy as np
import pytest

from plush.geometry.limb import POINT_LENGTH, limb_centreline, limb_mesh
from plush.parts import Limb

SCALE = 10.0  # inches per unit of finished height


def limb(**kw):
    base = {"kind": "limb", "id": "l", "name": "L", "colour": "#000000", "length": 0.3,
            "start_thickness": 0.1, "end_thickness": 0.1, "end_shape": "flat_sole",
            "attach": {"parent": "body", "azimuth_deg": 90, "elevation_deg": 0}}
    return Limb(**{**base, **kw})


def test_straight_limb_area_matches_cylinder_plus_sole():
    mesh = limb_mesh(limb(), SCALE)
    d, length = 0.1 * SCALE, 0.3 * SCALE
    assert mesh.area == pytest.approx(np.pi * d * length + np.pi * (d / 2) ** 2, rel=0.01)


def test_bent_limb_centreline_length_and_end_angle():
    points, tangents = limb_centreline(limb(bend_deg=60), SCALE)
    length = np.linalg.norm(np.diff(points, axis=0), axis=1).sum()
    assert length == pytest.approx(0.3 * SCALE, rel=0.005)
    assert np.dot(tangents[0], tangents[-1]) == pytest.approx(np.cos(np.radians(60)), abs=1e-9)


def test_point_limb_ends_in_single_tip():
    part = limb(end_shape="point", bend_deg=30)
    mesh = limb_mesh(part, SCALE)
    points, tangents = limb_centreline(part, SCALE)
    tip = points[-1] + tangents[-1] * POINT_LENGTH * (0.1 * SCALE / 2)
    assert np.linalg.norm(mesh.vertices - tip, axis=1).min() < 1e-9
```

**Step 2:** Run `cd engine && uv run pytest -q`.
Expected: a collection error, `ModuleNotFoundError: No module named 'plush.geometry.limb'`.

**Step 3: Create `engine/plush/geometry/limb.py`**

```python
"""Limbs (arms, legs, tails, horns): a tapered tube along a bent centreline.

Local frame: the limb starts at the origin, where it is sewn on and left
open, grows along +y and bends toward +z.
"""

from __future__ import annotations

import numpy as np
import trimesh

from plush.parts import EndShape, Limb

RINGS = 40
SEGMENTS = 48
CAP_RINGS = 12
POINT_LENGTH = 1.5  # length of a pointed end, in end radii


def limb_centreline(part: Limb, scale_in: float, n: int = RINGS) -> tuple[np.ndarray, np.ndarray]:
    """Points and unit tangents along the centreline, from start to end."""
    length = part.length * scale_in
    t = np.linspace(0.0, 1.0, n)
    theta = np.radians(part.bend_deg)
    zeros = np.zeros(n)
    if theta < 1e-9:
        points = np.column_stack([zeros, length * t, zeros])
        tangents = np.tile([0.0, 1.0, 0.0], (n, 1))
    else:
        radius = length / theta
        a = theta * t
        points = np.column_stack([zeros, radius * np.sin(a), radius * (1 - np.cos(a))])
        tangents = np.column_stack([zeros, np.cos(a), np.sin(a)])
    return points, tangents


def _ring(centre: np.ndarray, tangent: np.ndarray, radius: float) -> np.ndarray:
    x_axis = np.array([1.0, 0.0, 0.0])
    b_axis = np.cross(x_axis, tangent)
    phi = np.linspace(0.0, 2 * np.pi, SEGMENTS, endpoint=False)
    return centre + radius * (np.outer(np.cos(phi), x_axis) + np.outer(np.sin(phi), b_axis))


def limb_mesh(part: Limb, scale_in: float) -> trimesh.Trimesh:
    points, tangents = limb_centreline(part, scale_in)
    t = np.linspace(0.0, 1.0, len(points))
    radii = ((1 - t) * part.start_thickness + t * part.end_thickness) / 2 * scale_in
    rings = [_ring(p, d, r) for p, d, r in zip(points, tangents, radii)]

    end, tan, r_end = points[-1], tangents[-1], radii[-1]
    if part.end_shape is EndShape.ROUND:
        alpha = np.linspace(0, np.pi / 2, CAP_RINGS + 1)[1:-1]
        rings += [_ring(end + tan * r_end * np.sin(a), tan, r_end * np.cos(a)) for a in alpha]
        tip = end + tan * r_end
    elif part.end_shape is EndShape.POINT:
        k = np.arange(1, CAP_RINGS) / CAP_RINGS
        rings += [_ring(end + tan * POINT_LENGTH * r_end * f, tan, r_end * (1 - f)) for f in k]
        tip = end + tan * POINT_LENGTH * r_end
    else:  # flat sole: a disc closing the end
        tip = end

    vertices = np.vstack(rings + [tip[None, :]])
    s = SEGMENTS
    faces = []
    for i in range(len(rings) - 1):
        for j in range(s):
            a, b = i * s + j, i * s + (j + 1) % s
            c, d = a + s, b + s
            faces += [[a, c, b], [b, c, d]]
    tip_index = len(vertices) - 1
    last = (len(rings) - 1) * s
    faces += [[last + j, tip_index, last + (j + 1) % s] for j in range(s)]
    return trimesh.Trimesh(vertices=vertices, faces=np.array(faces), process=False)
```

**Step 4:** Run `cd engine && uv run pytest -q`.
Expected: `25 passed`.

**Step 5:** Commit: `git add engine/plush/geometry/limb.py engine/tests/test_limb.py && git commit -m "feat(engine): limb geometry"`

### Task 2.5: Flat parts and surface features

**Files:**
- Create: `engine/plush/geometry/flat_part.py` and `engine/plush/geometry/feature.py`
- Test: `engine/tests/test_flat_part.py`

Surface features are tested through assembly in Task 2.6.

**Step 1: Write the failing test file `engine/tests/test_flat_part.py`**

```python
import numpy as np
import pytest

from plush.geometry.flat_part import flat_part_mesh, outline_polygon
from plush.parts import FlatPart

SCALE = 10.0  # inches per unit of finished height


def flat(**kw):
    base = {"kind": "flat_part", "id": "f", "name": "F", "colour": "#000000", "outline": "round",
            "width": 0.2, "height": 0.3,
            "attach": {"parent": "body", "azimuth_deg": 0, "elevation_deg": 90}}
    return FlatPart(**{**base, **kw})


def test_round_outline_area_is_half_ellipse():
    poly = outline_polygon(flat(), SCALE)
    w, h = 0.2 * SCALE, 0.3 * SCALE
    assert poly.area == pytest.approx(np.pi * w * h / 4, rel=0.01)


@pytest.mark.parametrize("outline", ["round", "pointed", "long_oval", "leaf"])
def test_outlines_are_valid_and_fill_their_box(outline):
    poly = outline_polygon(flat(outline=outline), SCALE)
    assert poly.is_valid
    minx, miny, maxx, maxy = poly.bounds
    assert (maxx - minx, maxy - miny) == pytest.approx((0.2 * SCALE, 0.3 * SCALE), rel=0.005)


def test_zero_puffiness_is_flat():
    mesh = flat_part_mesh(flat(puffiness=0.0), SCALE)
    assert mesh.extents[2] <= 0.01
    assert flat_part_mesh(flat(puffiness=0.5), SCALE).extents[2] > 0.1
```

**Step 2:** Run `cd engine && uv run pytest -q`.
Expected: a collection error, `ModuleNotFoundError: No module named 'plush.geometry.flat_part'`.

**Step 3: Create `engine/plush/geometry/flat_part.py`**

```python
"""Flat parts (ears, wings, fins): an outline sewn as a lightly stuffed pillow.

Local frame: the straight base edge lies on y = 0 (where the part is sewn
on), the tip points along +y and the front face looks along +z.
"""

from __future__ import annotations

import numpy as np
import shapely
import trimesh
from scipy.spatial import Delaunay
from shapely.geometry import Polygon

from plush.parts import FlatPart, Outline

PROFILE_SAMPLES = 96
GRID = 24


def _half_width(outline: Outline, t: np.ndarray) -> np.ndarray:
    """Half-width at height fraction t (0 = base, 1 = tip), as a fraction of half the width."""
    if outline is Outline.ROUND:
        return np.sqrt(np.clip(1 - t**2, 0, None))
    if outline is Outline.POINTED:
        return 1 - t
    if outline is Outline.LONG_OVAL:
        return np.clip(1 - t**4, 0, None) ** 0.25
    return np.clip(np.sin(np.pi * (0.25 + 0.75 * t)), 0, None)  # leaf


def outline_polygon(part: FlatPart, scale_in: float) -> Polygon:
    w, h = part.width * scale_in, part.height * scale_in
    t = np.sin(np.linspace(0, np.pi / 2, PROFILE_SAMPLES))  # dense near the tip
    hw = _half_width(part.outline, t) * w / 2
    right = np.column_stack([hw, t * h])
    left = np.column_stack([-hw[-2::-1], t[-2::-1] * h])
    return Polygon(np.vstack([right, left]))


def flat_part_mesh(part: FlatPart, scale_in: float) -> trimesh.Trimesh:
    poly = outline_polygon(part, scale_in)
    w, h = part.width * scale_in, part.height * scale_in
    boundary = np.asarray(poly.exterior.coords)[:-1]
    gx, gy = np.meshgrid(np.linspace(-w / 2, w / 2, GRID), np.linspace(0, h, GRID))
    grid = np.column_stack([gx.ravel(), gy.ravel()])
    inner = poly.buffer(-0.02 * min(w, h))
    grid = grid[shapely.contains_xy(inner, grid[:, 0], grid[:, 1])]
    pts = np.vstack([boundary, grid])

    tri = Delaunay(pts).simplices
    centroids = pts[tri].mean(axis=1)
    tri = tri[shapely.contains_xy(poly, centroids[:, 0], centroids[:, 1])]
    e1, e2 = pts[tri[:, 1]] - pts[tri[:, 0]], pts[tri[:, 2]] - pts[tri[:, 0]]
    flip = (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) < 0
    tri[flip] = tri[flip][:, ::-1]  # all counter-clockwise, so the front faces +z

    dist = shapely.distance(poly.exterior, shapely.points(pts))
    thickness = part.puffiness * 0.5 * min(w, h)
    puff = thickness / 2 * np.sin(np.pi / 2 * dist / dist.max())
    cup = part.cupping * (w / 4) * (pts[:, 0] / (w / 2)) ** 2

    n, nb = len(pts), len(boundary)
    top = np.column_stack([pts, cup + puff])
    back = np.column_stack([pts[nb:], cup[nb:] - puff[nb:]])
    vertices = np.vstack([top, back])
    back_index = np.concatenate([np.arange(nb), n + np.arange(n - nb)])  # rim shared
    faces = np.vstack([tri, back_index[tri][:, ::-1]])
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
```

**and `engine/plush/geometry/feature.py`**

```python
"""Surface features (eyes, nose, mouth, patches): flat shapes laid on a part.

Local frame: the shape lies in the x-y plane, centred on the origin, facing +z.
They are drawn for the 3D view only; their sewing templates come later.
"""

from __future__ import annotations

import numpy as np
import trimesh

from plush.parts import FeatureShape, SurfaceFeature

SEGMENTS = 32


def feature_outline(part: SurfaceFeature, scale_in: float) -> np.ndarray:
    w, h = part.width * scale_in, part.height * scale_in
    if part.shape in (FeatureShape.CIRCLE, FeatureShape.OVAL):
        a = np.linspace(0, 2 * np.pi, SEGMENTS, endpoint=False)
        return np.column_stack([w / 2 * np.cos(a), h / 2 * np.sin(a)])
    if part.shape is FeatureShape.TRIANGLE:
        return np.array([[-w / 2, h / 2], [0, -h / 2], [w / 2, h / 2]])  # points down, like a nose
    return np.array([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]])


def feature_mesh(part: SurfaceFeature, scale_in: float) -> trimesh.Trimesh:
    outline = feature_outline(part, scale_in)
    k = len(outline)
    vertices = np.vstack([np.column_stack([outline, np.zeros(k)]), [[0.0, 0.0, 0.0]]])
    faces = [[i, (i + 1) % k, k] for i in range(k)]  # fan from the centre, facing +z
    return trimesh.Trimesh(vertices=vertices, faces=np.array(faces), process=False)
```

**Step 4:** Run `cd engine && uv run pytest -q`.
Expected: `31 passed`.

**Step 5:** Commit: `git add engine/plush/geometry/flat_part.py engine/plush/geometry/feature.py engine/tests/test_flat_part.py && git commit -m "feat(engine): flat-part and surface-feature geometry"`

### Task 2.6: Assembly

**Files:** create `engine/plush/geometry/assemble.py`; test `engine/tests/test_assemble.py`.

**Step 1: Write the failing test file `engine/tests/test_assemble.py`**

```python
import json

import numpy as np
import pytest
import trimesh

from plush.geometry.assemble import assemble
from plush.parts import parse_kit

from kits import bear


@pytest.fixture(scope="module")
def placed():
    return assemble(parse_kit(json.dumps(bear())), finished_height_in=12.0)


def test_part_meshes_face_outward(placed):
    for name, p in placed.items():
        if p.kind == "surface_feature":
            continue
        m = p.mesh
        outward = np.einsum("ij,ij->i", m.face_normals, m.triangles_center - m.vertices.mean(axis=0))
        assert outward.mean() > 0, name


def test_pair_copies_mirror_each_other(placed):
    for pid in ("ear", "arm", "eye"):
        left, right = placed[f"{pid}_left"].mesh.vertices, placed[f"{pid}_right"].mesh.vertices
        assert np.abs(left * [-1, 1, 1] - right).max() < 1e-9
        assert left[:, 0].mean() > 0  # the left copy is on the character's left (+x)


def test_children_attach_on_parent_surface(placed):
    for name, p in placed.items():
        if p.parent is None:
            continue
        _, distance, _ = trimesh.proximity.closest_point(placed[p.parent].mesh, p.anchor[None, :])
        assert distance[0] < 0.01, name


def test_assembly_height_equals_finished_height(placed):
    lo = np.min([p.mesh.bounds[0] for p in placed.values()], axis=0)
    hi = np.max([p.mesh.bounds[1] for p in placed.values()], axis=0)
    assert hi[1] - lo[1] == pytest.approx(12.0, abs=1e-6)
    assert lo[1] == pytest.approx(0.0, abs=1e-9)
```

**Step 2:** Run `cd engine && uv run pytest -q`.
Expected: a collection error, `ModuleNotFoundError: No module named 'plush.geometry.assemble'`.

**Step 3: Create `engine/plush/geometry/assemble.py`**

```python
"""Place every part on its parent at finished size; pairs become left/right copies."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh

from plush.geometry.feature import feature_mesh
from plush.geometry.flat_part import flat_part_mesh
from plush.geometry.limb import limb_mesh
from plush.geometry.rounded_solid import rounded_solid_mesh
from plush.parts import Kit

SINK = 0.25  # fraction of a rounded child's height sunk into its parent
FEATURE_LIFT_IN = 0.01  # gap between a surface feature and the surface (3D view only)
UP = np.array([0.0, 1.0, 0.0])
FRONT = np.array([0.0, 0.0, 1.0])


@dataclass
class Placed:
    """One part in character space (inches)."""

    part_id: str
    kind: str
    mesh: trimesh.Trimesh
    rotation: np.ndarray  # local -> world
    anchor: np.ndarray | None  # point on the parent's surface where it attaches
    parent: str | None  # name of the placed parent


def _rotation(axis: np.ndarray, angle_deg: float) -> np.ndarray:
    return trimesh.transformations.rotation_matrix(np.radians(angle_deg), axis)[:3, :3]


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def _perpendicular(v: np.ndarray, n: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    p = v - np.dot(v, n) * n
    if np.linalg.norm(p) < 1e-6:
        p = fallback - np.dot(fallback, n) * n
    return _unit(p)


def _local_mesh(part, scale_in: float) -> trimesh.Trimesh:
    builders = {
        "rounded_solid": rounded_solid_mesh,
        "limb": limb_mesh,
        "flat_part": flat_part_mesh,
        "surface_feature": feature_mesh,
    }
    return builders[part.kind](part, scale_in)


def _surface_hit(parent: Placed, direction: np.ndarray, name: str) -> tuple[np.ndarray, np.ndarray]:
    origin = parent.mesh.bounds.mean(axis=0)
    locations, _, tri = parent.mesh.ray.intersects_location(
        origin[None, :], direction[None, :], multiple_hits=False
    )
    if len(locations) == 0:
        raise ValueError(f"part {name!r}: no surface found on {parent.part_id!r} in that direction")
    # blend the corner normals so a hit on a vertex or edge gives a symmetric, smooth normal
    corners = parent.mesh.faces[tri[0]]
    weights = trimesh.triangles.points_to_barycentric(
        parent.mesh.vertices[corners][None, :, :], locations[:1]
    )[0]
    normal = _unit(weights @ parent.mesh.vertex_normals[corners])
    return locations[0], normal


def _place(part, parent: Placed | None, scale_in: float, name: str, parent_name: str | None) -> Placed:
    local = _local_mesh(part, scale_in)
    if parent is None:
        return Placed(part.id, part.kind, local, np.eye(3), None, None)

    a = part.attach
    az, el = np.radians(a.azimuth_deg), np.radians(a.elevation_deg)
    direction = parent.rotation @ np.array([np.sin(az) * np.cos(el), np.sin(el), np.cos(az) * np.cos(el)])
    anchor, normal = _surface_hit(parent, _unit(direction), name)
    up, front = parent.rotation @ UP, parent.rotation @ FRONT

    if part.kind == "surface_feature":
        z = normal
        y = _perpendicular(up, z, front)
        rotation = _rotation(z, a.yaw_deg) @ np.column_stack([np.cross(y, z), y, z])
        position = anchor + normal * FEATURE_LIFT_IN
    else:
        y = normal
        z = _perpendicular(front, y, up)
        rotation = np.column_stack([np.cross(y, z), y, z])
        rotation = _rotation(up, a.yaw_deg) @ rotation
        grow = rotation[:, 1]
        pitch_axis = np.cross(grow, up)
        if np.linalg.norm(pitch_axis) < 1e-6:
            pitch_axis = rotation[:, 0]
        rotation = _rotation(_unit(pitch_axis), a.pitch_deg) @ rotation
        if part.kind == "rounded_solid":
            position = anchor + rotation[:, 1] * part.height * scale_in * (0.5 - SINK)
        else:
            position = anchor

    mesh = local.copy()
    mesh.vertices = mesh.vertices @ rotation.T + position
    return Placed(part.id, part.kind, mesh, rotation, anchor, parent_name)


def _mirror(placed: Placed, renames: dict[str, str]) -> Placed:
    flip = np.diag([-1.0, 1.0, 1.0])
    mesh = trimesh.Trimesh(
        vertices=placed.mesh.vertices @ flip, faces=placed.mesh.faces[:, ::-1], process=False
    )
    anchor = None if placed.anchor is None else placed.anchor @ flip
    parent = renames.get(placed.parent, placed.parent)
    return Placed(placed.part_id, placed.kind, mesh, flip @ placed.rotation, anchor, parent)


def assemble(kit: Kit, finished_height_in: float) -> dict[str, Placed]:
    """All parts placed in character space, scaled so the toy is exactly finished_height_in tall.

    A paired part (and everything attached to it) appears twice, named
    '<id>_left' and '<id>_right'; the right copy is the mirror of the left.
    """
    children: dict[str, list] = {p.id: [] for p in kit.parts}
    root = next(p for p in kit.parts if p.attach is None)
    for p in kit.parts:
        if p.attach is not None:
            children[p.attach.parent].append(p)

    placed: dict[str, Placed] = {}

    def build(part, parent_name: str | None, suffix: str, out: dict[str, Placed]) -> None:
        name = part.id + suffix
        parent = None if parent_name is None else out.get(parent_name) or placed[parent_name]
        out[name] = _place(part, parent, finished_height_in, name, parent_name)
        for child in children[part.id]:
            if not child.pair:
                build(child, name, suffix, out)
                continue
            # pairs only hang from symmetric, unpaired parts (enforced in parts.py)
            side, other = ("_left", "_right") if child.attach.azimuth_deg > 0 else ("_right", "_left")
            subtree: dict[str, Placed] = {}
            build(child, name, side, subtree)
            renames = {n: n[: -len(side)] + other for n in subtree}
            for sub_name, sub in subtree.items():
                out[sub_name] = sub
                out[renames[sub_name]] = _mirror(sub, renames)

    build(root, None, "", placed)

    lo = np.min([p.mesh.bounds[0] for p in placed.values()], axis=0)
    hi = np.max([p.mesh.bounds[1] for p in placed.values()], axis=0)
    k = finished_height_in / (hi[1] - lo[1])
    shift = np.array([0.0, -lo[1] * k, 0.0])  # toy stands on y = 0
    for p in placed.values():
        p.mesh.vertices = p.mesh.vertices * k + shift
        if p.anchor is not None:
            p.anchor = p.anchor * k + shift
    return placed
```

**Step 4:** Run `cd engine && uv run pytest -q`.
Expected: `35 passed`.

**Step 5:** Commit: `git add engine/plush/geometry/assemble.py engine/tests/test_assemble.py && git commit -m "feat(engine): place parts on parents; mirror pairs; scale to finished height"`

### Task 2.7: Record Phase 2

Add "Phase 2 done: 35 passed, 0 failed, 0 skipped" with the date to `docs/PROGRESS.md`, then commit it.

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

**Acceptance:** 48 passed.

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

**Acceptance:** 54 passed.

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

**Acceptance:** 65 passed.

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

**Acceptance:** 80 passed.

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

**Acceptance:** 89 passed.

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

**Acceptance:** 91 passed in the default run, with the live results recorded separately.

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
