# Critique: full health review — Plushie Pattern Generator

Date: 2026-10-12
Scope: whole project at `/Volumes/WS4TB/Repo_File_Cab/plush_pg/plushie-pattern-generator` (Angular 21 front end in `src/app/`, Express server in `src/server.ts`, docs `README.md` and `handoff.md`).
Not a git repository, so there are no commit messages to check.

## 1. Bottom line

- **Fake images can pass as real ones.** When the image AI fails (no key, quota used up, or no network), the app returns built-in placeholder drawings. It tells the user "Sewing idea created" and captions the placeholder "Realistic wool product render". I reproduced this by running the server with the network blocked.
- **The printed pattern can't be cut from.** Every piece is one of five plain shapes. The sizes have no units and are capped at a small on-screen size, yet the printout is headed "1:1 physical placement scale".
- **Later steps lose track of the character.** The preview picture and the sewing instructions are generated without the character images, without the pattern pieces on the cutting board, and without the skill level the user picked at sign-in. They can describe a different toy from the pattern.
- **Failures are saved as finished work.** If instruction generation fails, the error message is stored as the finished guide and the project is labelled "Active Guide Complete".
- **The checks that exist pass, but they don't test the product.** The one unit test, lint and the production build all pass. The test only checks that the page component can be created. The project has no version control, and `handoff.md` claims several things the code doesn't do.

## 2. Findings

| # | Severity | Finding | Evidence | Classification |
|---|---|---|---|---|
| C1 | Critical | When an image call fails, the server returns hardcoded placeholder SVGs as a normal success. The client ignores the `isFallback` flag and reports success. The preview placeholder has no flag at all. The model-drawn SVG fallback is mislabelled `isFallback: false`. A missing key silently becomes `'DUMMY_KEY'`, so the app starts fine and then only shows placeholders. A placeholder teddy can then be selected and sent for analysis, giving a "pattern" for a generic teddy. | `src/server.ts:22`, `:200-264`, `:418-476`, `:233`; `src/app/app.ts:313-325`; `src/app/app.html:638`. Offline run (no keys, outbound network blocked): `POST /api/generate-images` → HTTP 200 `{"success":true,"isFallback":true}`, SVG text "Plushie Concept Draft". `POST /api/generate-plushie-preview` → HTTP 200 `{"desc":"Default plushie preview model placeholder."}`, SVG text "Finished Plushie Preview Model". | HYBRID. Switch: any exception from the image call. No flag or env var controls it. |
| C2 | Critical | The printed stencil isn't usable as a sewing pattern. Each piece is a circle, rectangle, oval, triangle or "shield". Sizes have no unit and are capped at 130 on-screen pixels. They are drawn in an 800×450 box squeezed into a 380 px-high panel, under the heading "1:1 PHYSICAL PLACEMENT SCALE". The model's `cuttingLayoutSize` is requested and then thrown away. | `src/app/app.ts:396-402`; `src/app/app.html:922`, `:928-931`; `src/server.ts:322-329` (requested), with no client reference (`grep cuttingLayoutSize` matches only `server.ts`) | DEMO (the claimed scale isn't implemented) |
| M1 | Major | Failed preview or guide requests are saved as if they succeeded. Neither call checks `response.ok`. A failed guide stores `{"error": ...}` as `buildGuide`, opens the guide page with empty lists, and the desk card says "Active Guide Complete". A failed preview leaves the page on "Generating mockup outcome picture..." indefinitely. The server parses model JSON without checking the required fields. | `src/app/app.ts:497-503`, `:659-666`; `src/app/app.html:236-237`, `:635`; `src/server.ts:366`, `:541`. Offline run: `/api/generate-build-guide` → HTTP 500 `{"error":"Failed to compile final builder steps"}`. The client path was traced in code, not run in a browser. | — |
| M2 | Major | Preview and guide ignore the character, the pieces and the skill level. The preview request sends only the customization choices and the refinement text. The guide request sends difficulty, fabrics, choices and refinement text, but not the images, cutting pieces or skill level. Skill level is only ever displayed, although the desk page promises instructions "tailored to your experience". The refinement box says changes flow into "templates outlines", but pieces only come from the analysis step, which never receives the refinement. | `src/app/app.ts:491-494`, `:650-655`; `src/server.ts:380-388`, `:489-498`; `profileLevel` appears only at `app.ts:79,150,162,173` and `app.html:22,151,737`; `src/app/app.html:146`, `:573` | ORPHAN (skill level); preview and guide are LIVE but not connected to the analysis output |
| M3 | Major | Refinement text leaks between projects and isn't saved. `extraRefinementPrompt` is one value for the whole component. It is never reset in `startNewProject`/`resumeProject` and never written to the project's own `refinementPrompt` field, so project B's guide gets project A's request and a page reload loses it. | `src/app/app.ts:99`, `:226-260`; field declared at `:64` and never assigned (`grep refinementPrompt`) | — |
| M4 | Major | Images can fail to save or fail to send. Full-size images are stored as base64 text in browser local storage (usually limited to about 5 MB per site), and that write has no error handling. The server rejects request bodies over 10 MB. The browser never shrinks images. | `src/app/app.ts:209-211`, `:271-296`; `src/server.ts:161`. Offline run: 11 MB analysis request → HTTP 413. The storage-quota failure was traced in code, not run in a browser. | — |
| M5 | Major | Image generation always calls Google directly with a hardcoded model, even when OpenRouter is configured. A Google quota error (the handoff's own "highest-risk issue") becomes a C1 placeholder. Model IDs are hardcoded in four places, against your rule that you pick models. | `src/server.ts:61`, `:144`, `:174`, `:392`; `handoff.md:15-16` | — |
| M6 | Major | The printed manual shows a fixed date, "Date Generated: 2026-06-01", on every project. | `src/app/app.html:738` | DEMO |
| M7 | Major | The API is open to the local network and spends your keys. `npm run dev` listens on all network interfaces (`--host=0.0.0.0`) and accepts any hostname (`--allowed-hosts=true`). The `/api/*` routes have no access check and no rate limit. | `package.json:7`; `src/server.ts:163`, `:273`, `:376`, `:485`. Not tested from a second device. | — |
| M8 | Major | No version control. Handoff "Next Step 1: Initialize Git" is still open. | `git rev-parse` → "fatal: not a git repository"; `handoff.md:33-34`, `:334-343` | — |
| M9 | Major | Almost no tests. There is one test (the component gets created). Nothing tests the server routes, the fallbacks, the layout and seam-allowance maths, or saving. | `src/app/app.spec.ts:11-15`; `npx ng test --watch=false` → 1 file, 1 passed, 0 failed, 0 skipped | — |
| M10 | Major | The docs claim things the code doesn't do. (a) "OpenRouter authentication failures → fail over gracefully to direct Google GenAI": in the code, an OpenRouter failure just raises an error and nothing retries with Google. (b) "Complexity Analysis Accuracy — tested via local simulation": no such test exists. (c) "Vector SVG step-by-step illustrations" is listed as working, but these are three fixed decorative icons, identical for every project. (d) Every module is marked "green". (e) The README says to put the key in `.env.local`, but the server reads `.env`. Following the README gives no key, which leads straight to the C1 placeholders. | (a) `handoff.md:61`, `:401-403` vs `src/server.ts:110-113`; (b) `handoff.md:85` vs `src/app/app.spec.ts`; (c) `handoff.md:6`, `:12`, `:67` vs `src/app/app.html:848-916`, `:1062-1122`; (d) `handoff.md:92-99`; (e) `README.md:18` vs `src/server.ts:13-15` | DEMO (illustrations) |
| m1 | Minor | Lint passes only because a whole-file `eslint-disable` hides 8 errors (7 "explicit any", 1 unused variable). The handoff discloses this. | `src/server.ts:1`; `npx eslint --no-inline-config "src/**/*.ts" "src/**/*.html"` → 8 errors | — |
| m2 | Minor | The export file name keeps spaces because the regex `/\\s+/g` matches a literal backslash, not whitespace. | `src/app/app.ts:683`; node check → `"fabric novice companion"` | — |
| m3 | Minor | Template leftovers. The page title is "Google AI Studio Angular App". OpenRouter calls are sent as `HTTP-Referer: https://github.com/google/gemini-angular-sample` with `User-Agent: aistudio-build`. The README is AI Studio boilerplate. | `src/index.html:5`; `src/server.ts:25`, `:104`; `README.md` | — |
| m4 | Minor | Sign-in is just a name saved in the browser, with no check, yet the UI says it "Saves securely". Uploaded images go to Google or OpenRouter, but the UI doesn't say so, and the handoff says "No user PII". | `src/app/app.ts:159-169`; `src/app/app.html:129`; `handoff.md:129`, `:265` | — |
| m5 | Minor | The skill levels don't match: sign-in offers Novice/Hobbyist/Artisan, but the difficulty scale is Novice/Scout/Artisan. | `src/app/app.html:115-117`; `src/server.ts:294` | — |
| m6 | Minor | Angular's server-side host check fails on every page load ("Header host ... is not allowed ... will become a 400 Bad Request in a future major version"). `allowedHosts` is not configured. | Offline server log | — |
| m7 | Minor | `.env` contains the Gemini key a second time, inside a commented-out `curl` example. `.gitignore` covers `.env*`. | `.env` comment block | — |
| m8 | Minor | Dead or duplicated code. A `parts` array is built and never used in the analysis route. Data-URL parsing and SVG cleanup are each copied twice. | `src/server.ts:276-296`, `:126-140` vs `:278-292`, `:213-235` vs `:434-455` | — |
| m9 | Minor | Handoff paths point to `/Volumes/WS4TB/plush_pg/...`, but the project now lives at `/Volumes/WS4TB/Repo_File_Cab/plush_pg/...`. | `handoff.md:170`, `:455` | — |
| m10 | Minor | Hardcoded fallback customization choices ("Contrast Wool Border", etc.). They only appear for saved projects that have choices but no option list. | `src/app/app.html:543-562` | DEMO |
| m11 | Minor | The UI always says "Gemini 3.5", whatever model is configured. Image steps actually use `gemini-2.5-flash-image`. | `src/app/app.html:94`, `:399`, `:428`, `:1355` | — |

## 3. Fix plan

The steps are in dependency order, and each Critical (C) and Major (M) finding is closed exactly once. None of these fixes is applied yet.

1. **Set up version control (closes M8).**
   Files: run `git init`. Confirm `.gitignore` keeps `.env` out, then make a first commit containing the code, `handoff.md` and this review. While there, delete the duplicate key comment in `.env` (m7).
   Verify: `git check-ignore .env` prints `.env`; `git ls-files | grep -c '^\.env$'` prints `0`; `git status --porcelain` prints nothing.
   **Needs your approval:** it creates a repository and a commit.

2. **Add a test harness that uses no mocks (closes M9).**
   Files: add a Node-side test command (`npm run test:server`, using a vitest config with the Node environment). It builds and starts the real server with no keys and outbound traffic sent to a dead local proxy (`NODE_USE_ENV_PROXY=1 HTTPS_PROXY=http://127.0.0.1:9`), then checks the HTTP status of each `/api/*` route. Move request building and the layout maths into pure functions, so unit tests can call them directly.
   Verify: `npm run test:server` and `npx ng test --watch=false` both run, and report counts above the current 1 test.
   **Needs your approval** only for an optional live test that calls Google or OpenRouter with your keys. The offline tests send nothing out.

3. **Stop presenting placeholders as results (closes C1).**
   Files: `src/server.ts`. Remove `'DUMMY_KEY'` and exit at startup with a clear message if neither key is set. Delete the two hardcoded placeholder SVGs. When image generation fails, return HTTP 502 with the reason (for example a quota error). If you keep the model-drawn SVG fallback, return it with `source: "svg-sketch"`.
   Files: `src/app/app.ts` and `app.html`. Show failures as failures. Show a visible "AI sketch, not a photo render" badge whenever `source` is not the image model.
   Verify: offline `POST /api/generate-images` returns `502` (today it returns `200`); `grep -c "Plushie Concept Draft\|Finished Plushie Preview Model" src/server.ts` prints `0`; a server test confirms a missing key stops startup.
   **No approval needed**, unless you want to keep the placeholder images. Your rules require that they be approved and labelled.

4. **Never save a failed response (closes M1).**
   Files: `src/app/app.ts`. Check `response.ok` in `designOutcomePreview` and `compileBuildGuide`, and only set `outcomePreviewUrl`/`buildGuide` on success.
   Files: `src/server.ts`. Check the required fields of the parsed model JSON and return 502 if any are missing.
   Verify: a unit test where the response is an error leaves `activeProject().buildGuide` undefined and `currentStep()` at `'preview'`; offline `POST /api/generate-build-guide` returns a non-200 status with an `error` field.
   **No approval needed.**

5. **Choose the providers and models (closes M5).**
   Files: `src/server.ts`. Read the text and image model IDs from env vars (`TEXT_MODEL`, `IMAGE_MODEL`), with no defaults in the code, and refuse to start if either is unset. Send image generation through the provider you choose. Make the UI model labels (m11) read from the server.
   Verify: `grep -nE "gemini-[0-9]" src/server.ts` returns nothing; starting the server without `IMAGE_MODEL` exits with a clear message.
   **Needs your input:** pick the text and image models, and say whether images should go through OpenRouter. OpenRouter's public list fetched today includes `google/gemini-2.5-flash-image`, `google/gemini-3.1-flash-image`, `google/gemini-3-pro-image` and `google/gemini-3.1-flash-lite-image`. I have not confirmed that OpenRouter's chat endpoint returns images for each of them; that needs checking against OpenRouter's docs once you've chosen.

6. **Make image saving and upload reliable (closes M4).**
   Files: `src/app/app.ts`. Shrink each image in the browser to a maximum of 1024 px before storing or sending it. Move project storage from `localStorage` to IndexedDB, wrap every write in error handling, and show a visible "not saved" message when a write fails.
   Verify: a unit test of the resize function returns an image no larger than 1024 px; an offline server test with three resized images gets past the size check (no 413).
   **No approval needed.**

7. **Keep refinement text per project (closes M3).**
   Files: `src/app/app.ts`. Write the refinement text into `project.refinementPrompt` on change, restore it in `resumeProject`, and clear it in `startNewProject`.
   Verify: a unit test sets a refinement, calls `startNewProject()`, and gets `extraRefinementPrompt() === ''`; `resumeProject(p)` restores `p.refinementPrompt`.
   **No approval needed.**

8. **Connect preview and guide to the actual character and pieces (closes M2).**
   Files: `src/app/app.ts` and `src/server.ts`.
   - The preview request includes the selected reference images, or the analysis description.
   - The guide request includes the cutting pieces (name, count, size) and the skill level.
   - The guide prompt names those pieces.
   - The sign-in levels are aligned with the difficulty scale (m5).
   - Either re-run piece analysis when refinement text is given, or change the refinement copy at `app.html:573` so it no longer promises template changes.

   Verify: unit tests on the pure request-building functions from step 2 show that `cuttingPieces` and `profileLevel` are present in the guide request and the images in the preview request.
   **Needs your approval** for one live end-to-end run with a test image you choose. That run sends the image to the provider.

9. **Make the printed pattern honest about scale (closes C2).** There are two options:
   - **(a) Real scale.** Ask the model for piece sizes in a stated unit, remove the 130 px cap, render the print view in physical units (SVG `width="…cm"` with a matching viewBox), split it across pages, and print a known test square.
   - **(b) Layout preview only.** Drop the "1:1" heading and label the output as a layout preview, not a cutting pattern.

   Files: `src/server.ts` (schema descriptions), `src/app/app.ts:396-422`, `src/app/app.html:919-958`.
   Verify for (a): a unit test that a 10 cm piece renders with `width="10cm"`, and a printed test square that measures correctly with a ruler (only you can do that check). Verify for (b): `grep -n "1:1" src/app/app.html` returns nothing.
   **Needs your input:** choose (a) or (b), and for (a) choose cm or inches. Option (a) is a scope decision.

10. **Remove the fixed date (closes M6).**
    Files: `src/app/app.ts` stores a `guideGeneratedAt` timestamp when the guide is created; `src/app/app.html:738` displays it.
    Verify: `grep -n "2026-06-01" src/app/app.html` returns nothing; a unit test renders the stored date.
    **No approval needed.**

11. **Close the network exposure (closes M7).**
    Files: `package.json:7`. Use `--host=127.0.0.1` and remove `--allowed-hosts=true`.
    Verify: while `npm run dev` runs, `lsof -nP -iTCP:3000 -sTCP:LISTEN` shows `127.0.0.1:3000`, not `*:3000`.
    **Needs your input:** if you use the app from a phone or another computer, say so; then the plan becomes a shared-secret header plus a rate limit instead.

12. **Correct the docs to match the code (closes M10).**
    Files: `README.md` (`.env`, OpenRouter, model env vars) and `handoff.md`:
    - Remove the failover claim. Building failover instead would be a scope change.
    - Remove the "local simulation" claim.
    - Describe the illustrations as decorative.
    - Set module statuses from this review.
    - Fix the paths.

    Verify: `grep -nE "Failover gracefully|local simulation|\.env\.local" README.md handoff.md` returns nothing.
    **No approval needed.**

## 4. Verified working

- **Unit tests:** `npx ng test --watch=false` → 1 test file, 1 test passed, 0 failed, 0 skipped (vitest 4.1.8).
- **Lint:** `npx ng lint` → "All files pass linting." This is only true with the suppression noted in m1.
- **Production build:** `npx ng build` succeeds. Initial bundle 422.93 kB raw, no budget warnings, 1 route prerendered. This rebuilt `dist/` on 2026-10-12.
- **Server, run offline** (no keys, outbound traffic to a dead proxy, confirmed with `fetch` → `ECONNREFUSED`):
  - `GET /` returns 200.
  - All four `/api/*` routes respond. Images and preview return 200 with a placeholder; analysis and guide return 500; an 11 MB body returns 413.
- **OpenRouter text model:** `google/gemini-3.5-flash` (the code default and the `.env` value) is present in OpenRouter's public model list fetched 2026-10-12 (458 models).
- **Model-drawn SVGs can't run scripts.** They are only shown through `<img [src]>` (`app.html:209`, `:365`, `:633`, `:755`), which doesn't execute scripts inside an SVG. A search of `src/` for `innerHTML`, `outerHTML`, `bypassSecurityTrust`, `DomSanitizer`, `[srcdoc]` and `eval(` found none.
- **`.env` is excluded from git:** `.gitignore` has `.env*` with an exception for `.env.example`.

## 5. Unknowns

- **Whether the real AI path works today.** I didn't run it, because it would send prompts and images to Google or OpenRouter using your keys. Checking it needs your OK for one end-to-end run with a test image you choose.
- **Whether `gemini-3.5-flash` and `gemini-2.5-flash-image` are valid on Google's direct API.** Checking needs a model-list call to Google with your key.
- **Browser-only behaviour:** the local-storage quota failure, the real print output, and dragging pieces and the sliders on the canvas. I didn't run a browser. Checking needs a browser session, and for print scale, a physical printout.
- **Known dependency vulnerabilities.** I didn't run `npm audit`, because it sends the dependency list to the npm registry. Checking needs your OK to run it.
- **Reachability from another device on your network** (M7). Not tested.
