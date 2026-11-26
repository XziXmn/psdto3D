"""Convert a legacy PSDTO3D project (*.tw3d2) into the new JSON project format.

The converter is the first, concrete step of the rewrite plan: it proves that the
legacy data is fully representable in the new schema, and it produces a project
that records the PSD digest so a wrong PSD/project pairing is detected instead of
crashing.

    python tw3d2_to_json.py "sample/3d2.tw3d2" --out "sample/3d2.psd3d.json" --relative
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psdinfo
import tw3d2

COLOR_MODES = {0: 'bitmap', 1: 'gray', 2: 'indexed', 3: 'rgb', 4: 'cmyk', 7: 'lab', 8: 'duotone', 9: 'lab'}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def convert(project_path, out_path, relative=True):
    proj = tw3d2.Project.load(project_path)
    base = os.path.dirname(os.path.abspath(project_path))
    psd = proj.psd_path
    psd_abs = psd if os.path.isabs(psd) else os.path.join(base, psd)
    doc = {
        'format': 'psdto3d-ng-project',
        'version': 1,
        'source': {},
        'lens': {},
        'output': {},
        'layers': [],
        'curves': [],
        'meta': {
            'author': proj.banner[2].replace('Author:', '').strip() if len(proj.banner) > 2 else '',
            'savedAt': proj.timestamp,
            'legacy': {
                'file': os.path.basename(project_path),
                'sha256': sha256(project_path),
                'timestamp': proj.timestamp,
            },
        },
    }

    source = {
        'psd': os.path.relpath(psd_abs, base).replace('\\', '/') if relative else psd_abs,
        'sha256': sha256(psd_abs) if os.path.isfile(psd_abs) else '',
        'width': proj.width,
        'height': proj.height,
        'layerCount': proj.layer_count,
    }
    if os.path.isfile(psd_abs):
        h = psdinfo.read_psd_header(psd_abs)
        source.update({
            'width': h.width,
            'height': h.height,
            'layerCount': h.layers if h.layers is not None else proj.layer_count,
            'colorMode': COLOR_MODES.get(h.color_mode, 'rgb'),
            'bitsPerChannel': h.depth,
        })
    if not source['sha256']:
        print('warning: PSD not found, digest left empty: %s' % psd_abs, file=sys.stderr)
    doc['source'] = source

    doc['lens'] = {
        'lpi': proj.lpi,
        'views': max(proj.angles, 2),
        'depth': proj.depth,
        'direction': 'vertical',
        'offset': 0,
    }
    doc['output'] = {
        'dpi': proj.dpi,
        'width': proj.width,
        'height': proj.height,
        'color': 'cmyk' if source.get('colorMode') == 'cmyk' else (
            'gray' if source.get('colorMode') == 'gray' else 'rgb'),
        'tiffCompression': 'lzw',
        'interlaceOrder': 'left-to-right',
    }
    for i in range(proj.layer_count):
        layer = proj.layers[i] if i < len(proj.layers) else tw3d2.Layer(7, 5, '1.0')
        doc['layers'].append({
            'index': i,
            'angle': float(layer.angle),
            'group': layer.group,
            'scale': float(layer.scale),
            'offset': proj.offsets[i] if i < len(proj.offsets) else 0,
            'visible': True,
        })
    for b in proj.blocks:
        doc['curves'].append({
            'layer': b.layer,
            'group': b.group,
            'sub': b.sub,
            'points': [[x, y] for x, y in b.points],
        })

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--out', default=None)
    ap.add_argument('--absolute', action='store_true')
    a = ap.parse_args()
    out = a.out or (os.path.splitext(a.project)[0] + '.psd3d.json')
    doc = convert(a.project, out, relative=not a.absolute)
    print('written %s  (layers=%d, curves=%d, psd=%s)' %
          (out, len(doc['layers']), len(doc['curves']), doc['source']['psd']))


if __name__ == '__main__':
    main()
