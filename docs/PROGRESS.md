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
- [ ] Phase 3: panels, flattening, seams (expected 48)
- [ ] Phase 4: stuffing correction (expected 54)
- [ ] Phase 5: finishing and checks (expected 65)
- [ ] Phase 6: outputs (expected 80)
- [ ] Phase 7: projects and local service (expected 89)
- [ ] Phase 8: picture reading (expected 91, plus live tests run with approval)
- [ ] Phase 9: Angular front end (expected 10 Angular tests)
- [ ] Phase 10: documentation and end-to-end run

## Open items waiting on the owner (approval gates in the plan)

- G2: approve each starting value in `engine/settings.toml` (before Phase 3).
- G3: choose the vision model from OpenRouter's list (Phase 8).
- G4: supply real pictures and approve the live reading test (Phase 8).
- G5: approve the end-to-end run with a real picture (Phase 10).
- Optional: approval to run `npm audit` (it sends the dependency list to the npm registry).

## Known issues in the existing app (being replaced, not patched)

See the critique's findings C1, C2 and M1 to M10. The design replaces the code involved.
