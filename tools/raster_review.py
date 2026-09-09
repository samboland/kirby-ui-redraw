"""Review existing raster outputs without regenerating or changing images."""
from pathlib import Path
from html import escape


def main():
    root=Path(__file__).resolve().parents[1]/'assets/kirby/demos'
    out=root/'raster-review'
    out.mkdir(exist_ok=True)
    pairs=[('Dedede: saved StarSample baseline','../dedede/source.png','../hybrid-contours/mild/input.png')]
    for source in sorted((root/'test-set-02/inputs').glob('*.png')):
        result=root/'test-set-02/results/starsample-hq-batch'/source.name
        if result.exists():
            pairs.append((source.stem,'../test-set-02/inputs/'+source.name,'../test-set-02/results/starsample-hq-batch/'+source.name))
    cards=[]
    for title,source,result in pairs:
        assert (out/source).exists() and (out/result).exists()
        cards.append(f'<section><h2>{escape(title)}</h2><div class="pair"><figure><figcaption>Original</figcaption><a href="{source}"><img class="source" src="{source}" loading="lazy"></a></figure><figure><figcaption>Saved raster output</figcaption><a href="{result}"><img src="{result}" loading="lazy"></a></figure></div></section>')
    (out/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Raster baseline</title><style>body{font:17px system-ui;background:#242832;color:#eee;margin:24px}section{max-width:1200px;margin:36px auto}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}figcaption{padding:8px}img{width:100%;max-height:650px;object-fit:contain;background:repeating-conic-gradient(#65707e 0% 25%,#46505e 0% 50%) 0/24px 24px}.source{image-rendering:pixelated}a{color:#acf}</style><h1>Raster baseline</h1><p>Existing StarSample raster results, before the vector experiments. These files are shown as saved; no new processing was applied.</p><p>The Dedede comparison uses the saved snapshot used to begin the contour experiments. Other rows show the saved chaiNNer batch outputs. Click an image to open its file.</p>'''+''.join(cards),encoding='utf-8')
    print(f'{len(pairs)} existing raster comparisons linked.')


if __name__=='__main__':main()
