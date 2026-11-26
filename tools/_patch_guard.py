import importlib.util
import pefile

spec = importlib.util.spec_from_file_location("rg", r"tools\patch_render_guard.py")
rg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rg)

EXE = r"_work\2022\psdto3d101.exe"
IB = 0x400000
pe = pefile.PE(EXE)
data = bytearray(open(EXE, "rb").read())

def off(va):
    return pe.get_offset_from_rva(va - IB)

sites = [
    (0x5023B4, 0x5023D6, 0x502BDB),
    (0x501080, 0x5010A2, 0x501833),
]
cave = 0x51437D
for site, fall, mis in sites:
    blob = rg.build_guard(cave, fall, mis)
    if any(data[off(cave):off(cave) + len(blob)]):
        raise SystemExit("cave %X not empty" % cave)
    rel = (cave - (site + 5)) & 0xFFFFFFFF
    slot = off(site)
    cur = bytes(data[slot:slot + 5])
    if cur[0] == 0xE9:
        raise SystemExit("site %X already patched" % site)
    data[slot:slot + rg.SITE_LEN] = b"\xe9" + rel.to_bytes(4, "little") + b"\x90" * (rg.SITE_LEN - 5)
    data[off(cave):off(cave) + len(blob)] = blob
    print("site %X -> %X (%d)" % (site, cave, len(blob)))
    cave += len(blob)

pe = pefile.PE(data=bytes(data))
pe.OPTIONAL_HEADER.CheckSum = pe.generate_checksum()
pe.write(EXE)
print("next free", hex(cave), "checksum", hex(pe.OPTIONAL_HEADER.CheckSum))
