"""Extract native Wii textures from a DolphinTool DATA/files tree.

No game assets are embedded. Output is local and excluded from git.
"""
import argparse
import collections
import hashlib
import html
import json
import re
import struct
from pathlib import Path
from PIL import Image
import numpy as np

def u32(data, pos=0):
    return struct.unpack_from('>I', data, pos)[0]

def u16(data, pos=0):
    return struct.unpack_from('>H', data, pos)[0]

def string(data, pos):
    if not 0 <= pos < len(data):
        raise ValueError('String outside container')
    return data[pos:data.index(0, pos)].decode('utf-8', errors='replace')

def decompress(data):
    kind = data[0]
    if kind not in (0x10, 0x11):
        raise ValueError('Unsupported compression')
    size = int.from_bytes(data[1:4], 'little')
    pos = 4
    if size == 0:
        size = int.from_bytes(data[4:8], 'little')
        pos = 8
    if size > 256 * 1024 * 1024:
        raise ValueError('Decompression limit exceeded')
    out = bytearray()
    while len(out) < size:
        flags = data[pos]; pos += 1
        for shift in range(7, -1, -1):
            if len(out) >= size:
                break
            if not flags & (1 << shift):
                out.append(data[pos]); pos += 1
                continue
            a, b = data[pos:pos+2]; pos += 2
            high = a >> 4
            if kind == 0x10:
                length, distance = high + 3, ((a & 15) << 8 | b) + 1
            elif high == 0:
                c = data[pos]; pos += 1
                length = ((a & 15) << 4 | b >> 4) + 0x11
                distance = ((b & 15) << 8 | c) + 1
            elif high == 1:
                c, d = data[pos:pos+2]; pos += 2
                length = ((a & 15) << 12 | b << 4 | c >> 4) + 0x111
                distance = ((c & 15) << 8 | d) + 1
            else:
                length, distance = high + 1, ((a & 15) << 8 | b) + 1
            if distance > len(out):
                raise ValueError('Invalid LZ back reference')
            length = min(length, size - len(out))
            # Repeat the previous span; supports overlapping back references.
            span = out[-distance:]
            out.extend((span * ((length + distance - 1)//distance))[:length])
    return bytes(out)

def archive_files(data):
    base = u32(data, 4)
    count = u32(data, base + 8)
    names = base + count * 12
    if names > len(data):
        raise ValueError('Invalid U8 node table')
    stack = [(count, '')]
    for index in range(1, count):
        while index >= stack[-1][0]:
            stack.pop()
        tag, offset, size = struct.unpack_from('>III', data, base + index*12)
        name = stack[-1][1] + string(data, names + (tag & 0xffffff))
        if tag >> 24:
            stack.append((size, name + '/'))
        else:
            if offset + size > len(data):
                raise ValueError('U8 member outside container')
            yield name, data[offset:offset+size]

def material_palettes(data):
    """Resolve actual texture/palette associations from MDL0 sampler tables."""
    result=collections.defaultdict(set)
    for match in re.finditer(b'MDL0',data):
        base=match.start()
        version=u32(data,base+8)
        if version not in (8,9,10,11):continue
        offset=u32(data,base+(0x30 if version>=10 else 0x28))
        if not offset:continue
        table=base+offset
        for i in range(u32(data,table+4)):
            entry=table+24+i*16
            material=table+u32(data,entry+12)
            count=u32(data,material+0x2c)
            samplers=material+u32(data,material+0x30)
            if count>8:raise ValueError('Invalid MDL0 sampler count')
            for j in range(count):
                sampler=samplers+j*0x34
                tex,pal=u32(data,sampler),u32(data,sampler+4)
                if tex and pal:
                    result[string(data,sampler+tex)].add(string(data,sampler+pal))
    return result

def rgb565(value):
    r, g, b = value >> 11, (value >> 5) & 63, value & 31
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2), 255)

def rgb5a3(value):
    if value & 0x8000:
        r, g, b = (value >> 10) & 31, (value >> 5) & 31, value & 31
        return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2), 255)
    a = (value >> 12) & 7
    return (((value >> 8) & 15)*17, ((value >> 4) & 15)*17, (value & 15)*17,
            (a << 5) | (a << 2) | (a >> 1))

def palette(data, fmt, count):
    if fmt not in (0, 1, 2):
        raise ValueError(f'Unsupported palette {fmt}')
    return [((v & 255,)*3 + (v >> 8,)) if fmt == 0 else
            rgb565(v) if fmt == 1 else rgb5a3(v)
            for v in (u16(data, i*2) for i in range(count))]

FORMATS = {0:(8,8,32,'I4'), 1:(8,4,32,'I8'), 2:(8,4,32,'IA4'),
           3:(4,4,32,'IA8'), 4:(4,4,32,'RGB565'), 5:(4,4,32,'RGB5A3'),
           6:(4,4,64,'RGBA8'), 8:(8,8,32,'CI4'), 9:(8,4,32,'CI8'),
           10:(4,4,32,'CI14X2'), 14:(8,8,32,'CMPR')}

def decode_reference(data, width, height, fmt, colors=None):
    if not 0 < width <= 8192 or not 0 < height <= 8192:
        raise ValueError('Invalid texture dimensions')
    bw, bh, blocksize, _ = FORMATS[fmt]
    needed = ((width+bw-1)//bw)*((height+bh-1)//bh)*blocksize
    if len(data) < needed:
        raise ValueError('Truncated texture')
    out = bytearray(width*height*4)
    def put(x, y, rgba):
        if x < width and y < height:
            off = (y*width+x)*4
            out[off:off+4] = bytes(rgba)
    pos = 0
    for ty in range(0, height, bh):
        for tx in range(0, width, bw):
            block = data[pos:pos+blocksize]; pos += blocksize
            if fmt == 14:
                for sy, sx, off in [(0,0,0),(0,4,8),(4,0,16),(4,4,24)]:
                    a,b = u16(block,off),u16(block,off+2)
                    ca,cb = rgb565(a),rgb565(b)
                    if a>b:
                        cc=tuple((5*ca[k]+3*cb[k])>>3 for k in range(3))+(255,)
                        cd=tuple((3*ca[k]+5*cb[k])>>3 for k in range(3))+(255,)
                    else:
                        cc=tuple((ca[k]+cb[k])//2 for k in range(3))+(255,)
                        cd=cc[:3]+(0,)
                    table=[ca,cb,cc,cd]
                    for y in range(4):
                        for x in range(4):
                            put(tx+sx+x,ty+sy+y,table[(block[off+4+y]>>(6-2*x))&3])
                continue
            for y in range(bh):
                for x in range(bw):
                    i=y*bw+x
                    if fmt in (0,8):
                        v=(block[i//2]>>(4 if i%2==0 else 0))&15
                    elif fmt in (1,2,9):
                        v=block[i]
                    elif fmt != 6:
                        v=u16(block,i*2)
                    if fmt==0: rgba=(v*17,)*4
                    elif fmt==1: rgba=(v,)*4
                    elif fmt==2: rgba=((v&15)*17,)*3+((v>>4)*17,)
                    elif fmt==3: rgba=(v&255,)*3+(v>>8,)
                    elif fmt==4: rgba=rgb565(v)
                    elif fmt==5: rgba=rgb5a3(v)
                    elif fmt==6: rgba=(block[i*2+1],block[32+i*2],block[33+i*2],block[i*2])
                    else:
                        if colors is None: raise ValueError('Missing palette')
                        rgba=colors[v & 0x3fff if fmt==10 else v]
                    put(tx+x,ty+y,rgba)
    return Image.frombytes('RGBA',(width,height),bytes(out))

def decode(data,width,height,fmt,colors=None):
    """Vectorized GX decoder; reference implementation retained for differential tests."""
    if not 0 < width <= 8192 or not 0 < height <= 8192:
        raise ValueError('Invalid texture dimensions')
    bw,bh,bs,_=FORMATS[fmt]
    nx,ny=(width+bw-1)//bw,(height+bh-1)//bh
    size=nx*ny*bs
    if len(data)<size:raise ValueError('Truncated texture')
    raw=np.frombuffer(data,dtype=np.uint8,count=size).reshape(-1,bs)
    def convert(v,kind):
        v=v.astype(np.uint32)
        if kind==4:
            r=(v>>11)&31;g=(v>>5)&63;b=v&31
            return np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2),np.full_like(v,255)),axis=-1)
        if kind==5:
            opaque=(v&32768)!=0;r=(v>>10)&31;g=(v>>5)&31;b=v&31;a=(v>>12)&7
            return np.stack((np.where(opaque,(r<<3)|(r>>2),((v>>8)&15)*17),
                np.where(opaque,(g<<3)|(g>>2),((v>>4)&15)*17),
                np.where(opaque,(b<<3)|(b>>2),(v&15)*17),
                np.where(opaque,255,(a<<5)|(a<<2)|(a>>1))),axis=-1)
    if fmt==14:
        blocks=raw.reshape(-1,8)
        a=blocks[:,0].astype(np.uint32)*256+blocks[:,1]
        b=blocks[:,2].astype(np.uint32)*256+blocks[:,3]
        ca,cb=convert(a,4),convert(b,4)
        avg=(ca+cb)//2
        cc=np.where((a>b)[:,None],(5*ca+3*cb)>>3,avg)
        cd=np.where((a>b)[:,None],(3*ca+5*cb)>>3,avg)
        cd[:,3]=np.where(a>b,255,0)
        table=np.stack((ca,cb,cc,cd),axis=1)
        indices=(blocks[:,4:,None]>>np.array([6,4,2,0],dtype=np.uint8))&3
        pix=table[np.arange(len(blocks))[:,None,None],indices]
        pix=pix.reshape(ny,nx,2,2,4,4,4).transpose(0,2,4,1,3,5,6).reshape(ny*8,nx*8,4)
    else:
        if fmt in (0,8):v=np.stack((raw>>4,raw&15),axis=-1).reshape(len(raw),-1)
        elif fmt in (1,2,9):v=raw
        elif fmt!=6:v=raw[:,::2].astype(np.uint32)*256+raw[:,1::2]
        if fmt in (0,1):
            if fmt==0:v=v*17
            pix=np.repeat(v[:,:,None],4,axis=-1)
        elif fmt in (2,3):
            intensity=(v&15)*17 if fmt==2 else v&255
            alpha=(v>>4)*17 if fmt==2 else v>>8
            pix=np.stack((intensity,intensity,intensity,alpha),axis=-1)
        elif fmt in (4,5):pix=convert(v,fmt)
        elif fmt==6:pix=np.stack((raw[:,1:32:2],raw[:,32::2],raw[:,33::2],raw[:,:32:2]),axis=-1)
        else:
            if colors is None:raise ValueError('Missing palette')
            pix=np.asarray(colors,dtype=np.uint8)[v&0x3fff if fmt==10 else v]
        pix=pix.reshape(ny,nx,bh,bw,4).transpose(0,2,1,3,4).reshape(ny*bh,nx*bw,4)
    return Image.fromarray(pix[:height,:width].astype(np.uint8))

class Extractor:
    def __init__(self, output):
        self.output=output
        (output/'textures').mkdir(parents=True,exist_ok=True)
        (output/'thumbs').mkdir(exist_ok=True)
        self.records=[]; self.errors=[]; self.seen={}; self.kinds=collections.Counter()
        self.raw_seen={}

    def emit(self,data,w,h,fmt,colors,source,name):
        bw,bh,bs,_=FORMATS[fmt]
        size=((w+bw-1)//bw)*((h+bh-1)//bh)*bs
        raw_key=hashlib.sha256(struct.pack('>III',w,h,fmt)+data[:size]+bytes(c for p in (colors or []) for c in p)).digest()
        origin={'container':source,'name':name}
        if raw_key in self.raw_seen:
            self.raw_seen[raw_key]['sources'].append(origin)
            return
        image=decode(data,w,h,fmt,colors)
        digest=hashlib.sha256(struct.pack('>II',w,h)+image.tobytes()).hexdigest()
        origin={'container':source,'name':name}
        if digest in self.seen:
            self.seen[digest]['sources'].append(origin)
            self.raw_seen[raw_key]=self.seen[digest]
            return
        safe=re.sub(r'[^A-Za-z0-9_.-]+','_',name)[:90]
        filename=f'{digest[:16]}_{safe}.png'
        image.save(self.output/'textures'/filename)
        thumb=image.copy(); thumb.thumbnail((144,112))
        thumb.save(self.output/'thumbs'/filename)
        record=dict(id=digest[:16],file='textures/'+filename,thumbnail='thumbs/'+filename,
                    width=w,height=h,format=FORMATS[fmt][3],sources=[origin])
        self.records.append(record); self.seen[digest]=record
        self.raw_seen[raw_key]=record

    def font(self,data,source):
        p=u16(data,12)
        for _ in range(u16(data,14)):
            if data[p:p+4]==b'TGLP':
                size=u32(data,p+12);count=u16(data,p+16);fmt=u16(data,p+18)
                w,h=u16(data,p+24),u16(data,p+26);offset=u32(data,p+28)
                for i in range(count):
                    self.emit(data[offset+i*size:offset+(i+1)*size],w,h,fmt,None,source,f'{Path(source).stem}_sheet{i}')
            length=u32(data,p+4)
            if length<8:raise ValueError('Invalid font section size')
            p+=length

    def reft(self,data,source):
        table=0x18+u32(data,0x18)
        cursor=table+8
        for _ in range(u16(data,table+4)):
            n=u16(data,cursor);name=string(data,cursor+2)
            start=table+u32(data,cursor+2+n)
            w,h=u16(data,start+4),u16(data,start+6)
            length=u32(data,start+8);fmt=data[start+12]
            count=u16(data,start+14)
            colors=palette(data[start+32+length:],data[start+13],count) if count else None
            self.emit(data[start+32:start+32+length],w,h,fmt,colors,source,name)
            cursor+=10+n

    def tpl(self,data,source):
        count,table=u32(data,4),u32(data,8)
        if count > 4096: raise ValueError('Invalid TPL count')
        for i in range(count):
            header,pal=struct.unpack_from('>II',data,table+i*8)
            h,w,fmt,offset=struct.unpack_from('>HHII',data,header)
            colors=None
            if pal:
                colors=palette(data[u32(data,pal+8):],u32(data,pal+4),u16(data,pal))
            self.emit(data[offset:],w,h,fmt,colors,source,f'{Path(source).stem}_{i}')

    def brres(self,data,source):
        # TEX0/PLT0 signatures are validated before their data is decoded.
        palettes={}
        for match in re.finditer(b'PLT0',data):
            p=match.start()
            if p+32>len(data) or u32(data,p+8) not in (1,3): continue
            name=string(data,p+u32(data,p+20))
            palettes[name]=palette(data[p+u32(data,p+16):],u32(data,p+24),u16(data,p+28))
        found=0
        bindings=material_palettes(data) if palettes else {}
        for match in re.finditer(b'TEX0',data):
            p=match.start()
            if p+48>len(data) or u32(data,p+8) not in (1,2,3): continue
            version=u32(data,p+8)
            if version==2: raise ValueError('TEX0 version 2 needs explicit layout support')
            name=string(data,p+u32(data,p+20))
            w,h=struct.unpack_from('>HH',data,p+28)
            fmt=u32(data,p+32)
            names=bindings.get(name) or ({name} if name in palettes else set())
            if fmt in (8,9,10) and not names:
                self.errors.append(dict(source=source,texture=name,error='Missing palette association; animated binding requires review'))
                continue
            if fmt in (8,9,10):
                for pal_name in sorted(names):
                    self.emit(data[p+u32(data,p+16):],w,h,fmt,palettes.get(pal_name),source,
                              name if pal_name==name else f'{name}__palette_{pal_name}')
            else:self.emit(data[p+u32(data,p+16):],w,h,fmt,None,source,name)
            found+=1
        return found

    def walk(self,data,source,depth=0):
        if depth>12: raise ValueError('Archive nesting limit')
        if not data: return
        if source.endswith(('.cmp','.cmpbin')):
            data=decompress(data)
            self.kinds['compressed']+=1
        if data[:4]==b'U\xaa8-':
            self.kinds['U8']+=1
            for name,member in archive_files(data):
                try: self.walk(member,source+'::'+name,depth+1)
                except Exception as exc: self.errors.append(dict(source=source+'::'+name,error=str(exc)))
        elif data[:4]==b'\x00 \xaf0':
            self.kinds['TPL']+=1; self.tpl(data,source)
        elif data[:4]==b'bres':
            self.kinds['BRRES']+=1; self.brres(data,source)
        elif data[:4]==b'RFNT':
            self.kinds['BRFNT']+=1;self.font(data,source)
        elif data[:4]==b'REFT':
            self.kinds['BREFT']+=1;self.reft(data,source)
        else:
            self.kinds[data[:4].hex()]+=1

    def finish(self):
        for rec in self.records:
            rec['ui']=any(s['container'].startswith(('lyt/','hbm/','font/')) for s in rec['sources'])
        report=dict(unique_textures=len(self.records),references=sum(len(r['sources']) for r in self.records),
                    ui_textures=sum(r['ui'] for r in self.records),containers=dict(self.kinds),errors=self.errors)
        (self.output/'manifest.json').write_text(json.dumps(self.records,indent=2),encoding='utf-8')
        (self.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        payload=json.dumps(self.records).replace('<','\\u003c')
        page='''<!doctype html><meta charset="utf-8"><title>Kirby original texture catalog</title>
<style>body{background:#17191f;color:#eee;font:15px system-ui;margin:28px}input,select{padding:10px;margin:8px;background:#292d38;color:white;border:1px solid #666}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}article{background:#252934;padding:12px;border-radius:8px;overflow-wrap:anywhere}img{width:100%;height:120px;object-fit:contain;background:repeating-conic-gradient(#666 0% 25%,#999 0% 50%) 0/16px 16px}small{color:#bbc2d2}a{color:#afceff}button{padding:10px}</style>
<h1>Kirby original texture catalog</h1><p>Native texture pixels extracted from your Wii disc. No upscale pack or generated artwork.</p>
<input id="query" placeholder="Search texture or archive name"><select id="scope"><option value="ui">UI candidates</option><option value="all">All textures</option></select><p id="count"></p><main></main><button id="more">Show more</button>
<script>const records=PAYLOAD;let limit=120;const q=document.querySelector('#query'),s=document.querySelector('#scope'),main=document.querySelector('main');
function draw(){let term=q.value.toLowerCase();let rows=records.filter(r=>(s.value==='all'||r.ui)&&JSON.stringify(r.sources).toLowerCase().includes(term));document.querySelector('#count').textContent=`${rows.length} textures, showing ${Math.min(limit,rows.length)}. Click an image for the original PNG.`;main.replaceChildren();for(let r of rows.slice(0,limit)){let a=document.createElement('article'),link=document.createElement('a'),img=document.createElement('img'),title=document.createElement('p'),meta=document.createElement('small');link.href=r.file;link.target='_blank';img.src=r.thumbnail;img.loading='lazy';link.append(img);title.textContent=r.sources[0].name;meta.textContent=`${r.width} × ${r.height} · ${r.format} · ${r.id} · ${r.sources[0].container}`;a.append(link,title,meta);main.append(a)}document.querySelector('#more').hidden=limit>=rows.length}q.oninput=s.onchange=()=>{limit=120;draw()};document.querySelector('#more').onclick=()=>{limit+=120;draw()};draw();</script>'''
        (self.output/'index.html').write_text(page.replace('PAYLOAD',payload),encoding='utf-8')
        print(json.dumps(report,indent=2),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--retry-errors',action='store_true',help='Retry only failed top-level containers from an existing report')
    args=p.parse_args();ex=Extractor(args.output)
    if args.retry_errors:
        previous=json.loads((args.output/'report.json').read_text(encoding='utf-8'))
        targets={e['source'].split('::')[0] for e in previous['errors']}
        for r in json.loads((args.output/'manifest.json').read_text(encoding='utf-8')):
            r['sources']=[s for s in r['sources'] if s['container'].split('::')[0] not in targets]
            if not r['sources']:continue
            with Image.open(args.output/r['file']) as image:
                digest=hashlib.sha256(struct.pack('>II',r['width'],r['height'])+image.convert('RGBA').tobytes()).hexdigest()
            ex.records.append(r);ex.seen[digest]=r
        # Preserve original inventory separately; retry counters describe this pass.
        ex.kinds['retry_top_level_containers']=len(targets)
        for relative in sorted(targets):
            file=args.input/relative
            if not file.resolve().is_relative_to(args.input.resolve()):raise ValueError('Invalid retry path')
            try:ex.walk(file.read_bytes(),relative)
            except Exception as exc:ex.errors.append(dict(source=relative,error=str(exc)))
        ex.finish()
        return
    files=sorted(args.input.rglob('*'))
    for i,file in enumerate(files):
        if not file.is_file():continue
        relative=file.relative_to(args.input).as_posix()
        if file.suffix.lower() in ('.brstm','.mo','.brsar','.msbt','.msbp','.map','.txt','.csv'):continue
        try:ex.walk(file.read_bytes(),relative)
        except Exception as exc:ex.errors.append(dict(source=relative,error=str(exc)))
        if i%100==0:print(f'{i}/{len(files)} entries; {len(ex.records)} unique textures',flush=True)
    ex.finish()

if __name__=='__main__':main()
