"""Eye-like region proposal from dark components, ellipses, and robust upper envelopes.

Color and geometry heuristics, not a general semantic detector. No hand-selected boxes.
"""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


def ellipse(mask):
    contours, _ = cv2.findContours(mask.astype('uint8'), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    points = max(contours, key=cv2.contourArea)[:, 0, :]
    # The upper boundary can contain occlusions. Fit the visible lower and side arc.
    cutoff = np.quantile(points[:, 1], .35)
    lower = points[points[:, 1] >= cutoff]
    return cv2.fitEllipse(lower.astype('float32'))


def element(e, fill):
    (x, y), (w, h), angle = e
    return f'<ellipse cx="{x:.3f}" cy="{y:.3f}" rx="{w/2:.3f}" ry="{h/2:.3f}" transform="rotate({angle:.3f} {x:.3f} {y:.3f})" fill="{fill}"/>'


def main():
    root = Path(__file__).resolve().parents[1]/'assets/kirby/demos'
    out = root/'eye-shapes'
    out.mkdir(exist_ok=True)
    rgba = np.asarray(Image.open(root/'hybrid-contours/mild/input.png').convert('RGBA'))
    rgb, alpha = rgba[:, :, :3], rgba[:, :, 3]
    h, w = alpha.shape
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    dark = ((hsv[:, :, 2] < 115) & (alpha > 128)).astype('uint8')
    n, labels, stats, _ = cv2.connectedComponentsWithStats(dark)
    models, markup = [], []
    for i in range(1, n):
        x, y, width, height, area = map(int, stats[i])
        if area < w*h*.002 or not .35 < width/height < 1.6 or area/(width*height) < .3:
            continue
        pupil = labels == i
        # White components adjacent to the dark component are proposed sclera/highlights.
        neutral = ((hsv[:, :, 1] < 65) & (hsv[:, :, 2] > 145) & (alpha > 128)).astype('uint8')
        count, white_labels, white_stats, _ = cv2.connectedComponentsWithStats(neutral)
        nearby = cv2.dilate(pupil.astype('uint8'), np.ones((9, 9), 'uint8')) > 0
        ids = [j for j in np.unique(white_labels[nearby]) if j and white_stats[j, 4] < area*3]
        whites = [white_labels == j for j in ids]
        if not whites:
            continue
        sclera = max(whites, key=np.sum)
        highlights = [mask for mask in whites if mask is not sclera and mask.sum() < area*.3]
        whole = (pupil | sclera).astype('uint8')
        whole = cv2.morphologyEx(whole, cv2.MORPH_CLOSE, np.ones((5, 5), 'uint8'))
        outer, iris = ellipse(whole), ellipse(pupil)
        # Robust quadratic upper envelope ignores downward detours around highlights.
        xs = np.flatnonzero(whole.any(axis=0))
        top = np.array([np.flatnonzero(whole[:, col])[0] for col in xs], float)
        t = (xs-xs[0])/max(float(xs[-1]-xs[0]), 1)
        design = np.column_stack((np.ones(len(t)), t, t*t))
        weights = np.ones(len(t))
        for _ in range(12):
            coef = np.linalg.lstsq(design*weights[:, None]**.5, top*weights**.5, rcond=None)[0]
            residual = top-design@coef
            weights = np.where(residual > 0, .12, .88)
        left, right = float(xs[0]), float(xs[-1])
        y0, y1 = float(coef[0]), float(coef.sum())
        control_y = float(coef[0]+coef[1]/2)
        lid = f'M {left} {y0} Q {(left+right)/2} {control_y} {right} {y1}'
        clip = lid+f' L {right+width} {h} L {left-width} {h} Z'
        identifier = len(models)
        group = f'<defs><clipPath id="lid{identifier}"><path d="{clip}"/></clipPath></defs><g clip-path="url(#lid{identifier})">'
        group += element(outer, '#f4f4f2')+element(iris, '#17254d')
        for mask in highlights:
            contours, _ = cv2.findContours(mask.astype('uint8'), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            contour = max(contours, key=cv2.contourArea)
            if len(contour) >= 5:
                group += element(cv2.fitEllipse(contour), '#ffffff')
        group += '</g>'
        markup.append(group)
        models.append(dict(component=i, bounds=[x,y,width,height], outer=outer, iris=iris, highlights=len(highlights), lid_quadratic=coef.tolist(), lid=lid))
    header = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    shapes = ''.join(markup)
    (out/'shapes.svg').write_text(header+shapes+'</svg>')
    lines = ''.join(f'<path d="{m["lid"]}" fill="none" stroke="#00ff70" stroke-width="2"/>'+element(m['outer'], 'none').replace('fill="none"','fill="none" stroke="#ff1685" stroke-width="1"')+element(m['iris'], 'none').replace('fill="none"','fill="none" stroke="#00ffff" stroke-width="1"') for m in models)
    (out/'overlay.svg').write_text(header+'<image href="../hybrid-contours/mild/input.png" width="512" height="512"/>'+lines+'</svg>')
    (out/'models.json').write_text(json.dumps(models, indent=2))
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Simple eye shapes</title><style>body{background:#242832;color:white;font:16px system-ui;margin:24px}main{display:grid;grid-template-columns:1fr 1fr;gap:24px}object{width:100%;aspect-ratio:1;background:#587f9c}h2{margin-bottom:8px}</style><h1>Automatic eye-shape proposals</h1><p>Detected from dark regions and adjacent whites. No manually selected eye coordinates. Green: proposed eyelid. Pink: outer ellipse. Cyan: iris ellipse.</p><main><section><h2>Fit over original</h2><object data="overlay.svg" type="image/svg+xml"></object></section><section><h2>Vector shapes only</h2><object data="shapes.svg" type="image/svg+xml"></object></section></main><p>Flat colors expose geometry. Highlights and eyes are layered beneath a quadratic eyelid clip. The mouth and original asset are unchanged. This is a color-based proposal, not a validated general detector; overlap order is assumed.</p>''', encoding='utf-8')
    assert len(models) > 0
    assert all(np.isfinite(np.asarray(m['lid_quadratic'])).all() for m in models)
    print(json.dumps(models, indent=2))


if __name__ == '__main__':
    main()
