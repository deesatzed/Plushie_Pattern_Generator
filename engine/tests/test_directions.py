import pytest

from plush.directions import check_directions, directions


@pytest.fixture(scope="module")
def steps(bear_stuffed):
    kit, placed, pattern, _ = bear_stuffed
    return pattern, directions(kit, placed, pattern)


def test_every_piece_is_cut_in_exactly_one_step(steps):
    pattern, s = steps
    cut = [name for step in s if step.kind == "cut" for name in step.pieces]
    assert sorted(cut) == sorted(pattern.pieces)
    assert check_directions(pattern, s).passed


def test_every_seam_and_attachment_appears_once(steps):
    pattern, s = steps
    sewn = [sid for step in s if step.kind == "sew" for sid in step.seams]
    assert sorted(sewn) == sorted(pattern.panels.seams)
    attached = [c for step in s if step.kind == "attach" for c in step.attachments]
    assert sorted(attached) == sorted(m.child for m in pattern.attachments)


def test_a_missing_step_fails_check_6_and_names_the_seam(steps):
    pattern, s = steps
    dropped = next(step for step in s if step.kind == "sew")
    result = check_directions(pattern, [step for step in s if step is not dropped])
    assert not result.passed and any(dropped.seams[0] in w for w in result.where)


def test_features_come_first_and_the_gap_seam_last(steps):
    pattern, s = steps
    for f in (step for step in s if step.kind == "feature"):
        assert all(f.number < x.number for x in s if x.kind == "sew" and x.part == f.part)
    for part in ("body", "head"):
        sewn = [step.seams[0] for step in s if step.kind == "sew" and step.part == part]
        assert sewn[-1] == f"{part}:m0" and pattern.panels.seams[sewn[-1]].gap is not None
