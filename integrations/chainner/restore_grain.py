"""Reference-guided procedural grain. No model or GPU is required."""
from __future__ import annotations

import cv2
import numpy as np


def restore_grain(image, reference, strength=60, grain_size=1.5,
                  sensitivity=50, edge_protection=80, seed=0):
    """Return RGB(A) and an estimated texture mask. Inputs are normalized BGR(A)."""
    image = np.asarray(image, dtype=np.float32)
    reference = np.asarray(reference, dtype=np.float32)
    for a in (image, reference):
        if a.ndim != 3 or a.shape[2] not in (3, 4) or not np.isfinite(a).all():
            raise ValueError('Expected finite RGB or RGBA images.')
    if not 0 <= strength <= 200 or grain_size <= 0:
        raise ValueError('Invalid strength or grain size.')
    if not 0 <= sensitivity <= 100 or not 0 <= edge_protection <= 100:
        raise ValueError('Sensitivity and edge protection must be 0–100.')
    h, w = image.shape[:2]
    if abs(w / h - reference.shape[1] / reference.shape[0]) > 0.01:
        raise ValueError('Image and reference must have matching aspect ratios.')
    rgb = reference[:, :, :3]
    alpha = reference[:, :, 3] if reference.shape[2] == 4 else np.ones(rgb.shape[:2], np.float32)

    def blur(a, sigma):
        return cv2.GaussianBlur(a, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)

    # Normalized convolution prevents hidden transparent colors entering estimates.
    def smooth_rgb(sigma):
        weight = blur(alpha, sigma)
        return blur(rgb * alpha[:, :, None], sigma) / np.maximum(weight[:, :, None], 1e-6)

    fine = smooth_rgb(0.55)
    mid = smooth_rgb(1.3)
    broad = smooth_rgb(3.0)
    bands = [rgb - fine, fine - mid, mid - broad]
    valid = cv2.erode((alpha > 0.98).astype(np.float32), np.ones((5, 5), np.uint8))
    gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3) / 8
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3) / 8
    xx, yy, xy = blur(gx * gx, 2), blur(gy * gy, 2), blur(gx * gy, 2)
    coherence = np.sqrt((xx - yy)**2 + 4 * xy**2) / (xx + yy + 1e-8)
    energy = np.sqrt(blur(np.mean(bands[0]**2 + bands[1]**2, axis=2), 2))
    floor = (0.1 + (100 - sensitivity) * 0.012) / 255
    texture = np.clip((energy - floor) / (3 * floor + 1e-8), 0, 1)
    texture *= (1 - edge_protection / 100 * coherence)**2
    # Keep texture away from pronounced boundaries, including nondirectional corners.
    strong = np.sqrt(gx * gx + gy * gy)
    edge = cv2.dilate(np.clip((strong - 0.10) / 0.15, 0, 1), np.ones((3, 3), np.uint8))
    texture *= 1 - edge_protection / 100 * edge
    texture *= valid
    mask = cv2.resize(texture, (w, h), interpolation=cv2.INTER_LINEAR)
    if image.shape[2] == 4:
        mask *= image[:, :, 3]
    mask = np.clip(mask, 0, 1)
    rng = np.random.default_rng(int(seed))
    delta = np.zeros((h, w, 3), np.float32)
    for band, scale in zip(bands, (0.45, 1.2, 3.2)):
        amplitude = np.sqrt(blur(band * band * valid[:, :, None], 2))
        amplitude = cv2.resize(amplitude, (w, h), interpolation=cv2.INTER_LINEAR)
        noise = rng.standard_normal((h, w), dtype=np.float32)
        noise = blur(noise, max(0.2, grain_size * scale))
        noise -= noise.mean()
        noise /= max(float(noise.std()), 1e-6)
        # Shared noise across channels produces luminance grain, not RGB confetti.
        delta += noise[:, :, None] * amplitude
    result = image.copy()
    if strength:
        result[:, :, :3] = np.clip(image[:, :, :3] + delta * mask[:, :, None] * strength / 100, 0, 1)
    return result, mask


# Imports are kept below the numerical core so it can be tested independently.
from nodes.properties.inputs import ImageInput, NumberInput
from nodes.properties.outputs import ImageOutput
from .. import correction_group


@correction_group.register(
    schema_id='sam:image:restore_grain',
    name='Restore Grain from Reference',
    description='Generate new multiscale grain where the original contains fine texture. Connect the final upscale and untouched original. Alpha is preserved exactly. Mask output shows affected areas. This is an estimate: compression noise can also trigger it. Use after blur and final resize. Not guaranteed seamless for tiled textures.',
    icon='MdGrain',
    inputs=[ImageInput('Image', channels=[3, 4]),
            ImageInput('Reference Image', channels=[3, 4]),
            NumberInput('Strength', min=0, max=200, default=60, unit='%'),
            NumberInput('Grain Size', min=0.25, max=16, default=1.5, precision=2, unit='px'),
            NumberInput('Sensitivity', min=0, max=100, default=50),
            NumberInput('Edge Protection', min=0, max=100, default=80, unit='%'),
            NumberInput('Seed', min=0, max=2147483647, default=0)],
    outputs=[ImageOutput('Image', shape_as=0),
             ImageOutput('Texture Mask', image_type='Image { channels: 1 }')],
)
def restore_grain_node(image, reference, strength, grain_size, sensitivity, edge_protection, seed):
    return restore_grain(image, reference, strength, grain_size, sensitivity, edge_protection, seed)
