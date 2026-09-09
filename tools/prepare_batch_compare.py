"""Publish the comparison page and untouched originals beside a batch report."""
import argparse
import shutil
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--inputs', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
originals = args.output / 'originals'
originals.mkdir(parents=True, exist_ok=True)
for source in args.inputs.glob('*.png'):
    shutil.copy2(source, originals / source.name)
shutil.copy2(Path(__file__).with_name('batch_compare.html'), args.output / 'compare.html')
print(f'Viewer: {args.output / "compare.html"}')
