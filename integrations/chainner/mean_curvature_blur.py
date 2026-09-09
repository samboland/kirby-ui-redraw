"""Local chaiNNer node backed by GIMP's actual GEGL operation."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from nodes.properties.inputs import BoolInput, ImageInput, NumberInput
from nodes.properties.outputs import ImageOutput
from .. import blur_group


def apply_mean_curvature(img: np.ndarray, iterations: int, preserve_alpha: bool) -> np.ndarray:
    if not 0 <= iterations <= 500:
        raise ValueError('Iterations must be between 0 and 500.')
    if iterations == 0:
        return img
    executable = os.environ.get('CHAINNER_GEGL_PATH') or shutil.which('gegl')
    if not executable:
        executable = str(Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'GIMP 3/bin/gegl.exe')
    if not Path(executable).is_file():
        raise RuntimeError('GEGL was not found. Install GIMP 3 or set CHAINNER_GEGL_PATH to gegl.exe, then restart chaiNNer.')
    with tempfile.TemporaryDirectory(prefix='chainner-curvature-') as folder:
        source = Path(folder) / 'input.png'
        target = Path(folder) / 'output.png'
        encoded = np.rint(np.clip(img, 0, 1) * 65535).astype(np.uint16)
        if not cv2.imwrite(str(source), encoded):
            raise RuntimeError('Could not write the GEGL input image.')
        command = [executable, '--', 'gegl:load', f'path={source}',
                   'gegl:mean-curvature-blur', f'iterations={iterations}',
                   'gegl:png-save', f'path={target}', 'bitdepth=16']
        result = subprocess.run(command, capture_output=True, text=True, errors='replace',
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=600)
        if result.returncode:
            raise RuntimeError(f'GEGL failed ({result.returncode}): {result.stderr[-3000:]}')
        output = cv2.imread(str(target), cv2.IMREAD_UNCHANGED)
        if output is None:
            raise RuntimeError('GEGL did not return a readable image.')
        output = output.astype(np.float32) / (65535 if output.dtype == np.uint16 else 255)
        channels = 1 if img.ndim == 2 else img.shape[2]
        if channels == 1:
            if output.ndim == 3:
                output = output[:, :, 0]
            if img.ndim == 3:
                output = output[:, :, None]
        elif channels == 3:
            output = output[:, :, :3]
        if output.shape != img.shape:
            raise RuntimeError(f'GEGL changed image shape: {img.shape} to {output.shape}.')
        if preserve_alpha and channels == 4:
            output[:, :, 3] = img[:, :, 3]
        return np.clip(output, 0, 1)


@blur_group.register(
    schema_id='sam:gimp:mean_curvature_blur',
    name='Mean Curvature Blur (GIMP)',
    description='Runs GIMP GEGL Mean Curvature Blur. Start at 1–3 iterations on an oversampled image, then resize down. Uses 16-bit PNG transfer. Requires GIMP 3. Zero iterations bypasses processing.',
    icon='MdBlurOn',
    inputs=[ImageInput(), NumberInput('Iterations', min=0, max=500, default=2),
            BoolInput('Preserve Alpha', default=False).with_docs('Restore the input alpha after filtering. Disable for the GEGL operation output without alpha replacement.')],
    outputs=[ImageOutput(shape_as=0)],
)
def mean_curvature_blur_node(img: np.ndarray, iterations: int, preserve_alpha: bool) -> np.ndarray:
    return apply_mean_curvature(img, iterations, preserve_alpha)
