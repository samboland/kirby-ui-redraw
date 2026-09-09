"""Use GIMP's bundled GEGL Mean Curvature Blur before the final downsample."""
import argparse
import json
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from build_demos import resize_rgba

GEGL=r'C:\Program Files\GIMP 3\bin\gegl.exe'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--demos',type=Path,default=Path('assets/kirby/demos'))
    args=p.parse_args();root=args.demos.resolve()
    records=json.loads((root/'demo-manifest.json').read_text())
    report=[]
    html='''<!doctype html><meta charset="utf-8"><title>Mean Curvature Blur comparison</title>
<style>body{background:#202229;color:white;font:16px system-ui;margin:24px}a{color:#bedcff}.row{display:flex;gap:14px}.cell{width:25%}img{width:100%;height:350px;object-fit:contain;background:#666}.cell p{height:30px}section{margin:32px 0}</style>
<h1>Mean Curvature Blur before downscaling</h1>
<p>Actual GIMP GEGL filter. Each row shares one high-resolution input, then compares iterations 0, 1, 2, and 3.</p>
<p>Two processing sizes: 8× and 12× native, reduced to 4×. Original traced alpha is restored after filtering.</p>
<p>The shaded and illustrated rows use rejected AI color to test smoothing only. Changed artwork remains rejected. Extra interpolation adds no AI detail.</p>
<p><a href="index.html">Back to method comparisons</a></p>'''
    for rec in records:
        name=rec['name'];folder=root/name
        source=Image.open(folder/'source.png').convert('RGBA')
        color=Image.open(folder/('two-color-8x.png' if name=='fighter' else 'ai-returned.png')).convert('RGBA')
        original_matte=Image.open(folder/('two-color-8x.png' if name=='fighter' else 'alpha-8x.png')).convert('RGBA')
        for scale in (8,12):
            size=(source.width*scale,source.height*scale)
            high=resize_rgba(color,size)
            high_path=folder/f'curvature-input-{scale}x.png';high.save(high_path)
            matte=resize_rgba(original_matte,size).getchannel('A')
            html+=f'<section><h2>{rec["title"]} · {scale}× native → 4×</h2><p>Processing {size[0]} × {size[1]}</p><div class="row">'
            control=None
            for iterations in (0,1,2,3):
                filtered=folder/f'curvature-{scale}x-i{iterations}.png'
                if iterations:
                    subprocess.run([GEGL,'--','gegl:load','path='+str(high_path),'gegl:mean-curvature-blur',f'iterations={iterations}',
                                    'gegl:png-save','path='+str(filtered),'bitdepth=8'],check=True,capture_output=True)
                    candidate=Image.open(filtered).convert('RGBA')
                else:candidate=high.copy()
                candidate.putalpha(matte)
                final=resize_rgba(candidate,tuple(rec['final_size']))
                filename=f'curvature-{scale}x-i{iterations}-final.png';final.save(folder/filename)
                rgb=np.asarray(final,dtype=float)
                if control is None:control=rgb
                visible=rgb[:,:,3]>128
                difference=np.abs(rgb[:,:,:3]-control[:,:,:3])[visible]
                stats=dict(asset=name,processing_scale=scale,iterations=iterations,processing_size=size,final_size=rec['final_size'],
                           mean_rgb_difference=float(difference.mean()),max_rgb_difference=float(difference.max()),
                           file=name+'/'+filename)
                report.append(stats)
                html+=f'<div class="cell"><p>{iterations} iterations'+(' · control' if not iterations else '')+f'</p><a href="{name}/{filename}" target="_blank"><img src="{name}/{filename}"></a><small>Mean RGB change: {stats["mean_rgb_difference"]:.3f} / 255</small></div>'
                print(name,scale,iterations,round(stats['mean_rgb_difference'],4),flush=True)
            html+='</div></section>'
    (root/'curvature.html').write_text(html,encoding='utf-8')
    (root/'curvature-manifest.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
