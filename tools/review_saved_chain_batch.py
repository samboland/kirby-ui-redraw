"""Build a three-way review of the saved-chain batch."""
import json
from pathlib import Path
from html import escape


def main():
    root=Path(__file__).resolve().parents[1]/'assets/kirby/demos'
    out=root/'pipeline-batch-20260909'
    report=json.loads((out/'report.json').read_text())
    cards=[]
    for result in report['results']:
        name=result['name']
        images=[('Original','../test-set-02/inputs/'+name),('Previous raster','../test-set-02/results/starsample-hq-batch/'+name),('Your current chain',name)]
        cells=[]
        for label,path in images:
            assert (out/path).exists()
            cells.append(f'<figure><figcaption>{label}</figcaption><a href="{path}"><img src="{path}" loading="lazy"></a></figure>')
        cards.append(f'<section><h2>{escape(name)}</h2><div class="row">'+''.join(cells)+'</div></section>')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Current raster pipeline batch</title><style>body{background:#242832;color:white;font:17px system-ui;margin:24px}section{margin:36px auto;max-width:1500px}.row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}figure{margin:0}figcaption{padding:10px}img{width:100%;height:430px;object-fit:contain;background:repeating-conic-gradient(#65707e 0% 25%,#46505e 0% 50%) 0/24px 24px}figure:first-child img{image-rendering:pixelated}a{color:#acf}</style><h1>Your saved pipeline: batch test</h1><p>18% To Zero threshold → StarSample HQ at 4× with Separate Alpha → median radius 1 → GIMP Mean Curvature Blur, 3 iterations.</p><p>Settings and wiring copied from upscalingtest_01.chn. Threshold and blur affect alpha as saved. The 400% resize branch is only a source preview; there is no final downscale in the processing branch.</p><p>Previous raster outputs remain unchanged. Click an image for full size.</p>'''+''.join(cards),encoding='utf-8')
    print(f'Review contains {len(cards)} complete comparisons.')


if __name__=='__main__':main()
