"""Trace a PNG mask using the Potrace library bundled with Windows Inkscape."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
from PIL import Image


class Progress(C.Structure):
    _fields_ = [('callback', C.c_void_p), ('data', C.c_void_p),
                ('min', C.c_double), ('max', C.c_double), ('epsilon', C.c_double)]


class Params(C.Structure):
    _fields_ = [('turdsize', C.c_int), ('turnpolicy', C.c_int),
                ('alphamax', C.c_double), ('opticurve', C.c_int),
                ('opttolerance', C.c_double), ('progress', Progress)]


class Bitmap(C.Structure):
    _fields_ = [('w', C.c_int), ('h', C.c_int), ('dy', C.c_int),
                ('map', C.POINTER(C.c_ulong))]


class Point(C.Structure):
    _fields_ = [('x', C.c_double), ('y', C.c_double)]


class Curve(C.Structure):
    _fields_ = [('n', C.c_int), ('tag', C.POINTER(C.c_int)),
                ('c', C.POINTER(Point * 3))]


class TracePath(C.Structure):
    pass


TracePath._fields_ = [('area', C.c_int), ('sign', C.c_int), ('curve', Curve),
                     ('next', C.POINTER(TracePath)), ('childlist', C.POINTER(TracePath)),
                     ('sibling', C.POINTER(TracePath)), ('priv', C.c_void_p)]


class State(C.Structure):
    _fields_ = [('status', C.c_int), ('plist', C.POINTER(TracePath)), ('priv', C.c_void_p)]


def trace(source, destination, dll, mode='alpha', threshold=128, speckles=0,
          corners=1.0, tolerance=0.2):
    if not 0 <= threshold <= 255:
        raise ValueError('Threshold must be between 0 and 255.')
    dll = Path(dll).resolve()
    with os.add_dll_directory(str(dll.parent)):
        lib = C.CDLL(str(dll))
    lib.potrace_version.restype = C.c_char_p
    lib.potrace_param_default.restype = C.POINTER(Params)
    lib.potrace_param_free.argtypes = [C.POINTER(Params)]
    lib.potrace_state_free.argtypes = [C.POINTER(State)]
    lib.potrace_trace.argtypes = [C.POINTER(Params), C.POINTER(Bitmap)]
    lib.potrace_trace.restype = C.POINTER(State)
    with Image.open(source) as original:
        rgba = original.convert('RGBA')
    width, height = rgba.size
    alpha = rgba.getchannel('A')
    gray = rgba.convert('L')
    bits = C.sizeof(C.c_ulong) * 8
    stride = (width + bits - 1) // bits
    pixels = (C.c_ulong * (stride * height))()
    for y in range(height):
        for x in range(width):
            visible = alpha.getpixel((x, y)) >= threshold
            selected = visible and (mode == 'alpha' or gray.getpixel((x, y)) < threshold)
            if selected:
                pixels[y * stride + x // bits] |= 1 << (bits - 1 - x % bits)
    bitmap = Bitmap(width, height, stride, pixels)
    params = lib.potrace_param_default()
    if not params:
        raise MemoryError('Potrace parameter allocation failed.')
    state = None
    paths, segments = [], 0
    try:
        params.contents.turdsize = speckles
        params.contents.alphamax = corners
        params.contents.opttolerance = tolerance
        state = lib.potrace_trace(params, C.byref(bitmap))
        if not state or state.contents.status != 0:
            raise RuntimeError('Potrace did not complete the trace.')
        current = state.contents.plist
        def point(p):
            return f'{p.x:.5f},{p.y:.5f}'
        while current:
            curve = current.contents.curve
            commands = ['M' + point(curve.c[curve.n - 1][2])]
            for i in range(curve.n):
                pts = curve.c[i]
                if curve.tag[i] == 2:
                    commands += ['L' + point(pts[1]), 'L' + point(pts[2])]
                else:
                    commands += ['C' + ' '.join(point(p) for p in pts)]
            commands.append('Z')
            paths.append(' '.join(commands))
            segments += curve.n
            current = current.contents.next
    finally:
        if state:
            lib.potrace_state_free(state)
        lib.potrace_param_free(params)
    # Even-odd preserves holes without relying on contour orientation.
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}"><path fill="#000000" fill-rule="evenodd" '
           f'd="{" ".join(paths)}"/></svg>')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(svg, encoding='utf-8')
    report = dict(source=str(Path(source).resolve()), library=str(dll),
                  version=lib.potrace_version().decode(), width=width, height=height,
                  mode=mode, threshold=threshold, speckles=speckles, corners=corners,
                  tolerance=tolerance, contours=len(paths), segments=segments)
    destination.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--dll', default=r'C:\Program Files\Inkscape\bin\libpotrace-0.dll')
    parser.add_argument('--mode', choices=['alpha', 'dark'], default='alpha')
    parser.add_argument('--threshold', type=int, default=128)
    parser.add_argument('--speckles', type=int, default=0)
    parser.add_argument('--corners', type=float, default=1.0)
    parser.add_argument('--tolerance', type=float, default=0.2)
    args = parser.parse_args()
    print(json.dumps(trace(args.input, args.output, args.dll, args.mode, args.threshold,
                           args.speckles, args.corners, args.tolerance), indent=2))
