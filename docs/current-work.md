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
