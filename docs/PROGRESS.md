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
- [x] Phase 4: stuffing correction. 2026-10-12: 58 passed, 0 failed, 0 skipped (full run takes about 56 s). The Mylar balloon check passes within 3% (in the dry-run, a 2.20% rim and 1.88% thickness error at the default 2-stage stiffness; 3 stages are now used).
  - Task 4.3 gore comparison, from `cd engine && uv run python tools/gore_comparison.py` (2026-10-12):

    | Shape | Gores | Flattening stretch (check 4, limit 3%) | Stuffed deviation mean / worst (check 3, limits 3% / 8%) | Passes 3 / 4 |
    |---|---|---|---|---|
    | Ball, 6.00 in across | 6 | 6.63% | 0.71% / 2.49% | yes / no |
    | Ball, 6.00 in across | 8 | 3.71% | 0.42% / 1.44% | yes / no |
    | Ball, 6.00 in across | 12 | 1.55% | 0.23% / 0.58% | yes / yes |
    | Bear head, 5.78 in across | 6 | 7.37% | 0.67% / 2.98% | yes / no |
    | Bear head, 5.78 in across | 8 | 4.39% | 0.39% / 1.59% | yes / no |
    | Bear head, 5.78 in across | 12 | 1.87% | 0.22% / 0.68% | yes / yes |
- [ ] Phase 5: finishing and checks (expected 69)
- [ ] Phase 6: outputs (expected 84)
- [ ] Phase 7: projects and local service (expected 93)
- [ ] Phase 8: picture reading (expected 95, plus live tests run with approval)
- [ ] Phase 9: Angular front end (expected 10 Angular tests)
- [ ] Phase 10: documentation and end-to-end run

## Open items waiting on the owner (approval gates in the plan)

- After Phase 4: review check-3 results for 6, 8 and 12 gores, and decide whether to keep the 3% flattening-stretch limit (owner's choice, 2026-10-12).
- G3: choose the vision model from OpenRouter's list (Phase 8).
- G4: supply real pictures and approve the live reading test (Phase 8).
- G5: approve the end-to-end run with a real picture (Phase 10).
- Optional: approval to run `npm audit` (it sends the dependency list to the npm registry).

## Known issues in the existing app (being replaced, not patched)

See the critique's findings C1, C2 and M1 to M10. The design replaces the code involved.

## Decisions recorded during the work

- 2026-10-12: side panels plus a gusset removed from version 1. They need stretchy fabric; measurements are in the design doc. Rounded parts use gores, plus a flat base when the part has a flat bottom.
- 2026-10-12: the 3% stretch limit kept for now, to be revisited after Phase 4.
