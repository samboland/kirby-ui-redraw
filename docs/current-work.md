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
