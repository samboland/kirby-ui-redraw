"""Extract shared graph arcs and fit cubic Bezier paths for automatic processing."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter1d
from region_graph import thin

def unit(v):
    return v/max(np.linalg.norm(v),1e-9)

def fit(p,t0=None,t1=None,tolerance=.8):
    if len(p)==2:
        delta=(p[1]-p[0])/3
        return [[p[0],p[0]+delta,p[1]-delta,p[1]]]
    t0=unit(p[min(3,len(p)-1)]-p[0]) if t0 is None else t0
    t1=unit(p[max(0,len(p)-4)]-p[-1]) if t1 is None else t1
    u=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];u/=max(u[-1],1e-9)
    b=np.stack(((1-u)**3,3*u*(1-u)**2,3*u*u*(1-u),u**3),axis=1)
    base=(b[:,0]+b[:,1])[:,None]*p[0]+(b[:,2]+b[:,3])[:,None]*p[-1]
    a=np.stack((b[:,1,None]*t0,b[:,2,None]*t1),axis=2).reshape(-1,2)
    lengths=np.linalg.lstsq(a,(p-base).reshape(-1),rcond=None)[0]
    chord=np.linalg.norm(p[-1]-p[0])
    if np.any(lengths<0) or np.any(lengths>max(chord*3,5)):lengths=np.array([chord/3]*2)
    cp=np.array([p[0],p[0]+lengths[0]*t0,p[-1]+lengths[1]*t1,p[-1]])
    errors=np.linalg.norm(b@cp-p,axis=1);index=int(errors.argmax())
    if errors[index]<=tolerance or len(p)<=3:return [list(cp)]
    index=max(1,min(index,len(p)-2));t=unit(p[index+1]-p[index-1])
    return fit(p[:index+1],t0,-t,tolerance)+fit(p[index:],t,t1,tolerance)

def main():
    root=Path(__file__).resolve().parents[1]/'assets/kirby/demos';out=root/'bezier-paths';out.mkdir(exist_ok=True)
    mask=thin(np.asarray(Image.open(root/'region-graph/repaired-lines.png').convert('L'))<128)
    pixels={tuple(p) for p in np.argwhere(mask)}
    adj={}
    for y,x in pixels:
        neighbors=[]
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                q=(y+dy,x+dx)
                if q==(y,x) or q not in pixels:continue
                # Suppress diagonal shortcuts across a connected right-angle corner.
                if dx and dy and ((y,x+dx) in pixels or (y+dy,x) in pixels):continue
                neighbors.append(q)
        adj[(y,x)]=sorted(neighbors)
    repairs=json.loads((root/'region-graph/graph.json').read_text())['accepted_repairs']
    points=np.array(sorted(pixels));tree=cKDTree(points)
    forced=set()
    for repair in repairs:
        for key in ('start','end'):
            distance,index=tree.query(repair[key][::-1])
            if distance<=2:forced.add(tuple(points[index]))
    anchors={p for p in pixels if len(adj[p])!=2}|forced
    # Collapse adjacent junction pixels into one shared editable anchor.
    owner={};vertices=[]
    for p in sorted(anchors):
        if p in owner:continue
        group=[p];owner[p]=len(vertices)
        if len(adj[p])>=3 and p not in forced:
            for q in group:
                for r in adj[q]:
                    if r in anchors and r not in owner and len(adj[r])>=3 and r not in forced:
                        owner[r]=len(vertices);group.append(r)
        xy=np.mean(np.array(group)[:,::-1],axis=0).tolist();vertices.append(dict(id=len(vertices),point=xy))
    seen=set();raw=[]
    for p in sorted(anchors)+sorted(pixels-anchors):
        for q in adj[p]:
            key=tuple(sorted((p,q)))
            if key in seen:continue
            seen.add(key)
            if p in owner and q in owner and owner[p]==owner[q]:continue
            if p not in owner:
                owner[p]=len(vertices);vertices.append(dict(id=len(vertices),point=list(map(float,p[::-1]))));anchors.add(p)
            path=[p,q]
            while path[-1] not in anchors:
                options=[r for r in adj[path[-1]] if r!=path[-2]]
                if not options:break
                r=options[0];key=tuple(sorted((path[-1],r)))
                if key in seen:break
                seen.add(key);path.append(r)
            end=path[-1]
            if end not in owner:
                owner[end]=len(vertices);vertices.append(dict(id=len(vertices),point=list(map(float,end[::-1]))))
            xy=np.array([q[::-1] for q in path],float);xy[0]=vertices[owner[p]]['point'];xy[-1]=vertices[owner[end]]['point']
            if np.linalg.norm(np.diff(xy,axis=0),axis=1).sum()>0:raw.append((owner[p],owner[end],xy))
    paths=[]
    for start,end,xy in raw:
        if len(xy)>6:
            endpoints=xy[[0,-1]].copy()
            xy=gaussian_filter1d(xy,1.25,axis=0,mode='nearest')
            xy[0],xy[-1]=endpoints
        segments=np.array(fit(xy)).round(4).tolist();repair_ids=[]
        for i,r in enumerate(repairs):
            samples=np.linspace(r['start'],r['end'],10)
            if np.mean(cKDTree(xy).query(samples)[0]<1.5)>.6:repair_ids.append(i)
        assert np.allclose(segments[0][0],vertices[start]['point'],atol=.0001)
        assert np.allclose(segments[-1][-1],vertices[end]['point'],atol=.0001)
        paths.append(dict(id=len(paths),start=start,end=end,segments=segments,repair_ids=repair_ids))
    model=dict(version=1,width=mask.shape[1],height=mask.shape[0],vertices=vertices,paths=paths,repairs=repairs)
    (out/'curves.json').write_text(json.dumps(model,indent=2))
    def path_d(path):
        seg=path['segments'];return 'M'+','.join(map(str,seg[0][0]))+' '+ ' '.join('C'+' '.join(','.join(map(str,p)) for p in s[1:]) for s in seg)
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{mask.shape[1]}" height="{mask.shape[0]}" viewBox="0 0 {mask.shape[1]} {mask.shape[0]}"><g fill="none" stroke="black" stroke-width="1" stroke-linejoin="round" stroke-linecap="round">'
    svg+=''.join(f'<path id="arc-{p["id"]}" data-start="{p["start"]}" data-end="{p["end"]}" data-repairs="{",".join(map(str,p["repair_ids"]))}" d="{path_d(p)}"/>' for p in paths)+'</g></svg>'
    (out/'curves.svg').write_text(svg)
    (out/'index.html').write_text('<!doctype html><title>Bezier line network</title><h1>Bezier line network</h1><p><a href="../simple-curves/">Automatic simplification comparison</a></p><img src="curves.svg">',encoding='utf-8')
    print(json.dumps(dict(vertices=len(vertices),paths=len(paths),cubics=sum(len(p['segments']) for p in paths),repair_paths=sum(bool(p['repair_ids']) for p in paths))))

if __name__=='__main__':main()
