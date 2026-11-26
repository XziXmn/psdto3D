"""Minimal PSD header reader: size, depth, channel count and layer count.

Only the header plus the layer-info count are decoded (no pixel data), which is
what the project/PSD binding check needs.
"""
import struct


class PsdHeader:
    __slots__ = ('width', 'height', 'depth', 'channels', 'color_mode', 'layers', 'path')

    def __repr__(self):
        return ('PsdHeader(%dx%d depth=%d channels=%d mode=%d layers=%s)' %
                (self.width, self.height, self.depth, self.channels, self.color_mode, self.layers))


def read_psd_header(path):
    with open(path, 'rb') as f:
        data = f.read(26)
        if len(data) < 26 or data[:4] != b'8BPS':
            raise ValueError('not a PSD file: %s' % path)
        version = struct.unpack('>H', data[4:6])[0]
        if version != 1:
            raise ValueError('unsupported PSD version %d' % version)
        h = PsdHeader()
        h.path = path
        h.channels = struct.unpack('>H', data[12:14])[0]
        h.height, h.width = struct.unpack('>II', data[14:22])
        h.depth = struct.unpack('>H', data[22:24])[0]
        h.color_mode = struct.unpack('>H', data[24:26])[0]

        # skip colour mode data and image resources
        for _ in range(2):
            ln = struct.unpack('>I', f.read(4))[0]
            f.seek(ln, 1)
        layer_mask_len = struct.unpack('>I', f.read(4))[0]
        h.layers = None
        if layer_mask_len >= 4:
            layer_info_len = struct.unpack('>I', f.read(4))[0]
            if layer_info_len >= 2:
                count = struct.unpack('>h', f.read(2))[0]
                h.layers = abs(count)
    return h


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        try:
            print('%-40s %s' % (p.rsplit('\\', 1)[-1], read_psd_header(p)))
        except Exception as exc:  # noqa: BLE001
            print('%-40s ERROR %s' % (p.rsplit('\\', 1)[-1], exc))
