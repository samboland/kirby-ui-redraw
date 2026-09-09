# UI Redraw

Reconstruct low-resolution game UI as editable vector geometry, starting with Kirby's Return to Dream Land (USA, SUKE01).

The first stage extracts native assets from the user's disc image and creates a searchable local catalog. The tracing stage calls the Potrace DLL bundled with the user's installed Inkscape. No generative raster upscaling is used.

## Setup

Windows, Python 3.14, Pillow 12.2, NumPy 2.4, DolphinTool with the `extract` command, and Inkscape 1.3.2 were used for the initial run.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
& 'C:\Program Files\Dolphin Emulator\DolphinTool.exe' extract -i 'PATH_TO_YOUR_DISC.iso' -o work/disc -g -q
.\.venv\Scripts\python tools/extract_textures.py work/disc/DATA/files assets/kirby
Start-Process assets/kirby/index.html
```

The catalog opens as a local HTML file without a server. UI candidates appear first. Search matches original archive paths and texture names. Click a thumbnail for the unscaled PNG. `manifest.json` records every source reference; identical decoded images share one PNG.

## Trace one asset

```powershell
python tools/trace.py assets/kirby/textures/SELECTED.png work/selected.svg --mode alpha
inkscape work/selected.svg --export-type=png --export-filename=work/selected-4x.png --export-width=256
```

Choose a width of four times the original width. Alpha mode extracts opaque silhouettes, while dark mode extracts dark marks on a visible background. Outputs are black vector paths, not a reconstruction of multicolor art. Soft shadows, gradients, and font identification remain future work. `--threshold`, `--speckles`, `--corners`, and `--tolerance` control the trace. A JSON sidecar records parameters and library version.

## Extraction scope

The extractor reads Nintendo LZ10/LZ11, nested U8 archives, TPL images, BRRES TEX0/PLT0 images, BRFNT glyph sheets, and BREFT particle textures. It exports base mip levels. Original disc files, including unsupported formats, remain under `work/disc`. Videos are not decoded into frames. Each failed container is recorded in `assets/kirby/report.json`; inspect it before claiming complete coverage.

Exported filenames identify source assets. They are not yet Dolphin replacement hashes. In-game material colors, texture combiners, layout transforms, and lighting are not baked into these raw images.

## Validation

```powershell
python -m unittest discover -s tools -p test_*.py -v
```

Synthetic tests cover compression, archive reading, byte ordering, alpha, palettes, tiled block order, and CMPR quadrants. These tests do not replace visual review of game assets.

## Project data

`assets/`, `work/`, `.venv/`, and game images are ignored by git. Keep game data local. Commit source tools and documentation only. The Inkscape DLL is not bundled or copied into this project.

See `docs/formats.md` for format references and `docs/current-work.md` for the handoff.
