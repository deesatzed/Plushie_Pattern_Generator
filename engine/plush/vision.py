"""Read a character picture into a part kit with a hosted vision model, through OpenRouter.

The model is asked to answer in exactly the part-kit format (its JSON Schema). The answer is
checked with parse_kit, and anything that does not fit is reported as an error. There is no
fallback: a failed reading never produces a made-up kit. The model comes from the
PLUSH_VISION_MODEL setting; no model name is written in this code.
"""

from __future__ import annotations

import base64
import copy

import httpx
from pydantic import ValidationError

from plush.parts import Kit, kit_json_schema, parse_kit

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_S = 180.0

PROMPT = """You are reading a picture of one cartoon or drawn character, to plan a sewn plush toy.
Describe the character as a kit of parts, answering ONLY with JSON that matches the given schema.
- There is exactly one root part: the body, a rounded_solid with no "attach".
- The head and other rounded parts are rounded_solid and attach to the body.
- Ears, wings and fins are flat_part. Arms, legs, tails, horns and trunks are limb.
- Eyes, noses, mouths, cheeks and patches are surface_feature (choose embroidery, applique or safety_eye).
- Left and right twins are ONE part with "pair": true, placed on the character's left (positive azimuth).
- Attachment directions: azimuth 0 = front, +90 = the character's left; elevation +90 = top, -90 = bottom.
- Sizes are fractions of the character's total height. Colours are hex, like #A0522D.
- Part ids use lowercase letters, digits and underscores, and must not end in _left or _right.
Simplify any detail a plush toy cannot show."""


class ReadError(RuntimeError):
    """The picture could not be read into a valid part kit."""


def _portable_schema() -> dict:
    """The kit schema without the 'discriminator' hints some providers reject (the answer is
    still validated in full by parse_kit)."""
    def strip(node):
        if isinstance(node, dict):
            node.pop("discriminator", None)
            for value in node.values():
                strip(value)
        elif isinstance(node, list):
            for value in node:
                strip(value)
        return node
    return strip(copy.deepcopy(kit_json_schema()))


def build_request(picture: bytes, media_type: str, model: str) -> dict:
    data_url = f"data:{media_type};base64,{base64.b64encode(picture).decode()}"
    return {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "part_kit", "strict": False, "schema": _portable_schema()}},
    }


def _answer_text(reply: dict) -> str:
    content = reply["choices"][0]["message"]["content"]
    text = content if isinstance(content, str) else "".join(p.get("text", "") for p in content)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text


def read_picture(picture: bytes, media_type: str, model: str, api_key: str) -> Kit:
    body = build_request(picture, media_type, model)
    headers = {"Authorization": f"Bearer {api_key}", "X-Title": "Plush pattern generator"}
    try:
        response = httpx.post(OPENROUTER_URL, json=body, headers=headers, timeout=TIMEOUT_S)
    except httpx.HTTPError as e:
        raise ReadError(f"could not reach OpenRouter (network problem): {e}") from e
    if response.status_code != 200:
        raise ReadError(f"OpenRouter answered {response.status_code}: {response.text[:300]}")
    try:
        text = _answer_text(response.json())
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise ReadError("OpenRouter's reply contained no answer") from e
    try:
        return parse_kit(text)
    except ValidationError as e:
        raise ReadError(f"the model's answer is not a valid part kit: {e}") from e
