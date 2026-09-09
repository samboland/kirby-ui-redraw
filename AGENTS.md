# UI Redraw instructions

Purpose: original game asset extraction, visual review, and editable vector reconstruction. Start with the Potrace library installed with Inkscape. Sam authorized mixed vector and AI upscaling demos on 2026-09-08. Compare methods by asset type. Label generative reconstruction separately from dedicated super-resolution. Reject changed artwork and preserve originals.

Read README.md and docs/current-work.md before changes. Preserve source resolution, alpha, original names, and source-container provenance. Mark unknown formats and uncertain mappings explicitly.

Keep all extracted assets, source ISOs, cached archives, contact sheets, and local configuration out of git. Do not modify the user's ISO or Dolphin settings. Do not launch games. User review happens through the local catalog and trace comparisons.

Run the decoder tests after extraction changes. Inspect PNG output before claiming image fidelity. Store machine-readable extraction counts and errors with local assets.

Commit source changes on main and push when a remote exists. Do not create feature branches. Do not delegate unless explicitly requested.
