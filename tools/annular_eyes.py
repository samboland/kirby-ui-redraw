"""Fit elliptical annular sectors to connected white eye islands, without eye coordinates."""
import json
import argparse
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from scipy.optimize import differential_evolution
from scipy.special import expit


def membership(v, points, soft=True):
    cx, cy, a, b, rotation, dx, dy, scale, middle, span = v
    c, s = np.cos(rotation), np.sin(rotation)
    q = points-[cx, cy]
    x, y = q[:, 0]*c+q[:, 1]*s, -q[:, 0]*s+q[:, 1]*c
    outer = (1-np.hypot(x/a, y/b))*min(a,b)
    inner = (np.hypot((x/a-dx)/scale, (y/b-dy)/scale)-1)*min(a,b)*scale
    angle = np.arctan2(y/b, x/a)
    wedge = (np.cos(angle-middle)-np.cos(span/2))*min(a,b)
    if soft:
        return expit(outer)*expit(inner)*expit(wedge)
    return (outer >= 0) & (inner >= 0) & (wedge >= 0)


def fit_sector(mask):
    yy, xx = np.where(mask)
    xmin, xmax, ymin, ymax = xx.min(), xx.max(), yy.min(), yy.max()
    width, height = xmax-xmin+1, ymax-ymin+1
    size = max(width,height)
    minimum_axis = size*(.08 if width/height < .4 else .2)
    gx, gy = np.meshgrid(np.arange(max(0,xmin-size*.5),min(mask.shape[1],xmax+size*.5),2),
                         np.arange(max(0,ymin-size*.5),min(mask.shape[0],ymax+size*.5),2))
    points = np.column_stack((gx.ravel(),gy.ravel()))
    target = mask[points[:,1].astype(int),points[:,0].astype(int)].astype(float)
    bounds = [(xmin-size*.6,xmax+size*.6),(ymin-size*.6,ymax+size*.6),
              (minimum_axis,size*1.1),(minimum_axis,size*1.1),(-np.pi,np.pi),
              (-.35,.35),(-.35,.35),(.35,.96),(-np.pi,np.pi),(.5,5.8)]
    def loss(v):
        predicted = membership(v, points)
        dice = 2*np.sum(predicted*target)/(predicted.sum()+target.sum()+1e-9)
        # Ensure the offset inner ellipse stays within the outer ellipse.
        excess = max(0, np.hypot(v[5],v[6])+v[7]-1)
        return 1-dice+excess*5
    attempts = [differential_evolution(loss,bounds,seed=seed,popsize=9,maxiter=240,tol=.0005,polish=True)
                for seed in ([31,73,117] if width/height < .4 else [31])]
    result = min(attempts,key=lambda r:r.fun)
    # Report dense pixel overlap, separately from the soft optimization objective.
    gx, gy = np.meshgrid(np.arange(mask.shape[1]),np.arange(mask.shape[0]))
    prediction = membership(result.x,np.column_stack((gx.ravel(),gy.ravel())),False).reshape(mask.shape)
    iou = float((prediction & mask).sum()/max((prediction | mask).sum(),1))
    return result.x, dict(iou=iou, objective=float(result.fun), evaluations=result.nfev,
                           converged=bool(result.success), inner_containment=float(np.hypot(result.x[5],result.x[6])+result.x[7]))


def band_geometry(v):
    cx,cy,a,b,rotation,dx,dy,scale,middle,span = map(float,v)
    c,s = np.cos(rotation),np.sin(rotation)
    def point(theta, inner=False):
        x,y=a*np.cos(theta),b*np.sin(theta)
        if inner:
            x,y=x*scale+a*dx,y*scale+b*dy
        return [cx+x*c-y*s,cy+x*s+y*c]
    start,end=middle-span/2,middle+span/2
    angles=np.linspace(start,end,1024)
    inner_angles=np.unwrap(np.arctan2(np.sin(angles)-dy,np.cos(angles)-dx))
    inner_start,inner_end=inner_angles[0],inner_angles[-1]
    p,q=point(start),point(end)
    ip,iq=point(inner_start,True),point(inner_end,True)
    angle=np.rad2deg(rotation)
    path=f'M {p[0]} {p[1]} A {a} {b} {angle} {int(span>np.pi)} 1 {q[0]} {q[1]} L {iq[0]} {iq[1]} A {a*scale} {b*scale} {angle} {int(inner_end-inner_start>np.pi)} 0 {ip[0]} {ip[1]} Z'
    polygon=np.array([point(t) for t in angles]+[point(t,True) for t in np.linspace(inner_end,inner_start,1024)])
    return path,polygon


def svg_sector(v, identifier):
    path,_=band_geometry(v)
    return f'<path id="band{identifier}" d="{path}" fill="#f5f5f5"/>'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates',type=Path,nargs='*',help='Render the best saved fit per component, without rerunning optimization.')
    args=parser.parse_args()
    saved=[r for path in (args.candidates or []) for r in json.loads(path.read_text())]
    root=Path(__file__).resolve().parents[1]/'assets/kirby/demos'
    out=root/'annular-eyes';out.mkdir(exist_ok=True)
    rgba=np.asarray(Image.open(root/'hybrid-contours/mild/input.png').convert('RGBA'))
    hsv=cv2.cvtColor(rgba[:,:,:3],cv2.COLOR_RGB2HSV)
    _,dark,stats,_=cv2.connectedComponentsWithStats(((hsv[:,:,2]<115)&(rgba[:,:,3]>128)).astype('uint8'))
    _,whites,ws,_=cv2.connectedComponentsWithStats(((hsv[:,:,1]<65)&(hsv[:,:,2]>145)&(rgba[:,:,3]>128)).astype('uint8'))
    results=[];sectors=[];evidence=[]
    for i,stat in enumerate(stats[1:],1):
        x,y,w,h,area=map(int,stat)
        if area<rgba.shape[0]*rgba.shape[1]*.002 or not .35<w/h<1.6 or area/(w*h)<.3:
            continue
        adjacent=cv2.dilate((dark==i).astype('uint8'),np.ones((9,9),'uint8'))>0
        ids=[j for j in np.unique(whites[adjacent]) if j and ws[j,4]<area*3]
        if not ids:continue
        island=whites==max(ids,key=lambda j:ws[j,4])
        existing=[r for r in saved if r['component']==i]
        if existing:
            chosen=max(existing,key=lambda r:r['iou'])
            parameters=np.asarray(chosen['parameters'])
            report={k:v for k,v in chosen.items() if k not in ('component','parameters')}
        else:
            parameters,report=fit_sector(island)
        _,polygon=band_geometry(parameters)
        raster=np.zeros(island.shape,'uint8')
        cv2.fillPoly(raster,[np.round(polygon*256).astype('int32')],1,shift=8)
        prediction=raster>0
        report['radial_fit_iou']=report.get('radial_fit_iou',report['iou'])
        report['iou']=float((prediction & island).sum()/max((prediction | island).sum(),1))
        report['geometry']='paired elliptical arcs with direct endpoint joins'
        results.append(dict(component=i,parameters=parameters.tolist(),**report))
        sectors.append(svg_sector(parameters,i))
        contours,_=cv2.findContours(island.astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            d='M'+' L'.join(f'{x},{y}' for x,y in contour[:,0,:])+' Z'
            evidence.append(f'<path d="{d}" fill="none" stroke="#ff1685" stroke-width="1"/>')
        print(json.dumps(results[-1]),flush=True)
    header='<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
    (out/'sectors.svg').write_text(header+''.join(sectors)+'</svg>')
    original='<image href="../hybrid-contours/mild/input.png" width="512" height="512"/>'
    (out/'overlay.svg').write_text(header+original+'<g opacity=".8">'+''.join(sectors)+'</g>'+''.join(evidence)+'</svg>')
    (out/'fit.json').write_text(json.dumps(results,indent=2))
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Annular eye sectors</title><style>body{background:#242832;color:white;font:16px system-ui;margin:24px}main{display:grid;grid-template-columns:1fr 1fr;gap:24px}object{width:100%;aspect-ratio:1;background:#557b91}</style><h1>Annular sectors for the eyes</h1><p>White: fitted sectors. Pink: observed white-island boundary. Original eyes remain visible beneath the overlay.</p><main><section><h2>Fit over original</h2><object data="overlay.svg"></object></section><section><h2>Vector sclera bands</h2><object data="sectors.svg"></object></section></main><p>Each band now joins its outer and inner elliptical arcs directly. The radial mask that caused the notch is removed. Parameters still come from the earlier sector fit; reported overlap is recomputed for the new band. This experiment fits sclera bands; irises and highlights remain original in the overlay. The mouth is unchanged.</p><p>Pixel intersection-over-union: '''+'; '.join(f'eye {r["component"]}: {r["iou"]:.1%}' for r in results)+'. Overlap is a diagnostic, not an acceptance decision.</p>',encoding='utf-8')


if __name__=='__main__':main()
