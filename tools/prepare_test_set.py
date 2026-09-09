"""Copy original native textures into a small chaiNNer evaluation set."""
import json
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

CASES=[
 ('01-star','78b206f2971eeff2','Tiny shaded icon'),
 ('02-waddle-dee','671bf1d0ff64e3ef','Tiny face and outline'),
 ('03-pointer','f6327442142fbd54','White edges against transparency'),
 ('04-metal-number','91126b5e905afac6','Metallic shading and numeral shape'),
 ('05-kirby-face','c80e89718b1c0b73','Round face and subtle shading'),
 ('06-crown','c237e9a5682bb8f4','Small stars and glossy highlights'),
 ('07-dragon-boss','4771a2cfef54a1cb','Dense character detail'),
 ('08-water-pattern','b4dcf4be5c296089','Repeating curves; inspect seams'),
 ('09-sword-card','e7206ec09ae284db','Illustration and transparency'),
 ('10-ice-card','f431315089a97510','Illustration and light effects'),
]

def main():
    root=Path(__file__).resolve().parents[1]/'assets/kirby'
    records={r['id']:r for r in json.loads((root/'manifest.json').read_text())}
    output=root/'demos/test-set-02';inputs=output/'inputs';inputs.mkdir(parents=True,exist_ok=True)
    (output/'results').mkdir(exist_ok=True)
    sheet=Image.new('RGB',(1250,660),'#282b33');draw=ImageDraw.Draw(sheet)
    manifest=[]
    for i,(name,identity,purpose) in enumerate(CASES):
        r=records[identity];source=root/r['file'];target=inputs/(name+'.png')
        shutil.copy2(source,target)
        assert source.read_bytes()==target.read_bytes()
        im=Image.open(target).convert('RGBA');size=im.size
        im.thumbnail((222,235))
        if max(size)<128:im=im.resize((im.width*2,im.height*2),Image.Resampling.NEAREST)
        x=(i%5)*250;y=(i//5)*330
        tile=Image.new('RGBA',(230,245),'#646771');tile.alpha_composite(im,((230-im.width)//2,(245-im.height)//2))
        sheet.paste(tile.convert('RGB'),(x+10,y+10))
        draw.text((x+10,y+263),name,fill='white')
        draw.text((x+10,y+281),f'{size[0]} x {size[1]} native',fill='white')
        draw.text((x+10,y+300),purpose,fill='#c2c8d6')
        manifest.append(dict(name=name,purpose=purpose,source=r))
    sheet.save(output/'contact-sheet.png')
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    page='<meta charset="utf-8"><title>Kirby test set 02</title><style>body{background:#282b33;color:white;font:18px system-ui;margin:25px}a{color:#acd5ff}img{max-width:100%}li{margin:12px}</style><h1>Ten original textures for chaiNNer</h1><p>Inputs are byte-identical copies at native resolution. Save your upscales in the sibling results folder.</p><img src="contact-sheet.png"><ul>'
    for name,identity,purpose in CASES:
        page+=f'<li><a href="inputs/{name}.png">{name}</a>: {purpose}</li>'
    (output/'index.html').write_text(page+'</ul>',encoding='utf-8')
    print(output)

if __name__=='__main__':main()
