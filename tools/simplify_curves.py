"""Automatic simplification experiment. No manual path edits or source changes."""
import json
import copy
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree
from bezier_graph import fit


def sample(segments):
    parts = []
    for segment in segments:
        cp = np.asarray(segment)
        count = max(3, int(np.linalg.norm(np.diff(cp, axis=0), axis=1).sum()) + 1)
        t = np.linspace(0, 1, count, endpoint=False)
        b = np.stack(((1-t)**3, 3*t*(1-t)**2, 3*t*t*(1-t), t**3), axis=1)
        parts.extend(b @ cp)
    return np.vstack((parts, segments[-1][-1]))


def merge_arcs(model):
    arcs = [dict(start=p['start'], end=p['end'], points=sample(p['segments'])) for p in model['paths']]
    # Repair provenance boundaries are not geometric corners. Dissolve degree-two vertices.
    while True:
        incidence = {}
        for i, arc in enumerate(arcs):
            for end in ('start', 'end'):
                incidence.setdefault(arc[end], []).append(i)
        pair = next(((v, ids) for v, ids in incidence.items() if len(ids) == 2 and ids[0] != ids[1]), None)
        if pair is None:
            break
        vertex, (i, j) = pair
        a, b = arcs[i], arcs[j]
        if a['end'] != vertex:
            a = dict(start=a['end'], end=a['start'], points=a['points'][::-1])
        if b['start'] != vertex:
            b = dict(start=b['end'], end=b['start'], points=b['points'][::-1])
        arcs = [arc for k, arc in enumerate(arcs) if k not in (i, j)]
        arcs.append(dict(start=a['start'], end=b['end'], points=np.vstack((a['points'], b['points'][1:]))))
    return arcs


def write_svg(model, path):
    data = []
    for p in model['paths']:
        segments = p['segments']
        d = 'M' + ','.join(map(str, segments[0][0]))
        d += ' '.join(' C' + ' '.join(','.join(map(str, pt)) for pt in s[1:]) for s in segments)
        data.append(f'<path d="{d}"/>')
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {model["width"]} {model["height"]}" width="{model["width"]}" height="{model["height"]}"><g fill="none" stroke="black" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">'+''.join(data)+'</g></svg>')


def clean_junctions(model):
    """Collapse small graph tangles with a bounded cluster diameter, without feature masks."""
    result = copy.deepcopy(model)
    xy = np.array([v['point'] for v in model['vertices']])
    parent = list(range(len(xy)))
    groups = {i: {i} for i in parent}
    def owner(i):
        while parent[i] != i:
            i = parent[i]
        return i
    lengths = [np.linalg.norm(np.diff(sample(p['segments']), axis=0), axis=1).sum() for p in model['paths']]
    for index in np.argsort(lengths):
        p = model['paths'][index]
        if lengths[index] > 6:
            break
        a, b = owner(p['start']), owner(p['end'])
        if a == b:
            continue
        members = groups[a] | groups[b]
        points = xy[list(members)]
        if np.linalg.norm(points[:, None]-points[None, :], axis=2).max() > 8:
            continue
        parent[b] = a
        groups[a] = members
    centers = {owner(i): xy[list(groups[owner(i)])].mean(axis=0) for i in range(len(xy))}
    paths = []
    removed = 0
    for p, length in zip(result['paths'], lengths):
        start, end = owner(p['start']), owner(p['end'])
        if start == end and length <= 12:
            removed += 1
            continue
        # Translate endpoint handles with their shared junctions.
        first, last = p['segments'][0], p['segments'][-1]
        for segment, indices, old, new in [(first, (0, 1), first[0], centers[start]), (last, (2, 3), last[3], centers[end])]:
            delta = new-np.asarray(old)
            for i in indices:
                segment[i] = (np.asarray(segment[i])+delta).tolist()
        p.update(start=start, end=end, id=len(paths))
        paths.append(p)
    for i, vertex in enumerate(result['vertices']):
        vertex['point'] = centers[owner(i)].tolist()
    result['paths'] = paths
    result['cleanup'] = dict(removed_short_paths=removed, maximum_cluster_diameter=8)
    return result


def main():
    root = Path(__file__).resolve().parents[1] / 'assets/kirby/demos'
    model = json.loads((root/'bezier-paths/curves.json').read_text())
    out = root/'simple-curves'
    out.mkdir(exist_ok=True)
    arcs = merge_arcs(model)
    write_svg(model, out/'control.svg')
    report = []
    for name, sigma, tolerance in [('junction-cleanup', 2, 1.2), ('simple', 2, 2), ('simpler', 4, 5), ('minimal', 7, 9)]:
        current = clean_junctions(model) if name == 'junction-cleanup' else model
        arcs = merge_arcs(current)
        paths, deviations = [], []
        for arc in arcs:
            raw = arc['points']
            # Uniform distance sampling makes smoothing independent of input subdivision.
            distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(raw, axis=0), axis=1))]
            u = np.linspace(0, distance[-1], max(3, int(distance[-1])+1))
            points = np.column_stack([np.interp(u, distance, raw[:, axis]) for axis in (0, 1)])
            smooth = gaussian_filter1d(points, sigma, axis=0, mode='nearest')
            smooth[0], smooth[-1] = raw[0], raw[-1]
            segments = np.asarray(fit(smooth, tolerance=tolerance)).round(4).tolist()
            assert np.isfinite(segments).all()
            assert np.allclose(segments[0][0], raw[0])
            assert np.allclose(segments[-1][-1], raw[-1])
            for a, b in zip(segments, segments[1:]):
                assert a[-1] == b[0]
            output = sample(segments)
            deviations.append(max(cKDTree(output).query(raw)[0].max(), cKDTree(raw).query(output)[0].max()))
            paths.append(dict(id=len(paths), start=arc['start'], end=arc['end'], segments=segments))
        result = dict(current, paths=paths)
        write_svg(result, out/f'{name}.svg')
        (out/f'{name}.json').write_text(json.dumps(result))
        report.append(dict(name=name, paths=len(paths), cubics=sum(len(p['segments']) for p in paths), max_sampled_displacement=round(max(deviations), 2), smoothing_sigma=sigma, fit_tolerance=tolerance, cleanup=current.get('cleanup')))
    (out/'report.json').write_text(json.dumps(report, indent=2))
    def overlay(name):
        curves = (out/f'{name}.svg').read_text().replace('stroke="black"', 'stroke="#ff1685"')
        return '<div class="overlay"><img class="original" alt="Upscaled original" src="../hybrid-contours/mild/input.png">'+curves+'</div>'
    cards = '<article><h2>Control</h2><p>376 cubic segments</p>'+overlay('control')+'</article>'
    for item in report:
        cards += f'<article><h2>{item["name"].title()}</h2><p>{item["cubics"]} cubic segments · maximum sampled shift {item["max_sampled_displacement"]} px</p>'+overlay(item['name'])+'</article>'
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Automatic curve simplification</title>
<style>body{background:#242832;color:#eee;font:16px system-ui;margin:24px;--image-opacity:1;--line-opacity:1}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.overlay{position:relative;background:white}.original{display:block;width:100%;opacity:var(--image-opacity)}.overlay svg{position:absolute;inset:0;width:100%;height:100%;opacity:var(--line-opacity);pointer-events:none}h2{margin-bottom:4px}nav{position:sticky;top:0;z-index:2;padding:12px;background:#242832;display:flex;gap:24px;flex-wrap:wrap}label{display:flex;align-items:center;gap:8px}</style>
<h1>Automatic curve simplification</h1><p>Pink curves over the unchanged StarSample upscale used for this experiment. All panels share the same alignment.</p>
<nav><label>Original opacity <input aria-label="Original opacity" type="range" min="0" max="100" value="100" oninput="document.body.style.setProperty('--image-opacity',this.value/100)"></label><label><input type="checkbox" checked onchange="document.body.style.setProperty('--line-opacity',this.checked?1:0)">Show curves</label></nav>
<p>Junction-cleanup removes tiny graph tangles before fitting, with a tighter tolerance to retain mouth bends. Its shift measurement excludes junction movement. Other panels retain the previous method. Region crossings and lost details remain unvalidated.</p><main>'''+cards+'</main>', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
