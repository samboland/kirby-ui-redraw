"""Eye-like region proposal from dark components, ellipses, and robust upper envelopes.

Color and geometry heuristics, not a general semantic detector. No hand-selected boxes.
"""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image


def ellipse(mask, lid=None, return_candidates=False):
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
    ranked = []
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
        ranked.append((score, e))
    if not ranked:
        raise ValueError('No sufficiently supported truncated ellipse')
    ranked.sort(key=lambda item: item[0])
    return ranked if return_candidates else ranked[0][1]


def boundary(e, count=2048):
    center, size, angle = e
    t = np.arange(count)*2*np.pi/count
    theta = np.deg2rad(angle)
    rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    return (np.column_stack((np.cos(t), np.sin(t)))*(np.asarray(size)/2))@rotation.T+center


def ellipse_level(e, points):
    center, size, angle = e
    theta = np.deg2rad(angle)
    rotation = np.array([[np.cos(theta), np.sin(theta)], [-np.sin(theta), np.cos(theta)]])
    return (((points-center)@rotation.T/(np.asarray(size)/2))**2).sum(axis=1)


def joint_ellipses(whole, pupil, lid):
    outers = ellipse(whole, lid, True)
    irises = ellipse(pupil, lid, True)
    best = None
    rejected = 0
    # Full ellipse containment is deliberately stronger than visible-only containment.
    # The pupil remains inside the eye even behind an occluding eyelid.
    iris_points = [boundary(e) for _, e in irises]
    for outer_score, outer in outers:
        for (iris_score, iris), points in zip(irises, iris_points):
            score = outer_score+iris_score
            if best is not None and score >= best[0]:
                continue
            if ellipse_level(outer, points).max() > 1-1e-6:
                rejected += 1
                continue
            best = (score, outer, iris)
    if best is None:
        raise ValueError('No supported nested ellipse pair; retain the source instead')
    dense_max = float(ellipse_level(best[1], boundary(best[2], 32768)).max())
    assert dense_max <= 1, 'Dense containment validation failed'
    return best[1], best[2], dict(outer_candidates=len(outers), iris_candidates=len(irises), rejected_pairs=rejected, maximum_iris_level=dense_max, constraint='full ellipse containment sampled at 32768 points')


def element(e, fill):
    (x, y), (w, h), angle = e
    return f'<ellipse cx="{x:.3f}" cy="{y:.3f}" rx="{w/2:.3f}" ry="{h/2:.3f}" transform="rotate({angle:.3f} {x:.3f} {y:.3f})" fill="{fill}"/>'


def eyelid_band(rgb, hsv, left, right, coef, height):
    blue = (hsv[:, :, 0] >= 90) & (hsv[:, :, 0] <= 125) & (hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 130)
    samples = []
    for x in range(int(left), int(right)+1):
        t = (x-left)/(right-left)
        bottom = float(coef@[1, t, t*t])
        y = int(round(bottom))-2
        search = np.arange(max(0, y-12), min(len(blue), y+5))
        valid = search[blue[search, x]]
        if not len(valid):
            continue
        y = int(valid[np.argmin(np.abs(valid-y))])
        upper = y
        while upper > 0 and blue[upper-1, x] and y-upper < height*.45:
            upper -= 1
        thickness = bottom-upper
        if 3 < thickness < height*.4:
            samples.append((x, upper, bottom))
    if len(samples) < 12:
        return '', None
    data = np.asarray(samples)
    # Use the longest continuous run, avoiding unrelated blue regions.
    runs = np.split(data, np.flatnonzero(np.diff(data[:, 0]) > 3)+1)
    data = max(runs, key=len)
    if len(data) < 12:
        return '', None
    a, b = left, right
    t = (data[:, 0]-a)/(b-a)
    design = np.column_stack((np.ones(len(t)), t, t*t))
    # A lens-shaped band tapers into the shared endpoints instead of vertical end caps.
    basis = t*(1-t)
    thickness = np.clip(data[:, 2]-data[:, 1], 0, height*.4)
    amplitude = float(np.dot(basis, thickness)/max(np.dot(basis, basis), 1e-9))
    ta, tb = (a-left)/(right-left), (b-left)/(right-left)
    lower = np.array([coef@[1, ta, ta*ta], (coef[1]+2*coef[2]*ta)*(tb-ta), coef[2]*(tb-ta)**2])
    upper = lower+np.array([0, -amplitude, amplitude])
    d = f'M {a} {upper[0]} Q {(a+b)/2} {upper[0]+upper[1]/2} {b} {upper.sum()} L {b} {lower.sum()} Q {(a+b)/2} {lower[0]+lower[1]/2} {a} {lower[0]} Z'
    colors = [rgb[int((top+bottom)/2), int(x)] for x, top, bottom in data]
    color = '#'+''.join(f'{int(c):02x}' for c in np.median(colors, axis=0))
    return f'<path d="{d}" fill="{color}"/>', dict(path=d, color=color, samples=len(data))


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
        sclera_fragments = []
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
                if size > area*.01 and size/box_area < .35:
                    sclera_fragments.append(mask)
        whole = (pupil | sclera).astype('uint8')
        for fragment in sclera_fragments:
            whole |= fragment.astype('uint8')
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
        outer, iris, joint_info = joint_ellipses(whole, pupil, (left, right, coef))
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
        band, band_info = eyelid_band(rgb, hsv, left, right, coef, height)
        group += band
        markup.append(group)
        models.append(dict(component=i, bounds=[x,y,width,height], outer=outer, iris=iris, joint_fit=joint_info, highlights=len(highlights), rejected_highlights=rejected_highlights, sclera_fragments=len(sclera_fragments), eyelid_band=band_info, lid_quadratic=coef.tolist(), lid=lid))
    header = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    shapes = ''.join(markup)
    (out/'shapes.svg').write_text(header+shapes+'</svg>')
    lines = ''.join(f'<path d="{m["lid"]}" fill="none" stroke="#00ff70" stroke-width="2"/>'+element(m['outer'], 'none').replace('fill="none"','fill="none" stroke="#ff1685" stroke-width="1"')+element(m['iris'], 'none').replace('fill="none"','fill="none" stroke="#00ffff" stroke-width="1"') for m in models)
    lines += ''.join(f'<path d="{m["eyelid_band"]["path"]}" fill="none" stroke="#ffad00" stroke-width="1"/>' for m in models if m['eyelid_band'])
    (out/'overlay.svg').write_text(header+'<image href="../hybrid-contours/mild/input.png" width="512" height="512"/>'+lines+'</svg>')
    (out/'models.json').write_text(json.dumps(models, indent=2))
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Simple eye shapes</title><style>body{background:#242832;color:white;font:16px system-ui;margin:24px}main{display:grid;grid-template-columns:1fr 1fr;gap:24px}object{width:100%;aspect-ratio:1;background:#587f9c}h2{margin-bottom:8px}</style><h1>Automatic eye-shape proposals</h1><p>Detected from dark regions and adjacent whites. No manually selected eye coordinates. Green: proposed eyelid. Pink: outer ellipse. Cyan: iris ellipse. Orange: eyelid outline.</p><main><section><h2>Fit over original</h2><object data="overlay.svg" type="image/svg+xml"></object></section><section><h2>Vector shapes only</h2><object data="shapes.svg" type="image/svg+xml"></object></section></main><p>Flat colors expose geometry. Blue eyelids use two quadratic curves with tapering ends. Their thickness is estimated from the source blue band. Highlights and eyes remain beneath the eyelid clip. The mouth and original asset are unchanged. This is a color-based proposal, not a validated general detector; overlap order is assumed.</p>''', encoding='utf-8')
    assert len(models) > 0
    assert all(np.isfinite(np.asarray(m['lid_quadratic'])).all() for m in models)
    print(json.dumps(models, indent=2))


if __name__ == '__main__':
    main()
