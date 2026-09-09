# Mean Curvature Blur for chaiNNer

Installed and tested against chaiNNer 0.25.1 on Windows, using GIMP 3's bundled GEGL executable.

Save your chain and restart chaiNNer. Search for **Mean Curvature Blur (GIMP)** under Image Filter > Blur.

Connect: **Upscale Image > Mean Curvature Blur (GIMP) > Resize > Save Image**.

- Iterations defaults to 2. Start with 1–3. Zero returns the input unchanged.
- Preserve Alpha defaults off, returning GEGL's output. Enable it to restore the original input alpha after filtering.
- The node uses 16-bit PNG transfer to GEGL and returns normalized float image data. Dimensions and channel count are preserved.
- GEGL runs without a visible window. Temporary images are removed after completion or failure.
- This calls the actual `gegl:mean-curvature-blur` operation; it is not an approximation.

GIMP is located through `CHAINNER_GEGL_PATH`, PATH, or `C:\Program Files\GIMP 3\bin\gegl.exe`.

## Reinstall after chaiNNer updates

The node is installed into chaiNNer's existing Blur package. Application updates can remove it. Run:

```powershell
& C:\Users\sam\Dev-Projects\ui-redraw\integrations\chainner\install.ps1
```

The installer copies only this node and backs up a differing prior copy. An optional `-ResourcesPath` selects another backend source directory.

Restart is left to the user so an unsaved chain is not interrupted.

Reference: https://gegl.org/operations/gegl-mean-curvature-blur.html
