"""Live reading test (gate G4): send each owner picture to each chosen model, once.

Run from engine/ with the owner's approval:
    uv run --env-file ../.env python tools/live_read.py MODEL [MODEL ...]

Pictures come from projects/_live_pictures/ (ignored by git). Each answer is saved to
projects/_live_pictures/results/<model>/<picture>.json, either the part kit or the error,
and a summary with the measured time per request is printed.
"""

import json
import os
import sys
import time
from pathlib import Path

from plush.vision import ReadError, read_picture

PICTURES = Path(__file__).resolve().parents[2] / "projects" / "_live_pictures"
TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def main(models: list[str]) -> None:
    key = os.environ["OPENROUTER_API_KEY"]
    pictures = sorted(p for p in PICTURES.iterdir() if p.suffix.lower() in TYPES)
    if not pictures:
        sys.exit(f"no pictures in {PICTURES}")
    print("model | picture | result | seconds | parts")
    for model in models:
        out = PICTURES / "results" / model.replace("/", "__")
        out.mkdir(parents=True, exist_ok=True)
        for picture in pictures:
            start = time.perf_counter()
            try:
                kit = read_picture(picture.read_bytes(), TYPES[picture.suffix.lower()], model, key)
                result = kit.model_dump(mode="json")
                kinds = {}
                for p in kit.parts:
                    kinds[p.kind] = kinds.get(p.kind, 0) + 1
                summary = f"valid kit | {time.perf_counter() - start:.1f} | {len(kit.parts)} {kinds}"
            except ReadError as e:
                result = {"error": str(e)}
                summary = f"ERROR: {str(e)[:160]} | {time.perf_counter() - start:.1f} | -"
            (out / f"{picture.stem}.json").write_text(json.dumps(result, indent=2))
            print(f"{model} | {picture.name} | {summary}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
