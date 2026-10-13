import base64
import json
import os
from pathlib import Path

import pytest

from plush.parts import Kit
from plush.vision import ReadError, build_request, read_picture

LIVE_PICTURES = Path(__file__).resolve().parents[2] / "projects" / "_live_pictures"


def test_request_carries_the_picture_the_schema_and_the_chosen_model():
    body = build_request(b"\x89PNG picture bytes", "image/png", "provider/model-from-settings")
    assert body["model"] == "provider/model-from-settings"
    content = body["messages"][0]["content"]
    assert content[1]["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(b"\x89PNG picture bytes").decode()
    schema = json.dumps(body["response_format"]["json_schema"]["schema"])
    assert '"flat_sole"' in schema and '"discriminator"' not in schema


def test_no_network_means_an_error_not_a_made_up_kit(monkeypatch):
    # every outbound request goes to a closed local port: the real code path, with no network
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.delenv("NO_PROXY", raising=False)
    with pytest.raises(ReadError, match="network"):
        read_picture(b"\x89PNG", "image/png", "provider/model-from-settings", "no-key-needed-offline")


@pytest.mark.live
@pytest.mark.parametrize("picture", sorted(LIVE_PICTURES.glob("*.*")) if LIVE_PICTURES.exists() else [])
def test_live_reading_of_owner_pictures(picture):
    """Runs only with `pytest -m live`, with the owner's approval (gate G4)."""
    kit = read_picture(picture.read_bytes(), "image/png" if picture.suffix == ".png" else "image/jpeg",
                       os.environ["PLUSH_VISION_MODEL"], os.environ["OPENROUTER_API_KEY"])
    assert isinstance(kit, Kit)
