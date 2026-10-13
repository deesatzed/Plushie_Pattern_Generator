# Progress

Read this file and `git log` before starting any work session.

## Current state (2026-10-12)

- [x] Critique of the existing app: `docs/reviews/2026-10-12-critique-full.md`
- [x] Version 1 design approved: `docs/plans/2026-10-12-part-kit-plush-design.md`
- [x] Git repository set up, with a baseline commit of the existing app
- [x] Implementation plan written: `docs/plans/2026-10-12-part-kit-plush-implementation.md`. Phases 0 and 1 were dry-run in a scratch copy on 2026-10-12 (2, then 9, then 16 tests passed).
- [x] Implementation plan approved by the owner (2026-10-12), together with gate G1 (hand-written test-only kits). Work happens on branch `feat/part-kit-v1`.
- [x] Phase 0: engine skeleton. 2026-10-12: `cd engine && uv run pytest -q` gave 2 passed, 0 failed, 0 skipped.
- [x] Phase 1: part-kit format. 2026-10-12: 16 passed, 0 failed, 0 skipped.
- [x] Phase 2: part geometry. 2026-10-12: 35 passed, 0 failed, 0 skipped. Added the `rtree` dependency and two kit rules: reserved `_left`/`_right` ids, and pairs only on symmetric parts.
- [x] Gate G2: owner approved all starting values in `engine/settings.toml` (2026-10-12).
- [x] Phase 3: panels, flattening, seams. 2026-10-12: 51 passed, 0 failed, 0 skipped. The test bear's panels: body 8 gores + base, head 10 gores, arm 8 strips, ear front + back; worst stretch 2.92%; seam sides match within 0.000006 in.
- [x] Phase 4: stuffing correction. 2026-10-12: 58 passed, 0 failed, 0 skipped (full run takes about 56 s). Mylar balloon check, measured 2026-10-12 at stiffness stages (1e2, 1e3, 1e4): rim radius 1.96% from the published value, thickness 0.06%, worst fabric stretch 0.154%. The test limit is 3%.
  - Task 4.3 gore comparison, from `cd engine && uv run python tools/gore_comparison.py` (2026-10-12):

    | Shape | Gores | Flattening stretch (check 4, limit 3%) | Stuffed deviation mean / worst (check 3, limits 3% / 8%) | Passes 3 / 4 |
    |---|---|---|---|---|
    | Ball, 6.00 in across | 6 | 6.63% | 0.71% / 2.49% | yes / no |
    | Ball, 6.00 in across | 8 | 3.71% | 0.42% / 1.44% | yes / no |
    | Ball, 6.00 in across | 12 | 1.55% | 0.23% / 0.58% | yes / yes |
    | Bear head, 5.78 in across | 6 | 7.37% | 0.67% / 2.98% | yes / no |
    | Bear head, 5.78 in across | 8 | 4.39% | 0.39% / 1.59% | yes / no |
    | Bear head, 5.78 in across | 12 | 1.87% | 0.22% / 0.68% | yes / yes |
- [x] Phase 5: finishing and checks. 2026-10-12: 78 passed, 0 failed, 0 skipped (full run about 2 min 14 s). On the test bear at 12 in, measured in the repo: 24 pieces (body 7 gores + base, head 8 gores, arm 6 strips, ear front + back), built in 53.8 s, nearly all of it stuffing.
  - Check 1 (seams match): pass, 0.0000 in (limit 1/32 in).
  - Check 3 (stuffed shape): pass, mean 0.53%, worst 2.62% (limits 3% / 8%). The ears are flat, so not simulated; their outline is exact.
  - Check 4 (flattening stretch): pass, 4.61% (limit 5%).
  - Check 5 (sewable): pass. The arms are 0.0029 in off the body and the head 0.0042 in. The ears are 0.089 in off, because a straight base sits on a curved head; that is within the 1/4 in allowance.
- [x] Phase 6: outputs. 2026-10-12: 95 passed, 0 failed, 0 skipped (full run about 2 min 23 s). On the test bear at 12 in, measured in the repo: the PDF has 22 pages (cover, 12 pattern pages, cutting layout, directions).
  - Check 2 (true scale): pass. Test square 0.0000 pt off, piece outlines within 0.0005 pt.
  - Check 6 (directions complete): pass, 45 steps.
  - Materials: fabric #C8A27A 44 x 19.1 in, fabric #F2D0D9 44 x 2.0 in, stuffing for about 233 cubic inches, 2 safety eyes 0.51 in across.
  - Rendered pages checked by eye (pdftoppm). Labels crowd each other on the cutting layout and around attachment notches; left for polish.
- [ ] Phase 7: projects and local service (expected 104; expanded in the plan 2026-10-12)
- [ ] Phase 8: picture reading (expected 106, plus live tests run with approval)
- [ ] Phase 9: Angular front end (expected 10 Angular tests)
- [ ] Phase 10: documentation and end-to-end run

## Open items waiting on the owner (approval gates in the plan)

- G3: choose the vision model from OpenRouter's list (Phase 8).
- G4: supply real pictures and approve the live reading test (Phase 8).
- G5: approve the end-to-end run with a real picture (Phase 10).
- Optional: approval to run `npm audit` (it sends the dependency list to the npm registry).

## Known issues in the existing app (being replaced, not patched)

See the critique's findings C1, C2 and M1 to M10. The design replaces the code involved.

## Decisions recorded during the work

- 2026-10-12: side panels plus a gusset removed from version 1. They need stretchy fabric; measurements are in the design doc. Rounded parts use gores, plus a flat base when the part has a flat bottom.
- 2026-10-12: the 3% stretch limit kept for now, to be revisited after Phase 4.
- 2026-10-12: after the Task 4.3 comparison, the owner raised `max_flatten_stretch` from 3% to 5%. Round parts get about 8 gores instead of 12. On the test bear's head, the simulated stuffed shape stays within 1.59% of the model at the worst point. Measured after the change: the test bear has a body of 7 gores + base, a head of 8 gores, arms of 6 strips each, and an ear front + back; worst flattening stretch 4.55%; engine tests 58 passed, 0 failed.
