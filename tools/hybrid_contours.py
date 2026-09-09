"""Prototype vector region masks over extended raster shading. No model calls."""
import argparse
import base64
import io
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
from trace import trace
from build_demos import resize_rgba, DLL, INKSCAPE

def vector_mask(mask,folder,name,sigma,tolerance):
    smooth=ndimage.gaussian_filter(mask.astype(float),sigma)>0.5
    a=Image.fromarray(smooth.astype(np.uint8)*255)
    rgba=Image.merge('RGBA',(a,a,a,a));p=folder/(name+'.png');rgba.save(p)
    svg=folder/(name+'.svg')
    report=trace(p,svg,DLL,speckles=3,corners=1.15,tolerance=tolerance)
    return ET.parse(svg).getroot()[0].attrib['d'],report

def build(source,folder,sigma,tolerance):
    folder.mkdir(parents=True,exist_ok=True)
    im=Image.open(source).convert('RGBA');im.save(folder/'input.png')
    rgb=np.asarray(im)[:,:,:3].astype(float)/255
    hsv=np.asarray(im.convert('HSV')).astype(float)/255
    h,s,v=hsv[:,:,0],hsv[:,:,1],hsv[:,:,2]
    visible=np.asarray(im)[:,:,3]>=128
    # Broad hue families, not luminance quantization: retain continuous shading.
    labels=np.full(h.shape,3)
    labels[(s>.28)&(h>.07)&(h<.22)]=0
    labels[(s>.35)&((h<.07)|(h>.93))]=1
    labels[(s>.28)&(h>=.22)&(h<=.93)]=2
    labels[(v<.43)&(h>.48)&(h<.85)]=2
    w,hh=im.size
    paths=[];reports=[];images=[]
    names=['yellow','red','blue','neutral']
    for k,name in enumerate(names):
        region=(labels==k)&visible
        if region.sum()<8:continue
        path,report=vector_mask(region,folder,name,sigma,tolerance)
        # Extend uncontaminated interior color below the corrected boundary.
        core=ndimage.binary_erosion(region,iterations=2)
        if not core.any():core=region
        nearest=ndimage.distance_transform_edt(~core,return_distances=False,return_indices=True)
        filled=rgb[nearest[0],nearest[1]]
        filled[core]=rgb[core]
        layer=Image.fromarray(np.rint(np.clip(filled,0,1)*255).astype(np.uint8))
        buffer=io.BytesIO();layer.save(buffer,format='PNG')
        images.append((name,base64.b64encode(buffer.getvalue()).decode()))
        paths.append((name,path));reports.append(report)
    outer,report=vector_mask(visible,folder,'outer',sigma,tolerance);reports.append(report)
    defs=f'<clipPath id="outer"><path d="{outer}" clip-rule="evenodd"/></clipPath>'
    defs+=''.join(f'<clipPath id="{name}"><path d="{path}" clip-rule="evenodd"/></clipPath>' for name,path in paths)
    # Original raster backing prevents pinholes where independently fitted paths meet.
    buffer=io.BytesIO();im.convert('RGB').save(buffer,format='PNG')
    backing=base64.b64encode(buffer.getvalue()).decode()
    body=f'<image width="{w}" height="{hh}" href="data:image/png;base64,{backing}"/>'
    for name,encoded in images:
        body+=f'<image width="{w}" height="{hh}" clip-path="url(#{name})" href="data:image/png;base64,{encoded}"/>'
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{hh}" viewBox="0 0 {w} {hh}"><defs>{defs}</defs><g clip-path="url(#outer)">{body}</g></svg>'
    (folder/'hybrid.svg').write_text(svg)
    subprocess.run([INKSCAPE,str(folder/'hybrid.svg'),'--export-filename='+str(folder/'render-2x.png'),f'--export-width={w*2}'],capture_output=True,check=True)
    rendered=Image.open(folder/'render-2x.png').convert('RGBA')
    resize_rgba(rendered,im.size).save(folder/'final.png')
    (folder/'report.json').write_text(json.dumps(dict(source=str(source),sigma=sigma,tolerance=tolerance,regions=names,traces=reports),indent=2))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    for name,sigma,tolerance in [('mild',1.2,.8),('strong',2.5,2)]:
        build(a.source.resolve(),a.output.resolve()/name,sigma,tolerance)
    page='''<meta charset="utf-8"><title>Vector contours with raster shading</title><style>body{background:#24262d;color:white;font:18px system-ui;margin:25px}.row{display:flex;gap:18px}.row div{width:33%}img{width:100%;background:repeating-conic-gradient(#666 0% 25%,#999 0% 50%) 0/20px 20px}a{color:#acf}</style><h1>Vector contours with raster shading</h1><p>Broad color regions become simplified vector masks. Original shading extends beneath corrected boundaries. No new AI generation.</p><p>This prototype uses hue rules tailored to Dedede. Check eye highlights, mouth shape and region seams.</p><div class="row">'''
    for name,file in [('Input','mild/input.png'),('Mild cleanup','mild/final.png'),('Stronger cleanup','strong/final.png')]:
        page+=f'<div><p>{name}</p><a href="{file}"><img src="{file}"></a></div>'
    (a.output/'index.html').write_text(page+'</div><p><a href="mild/hybrid.svg">Editable hybrid SVG</a></p>',encoding='utf-8')

if __name__=='__main__':main()
