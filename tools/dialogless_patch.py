"""Make a psdto3d copy dialog-less for automated end-to-end tests.

The shell file dialogs cannot be driven from a non-interactive session (no
foreground window => no keyboard/mouse input), so this tool redirects the
GetOpenFileNameA / GetSaveFileNameA import slots to small stubs that fill the
OPENFILENAME with a fixed path and return TRUE.  The application then behaves
exactly as if a user had picked that file.

Only the *test copy* is patched; the shipped green package stays untouched.

    python dialogless_patch.py --exe <copy.exe> --open <project.tw3d2> --save <out.tif>
"""
import argparse
import json
import struct
import sys

import pefile

STUB = bytes.fromhex(
    '8B742404'      # mov esi,[esp+4]      ; OPENFILENAME*
    '8B7E1C'        # mov edi,[esi+0x1C]  ; lpstrFile
    'BE00000000'    # mov esi,<path>
    'B900000000'    # mov ecx,<len+1>
    'F3A4'          # rep movsb
    'B801000000'    # mov eax,1
    'C20400'        # ret 4
)


def rva_to_off(pe, rva):
    for s in pe.sections:
        span = max(s.Misc_VirtualSize, s.SizeOfRawData)
        if s.VirtualAddress <= rva < s.VirtualAddress + span:
            delta = rva - s.VirtualAddress
            if delta >= s.SizeOfRawData:
                raise SystemExit('RVA 0x%x is virtual-only in %s' % (rva, s.Name.rstrip(b'\x00').decode()))
            return s.PointerToRawData + delta
    raise SystemExit('RVA 0x%x not in any section' % rva)


def find_iat(pe, dll_name, func_names):
    out = {}
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        name = entry.dll.decode().lower()
        if name != dll_name.lower():
            continue
        for imp in entry.imports:
            fn = imp.name.decode() if imp.name else None
            if fn in func_names:
                out[fn] = imp.address        # RVA of the IAT slot
    return out


def find_zero_run(data, offset, length, need):
    i = offset
    while i + need <= offset + length:
        if data[i] == 0:
            j = i
            while j < offset + length and data[j] == 0:
                j += 1
            if j - i >= need:
                return i
            i = j
        else:
            i += 1
    return None


def build_stub(path_bytes, path_va):
    code = bytearray(STUB)
    struct.pack_into('<I', code, 8, path_va)
    struct.pack_into('<I', code, 13, len(path_bytes) + 1)
    return bytes(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--open', required=True, help='path returned by the open dialog')
    ap.add_argument('--save', required=True, help='path returned by the save dialog')
    ap.add_argument('--report', default=None)
    a = ap.parse_args()

    data = bytearray(open(a.exe, 'rb').read())
    pe = pefile.PE(data=bytes(data))
    base = pe.OPTIONAL_HEADER.ImageBase
    iat = find_iat(pe, 'comdlg32.dll', {'GetOpenFileNameA', 'GetSaveFileNameA'})
    if set(iat) != {'GetOpenFileNameA', 'GetSaveFileNameA'}:
        raise SystemExit('comdlg32 imports not found: %s' % iat)

    code_sec = [s for s in pe.sections if s.Characteristics & 0x20000000][0]
    data_sec = [s for s in pe.sections if not (s.Characteristics & 0x20000000)][0]

    # 1. strings in the data section's zero tail
    need = len(a.open) + 1 + len(a.save) + 1 + 8
    d_off = find_zero_run(data, data_sec.PointerToRawData, data_sec.SizeOfRawData, need)
    if d_off is None:
        raise SystemExit('no room for the path strings in the data section')
    open_bytes = a.open.encode('gbk')
    save_bytes = a.save.encode('gbk')
    open_va = base + data_sec.VirtualAddress + (d_off - data_sec.PointerToRawData)
    data[d_off:d_off + len(open_bytes) + 1] = open_bytes + b'\x00'
    s_off = d_off + len(open_bytes) + 1
    save_va = base + data_sec.VirtualAddress + (s_off - data_sec.PointerToRawData)
    data[s_off:s_off + len(save_bytes) + 1] = save_bytes + b'\x00'

    # 2. stubs in the code section's zero tail
    stub_open = build_stub(open_bytes, open_va)
    stub_save = build_stub(save_bytes, save_va)
    code_off = find_zero_run(data, code_sec.PointerToRawData, code_sec.SizeOfRawData,
                             len(stub_open) + len(stub_save) + 4)
    if code_off is None:
        raise SystemExit('no room for the stubs in the code section')
    code_va = base + code_sec.VirtualAddress + (code_off - code_sec.PointerToRawData)
    data[code_off:code_off + len(stub_open)] = stub_open
    save_stub_off = code_off + len(stub_open)
    save_stub_va = code_va + len(stub_open)
    data[save_stub_off:save_stub_off + len(stub_save)] = stub_save

    # 3. point the IAT slots at the stubs
    for name, target in (('GetOpenFileNameA', code_va), ('GetSaveFileNameA', save_stub_va)):
        off = rva_to_off(pe, iat[name] - base)
        struct.pack_into('<I', data, off, target)

    pe2 = pefile.PE(data=bytes(data))
    checksum = pe2.generate_checksum()
    struct.pack_into('<I', data, pe2.OPTIONAL_HEADER.get_file_offset() + 0x40, checksum)
    open(a.exe, 'wb').write(bytes(data))

    report = {
        'exe': a.exe,
        'iat': {k: hex(v) for k, v in iat.items()},
        'stubs': {'GetOpenFileNameA': hex(code_va), 'GetSaveFileNameA': hex(save_stub_va)},
        'paths': {'open': a.open, 'save': a.save},
        'string_vas': {'open': hex(open_va), 'save': hex(save_va)},
        'checksum': hex(checksum),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
