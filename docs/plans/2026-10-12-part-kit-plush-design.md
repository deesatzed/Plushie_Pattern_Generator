# Design: Part-kit plush pattern generator (version 1)

Date: 2026-10-12
Status: approved in conversation on 2026-10-12, section by section
Replaces: the current app's AI-guessed pattern pieces (see `docs/reviews/2026-10-12-critique-full.md`)

## Goal

You upload a picture of a cartoon or drawn character. The app builds a 3D model of it from soft parts, and you adjust that model. Once you approve it, the app works out what a seamstress needs to make a real plush toy: fabric panels at true size, how they join, and step-by-step directions.

## Decisions

| Question | Decision |
|---|---|
| How the user modifies the 3D model | Adjust parts: size, length, position and roundness, plus adding or removing parts. No free sculpting. |
| Who uses version 1 | Only the owner, on this Mac. No accounts and no hosting. |
| What counts as working | The automatic checks only (Section 4). There is no sewing test in version 1. |
| Which characters | Simple bodies: head and body, plus ears, arms, legs, tail, wings and horns. Faces are flat features. No humanoid hair or clothing. |
| Approach | A part kit. The AI reads the picture into a parts list, the 3D model is built from the parts, and the patterns come from each part's known construction. No image-to-3D model. |
| Where the picture is read | A hosted vision model through OpenRouter. The owner picks the model from the current OpenRouter list when that step is built. The picture leaves the Mac. |
| Fabrics | Low-stretch only: felt, cotton, linen and other wovens, modelled as not stretching. The fabric setting keeps a stretch value so measured stretchy fabrics can be added later. |
| Rounded parts (changed 2026-10-12 after measurement) | Gores only, plus a flat base when the part has a flat bottom. Side panels with a gusset are removed from version 1. Flattened with low-stretch fabric, a side panel spanning 30° needed 5.2% stretch and one spanning 60° needed 19.7%, against the 3% limit. They return with stretchy fabrics. Approved by the owner on 2026-10-12. |
| Paper and units | US Letter, in inches. |
| Who writes the directions | The app, from fixed templates. No AI in version 1. |

## Out of scope for version 1

- Image-to-3D generation (TRELLIS.2, Hunyuan3D).
- Side panels with a gusset on rounded parts (they need stretchy fabric; see Decisions).
- Free sculpting.
- Humanoid characters with hair or clothing.
- Stretchy fabrics such as minky and fleece.
- Sewing validation.
- A4 paper or metric units.
- AI-written directions.
- Hosting or sharing.

## 1. Flow and architecture

**Screens:**

1. **Upload:** one picture, ideally a front view.
2. **Read:** the vision model returns a parts list in the fixed format (Section 2).
3. **Shape:**
   - A 3D view of the parts, with the front view drawn over the picture so proportions can be matched by eye.
   - Select a part, then drag its handles or type values. Add or remove parts.
   - Set the finished height, then press **Approve**.
4. **Pattern:** the engine builds the panels and runs the seven checks. Each check shows pass or fail, the measured value, and where the problem is.
5. **Output:** a true-scale PDF and the directions. These are produced only when every check passes.

**Components:**

- **Front end:** the existing Angular shell, plus three.js for the 3D view. Editing happens in the browser.
- **Back end:** a Python service listening only on 127.0.0.1. It holds:
  - the pattern engine (numpy, scipy, shapely);
  - the PDF writer;
  - the single vision-model call.

  It replaces the Express server and server-side rendering.
- **Storage:** one folder per project on this Mac, holding the picture, the parts-list versions, the approved version, the pattern, the check report and the PDF. Browser storage is no longer used.

## 2. The part kit

| Kind | Used for | Parameters |
|---|---|---|
| Rounded solid | body, head, muzzle, belly bulge | width, height, depth, egg taper, flat bottom |
| Limb | arms, legs, tail, horns, trunk | length, thickness at each end, bend, end shape (round, flat sole, point) |
| Flat part | ears, wings, fins | outline (round, pointed, long oval, leaf), width, height, puffiness, cupping |
| Surface feature | eyes, nose, mouth, cheeks, patches | shape, size and position on a part, and method (embroidery, felt appliqué, safety eye) |

**Every part records:**

- its parent part and attachment point;
- its angle;
- its colour or fabric;
- its left/right twin, if any (twins are edited together by default, and this can be switched off);
- its sizes, as fractions of the finished height.

**The vision model's output:**

- It must match the schema exactly. Every type, end shape, outline and method comes from the fixed lists above.
- Anything that doesn't match is rejected and shown as an error. Nothing is guessed or filled in.

**Approval and editing:**

- **Approve** freezes a version with an ID. Editing after approval creates a new version.
- The editor warns as soon as a part falls below the size that can be sewn and turned right side out. That limit comes from Section 3.

## 3. Pattern engine

**Constructions:**

- **Rounded solid:** gores from top to bottom, plus a flat base when the part has a flat bottom. The engine uses the fewest gores that stay within tolerance. (Side panels plus a gusset were removed on 2026-10-12; see Decisions.)
- **Limb:** a single wrapped panel with an inside seam, plus a sole for a flat end. A bent limb gets an inner and an outer piece.
- **Flat part:** two mirror-image pieces, with an optional contrast fabric on the inside.
- **Surface feature:** a true-size appliqué template, an embroidery guide, or a safety-eye hole mark.

**Steps for each part:**

1. Build the part's 3D surface at finished size.
2. Place seams on it according to the construction.
3. Flatten all of a part's panels together. Start from least-squares conformal mapping, then move every edge toward its true length while holding matching seam edges to equal length. Seam sides may ease slightly along with the fabric, but they always match each other. Measure the remaining stretch. If it's over the limit, add another panel.
4. **Stuffing correction.** Sew the panels together virtually, inflate them with internal pressure using the low-stretch fabric model, and compare the result with the target shape. Adjust the panel outlines and repeat until the shape is within tolerance.
5. **Seam matching.** Make both sides of every seam equal in length. Add notches along each seam and at attachment points, and mark a stuffing gap on each closed part.
6. **Finishing.** Add an even outward seam allowance (a true offset, not a scaled shape), grain and fur-direction arrows, and a label: name, cut count, mirror flag and fabric.

**Known limit.** The checks prove the pattern is self-consistent and that its simulated stuffed shape matches the model. They don't prove that a real sewn toy matches. The stuffing simulation stays unconfirmed until something is sewn, which is outside version 1.

## 4. Automatic checks (the pass/fail test)

| # | Check | Passes when |
|---|---|---|
| 1 | Seams match | Both sides of every seam are the same length, within tolerance. |
| 2 | True scale | Reading the PDF's coordinates (72 points to the inch) shows the test square and every piece at exact size. |
| 3 | Stuffed shape matches the model | Each part's simulated stuffed shape is within tolerance of the approved model, both on average and at the worst point. |
| 4 | Flattening stretch | No panel needs more than the allowed stretch to lie flat. |
| 5 | Sewable | Every piece meets the minimum turnable size. Every piece has its seam allowance, every closed part has a stuffing gap, and every attachment has notches on both parts. |
| 6 | Complete | Every part of the model has pieces. Each piece appears in exactly one "cut" step, and each seam in exactly one "sew" step. |
| 7 | Matches the approved model | The pattern carries the approved version's ID. No pattern can be made from a model changed since approval. |

The results are shown on screen and saved as a report in the project folder. The tolerances live in a settings file, and their starting values will be proposed in the implementation plan for the owner to approve.

## 5. Outputs

**The PDF (US Letter, inches):**

- **Page 1:** the test square, a symbol legend, and a map of how the pages fit together.
- **Pieces at true size,** tiled across pages with row and column labels and trim and overlap lines.
- **Each piece shows:** its label, grain and fur-direction arrows, notches, the stuffing gap, and the seam line inside the cut line.
- **Cutting layout:** the pieces laid out on the fabric width (a setting), with the fur running one way.
- **Materials:**
  - fabric needed per colour, measured from the cutting layout;
  - the stuffed volume, calculated from the geometry (stuffing weight is not given, because there is no density data);
  - thread, and safety-eye sizes if used.

**The directions:**

- Built from the piece and seam graph in a fixed order:
  1. Cut the pieces.
  2. Add features while the pieces are flat.
  3. Sew and turn the small parts.
  4. Stuff the limbs.
  5. Sew the head and body with the parts placed at their notches.
  6. Attach parts.
  7. Stuff, then close the gap with a ladder stitch.
- Each step names its pieces and notches.
- Each step has a diagram drawn from the real pieces, with the seam being sewn highlighted.

## 6. Errors and testing

**Errors:**

- **Reading fails, or the schema is invalid:** show a message with two choices, retry or start from a blank kit (a body and a head). Placeholder results are never shown.
- **AI key or model setting missing:** the service refuses to start and names what's missing.
- **A check fails:** the draft is shown with the failures marked, and no PDF is produced.
- **A save fails:** the owner is told straight away.

**Tests:**

- **Engine:** mathematical shapes with exact known answers. A cylinder must unroll to a rectangle whose width equals its circumference, and a sphere's gores must have equal seam lengths.
- **PDF:** read the produced PDF's coordinates.
- **Editor:** twin editing, version freezing and the too-small warning.
- **Picture reading:** an optional live test using real character pictures supplied by the owner. It calls the hosted model, so it runs only on request.

## Existing code

- **Keep:** the Angular shell.
- **Remove:** `src/server.ts`, server-side rendering, `localStorage` use, the old AI routes, the placeholder SVGs, and the hard-coded model IDs.
- **Rewrite:** the README and `handoff.md`.
- **Track:** progress in `docs/PROGRESS.md`, committed with the work.

## Open items (need the owner's input when reached)

- The vision model, chosen from OpenRouter's list at build time.
- Starting tolerance values for checks 1, 3 and 4, plus the minimum turnable size, the default seam allowance and the default fabric width. These will be proposed in the plan for approval.
