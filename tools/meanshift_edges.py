"""Mean-shift preprocessing and edge proposals, without palette quantization."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, binary_erosion


def edge_map(rgb, visible):
    lab=cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB)
    edges=np.zeros(visible.shape,np.uint8)
    for channel in cv2.split(lab):
        channel=cv2.GaussianBlur(channel,(0,0),.6)
        edges=cv2.bitwise_or(edges,cv2.Canny(channel,30,70,L2gradient=True))
    edges[~binary_erosion(visible,iterations=2)]=0
    return edges


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    rgba=np.asarray(Image.open(args.source).convert('RGBA')).copy()
    rgb=rgba[:,:,:3];alpha=rgba[:,:,3];visible=alpha>=128
    if not visible.any():raise ValueError('Input has no opaque region')
    # Hidden colors never participate: extend the closest visible RGB outside alpha.
    nearest=distance_transform_edt(~visible,return_distances=False,return_indices=True)
    extended=rgb.copy();extended[~visible]=rgb[nearest[0],nearest[1]][~visible]
    lab=cv2.cvtColor(extended,cv2.COLOR_RGB2LAB)
    reports=[]
    settings=[('control',0,0),('mild',6,10),('medium',12,20),('strong',20,30)]
    for name,sp,sr in settings:
        if sp:
            filtered_lab=cv2.pyrMeanShiftFiltering(lab,sp,sr,maxLevel=1,
                termcrit=(cv2.TERM_CRITERIA_MAX_ITER|cv2.TERM_CRITERIA_EPS,20,.5))
            filtered=cv2.cvtColor(filtered_lab,cv2.COLOR_LAB2RGB)
        else:filtered=extended.copy()
        pixels=np.dstack((filtered,alpha));Image.fromarray(pixels).save(out/f'{name}-filtered.png')
        edges=edge_map(filtered,visible)
        overlay=rgba.copy();overlay[edges>0,:3]=[255,30,180]
        Image.fromarray(overlay).save(out/f'{name}-overlay.png')
        Image.fromarray(edges).save(out/f'{name}-edges.png')
        saved=np.asarray(Image.open(out/f'{name}-filtered.png'))
        assert np.array_equal(saved[:,:,3],alpha) and saved.shape==rgba.shape
        reports.append(dict(name=name,spatial_radius=sp,color_radius=sr,
                            edge_pixels=int(np.count_nonzero(edges)),
                            mean_rgb_change=float(np.abs(filtered.astype(float)-rgb)[visible].mean())))
    (out/'report.json').write_text(json.dumps(dict(source=str(args.source.resolve()),
        method='OpenCV mean-shift filtering in 8-bit Lab; channel-wise Canny edge proposals, thresholds 30/70',
        note='Filtering stage only: not closed region labels or a final vector. Colors are not limited to a fixed palette.',
        candidates=reports),indent=2))
    html='''<!doctype html><meta charset="utf-8"><title>Mean-shift edge experiment</title>
<style>body{background:#252831;color:white;font:17px system-ui;margin:24px}button{padding:10px;margin:6px}.row{display:grid;grid-template-columns:repeat(4,minmax(200px,1fr));gap:14px}img{width:100%;background:repeating-conic-gradient(#666 0% 25%,#999 0% 50%) 0/20px 20px}a{color:#bce}</style>
<h1>Mean-shift edge experiment</h1><p>No fixed palette and no tracing. Nearby similar colors are grouped before detecting edges.</p>
<p>Magenta marks proposed internal edges over the unchanged input. These are edge candidates, not complete region boundaries.</p>
<button onclick="show('overlay')">Edge overlay</button><button onclick="show('filtered')">Filtered color</button><button onclick="show('edges')">Edges only</button><div class="row">'''
    for r in reports:
        n=r['name'];html+=f'<div><h2>{n.title()}</h2><p>Spatial {r["spatial_radius"]}, color {r["color_radius"]}</p><a href="{n}-overlay.png"><img data-name="{n}" src="{n}-overlay.png"></a><p>{r["edge_pixels"]:,} edge pixels</p></div>'
    html+='''</div><p>Settings use pixels and encoded 8-bit Lab color distance. Strong filtering may flatten shading or create false boundaries. Transparent RGB is extended before processing; output alpha is preserved exactly.</p>
<script>function show(mode){for(const im of document.querySelectorAll('img')){im.src=im.dataset.name+'-'+mode+'.png';im.parentElement.href=im.src}}</script>'''
    (out/'index.html').write_text(html,encoding='utf-8')
    print(json.dumps(reports))

if __name__=='__main__':main()
