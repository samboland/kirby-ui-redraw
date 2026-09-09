"""Layered Potrace of smoothed color-quantized artwork; SVG contains paths only."""
import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from trace import trace
from build_demos import DLL, INKSCAPE, resize_rgba

def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    source=Image.open(a.source).convert('RGBA');source.save(a.output/'input.png')
    # Use the installed GIMP operation for the requested smoothed input.
    subprocess.run([r'C:\Program Files\GIMP 3\bin\gegl.exe','--','gegl:load',f'path={a.source.resolve()}',
                    'gegl:mean-curvature-blur','iterations=2','gegl:png-save',f'path={(a.output/"smoothed.png").resolve()}','bitdepth=8'],check=True,capture_output=True)
    im=Image.open(a.output/'smoothed.png').convert('RGBA');im.putalpha(source.getchannel('A'));im.save(a.output/'smoothed.png')
    w,h=im.size;visible=np.asarray(im)[:,:,3]>=128
    reports=[]
    for count in (24,48):
        folder=a.output/str(count);folder.mkdir(exist_ok=True)
        rgb=im.convert('RGB');pixels=np.asarray(rgb).copy()
        # Hidden RGB must not consume palette entries.
        pixels[~visible]=np.median(pixels[visible],axis=0).astype(np.uint8)
        q=Image.fromarray(pixels).quantize(colors=count,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
        labels=np.asarray(q);palette=np.array(q.getpalette(),dtype=np.uint8).reshape(-1,3)
        paths=[];segments=0
        # Cumulative masks overlap underneath later colors, avoiding transparent seams.
        for i in range(count):
            mask=visible if i==0 else (gaussian_filter(((labels>=i)&visible).astype(float),.7)>=.5)&visible
            alpha=Image.fromarray(mask.astype(np.uint8)*255)
            input_path=folder/f'mask-{i}.png';Image.merge('RGBA',(alpha,alpha,alpha,alpha)).save(input_path)
            output_path=folder/f'path-{i}.svg'
            r=trace(input_path,output_path,DLL,speckles=2,corners=1.05,tolerance=.5)
            d=ET.parse(output_path).getroot()[0].attrib['d'];segments+=r['segments']
            color='#%02x%02x%02x'%tuple(palette[i])
            paths.append(f'<path fill="{color}" fill-rule="evenodd" d="{d}"/>')
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'+''.join(paths)+'</svg>'
        out=a.output/f'dedede-{count}-colors.svg';out.write_text(svg)
        tree=ET.fromstring(svg);assert all(e.tag.endswith('path') for e in tree)
        png=a.output/f'dedede-{count}-colors-2x.png'
        subprocess.run([INKSCAPE,str(out.resolve()),'--export-filename='+str(png.resolve()),f'--export-width={w*2}'],capture_output=True,check=True)
        resize_rgba(Image.open(png),im.size).save(a.output/f'dedede-{count}-colors.png')
        reports.append(dict(colors=count,segments=segments,bytes=out.stat().st_size,paths=len(paths)))
        print(reports[-1],flush=True)
    (a.output/'report.json').write_text(json.dumps(reports,indent=2))
    html='<meta charset="utf-8"><title>Full vector tracing</title><style>body{background:#252830;color:white;font:18px system-ui;margin:24px}.row{display:flex;gap:16px}.row div{width:33%}img{width:100%;background:#888}a{color:#acf}</style><h1>Full vector tracing of smoothed input</h1><p>Paths only. No embedded raster, masks, or AI calls. Color reduction approximates shading with flat regions.</p><div class="row">'
    for label,file in [('Smoothed input','smoothed.png'),('24 colors','dedede-24-colors.svg'),('48 colors','dedede-48-colors.svg')]:
        html+=f'<div><p>{label}</p><a href="{file}"><img src="{file}"></a></div>'
    (a.output/'index.html').write_text(html+'</div>',encoding='utf-8')

if __name__=='__main__':main()
