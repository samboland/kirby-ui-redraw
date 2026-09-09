"""Eye-like region proposal from dark components, ellipses, and robust upper envelopes.

Color and geometry heuristics, not a general semantic detector. No hand-selected boxes.
"""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


def ellipse(mask, lid=None):
    contours, _ = cv2.findContours(mask.astype('uint8'), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    points = max(contours, key=cv2.contourArea)[:, 0, :]
    if lid is not None:
        left, right, coef = lid
        t = (points[:, 0]-left)/max(right-left, 1)
        points = points[points[:, 1] > coef[0]+coef[1]*t+coef[2]*t*t+3]
    if len(points) < 12:
        raise ValueError('Insufficient exposed arc for ellipse fitting')
    span = np.ptp(points, axis=0).astype(float)
    center = points.mean(axis=0)
    candidates = [points]
    rng = np.random.default_rng(42)
    # Fit contiguous exposed arcs rather than treating every mask edge as ellipse evidence.
    for _ in range(240):
        count = max(8, int(len(points)*rng.uniform(.3, .8)))
        start = rng.integers(len(points))
        candidates.append(points[(np.arange(count)+start) % len(points)])
    best = None
    for subset in candidates:
        e = cv2.fitEllipse(subset.astype('float32'))
        c, size, angle = e
        radii = np.asarray(size)/2
        if radii.min() < 3 or radii.max() > span.max()*1.8 or radii.max()/radii.min() > 4:
            continue
        if np.linalg.norm(np.asarray(c)-center) > span.max():
            continue
        theta = np.deg2rad(angle)
        rotation = np.array([[np.cos(theta), np.sin(theta)], [-np.sin(theta), np.cos(theta)]])
        local = (points-np.asarray(c))@rotation.T
        normalized = local/radii
        f = (normalized**2).sum(axis=1)-1
        distance = np.abs(f)/np.maximum(2*np.linalg.norm(local/radii**2, axis=1), 1e-6)
        # Occlusion removes ellipse area; it cannot put visible eye pixels outside it.
        outside_penalty = np.maximum(distance-3, 0)*(f > 0)
        inliers = distance < 1.5
        # A short arc cannot strongly constrain hidden continuation.
        bins = np.floor((np.arctan2(normalized[:, 1], normalized[:, 0])+np.pi)*12/(2*np.pi)).astype(int)%12
        coverage = len(np.unique(bins[inliers]))
        if coverage < 5:
            continue
        score = float(np.minimum(1.5, distance).sum()+outside_penalty.sum()*4)
        if best is None or score < best[0]:
            best = (score, e, int(inliers.sum()), len(points), coverage)
    if best is None:
        raise ValueError('No sufficiently supported truncated ellipse')
    return best[1]


def element(e, fill):
    (x, y), (w, h), angle = e
    return f'<ellipse cx="{x:.3f}" cy="{y:.3f}" rx="{w/2:.3f}" ry="{h/2:.3f}" transform="rotate({angle:.3f} {x:.3f} {y:.3f})" fill="{fill}"/>'


def main():
    root = Path(__file__).resolve().parents[1]/'assets/kirby/demos'
    out = root/'truncated-eyes'
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
        highlights = []
        rejected_highlights = []
        for mask in whites:
            if mask is sclera:
                continue
            yy, xx = np.where(mask)
            size = int(mask.sum())
            box_area = int((xx.max()-xx.min()+1)*(yy.max()-yy.min()+1))
            # Thin anti-aliased sclera fragments are not compact specular highlights.
            if max(8, area*.005) <= size < area*.3 and size/box_area >= .35:
                highlights.append(mask)
            else:
                rejected_highlights.append(dict(area=size, box_fill=size/box_area))
        whole = (pupil | sclera).astype('uint8')
        whole = cv2.morphologyEx(whole, cv2.MORPH_CLOSE, np.ones((5, 5), 'uint8'))
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
        outer, iris = ellipse(whole, (left, right, coef)), ellipse(pupil, (left, right, coef))
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
        models.append(dict(component=i, bounds=[x,y,width,height], outer=outer, iris=iris, highlights=len(highlights), rejected_highlights=rejected_highlights, lid_quadratic=coef.tolist(), lid=lid))
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
