import json

import pytest

from plush.parts import parse_kit
from plush.projects import ApprovalError, Projects, version_id

from kits import bear, part


@pytest.fixture
def projects(tmp_path):
    return Projects(tmp_path / "projects")


def test_creating_a_project_stores_the_picture(projects):
    slug = projects.create("Rule-check Bear!", b"\x89PNG not a real picture", "png")
    assert slug == "rule-check-bear"
    assert (projects.folder(slug) / "picture.png").read_bytes() == b"\x89PNG not a real picture"
    assert projects.create("Rule-check Bear!", b"x", "png") == "rule-check-bear-2"


def test_drafts_are_numbered_versions(projects):
    slug = projects.create("bear", b"x", "png")
    kit = parse_kit(json.dumps(bear()))
    assert projects.save_draft(slug, kit) == 1
    assert projects.save_draft(slug, kit) == 2
    assert [p.name for p in projects.drafts(slug)] == ["kit-v1.json", "kit-v2.json"]


def test_approving_records_the_version_id(projects):
    slug = projects.create("bear", b"x", "png")
    kit = parse_kit(json.dumps(bear()))
    projects.save_draft(slug, kit)
    vid = projects.approve(slug, 12.0)
    assert vid == version_id(kit, 12.0) and len(vid) == 64
    assert projects.approved(slug)["draft"] == "kit-v1.json"
    _, height, check = projects.check_approved(slug)
    assert height == 12.0 and check.passed and check.number == 7


def test_check_7_refuses_a_model_changed_since_approval(projects):
    slug = projects.create("bear", b"x", "png")
    projects.save_draft(slug, parse_kit(json.dumps(bear())))
    projects.approve(slug, 12.0)
    changed = bear()
    part(changed, "arm")["length"] = 0.3
    projects.save_draft(slug, parse_kit(json.dumps(changed)))
    with pytest.raises(ApprovalError, match="changed after it was approved"):
        projects.check_approved(slug)
