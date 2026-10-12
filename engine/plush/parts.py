"""The part kit: the fixed vocabulary every character is built from.

Sizes are fractions of the finished height, so changing the height
rescales the whole character. The vision model must return exactly this
format; anything else is rejected by parse_kit, never guessed or repaired.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


def parse_kit(raw: str | bytes) -> Kit:
    """Validate a kit from JSON. Raises pydantic.ValidationError on any problem."""
    return Kit.model_validate_json(raw)


def kit_json_schema() -> dict:
    """JSON Schema sent to the vision model as its required output format."""
    return Kit.model_json_schema()
