# Current work

Updated 2026-09-08.

## Goal

Rebuild Kirby Wii UI with editable vector geometry. Start with Inkscape's bundled Potrace. Sam rejected the existing AI upscale pack.

## Completed

- Created this project in Dev-Projects, with source tools separated from ignored local assets.
- Extracted the SUKE01 DATA partition with DolphinTool, without launching the game.
- Decoded 7,436 unique textures, with 15,033 source references and 2,866 UI candidates.
- Added a searchable catalog at assets/kirby/index.html. A temporary server runs at http://127.0.0.1:8766.
- Preserved native dimensions, alpha, source names, archive paths, and duplicate references.
- Added the earlier Potrace ctypes prototype. It loads Inkscape's DLL in place and produces SVG paths.
- Sixteen decoder tests pass. Every catalog PNG and thumbnail opened successfully. The catalog loaded in the browser.

## Limits and next work

One texture, KbNormalEye.4 in g3d/subgame/setsuna/chara/Kirby.brres.cmp, has no matching palette or material binding. PAT0 records inspected in that archive do not reference it. It remains flagged in report.json; no palette was guessed.

Only base mip levels are exported. Videos and unsupported non-image containers remain in the extracted disc tree. This is not a claim that every embedded image in every format is decoded.

Choose simple flat UI symbols from the catalog. Run the Potrace prototype, compare contours against native pixels, and tune trace parameters. Multicolor layers, gradients, and typography need a later reconstruction stage.

Dolphin replacement filenames and in-game replacement behavior are not yet implemented or tested. Do not launch the game unless Sam asks.

## Upscaling demo handoff (2026-09-08)

Sam authorized combining raster-to-vector and AI upscaling by asset type, with oversampling before final reduction. This supersedes the original vector-only constraint.

Built three comparisons: a flat Fighter badge, a shaded Dedede portrait, and an illustrated Parasol card. See assets/kirby/demos/index.html, also served at http://127.0.0.1:8766/demos/.

The badge uses two-color Potrace. Other assets compare native-color interpolation, traced alpha, AI reconstruction, and AI color with traced alpha. All vector geometry renders at 8x native before linear-light, premultiplied-alpha reduction to 4x.

Built-in imagegen returned 1254x1254 for Dedede and 1201x1309 for Parasol. Requested sizes were 1024x1024 and 2320x2528. The Parasol output barely exceeds the final size; enlarging it to the processing canvas provides no extra model detail. Both AI outputs are rejected because they change artwork and have background defects. The alpha mask cannot correct changed faces or interior details.

Validation: 18 tests pass, including hidden-color bleed and linear-light averaging. PNG comparisons were visually inspected. No Dolphin replacement was installed or tested.

Next: review the local demos with Sam, tune vector paths where needed, and evaluate a dedicated super-resolution model. Generative image editing is not a validated upscale method for this project. Game assets and generated comparisons remain ignored by git.

Sam's preferred cleanup is oversampling, GIMP Mean Curvature Blur at 1-3 iterations, then final reduction. Added tools/curvature_demos.py using GIMP 3's actual bundled GEGL executable. It compares iterations 0-3 at 8x and 12x native, each reduced to 4x. Traced original alpha is restored after filtering. The browser comparison is assets/kirby/demos/curvature.html.

Curvature validation: all 24 outputs have the expected final dimensions, identical alpha to their unfiltered control, and nonzero filtered RGB changes. The 1-3 iteration differences are subtle after reduction; 12x processing reduces their effect further than 8x. Curvature comparison crops were visually reviewed. Eighteen automated tests pass. In-game behavior remains untested.

## chaiNNer custom node (2026-09-08)

Added Mean Curvature Blur (GIMP) to the installed chaiNNer 0.25.1 Blur group. It calls GIMP's actual GEGL operation through 16-bit PNG transfer. Default iterations: 2. Optional Preserve Alpha restores input alpha. Zero iterations bypasses GEGL.

Source and update-safe reinstall instructions are under integrations/chainner. The installer backs up a differing previous node. chaiNNer updates can remove the installed copy, requiring reinstallation.

Verified node registration, GEGL execution, exact alpha preservation when enabled, zero bypass, grayscale/RGB/RGBA shapes, and processing of Sam's current portrait. The running application's node palette remains unverified until Sam saves the chain and restarts chaiNNer. No running session was interrupted.

## Additional test assets (2026-09-08)

Sam reports StarSample 2.0 HQ gives good portrait results, and Separate Alpha fixed the visible fringe. Prepared ten additional original assets at assets/kirby/demos/test-set-02/inputs, with a sibling results folder and browser contact sheet. The set covers tiny icons, white transparent edges, metallic numerals, faces, detailed characters, repeating curves, and Sword/Ice cards. All inputs are verified byte-identical copies. Their upscales remain untested. Recreate the set with tools/prepare_test_set.py.

## Hybrid contour prototype (2026-09-08)

Added tools/hybrid_contours.py. It traces four broad hue regions from Sam's current StarSample Dedede output, simplifies their contours with Potrace, and clips extended raster shading through those paths. It renders at twice the input size and downsamples to the input dimensions. Mild and stronger candidates are in assets/kirby/demos/hybrid-contours/index.html.

The SVG is a hybrid document containing editable vector clipping paths and embedded raster shading. It is not wholly vector artwork. SciPy is required; the prototype ran with chaiNNer's bundled Python, which already provides SciPy.

Visual review: gradients remain, with changes at the hat, eye, and beak contours. Independent masks can introduce seams and over-sharpen transitions. Same-hue boundaries such as the mouth opening remain untreated. Hue rules are tailored to Dedede; this is not yet automatic segmentation for arbitrary assets. Do not batch-apply it without review. Original inputs remain unchanged.

## Full vector experiment (2026-09-08)

Sam requested a clean vector of the smoothed input after rejecting the hybrid contour result. Added tools/trace_full_vector.py. Input is the saved StarSample portrait snapshot from hybrid-contours/mild/input.png. Applies GEGL Mean Curvature Blur at 2 iterations, preserves source alpha, then traces 24/48-color cumulative masks with Potrace. Cumulative regions overlap to avoid gaps between separate masks.

The SVGs contain only filled paths, without image elements or clipping masks. They were rendered and visually inspected. 24 colors: 3,149 curve segments. 48 colors: 7,064 segments. Gradients become visible color bands, and minor contour defects remain. This is a full-vector comparison, not an approved replacement. Browser: assets/kirby/demos/full-vector/index.html. No in-game test.

## Mean-shift edge experiment (2026-09-08)

Sam rejected the banded full-vector trace and requested mean-shift clustering to identify boundaries. Added tools/meanshift_edges.py. This first experiment uses OpenCV's mean-shift filtering stage in joint spatial/8-bit Lab color space, followed by Canny proposals from all Lab channels. It does not yet assign closed cluster labels or trace shapes.

The comparison uses the same smoothed StarSample input. Settings: spatial/color radii 6/10, 12/20, and 20/30, plus an unfiltered control. Canny thresholds stay fixed at 30/70. Hidden RGB is extended before processing; output alpha and dimensions are verified unchanged. No input files were modified.

Visual review found useful eye, beak, and mouth edges, but also false gradient boundaries, especially with stronger filtering. Edge counts alone are not a quality score. Next: review overlays with Sam before choosing region clustering or contour fitting. Browser: assets/kirby/demos/mean-shift/index.html. This is not a final replacement texture or a completed vectorization method.

Sam preferred the unfiltered control edge map. Added alpha-boundary Canny edges to that control without modifying the existing internal edges. Exported white-background and transparent black line-art PNGs, with a cyan/magenta diagnostic overlay at demos/mean-shift/line-art.html. Verified every original control edge and alpha-edge pixel remains in the union. Visually reviewed; existing gaps and pixel-scale irregularities remain. This is a raster edge map, not vector paths.

## Region graph prototype (2026-09-08)

Added tools/region_graph.py. It thins the accepted control-plus-alpha line art, detects endpoints, proposes short tangent-aligned connections with crossing checks, and connects crop-truncated contours to the image border. These are heuristic proposals, not semantic understanding or confidence probabilities.

Current output: 48 initial endpoints; 24 interior repair proposals and 13 crop connections; 10 unmatched endpoints; 24 flood-filled regions of at least 12 pixels, plus 29 tiny regions retained in the label data. Proposed repairs appear green. Random region colors and median-color fills are diagnostic only.

Outputs at assets/kirby/demos/region-graph include graph.json, region-labels.npy, repaired line art, numbered regions, and a simplified shared-arc SVG. Junctions remain fixed during polyline simplification. Curve fitting and validation of vector-region topology remain pending; the filled regions currently use raster flood fill, not the simplified SVG.

Validation: all skeleton pixels remain present after repair; labels never extend outside alpha; region areas sum to the available interior. Visually checked overlays and regions; some unresolved gaps, tiny slivers, and ambiguous junctions remain. No shading reconstruction was attempted. Get Sam's region review before gradient representation or deformation.

## Automatic curve simplification (2026-09-08)

Sam explicitly rejected manual path editing. The intended engine processes every asset automatically, with strong preference for simple geometry.

Added tools/bezier_graph.py and tools/simplify_curves.py. Run them in that order with Python providing NumPy, Pillow, and SciPy, after region_graph.py. The current experiment uses Dedede only. The earlier editor is abandoned and is not part of the pipeline.

The extractor suppresses diagonal pixel shortcuts and fits a shared graph. Simplification dissolves degree-two vertices, samples by distance, smooths coordinates, and fits fewer cubic segments. Shared junctions remain fixed. No hand edits, AI calls, or shading changes occur.

Comparison: demos/simple-curves/. Control: 376 cubics. Simple: 232; simpler: 187; minimal: 171. All variants have 156 paths. Maximum sampled displacement from control is 2.08, 5.36, and 10.50 pixels respectively on the 512-pixel canvas. These are measured deviations, not guaranteed error bounds.

Validation: finite coordinates, fixed endpoints, and continuous segment joins passed for all variants. SVG rendering passed; strongest output visually inspected. Strong simplification removes mouth bumps but also changes eye curves and rounds crop corners. Incorrect connections remain. Crossings, region preservation, other assets, and automatic strength selection are not validated. Next: review simplification strength, then implement topology cleanup and candidate rejection before batch use.

## Junction cleanup experiment (2026-09-09)

Sam rejected flattened mouth curves and persistent eyelid bumps. Added Junction-cleanup to the existing overlaid simple-curves comparison. It automatically contracts paths at most 6 pixels long within clusters at most 8 pixels wide, removes resulting loops at most 12 pixels long, merges degree-two vertices, then fits with sigma 2 and tolerance 1.2. No semantic masks or manual path edits.

Result: 109 short paths removed, 90 remaining paths, 196 cubics. Finite coordinates, segment continuity, and all shared endpoint coordinates pass. Render inspected: mouth bends remain and several small contour kinks disappear. Larger eyelid junction irregularities remain. Contraction can remove legitimate tiny details; region topology and other assets remain unvalidated. The reported 1.37-pixel sampled fit shift excludes junction movement, as stated on the page. Next: review the new overlay before accepting this contraction rule or expanding it.

## Nearby-edge proposals (2026-09-09)

Added tools/neighbor_curves.py. It joins paths by tangent continuity, fits whole chains with one cubic, and ranks proposals using nearby smooth-edge alignment and how concentrated residual deviations are. No eyelid coordinates or semantic masks. Four candidates pass on Dedede; comparison at demos/neighbor-curves/ uses pink proposed curves and cyan replaced contours.

This is a proposal experiment, not an accepted automatic repair. Visual checks of the first two SVG renders show that chain selection can cross an intended feature boundary. Branches remain at their old locations when a curve moves, producing detached stubs. Nearby agreement alone does not reliably establish the intended eyelid contour. Native-source evidence, branch reattachment, crossing validation, and batch evaluation remain pending. Do not apply these proposals to final textures.

## Layered eye-shape experiment (2026-09-09)

Added tools/eye_shapes.py. Dark connected components and adjacent neutral bright components propose eye regions without hand-selected coordinates. Partial boundary ellipse fits model outer eyes and irises. Small adjacent white components propose highlights. An asymmetric quadratic fit estimates the upper envelope, discounting downward detours, and clips the layered vector shapes beneath that eyelid.

Detected both eyes on the saved StarSample portrait. Overlay and flat vector-only reconstruction are at demos/eye-shapes/. SVGs rendered and inspected; eyelid sweeps avoid highlight dips, but ellipse fits distort the eyes and highlight detection includes small false components. Layer ordering is assumed, not inferred. This is a color-based eye experiment, not a general automatic reconstruction engine. Original image and mouth remain unchanged. No shading reconstruction, other-asset validation, or automatic model acceptance yet.

## Truncated ellipse fitting (2026-09-09)

Changed eye_shapes.py to exclude points near the proposed eyelid and fit deterministic samples of exposed contour arcs. Candidates use capped boundary residuals, angular coverage, and a penalty for visible evidence outside the ellipse. Output moved to demos/truncated-eyes/; prior eye-shapes comparison remains intact.

Rendered overlay inspected: the larger eye and iris fit improve substantially. The smaller eye remains ill-conditioned, with implausible hidden extension. Do not accept it automatically. Only the eyelid is excluded explicitly; other occluders such as the beak are not inferred. Added a synthetic clipped-ellipse check during development. General occluder classification, uncertainty-based rejection, and batch validation remain pending.

Highlight false-positive fix: a thin 104-pixel white edge fragment beside the larger iris was classified as another highlight. Added minimum area and bounding-box fill checks. Each eye now retains one compact highlight; five fragments are rejected. Render inspected with the duplicate blob removed. Eye geometry is unchanged. General highlight classification remains unvalidated.

## Sclera extent and drawn eyelids (2026-09-09)

The thin white fragment rejected as a false highlight still belongs to the sclera evidence. Significant thin fragments now contribute to the outer-eye mask, improving its left extent. The fragment remains excluded from highlights.

Added blue eyelid bands using two quadratic curves with shared tapering endpoints. Thickness and flat color come from nearby blue source pixels. Both bands generated; one highlight per eye remains. Render inspected. The mouth and source image remain unchanged. The smaller ellipse remains unstable, and the lens-shaped eyelid assumption still needs visual review and validation on other assets.

## Joint ellipse containment (2026-09-09)

Outer and iris candidates are now selected jointly by total boundary score, rejecting pairs whose iris leaves the outer ellipse. This version enforces full-ellipse containment, stronger than visible-only containment. Candidate checks sample 2,048 iris boundary points; final validation uses 32,768 points. This is numerical validation, not a symbolic containment proof.

Both eye pairs passed dense containment checks. Three focused tests cover rejection of a better-scoring crossing pair, no feasible pair, and rotated coordinate transforms. Overlay rendered and inspected. The crossing smaller-eye fit is eliminated, but its hidden continuation remains uncertain and the beak occluder is still not modeled. No iris shrink or SVG clipping workaround was used. Other assets and perturbation stability remain untested.

## Strict outer white arc experiment (2026-09-09)

Added white/blue boundary isolation from the connected sclera island. Excludes nearby dark iris pixels, retains the longest continuous arc, and excludes the proposed eyelid. Outer fits use uncapped squared residuals and reject a 95th-percentile approximate boundary distance above 2 pixels. A white-island coverage check rejects fits explaining only a tiny fragment. Nested iris fitting remains required; a constrained iris refit is available when discrete pairs fail.

Separate review page: demos/white-arc-fit/. Bright green dots show selected evidence. Larger eye passes these heuristic checks; smaller eye is rejected with only 39 selected points. It is omitted from the vector panel instead of showing another unsupported fit. Earlier truncated-eyes outputs were regenerated from the previous committed algorithm and preserved. Three containment tests pass; overlay rendered and inspected. New arc-selection thresholds and constrained optimizer are not validated across assets. Next: improve selection of the smaller sclera's thin outer arc, without relaxing the edge requirement merely to produce a fit.

## Annular eye sectors (2026-09-09)

Sam requested annular sectors for eyes only. Added tools/annular_eyes.py: fits each connected white island with a rotated outer ellipse, offset scaled inner ellipse, and angular sector. Differential evolution minimizes soft mask overlap loss with an inner-containment penalty. Narrow islands get three deterministic starting runs and smaller permitted axes. No manual eye coordinates.

Demo: demos/annular-eyes/. Original eyes remain beneath the fitted white bands, with observed white boundaries in pink. Separate panel shows only vector sclera bands. This does not yet reconstruct iris or highlights with sectors. Mouth and source remain unchanged.

Best observed pixel IoU: larger island 93.54%, smaller island 82.65%. The demo retains best saved candidates across two parameter experiments using --candidates work/annular-first-fit.json assets/kirby/demos/annular-eyes/fit.json. Saved candidates are specific to this source; the reuse option does not verify source identity. Optimization hit its iteration limits; convergence is not claimed. Approximate overlap is not a fidelity approval.

Two geometry tests pass (hole/angular/exterior membership and rotation/translation). Overlay rendered and inspected. Sectors follow both white islands substantially better than the earlier missing-eye output, though endpoint and narrow-strip errors remain. Other assets, generalized classification, and shader reconstruction are untested.

## Remove radial-cut notch (2026-09-09)

Replaced the wedge-minus-offset-ellipse mask with one closed band path: outer elliptical arc, direct join, reversed inner elliptical arc, closing join. Inner endpoints are derived relative to the offset inner center, so no radial cut passes through its center gap. Render inspected; the additional notch is removed. Direct joins can still form corners; they are not inferred eyelid/beak curves.

The fit still initializes from the earlier radial-sector objective. Current band IoU is recomputed from the final polygon; historical radial IoU is separate in fit.json. Three sector tests pass, including the two-arc/no-mask regression. Re-optimization for the new band model and source-fitted occluder joins remain untested. Source artwork is unchanged.

## Enlarged overlay review and independent arc refit (2026-09-09)

Reviewed both eye overlays enlarged with Inkscape exports and image viewer. The prior direct joins had not repaired the oversized white patch: the inner ellipse was too small and the white band covered the iris. Added independent ellipse fits to the left/right boundaries of the connected white island. This improves the larger eye's inner edge. The smaller eye refit is visibly worse; a pixel-overlap comparison retains its previous paired-arc candidate automatically.

Added enlarged eye overlays to the comparison page. Refit and previous-band IoUs are recorded separately. Both final enlarged overlays inspected. Larger-eye endpoint cuts still miss some white near the beak; smaller-eye tips and thin boundary remain imperfect. This is an improvement, not a complete fidelity fix. Three existing sector tests pass; the row-based arc fitter is not validated on other assets or nonvertical bands.

## Return to raster baseline (2026-09-09)

Sam stopped vector reconstruction and requested the previous raster work. Added tools/raster_review.py and demos/raster-review/, linking the saved Dedede StarSample snapshot plus ten chaiNNer batch results against native originals. No processing, chain settings, or source images changed. All 11 source/output pairs exist. Vector experiments remain references, not the active path.

Active direction: raster upscaling with Separate Alpha and GIMP Mean Curvature Blur/downscale. Keep actual saved chain settings unless Sam changes them. Reshading remains a possible later raster operation, with existing silhouettes and alpha preserved; no reshading implementation or new processing is authorized by this handoff alone.

## Saved user chain batch (2026-09-09)

Ran work/upscalingtest_01.chn on all ten test-set-02 inputs through a separate chaiNNer backend on port 8767. The user's running app was not interrupted. The helper backend was stopped after completion. Added tools/run_saved_chain_batch.py and tools/review_saved_chain_batch.py. Output: demos/pipeline-batch-20260909/, including chain snapshot, report, and three-way comparison against native and previous raster.

Exact processing: To Zero threshold 18% (anti-aliasing off) BEFORE StarSample V2 HQ, custom 4x with Separate Alpha; median blur radius 1; GEGL Mean Curvature Blur 3, Preserve Alpha off. The saved source-preview resize branch is not a final downscale. Threshold and both blurs can change alpha; preserved the user's settings rather than silently changing them. PyTorch used saved GPU 0/FP16 settings.

All ten runs succeeded, outputs verified as RGBA PNGs at 4x native dimensions. Saved chain SHA-256 remained unchanged. Pointer, metallic numeral, and Sword card visually inspected; pointer thumb fringe appears reduced, but fidelity is not approved across all assets. In-game replacement, mipmaps, and animation consistency remain untested. Next: user review of the batch before applying to level-one dumps.
