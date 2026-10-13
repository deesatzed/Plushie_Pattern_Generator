"""Projects on disk: one folder per character, numbered kit drafts, and the approved version.

projects/<slug>/
    picture.<ext>          the uploaded picture
    kit-v<n>.json          every saved draft, numbered
    approved.json          the approved draft, finished height and version id
    report.json            the seven check results for the last pattern build
    pattern.pdf            present only when the last build passed all seven checks

The version id is the sha256 of the approved kit (canonical JSON) and the finished height.
Check 7: a pattern can only be built from the approved version, unchanged.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from plush.checks import CheckResult
from plush.parts import Kit, parse_kit


class ApprovalError(ValueError):
    """There is no approved version, or the model changed after approval."""


def canonical(kit: Kit) -> str:
    return json.dumps(kit.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def version_id(kit: Kit, finished_height_in: float) -> str:
    return hashlib.sha256(f"{canonical(kit)}|{finished_height_in!r}".encode()).hexdigest()


class Projects:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def folder(self, slug: str) -> Path:
        folder = self.root / slug
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", slug) or not folder.is_dir():
            raise KeyError(f"no project {slug!r}")
        return folder

    def create(self, name: str, picture: bytes, extension: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "character"
        slug, n = base, 1
        while (self.root / slug).exists():
            n += 1
            slug = f"{base}-{n}"
        folder = self.root / slug
        folder.mkdir()
        (folder / f"picture.{extension.lower().lstrip('.')}").write_bytes(picture)
        return slug

    def list(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def drafts(self, slug: str) -> list[Path]:
        return sorted(self.folder(slug).glob("kit-v*.json"), key=lambda p: int(p.stem.split("-v")[1]))

    def save_draft(self, slug: str, kit: Kit) -> int:
        n = len(self.drafts(slug)) + 1
        (self.folder(slug) / f"kit-v{n}.json").write_text(canonical(kit))
        return n

    def latest(self, slug: str) -> Kit:
        drafts = self.drafts(slug)
        if not drafts:
            raise ApprovalError(f"project {slug!r} has no saved model yet")
        return parse_kit(drafts[-1].read_text())

    def approve(self, slug: str, finished_height_in: float) -> str:
        kit = self.latest(slug)
        vid = version_id(kit, finished_height_in)
        record = {"draft": self.drafts(slug)[-1].name, "finished_height_in": finished_height_in,
                  "version_id": vid, "approved_at": datetime.now(timezone.utc).isoformat()}
        (self.folder(slug) / "approved.json").write_text(json.dumps(record, indent=2))
        return vid

    def approved(self, slug: str) -> dict | None:
        path = self.folder(slug) / "approved.json"
        return json.loads(path.read_text()) if path.exists() else None

    def check_approved(self, slug: str) -> tuple[Kit, float, CheckResult]:
        """Check 7. Raises ApprovalError if there is nothing to build from."""
        record = self.approved(slug)
        if record is None:
            raise ApprovalError(f"project {slug!r} has no approved model")
        kit = self.latest(slug)
        current = version_id(kit, record["finished_height_in"])
        if current != record["version_id"]:
            raise ApprovalError(f"project {slug!r}: the model changed after it was approved; approve it again")
        return kit, record["finished_height_in"], CheckResult(
            7, "Matches the approved model", True, f"version {current[:12]}", "the approved version")

    def save_report(self, slug: str, checks: list[CheckResult], version: str) -> None:
        report = {"version_id": version, "checks": [asdict(c) for c in checks]}
        (self.folder(slug) / "report.json").write_text(json.dumps(report, indent=2))

    def pdf_path(self, slug: str) -> Path:
        return self.folder(slug) / "pattern.pdf"
