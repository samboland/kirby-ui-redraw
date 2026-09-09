"""Rank whole-contour single-cubic proposals using nearby edge agreement."""
import copy
import json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from simplify_curves import sample, write_svg


def unit(v):
    return v / max(np.linalg.norm(v), 1e-9)


def chains(model):
    paths = model['paths']
    points = [sample(p['segments']) for p in paths]
    incidence = {}
    for i, p in enumerate(paths):
        for end in (0, 1):
            incidence.setdefault(p['start' if end == 0 else 'end'], []).append((i, end))
    pairs = {}
    for entries in incidence.values():
        options = []
        for j, a in enumerate(entries):
            pa = points[a[0]][::1 if a[1] == 0 else -1]
            ta = unit(pa[min(8, len(pa)-1)]-pa[0])
            for b in entries[j+1:]:
                if a[0] == b[0]:
                    continue
                pb = points[b[0]][::1 if b[1] == 0 else -1]
                tb = unit(pb[min(8, len(pb)-1)]-pb[0])
                options.append((-float(ta@tb), a, b))
        for score, a, b in sorted(options, reverse=True):
            if score > .55 and a not in pairs and b not in pairs:
                pairs[a], pairs[b] = b, a
    seen, result = set(), []
    starts = [(i, e) for i in range(len(paths)) for e in (0, 1) if (i, e) not in pairs]
    starts += [(i, 0) for i in range(len(paths))]
    for start in starts:
        current, ids, coords = start, [], []
        while current[0] not in seen:
            i, end = current
            seen.add(i)
            p = points[i][::1 if end == 0 else -1]
            coords.extend(p if not coords else p[1:])
            ids.append(i)
            next_end = (i, 1-end)
            if next_end not in pairs:
                break
            current = pairs[next_end]
        if ids:
            result.append(dict(ids=ids, points=np.asarray(coords)))
    return result


def cubic(points):
    distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    t = distance/max(distance[-1], 1e-9)
    b = np.stack(((1-t)**3, 3*t*(1-t)**2, 3*t*t*(1-t), t**3), axis=1)
    ends = b[:, :1]*points[0]+b[:, 3:]*points[-1]
    handles = np.linalg.lstsq(b[:, 1:3], points-ends, rcond=None)[0]
    cp = np.vstack((points[0], handles, points[-1]))
    return cp, b@cp, distance[-1]


def main():
    root = Path(__file__).resolve().parents[1]/'assets/kirby/demos'
    out = root/'neighbor-curves'
    out.mkdir(exist_ok=True)
    model = json.loads((root/'simple-curves/junction-cleanup.json').read_text())
    contours = chains(model)
    proposals = []
    for i, contour in enumerate(contours):
        p = contour['points']
        cp, fitted, length = cubic(p)
        if length < 25 or np.linalg.norm(p[-1]-p[0]) < length*.45:
            continue
        residual = np.linalg.norm(fitted-p, axis=1)
        if residual.max() < 1.5 or residual.max() > 12:
            continue
        tangent = np.gradient(fitted, axis=0)
        tangent /= np.maximum(np.linalg.norm(tangent, axis=1, keepdims=True), 1e-9)
        best = (0, None)
        for j, neighbor in enumerate(contours):
            if i == j:
                continue
            q = neighbor['points']
            if len(q) < 15:
                continue
            _, smooth, qlength = cubic(q)
            if qlength < 25 or np.sqrt(np.mean((smooth-q)**2)) > 2:
                continue
            distance, indices = cKDTree(q).query(fitted)
            qt = np.gradient(q, axis=0)
            qt /= np.maximum(np.linalg.norm(qt, axis=1, keepdims=True), 1e-9)
            agree = (np.abs(np.sum(tangent*qt[indices], axis=1)) > .9) & (distance > 2) & (distance < 22)
            support = float(agree.mean())
            if support > best[0]:
                best = (support, j)
        if best[0] < .25:
            continue
        # Favor deviations concentrated on short portions over broad shape changes.
        occupied = float((residual > residual.max()*.5).mean())
        score = best[0]*(1-occupied)*float(residual.max())
        proposals.append(dict(contour=i, path_ids=contour['ids'], neighbor=best[1], support=best[0], residual_occupancy=occupied, max_shift=float(residual.max()), score=score, cubic=cp.tolist()))
    proposals.sort(key=lambda p: p['score'], reverse=True)
    (out/'proposals.json').write_text(json.dumps(proposals, indent=2))
    write_svg(model, out/'control.svg')
    cards = []
    for rank, proposal in enumerate(proposals[:6], 1):
        result = copy.deepcopy(model)
        result['paths'] = [p for i, p in enumerate(result['paths']) if i not in proposal['path_ids']]
        result['paths'].append(dict(segments=[proposal['cubic']]))
        write_svg(result, out/f'candidate-{rank}.svg')
        svg = (out/f'candidate-{rank}.svg').read_text().replace('stroke="black"', 'stroke="#ff1685"')
        old = copy.deepcopy(model)
        old['paths'] = [model['paths'][i] for i in proposal['path_ids']]
        write_svg(old, out/f'before-{rank}.svg')
        original_svg = (out/f'before-{rank}.svg').read_text()
        group = original_svg[original_svg.index('<g '):original_svg.index('</g>')+4]
        outline = group.replace('stroke="black"', 'stroke="#10232b" stroke-dasharray="7 4"').replace('stroke-width="1"', 'stroke-width="5"')
        cyan = group.replace('stroke="black"', 'stroke="#00ffff" stroke-dasharray="7 4"').replace('stroke-width="1"', 'stroke-width="3"')
        old_svg = original_svg[:original_svg.index('<g ')] + outline + cyan + '</svg>'
        cards.append(f'<article><h2>Automatic proposal {rank}</h2><p>Nearby agreement {proposal["support"]:.0%}; maximum shift {proposal["max_shift"]:.1f}px</p><div class="stack"><img src="../hybrid-contours/mild/input.png">{svg}<div class="before">{old_svg}</div></div></article>')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Nearby-edge proposals</title><style>body{background:#242832;color:white;font:16px system-ui;margin:24px}main{display:grid;grid-template-columns:1fr 1fr;gap:20px}.stack{position:relative;background:white}.stack img{display:block;width:100%;opacity:.7}.stack svg{position:absolute;inset:0;width:100%;height:100%}.before{display:var(--before,block)}nav{position:sticky;top:0;background:#242832;padding:12px;z-index:2}</style><h1>Nearby-edge proposals</h1><p>Pink: proposed network. Cyan: replaced contour. Ranked automatically across the whole image, without eyelid coordinates.</p><nav><label><input type="checkbox" checked onchange="document.body.style.setProperty('--before',this.checked?'block':'none')">Show previous contour</label></nav><p>Proposals only. Branches are not reattached after contour replacement. The score is a heuristic, not confidence. Native-source evidence and crossing checks are not implemented.</p><main>'''+(''.join(cards) or '<p>No candidates passed.</p>')+'</main>', encoding='utf-8')
    print(json.dumps([{k:v for k,v in p.items() if k!='cubic'} for p in proposals[:6]], indent=2))


if __name__ == '__main__':
    main()
