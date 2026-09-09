"""Automatic simplification experiment. No manual path edits or source changes."""
import json
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


def main():
    root = Path(__file__).resolve().parents[1] / 'assets/kirby/demos'
    model = json.loads((root/'bezier-paths/curves.json').read_text())
    out = root/'simple-curves'
    out.mkdir(exist_ok=True)
    arcs = merge_arcs(model)
    write_svg(model, out/'control.svg')
    report = []
    for name, sigma, tolerance in [('simple', 2, 2), ('simpler', 4, 5), ('minimal', 7, 9)]:
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
        result = dict(model, paths=paths)
        write_svg(result, out/f'{name}.svg')
        (out/f'{name}.json').write_text(json.dumps(result))
        report.append(dict(name=name, paths=len(paths), cubics=sum(len(p['segments']) for p in paths), max_sampled_displacement=round(max(deviations), 2), smoothing_sigma=sigma, fit_tolerance=tolerance))
    (out/'report.json').write_text(json.dumps(report, indent=2))
    cards = '<article><h2>Control</h2><p>376 cubic segments</p><img src="control.svg"></article>'
    for item in report:
        cards += f'<article><h2>{item["name"].title()}</h2><p>{item["cubics"]} cubic segments · maximum sampled shift {item["max_sampled_displacement"]} px</p><img src="{item["name"]}.svg"></article>'
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Automatic curve simplification</title><style>body{background:#242832;color:#eee;font:16px system-ui;margin:24px}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}img{background:white;width:100%}h2{margin-bottom:4px}</style><h1>Automatic curve simplification</h1><p>Same connected line network, progressively fewer curves. No manual edits. Shared junctions stay fixed.</p><p>This experiment does not fix incorrect connections or validate region crossings. Shading is deferred.</p><main>'+cards+'</main>', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
