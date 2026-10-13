"""The printable pattern on US Letter: cover, true-scale pattern pages, cutting layout, directions.

Page 1 carries the test square, the legend, the page map, the materials and the settings
status. The pattern pages show every piece at true size (72 points per inch), tiled with
overlaps. Check 2 reads the PDF back and confirms the test square and every piece's cut
line are exactly where the layout puts them, at 72 points per inch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from plush.checks import CheckResult
from plush.directions import Step
from plush.finishing import Pattern, Piece
from plush.layout import FabricLayout
from plush.materials import Materials
from plush.settings import Settings

PT = 72.0
PAGE_W, PAGE_H = letter  # 612 x 792 points
MARGIN_IN = 0.5
PRINT_W_IN = PAGE_W / PT - 2 * MARGIN_IN
PRINT_H_IN = PAGE_H / PT - 2 * MARGIN_IN
GAP_IN = 0.5  # space between pieces on the pattern pages
COLUMNS = 2  # the pattern area is this many pages wide (more if a piece needs it)
TOLERANCE_PT = 0.01


@dataclass
class Sheet:
    offsets: dict[str, np.ndarray]  # piece -> shift of its outlines on the pattern area, inches
    width_in: float
    height_in: float
    tiles: list[tuple[int, int, np.ndarray]]  # (row from the top, column, lower-left of the printable area)


def sheet_layout(pattern: Pattern, settings: Settings) -> Sheet:
    """Pack the pieces in rows on the pattern area (top to bottom), then cut the area into pages."""
    step_x, step_y = PRINT_W_IN - settings.tile_overlap_in, PRINT_H_IN - settings.tile_overlap_in
    widest = max(np.ptp(p.cut[:, 0]) for p in pattern.pieces.values())
    columns = max(COLUMNS, math.ceil((widest + 2 * GAP_IN - settings.tile_overlap_in) / step_x))
    width = columns * step_x + settings.tile_overlap_in
    rows_down = []  # (piece, x of its left edge, distance of its top edge below the area's top)
    x, down, row_height = GAP_IN, GAP_IN, 0.0
    for p in sorted(pattern.pieces.values(), key=lambda p: -np.ptp(p.cut[:, 1])):
        w, h = np.ptp(p.cut, axis=0)
        if x > GAP_IN and x + w + GAP_IN > width:
            x, down, row_height = GAP_IN, down + row_height + GAP_IN, 0.0
        rows_down.append((p, x, down))
        x += w + GAP_IN
        row_height = max(row_height, h)
    height = down + row_height + GAP_IN
    offsets = {}
    for p, left, top_down in rows_down:
        lo, hi = p.cut.min(axis=0), p.cut.max(axis=0)
        offsets[p.name] = np.array([left - lo[0], (height - top_down) - hi[1]])
    rows = max(1, math.ceil((height - settings.tile_overlap_in) / step_y))
    tiles = [(r, c, np.array([c * step_x, height - r * step_y - PRINT_H_IN]))
             for r in range(rows) for c in range(columns)]
    return Sheet(offsets, width, height, tiles)


def _on_tile(outline: np.ndarray, origin: np.ndarray) -> bool:
    lo, hi = outline.min(axis=0), outline.max(axis=0)
    return bool(np.all(hi >= origin) and np.all(lo <= origin + [PRINT_W_IN, PRINT_H_IN]))


def _to_page(points_in: np.ndarray, origin_in: np.ndarray) -> np.ndarray:
    return (MARGIN_IN + np.asarray(points_in) - origin_in) * PT


def _poly(c: canvas.Canvas, pts: np.ndarray, closed: bool) -> None:
    path = c.beginPath()
    path.moveTo(*pts[0])
    for q in pts[1:]:
        path.lineTo(*q)
    if closed:
        path.close()
    c.drawPath(path, stroke=1, fill=0)


def _arrow(c: canvas.Canvas, tail: np.ndarray, head: np.ndarray, both: bool) -> None:
    c.line(*tail, *head)
    d = (head - tail) / np.linalg.norm(head - tail) * 6
    n = np.array([-d[1], d[0]]) * 0.5
    for tip, back in [(head, -d)] + ([(tail, d)] if both else []):
        c.line(*tip, *(tip + back + n))
        c.line(*tip, *(tip + back - n))


def _draw_piece(c: canvas.Canvas, piece: Piece, offset: np.ndarray, origin: np.ndarray, settings: Settings) -> None:
    def page(pts):
        return _to_page(np.asarray(pts) + offset, origin)

    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.8)
    c.setDash()
    _poly(c, page(piece.cut), closed=True)  # the cut line: check 2 reads this path back
    c.setLineWidth(0.5)
    c.setDash(3, 2)
    c.setStrokeColorRGB(0.4, 0.4, 0.4)
    _poly(c, page(piece.stitch), closed=True)
    c.setDash()
    stitch = piece.stitch
    for point, label in piece.notches:
        i = int(np.argmin(np.linalg.norm(stitch - point, axis=1)))
        tangent = stitch[(i + 1) % len(stitch)] - stitch[i - 1]
        normal = np.array([tangent[1], -tangent[0]]) / np.linalg.norm(tangent)  # outward: the line runs anticlockwise
        a, b = page([point, point + normal * settings.seam_allowance_in])
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.8)
        c.line(*a, *b)
        c.setFont("Helvetica", 5)
        c.drawString(*(b + normal * 2), label[:14])
    c.setStrokeColorRGB(0.85, 0.1, 0.1)
    c.setLineWidth(2)
    for gap in piece.gaps:
        _poly(c, page(gap), closed=False)
    c.setLineWidth(0.6)
    c.setDash(1, 2)
    c.setStrokeColorRGB(0.1, 0.3, 0.8)
    for line, label in piece.marks:
        if len(line) > 1:
            _poly(c, page(line), closed=False)
            c.setFont("Helvetica", 5)
            c.drawString(*page(line[len(line) // 2]), label)
    c.setDash()
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.6)
    tail, head = page(piece.grain)
    _arrow(c, tail, head, both=True)
    if piece.nap is not None:
        nap_tail, nap_head = page(piece.nap) + [12, 0]
        _arrow(c, nap_tail, nap_head, both=False)
    c.setFont("Helvetica", 7)
    centre = page([piece.grain.mean(axis=0)])[0]
    for k, line in enumerate(simpleSplit(piece.label, "Helvetica", 7, 140)):
        c.drawString(centre[0] + 18, centre[1] - 8 * k, line)


def _cover(c: canvas.Canvas, sheet: Sheet, materials: Materials, settings: Settings, title: str,
           checks: list[CheckResult]) -> None:
    left, top = MARGIN_IN * PT, PAGE_H - MARGIN_IN * PT
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, top - 16, title)
    c.setFont("Helvetica", 9)
    c.drawString(left, top - 32, f"US Letter, inches. Print at 100% (actual size); do not scale to fit. "
                                 f"{len(sheet.tiles)} pattern pages.")
    if not settings.approved_by_owner:
        c.setFillColorRGB(0.8, 0, 0)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left, top - 48, "Tolerance settings not yet approved by owner")
        c.setFillColorRGB(0, 0, 0)
    side = settings.test_square_in * PT
    square_y = top - 70 - side
    c.setLineWidth(1)
    c.rect(left, square_y, side, side)  # the test square: check 2 reads this back
    c.setFont("Helvetica", 9)
    c.drawString(left + side + 10, square_y + side - 10,
                 f"Test square: must measure exactly {settings.test_square_in:g} in on each side.")
    legend = ["Solid line: cut.", "Dashed line: sew.", "Short ticks: notches; match the letters.",
              "Red: leave open for turning and stuffing.", "Blue dotted: where another part or a feature goes.",
              "Double arrow: straight grain. Single arrow: the way the fur runs."]
    for k, line in enumerate(legend):
        c.drawString(left + side + 10, square_y + side - 26 - 12 * k, line)

    y = square_y - 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, "Page map: tape the pattern pages together like this")
    rows = max(r for r, _, _ in sheet.tiles) + 1
    cols = max(col for _, col, _ in sheet.tiles) + 1
    cell = min(28.0, 200.0 / cols)
    for r, col, _ in sheet.tiles:
        x0, y0 = left + col * cell, y - 10 - (r + 1) * cell
        c.rect(x0, y0, cell, cell)
        c.setFont("Helvetica", 7)
        c.drawString(x0 + 3, y0 + cell / 2 - 3, f"{r + 1}.{col + 1}")
    y -= 30 + rows * cell
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, "Materials")
    c.setFont("Helvetica", 9)
    lines = [f"Fabric {colour}: {width:g} in wide, {length:.1f} in long" for colour, width, length in materials.fabric]
    lines.append(f"Stuffing to fill about {materials.stuffed_volume_cuin:.0f} cubic inches")
    lines += [f"Safety eyes ({name}): {count} x {diameter:.2f} in across"
              for name, diameter, count in materials.safety_eyes]
    lines.append(materials.thread)
    for k, line in enumerate(lines):
        c.drawString(left, y - 14 - 12 * k, line)
    y -= 30 + 12 * len(lines)
    if checks:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left, y, "Automatic checks")
        c.setFont("Helvetica", 8)
        for k, r in enumerate(checks):
            c.drawString(left, y - 14 - 11 * k,
                         f"{r.number}. {r.name}: {'pass' if r.passed else 'FAIL'} - {r.measured} (limit {r.limit})")


def _pattern_page(c: canvas.Canvas, pattern: Pattern, sheet: Sheet, tile, settings: Settings) -> None:
    r, col, origin = tile
    rows = max(t[0] for t in sheet.tiles) + 1
    cols = max(t[1] for t in sheet.tiles) + 1
    left, bottom = MARGIN_IN * PT, MARGIN_IN * PT
    c.setFont("Helvetica", 8)
    c.drawString(left, PAGE_H - MARGIN_IN * PT / 2,
                 f"Pattern page {r + 1}.{col + 1} (rows 1-{rows}, columns 1-{cols}); "
                 f"overlap neighbouring pages by {settings.tile_overlap_in:g} in up to the grey lines")
    c.saveState()
    clip = c.beginPath()
    clip.rect(left, bottom, PRINT_W_IN * PT, PRINT_H_IN * PT)
    c.clipPath(clip, stroke=0, fill=0)
    for name, offset in sheet.offsets.items():
        piece = pattern.pieces[name]
        if _on_tile(piece.cut + offset, origin):
            _draw_piece(c, piece, offset, origin, settings)
    c.restoreState()
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(0.4)
    overlap = settings.tile_overlap_in * PT
    c.line(left + overlap, bottom, left + overlap, bottom + PRINT_H_IN * PT)
    c.line(left, bottom + PRINT_H_IN * PT - overlap, left + PRINT_W_IN * PT, bottom + PRINT_H_IN * PT - overlap)


def _cutting_layout(c: canvas.Canvas, fabric: list[FabricLayout]) -> None:
    left, top = MARGIN_IN * PT, PAGE_H - MARGIN_IN * PT
    c.setFont("Helvetica-Bold", 14)
    c.drawString(left, top - 14, "Cutting layout (not to scale)")
    y = top - 34
    for f in fabric:
        scale = min(PRINT_W_IN * PT / f.width_in, 250 / max(f.length_in, 1e-6))
        if y - f.length_in * scale - 30 < MARGIN_IN * PT:
            c.showPage()
            y = top - 20
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(left, y, f"Fabric {f.colour}: {f.width_in:g} in wide, {f.length_in:.1f} in long. "
                              "Grain runs up the page; place every piece as shown.")
        y -= 8 + f.length_in * scale
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.rect(left, y, f.width_in * scale, f.length_in * scale)
        c.setStrokeColorRGB(0, 0, 0)
        for placement in f.placements:
            pts = placement.outline * scale + [left, y]
            _poly(c, pts, closed=True)
            c.setFont("Helvetica", 5)
            name = placement.piece.split("/")[1] + (" (mirrored)" if placement.mirrored else "")
            c.drawString(*(pts.mean(axis=0) - [10, 2]), name)
        y -= 24


def _diagram(c: canvas.Canvas, pattern: Pattern, step: Step, x0: float, y0: float, size: float) -> None:
    names = list(dict.fromkeys(name for name, _ in step.highlight))
    shapes = [pattern.pieces[n].stitch for n in names]
    widths = [float(np.ptp(s[:, 0])) for s in shapes]
    scale = min(size / (sum(widths) + 0.3 * len(shapes)), size / max(float(np.ptp(s[:, 1])) for s in shapes))
    x = x0
    shift = {}
    for n, s, w in zip(names, shapes, widths):
        shift[n] = np.array([x, y0]) - s.min(axis=0) * scale
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.setLineWidth(0.5)
        _poly(c, s * scale + shift[n], closed=True)
        x += (w + 0.3) * scale
    c.setStrokeColorRGB(0.85, 0.1, 0.1)
    c.setLineWidth(1.5)
    for n, line in step.highlight:
        if len(line) > 1:
            _poly(c, np.asarray(line) * scale + shift[n], closed=False)
    c.setStrokeColorRGB(0, 0, 0)


def _directions(c: canvas.Canvas, pattern: Pattern, steps: list[Step]) -> None:
    left, top = MARGIN_IN * PT, PAGE_H - MARGIN_IN * PT
    c.setFont("Helvetica-Bold", 14)
    c.drawString(left, top - 14, "Directions")
    y = top - 36
    box = 1.6 * PT
    text_width = PRINT_W_IN * PT - box - 12
    for s in steps:
        lines = simpleSplit(f"{s.number}. {s.text}", "Helvetica", 9, text_width)
        height = max(12 * len(lines), box if s.highlight else 0) + 10
        if y - height < MARGIN_IN * PT:
            c.showPage()
            y = top - 20
        c.setFont("Helvetica", 9)
        for k, line in enumerate(lines):
            c.drawString(left, y - 12 * k, line)
        if s.highlight:
            _diagram(c, pattern, s, PAGE_W - MARGIN_IN * PT - box, y - box + 9, box)
        y -= height


def write_pdf(path: str, pattern: Pattern, sheet: Sheet, fabric: list[FabricLayout], steps: list[Step],
              materials: Materials, settings: Settings, title: str, checks: list[CheckResult] | None = None,
              scale: float = 1.0) -> None:
    """Write the pattern. `scale` is 1.0 for real use; other values exist only so a test can prove
    that check 2 catches a pattern saved or printed at the wrong size."""
    c = canvas.Canvas(path, pagesize=letter)
    c.setTitle(title)

    def new_page():
        if scale != 1.0:
            c.scale(scale, scale)

    new_page()
    _cover(c, sheet, materials, settings, title, checks or [])
    for tile in sheet.tiles:
        c.showPage()
        new_page()
        _pattern_page(c, pattern, sheet, tile, settings)
    c.showPage()
    new_page()
    _cutting_layout(c, fabric)
    c.showPage()
    new_page()
    _directions(c, pattern, steps)
    c.showPage()
    c.save()


def _read_paths(page) -> tuple[list[np.ndarray], list[tuple[float, float]]]:
    """Every path (as page points) and every rectangle (width, height, in points) drawn on a page."""
    paths, rects, current = [], [], []

    def visit(op, args, cm, tm):
        nonlocal current
        a, b, c_, d, e, f = (float(v) for v in cm)
        if op == b"m":
            if current:
                paths.append(np.array(current))
            x, y = float(args[0]), float(args[1])
            current = [(a * x + c_ * y + e, b * x + d * y + f)]
        elif op == b"l" and current:
            x, y = float(args[0]), float(args[1])
            current.append((a * x + c_ * y + e, b * x + d * y + f))
        elif op == b"re":
            rects.append((abs(float(args[2]) * a), abs(float(args[3]) * d)))

    page.extract_text(visitor_operand_before=visit)
    if current:
        paths.append(np.array(current))
    return paths, rects


def check_true_scale(pdf_path: str, pattern: Pattern, sheet: Sheet, settings: Settings) -> CheckResult:
    """Check 2: the test square and every piece's cut line are at exact size and position."""
    reader = PdfReader(pdf_path)
    where = []
    for i, page in enumerate(reader.pages):
        if (float(page.mediabox.width), float(page.mediabox.height)) != (PAGE_W, PAGE_H):
            where.append(f"page {i + 1} is not US Letter")
    side = settings.test_square_in * PT
    _, rects = _read_paths(reader.pages[0])
    square_error = min((max(abs(w - side), abs(h - side)) for w, h in rects), default=float("inf"))
    if square_error > TOLERANCE_PT:
        where.append(f"test square is off by {square_error:.3f} pt")
    worst = 0.0
    for k, (r, col, origin) in enumerate(sheet.tiles):
        paths, _ = _read_paths(reader.pages[1 + k])
        for name, offset in sheet.offsets.items():
            cut = pattern.pieces[name].cut + offset
            if not _on_tile(cut, origin):
                continue
            expected = _to_page(cut, origin)
            candidates = [p for p in paths if len(p) == len(expected)]
            error = min((float(np.abs(p - expected).max()) for p in candidates), default=float("inf"))
            worst = max(worst, error)
            if error > TOLERANCE_PT:
                where.append(f"{name} on page {r + 1}.{col + 1}: off by {error:.3f} pt")
    return CheckResult(2, "True scale", not where, f"square {square_error:.4f} pt, pieces {worst:.4f} pt",
                       f"{TOLERANCE_PT} pt", where)
