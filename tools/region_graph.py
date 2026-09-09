"""Propose conservative line-art gap repairs and inspect enclosed raster regions."""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree


def thin(mask):
    a=np.pad(mask.astype(np.uint8),1)
    for _ in range(80):
        changed=False
        for step in (0,1):
            p=[a[:-2,1:-1],a[:-2,2:],a[1:-1,2:],a[2:,2:],a[2:,1:-1],a[2:,:-2],a[1:-1,:-2],a[:-2,:-2]]
            count=sum(p);turns=sum((p[i]==0)&(p[(i+1)%8]==1) for i in range(8))
            if step==0:guard=(p[0]*p[2]*p[4]==0)&(p[2]*p[4]*p[6]==0)
            else:guard=(p[0]*p[2]*p[6]==0)&(p[0]*p[4]*p[6]==0)
            remove=(a[1:-1,1:-1]==1)&(count>=2)&(count<=6)&(turns==1)&guard
            changed|=bool(remove.any());a[1:-1,1:-1][remove]=0
        if not changed:break
    return a[1:-1,1:-1]>0


def neighbors(point,mask):
    y,x=point;h,w=mask.shape
    return [(yy,xx) for yy in range(max(0,y-1),min(h,y+2)) for xx in range(max(0,x-1),min(w,x+2)) if (yy,xx)!=point and mask[yy,xx]]


def direction(point,mask):
    path=[point]
    for _ in range(10):
        options=[p for p in neighbors(path[-1],mask) if p not in path]
        if len(options)!=1:break
        path.append(options[0])
    v=np.array(point,dtype=float)-np.array(path[-1]);length=np.linalg.norm(v)
    return v/max(length,1e-6),set(path)


def main():
    root=Path(__file__).resolve().parents[1]/'assets/kirby/demos'
    out=root/'region-graph';out.mkdir(exist_ok=True)
    source=Image.open(root/'full-vector/smoothed.png').convert('RGBA');rgba=np.asarray(source)
    visible=rgba[:,:,3]>=128
    initial=np.asarray(Image.open(root/'mean-shift/control-line-art.png'))[:,:,3]>0
    skeleton=thin(initial)
    degree=ndimage.convolve(skeleton.astype(int),np.ones((3,3),int),mode='constant')-skeleton
    endpoints=[tuple(p) for p in np.argwhere(skeleton&(degree==1))]
    directions={p:direction(p,skeleton) for p in endpoints}
    points=np.argwhere(skeleton);tree=cKDTree(points)
    candidates=[]
    for p in endpoints:
        tangent,local=directions[p]
        for j in tree.query_ball_point(p,24):
            q=tuple(points[j]);delta=np.array(q)-p;distance=np.linalg.norm(delta)
            if q in local or distance<2:continue
            alignment=float(np.dot(tangent,delta/distance))
            if alignment<.65:continue
            pair=q in directions
            if pair:
                other=float(np.dot(directions[q][0],-delta/distance))
                if other<.4:continue
            elif distance>10:continue
            else:other=.5
            path=np.rint(np.linspace(p,q,max(3,int(distance*2)))).astype(int)
            interior=path[3:-3]
            if len(interior) and skeleton[interior[:,0],interior[:,1]].any():continue
            if visible[path[:,0],path[:,1]].mean()<.8:continue
            # Short, aligned connections rank first. Scores are heuristic, not probabilities.
            score=(alignment+other)/2-distance/48+(0.15 if pair else 0)
            candidates.append((score,p,q,path,pair))
    candidates.sort(key=lambda c:c[0],reverse=True)
    repaired=skeleton.copy();used=set();repairs=[];added=np.zeros_like(skeleton)
    for score,p,q,path,pair in candidates:
        if p in used or (pair and q in used):continue
        interior=path[3:-3]
        if len(interior) and added[interior[:,0],interior[:,1]].any():continue
        line=np.zeros(skeleton.shape,np.uint8)
        cv2.line(line,tuple(map(int,p[::-1])),tuple(map(int,q[::-1])),1,1,cv2.LINE_8)
        added|=line.astype(bool);repaired|=line.astype(bool);used.add(p)
        if pair:used.add(q)
        repairs.append(dict(start=list(map(int,p[::-1])),end=list(map(int,q[::-1])),score=round(score,3),kind='endpoint pair' if pair else 'junction'))
    # Connect truncated contours to the crop when they stop within three pixels.
    h,w=visible.shape
    for p in endpoints:
        y,x=p
        targets=[(0,x),(h-1,x),(y,0),(y,w-1)]
        q=min(targets,key=lambda q:np.linalg.norm(np.array(q)-p))
        if p not in used and np.linalg.norm(np.array(q)-p)<=3:
            line=np.zeros(skeleton.shape,np.uint8)
            cv2.line(line,(x,y),(q[1],q[0]),1,1)
            repaired|=line.astype(bool);added|=line.astype(bool);used.add(p)
            repairs.append(dict(start=[int(x),int(y)],end=[int(q[1]),int(q[0])],score=None,kind='crop boundary'))
    # The image crop is a real boundary for regions intersecting its edge.
    repaired[0,:]|=visible[0,:];repaired[-1,:]|=visible[-1,:]
    repaired[:,0]|=visible[:,0];repaired[:,-1]|=visible[:,-1]
    labels,count=ndimage.label(visible&~repaired,structure=ndimage.generate_binary_structure(2,1))
    sizes=np.bincount(labels.ravel());ids=[i for i in range(1,count+1) if sizes[i]>=12]
    region_records=[];rng=np.random.default_rng(42)
    segmentation=np.full((*labels.shape,3),235,np.uint8)
    paint=np.full((*labels.shape,3),235,np.uint8)
    for i in ids:
        mask=labels==i;color=np.median(rgba[:,:,:3][mask],axis=0).astype(np.uint8)
        segmentation[mask]=rng.integers(70,230,3,dtype=np.uint8);paint[mask]=color
        y,x=ndimage.center_of_mass(mask)
        region_records.append(dict(id=i,area=int(sizes[i]),center=[round(x,2),round(y,2)],median_rgb=color.tolist()))
    segmentation[repaired]=[25,25,25];paint[repaired]=[25,25,25]
    preview=Image.fromarray(segmentation);draw=ImageDraw.Draw(preview)
    for r in region_records:
        if r['area']>150:draw.text(tuple(r['center']),str(r['id']),fill='black',stroke_width=1,stroke_fill='white')
    preview.save(out/'regions.png');Image.fromarray(paint).save(out/'flat-regions.png')
    overlay=Image.new('RGBA',source.size,'#666666');overlay.alpha_composite(source)
    overlay=np.asarray(overlay).copy();overlay[skeleton,:3]=[25,25,25];overlay[added]=[0,255,100,255]
    for repair in repairs:
        cv2.line(overlay,tuple(repair['start']),tuple(repair['end']),(0,255,100,255),2)
    Image.fromarray(overlay).save(out/'repairs.png')
    Image.fromarray((~repaired).astype(np.uint8)*255).save(out/'repaired-lines.png')
    # Export each graph arc once, keeping junctions fixed during conservative simplification.
    d=ndimage.convolve(repaired.astype(int),np.ones((3,3),int),mode='constant')-repaired
    anchors={tuple(p) for p in np.argwhere(repaired&(d!=2))};seen=set();arcs=[]
    for start in list(anchors)+[tuple(p) for p in np.argwhere(repaired)]:
        for nxt in neighbors(start,repaired):
            key=tuple(sorted((start,nxt)))
            if key in seen:continue
            arc=[start,nxt];seen.add(key)
            while arc[-1] not in anchors and arc[-1]!=start:
                options=[q for q in neighbors(arc[-1],repaired) if q!=arc[-2]]
                if not options:break
                q=options[0];key=tuple(sorted((arc[-1],q)))
                if key in seen:break
                seen.add(key);arc.append(q)
            if len(arc)>=2:
                xy=np.array([p[::-1] for p in arc],np.float32)
                fitted=cv2.approxPolyDP(xy,.6,arc[-1]==start).reshape(-1,2).tolist()
                arcs.append(fitted)
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {source.width} {source.height}" width="{source.width}" height="{source.height}"><g fill="none" stroke="black" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">'
    svg+=''.join('<polyline points="'+' '.join(f'{x},{y}' for x,y in arc)+'"/>' for arc in arcs)+'</g></svg>'
    (out/'graph.svg').write_text(svg)
    np.save(out/'region-labels.npy',labels)
    report=dict(input_endpoints=len(endpoints),accepted_repairs=repairs,remaining_unmatched_endpoints=len(set(endpoints)-used),
                regions=region_records,tiny_regions=int(sum(sizes[1:]<12)),graph_arcs=arcs,
                limitations='Straight gap proposals with direction and crossing checks; no semantic model. Shared graph exported as simplified polylines, not fitted Bezier curves. Regions are raster flood-fill results; vector topology not yet validated. Flat fills are diagnostic only.')
    (out/'graph.json').write_text(json.dumps(report,indent=2))
    assert np.all(repaired[skeleton]);assert np.all(labels[~visible]==0)
    assert sum(sizes[1:])==np.count_nonzero(visible&~repaired)
    html='''<meta charset="utf-8"><title>Region graph prototype</title><style>body{background:#252830;color:white;font:18px system-ui;margin:24px}.row{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}img{width:100%;background:white}a{color:#acf}</style><h1>Gap repair and region discovery</h1><p>Green lines are proposed repairs. Region colors and numbers are diagnostic, not reconstructed shading.</p>'''
    html+=f'<p>{len(endpoints)} endpoints · {len(repairs)} repair proposals · {len(ids)} regions of at least 12 pixels</p><div class="row">'
    for title,file in [('Proposed connections','repairs.png'),('Enclosed regions','regions.png'),('Repaired raster line art','repaired-lines.png'),('Simplified graph preview','graph.svg')]:
        html+=f'<div><h2>{title}</h2><a href="{file}"><img src="{file}"></a></div>'
    html+='</div><p><a href="graph.json">Graph and repair data</a> · <a href="flat-regions.png">Diagnostic flat-color regions</a></p><p>Some gaps remain open. Tiny regions are not merged automatically. Shading storage and deformation are deferred until boundaries pass review.</p>'
    (out/'index.html').write_text(html,encoding='utf-8')
    print(json.dumps({k:len(v) if isinstance(v,list) else v for k,v in report.items() if k!='limitations'}))

if __name__=='__main__':main()
