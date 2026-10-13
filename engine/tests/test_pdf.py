import dataclasses

import pytest
from pypdf import PdfReader

from plush.directions import directions
from plush.layout import cutting_layout
from plush.materials import materials
from plush.pdf import PAGE_H, PAGE_W, _read_paths, check_true_scale, sheet_layout, write_pdf
from plush.settings import load_settings

SETTINGS = load_settings()


@pytest.fixture(scope="module")
def printed(bear_stuffed, tmp_path_factory):
    kit, placed, pattern, stuffing = bear_stuffed
    fabric = cutting_layout(pattern, SETTINGS)
    steps = directions(kit, placed, pattern)
    mats = materials(kit, placed, fabric, stuffing)
    sheet = sheet_layout(pattern, SETTINGS)
    folder = tmp_path_factory.mktemp("pdf")
    args = (pattern, sheet, fabric, steps, mats)
    write_pdf(str(folder / "true.pdf"), *args, SETTINGS, "Rule-check bear")
    write_pdf(str(folder / "shrunk.pdf"), *args, SETTINGS, "Rule-check bear", scale=0.97)
    unapproved = dataclasses.replace(SETTINGS, approved_by_owner=False)
    write_pdf(str(folder / "unapproved.pdf"), *args, unapproved, "Rule-check bear")
    return pattern, sheet, folder


def test_test_square_is_exactly_two_inches(printed):
    _, _, folder = printed
    _, rects = _read_paths(PdfReader(folder / "true.pdf").pages[0])
    assert any(abs(w - 144) < 1e-6 and abs(h - 144) < 1e-6 for w, h in rects)


def test_check_2_finds_every_piece_at_true_scale(printed):
    pattern, sheet, folder = printed
    result = check_true_scale(str(folder / "true.pdf"), pattern, sheet, SETTINGS)
    assert result.passed, result.where


def test_every_page_is_us_letter(printed):
    _, _, folder = printed
    for page in PdfReader(folder / "true.pdf").pages:
        assert (float(page.mediabox.width), float(page.mediabox.height)) == (PAGE_W, PAGE_H)


def test_page_map_lists_every_pattern_page(printed):
    _, sheet, folder = printed
    text = PdfReader(folder / "true.pdf").pages[0].extract_text()
    for r, c, _ in sheet.tiles:
        assert f"{r + 1}.{c + 1}" in text


def test_check_2_fails_for_a_shrunk_copy(printed):
    pattern, sheet, folder = printed
    result = check_true_scale(str(folder / "shrunk.pdf"), pattern, sheet, SETTINGS)
    assert not result.passed and any("test square" in w for w in result.where)


def test_unapproved_settings_are_stamped_on_the_cover(printed):
    _, _, folder = printed
    assert "Tolerance settings not yet approved by owner" in PdfReader(folder / "unapproved.pdf").pages[0].extract_text()
    assert "not yet approved" not in PdfReader(folder / "true.pdf").pages[0].extract_text()
