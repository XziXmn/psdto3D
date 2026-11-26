"""psdto3d 绿色版 (portable build) maker.

Evidence base (REA static analysis of the shipped PE images, see 构建报告*.json):

* ``psdto3d101.exe`` is a 32-bit Delphi (Borland) VCL application.  It imports
  only ``borlndmm.dll`` and ``cmyktiff2.dll`` from the distribution folder; the
  remaining modules are loaded dynamically by name at run time.
* The startup path contains the dongle (USBKey) gate::

      call  <dongle status>            ; 0 = licensed, 0xFFFFFBE3 = no key
      cmp   eax, 0FFFFFBE3h
      jne   short @@next
      mov   eax, offset aNoSoftwareKey ; "The system did not find any software key, ..."
      call  ShowMessage
      call  Halt
  @@next:
      call  <dongle status>
      test  eax, eax
      je    short @@licensed
      ...  "Register file error, because the key did not write the license number ..."
  @@licensed:
      ...  normal start-up

  The two conditionals are rewritten so the licensed continuation is always
  taken.  Nothing else in the image, and no DLL of the distribution, carries a
  licence gate ("software key" / "Register file error" literals appear only in
  psdto3d101.exe and in the separate KeyReg101.exe).
* The image carries an embedded RT_MANIFEST with
  ``requestedExecutionLevel level="requireAdministrator"``; it is rewritten to
  ``asInvoker`` so the portable build starts without a UAC prompt.
* The image header lacks IMAGE_FILE_LARGE_ADDRESS_AWARE, so the 32-bit process
  is limited to 2 GiB on 64-bit Windows.  The flag is set, which gives the same
  process the full 4 GiB user address space on x64 (large PSD projects).

Usage:
    python make_green.py --src-dir "Psdto3d" --exe psdto3d101.exe \
        --out-dir "psdto3d101绿色版_2025" --label "2025-03-24"
"""
import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys

import pefile

NO_KEY_ANSI = b"The system did not find any software key, please insert it."
STATUS_NO_KEY = 0xFFFFFBE3

MANIFEST_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
    '<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">\r\n'
    '<trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">\r\n'
    '<security>\r\n'
    '<requestedPrivileges>\r\n'
    '<requestedExecutionLevel level="{level}"{uiaccess}/>\r\n'
    '</requestedPrivileges>\r\n'
    '</security>\r\n'
    '</trustInfo>\r\n'
    '</assembly>\r\n'
)

SKIP_SUFFIXES = ('.obj', '.lll')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def find_all(buf, needle):
    out, i = [], buf.find(needle)
    while i != -1:
        out.append(i)
        i = buf.find(needle, i + 1)
    return out


class Image:
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.data = bytearray(f.read())
        self.pe = pefile.PE(data=bytes(self.data))
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.notes = []
        self.report = {}

    # -- licence ---------------------------------------------------------
    def patch_licence(self):
        raw = bytes(self.data)
        hits = find_all(raw, NO_KEY_ANSI)
        if len(hits) != 1:
            raise SystemExit('NO_KEY literal count = %d (expected 1)' % len(hits))
        str_va = self.base + self.pe.get_rva_from_offset(hits[0])
        refs = find_all(raw, b'\xb8' + struct.pack('<I', str_va))
        if len(refs) != 1:
            raise SystemExit('mov-eax reference count = %d (expected 1)' % len(refs))
        ref_off = refs[0]
        window_start = max(0, ref_off - 0x80)
        window = raw[window_start:ref_off]
        cmp_pat = b'\x3d' + struct.pack('<I', STATUS_NO_KEY)
        pos = window.rfind(cmp_pat)
        if pos == -1:
            raise SystemExit('dongle status compare not found')
        cmp_off = window_start + pos
        jne_off = cmp_off + 5
        if raw[jne_off] != 0x75:
            raise SystemExit('unexpected opcode after status compare: %02x' % raw[jne_off])
        self.data[jne_off] = 0xEB
        self.notes.append('licence gate 1: jne -> jmp at file 0x%x (va 0x%x)' %
                          (jne_off, self.base + self.pe.get_rva_from_offset(jne_off)))
        tail_start = ref_off
        te = raw.find(b'\x85\xc0', tail_start, tail_start + 0x40)
        if te == -1:
            raise SystemExit('second status test not found')
        after = raw[te + 2]
        ok = 0x70 <= after <= 0x7F or (after == 0x0F and 0x80 <= raw[te + 3] <= 0x8F)
        if not ok:
            raise SystemExit('second status test not followed by jcc')
        self.data[te:te + 2] = b'\x31\xc0'
        self.notes.append('licence gate 2: test -> xor at file 0x%x (va 0x%x)' %
                          (te, self.base + self.pe.get_rva_from_offset(te)))
        self.report['licence_patches'] = [
            {'file_offset': '0x%x' % jne_off, 'before': '750f', 'after': 'eb0f',
             'va': '0x%x' % (self.base + self.pe.get_rva_from_offset(jne_off)),
             'purpose': 'skip the "no software key" abort'},
            {'file_offset': '0x%x' % te, 'before': '85c0', 'after': '31c0',
             'va': '0x%x' % (self.base + self.pe.get_rva_from_offset(te)),
             'purpose': 'always continue on the licensed path'},
        ]

    # -- 64-bit addressing ------------------------------------------------
    def set_large_address_aware(self):
        fh = self.pe.FILE_HEADER.get_file_offset() + 0x12  # Characteristics
        cur = struct.unpack_from('<H', self.data, fh)[0]
        struct.pack_into('<H', self.data, fh, cur | 0x0020)
        self.notes.append('IMAGE_FILE_LARGE_ADDRESS_AWARE: 0x%04x -> 0x%04x' % (cur, cur | 0x0020))
        self.report['characteristics'] = {'before': '0x%04x' % cur, 'after': '0x%04x' % (cur | 0x20)}
        return cur & 0x20 == 0

    # -- manifest ---------------------------------------------------------
    def rewrite_manifest(self, level='asInvoker', uiaccess=False):
        r = getattr(self.pe, 'DIRECTORY_ENTRY_RESOURCE', None)
        if r is None:
            self.notes.append('no resource directory; manifest unchanged')
            return False
        for e in r.entries:
            if e.struct.Id != 24:
                continue
            for d in e.directory.entries:
                for lang in d.directory.entries:
                    info = lang.data.struct
                    off = self.pe.get_offset_from_rva(info.OffsetToData)
                    old = bytes(self.data[off:off + info.Size])
                    new = MANIFEST_TEMPLATE.format(
                        level=level, uiaccess=' uiAccess="false"' if uiaccess else '').encode('utf-8')
                    if len(new) > info.Size:
                        new = MANIFEST_TEMPLATE.format(level=level, uiaccess='').encode('utf-8')
                    if len(new) > info.Size:
                        raise SystemExit('new manifest (%d) does not fit the %d-byte slot'
                                         % (len(new), info.Size))
                    pad = info.Size - len(new)
                    new = new[:-len(b'</assembly>\r\n')] + b' ' * pad + b'</assembly>\r\n'
                    assert len(new) == info.Size
                    self.data[off:off + info.Size] = new
                    self.notes.append('manifest requestedExecutionLevel -> %s (%d bytes slot)'
                                      % (level, info.Size))
                    self.report['manifest'] = {
                        'old': old.decode('utf-8', 'replace').replace('\r\n', ' '),
                        'new': new.decode('utf-8', 'replace').replace('\r\n', ' '),
                    }
                    return True
        self.notes.append('no RT_MANIFEST resource; manifest unchanged')
        return False

    # -- checksum ---------------------------------------------------------
    def fix_checksum(self):
        pe = pefile.PE(data=bytes(self.data))
        want = pe.generate_checksum()
        off = pe.OPTIONAL_HEADER.get_file_offset() + 0x40
        struct.pack_into('<I', self.data, off, want)
        self.notes.append('PE checksum set to 0x%08x' % want)
        self.report['checksum'] = '0x%08x' % want


def package(src_dir, exe_name, out_dir, label, elevation, crash_guard=True):
    out_dir = os.path.abspath(out_dir)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)

    copied, skipped = [], []
    for root, dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        target = out_dir if rel == '.' else os.path.join(out_dir, rel)
        os.makedirs(target, exist_ok=True)
        for name in files:
            src = os.path.join(root, name)
            if name.lower().endswith(SKIP_SUFFIXES):
                skipped.append(os.path.relpath(src, src_dir))
                continue
            shutil.copy2(src, os.path.join(target, name))
            copied.append(os.path.relpath(src, src_dir))

    src_exe = os.path.join(out_dir, exe_name)
    img = Image(src_exe)
    img.report['source'] = os.path.relpath(src_exe, out_dir)
    img.report['source_sha256'] = sha256(src_exe)
    img.report['machine'] = 'x86'
    img.report['image'] = 'PE32'
    shutil.copy2(src_exe, os.path.join(out_dir, exe_name + '.orig'))
    img.patch_licence()
    img.set_large_address_aware()
    img.rewrite_manifest(level=elevation)
    img.fix_checksum()
    with open(src_exe, 'wb') as f:
        f.write(bytes(img.data))
    img.report['output_sha256'] = sha256(src_exe)
    img.report['label'] = label
    img.report['notes'] = img.notes
    img.report['files_copied'] = len(copied)
    img.report['files_skipped'] = skipped

    # second stage: null-guard for the 3D generator (0x50A001 crash), see
    # docs/故障诊断_浮点异常与AV.md
    if crash_guard:
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'patch_crash_guard.py')
        if os.path.isfile(helper):
            guard_report = os.path.join(out_dir, '_crash_guard.json')
            rc = subprocess.call([sys.executable, helper, src_exe, '--report', guard_report])
            img.report['crash_guard'] = {'applied': rc == 0, 'report': guard_report}
            img.report['output_sha256'] = sha256(src_exe)
            if os.path.isfile(guard_report):
                os.remove(guard_report)
        else:
            img.report['crash_guard'] = {'applied': False, 'reason': 'patch_crash_guard.py not found'}
    return img.report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
    ap.add_argument('--exe', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--label', default='')
    ap.add_argument('--elevation', default='asInvoker',
                    choices=['asInvoker', 'requireAdministrator', 'highestAvailable'])
    ap.add_argument('--report', default=None)
    ap.add_argument('--no-crash-guard', action='store_true')
    a = ap.parse_args()
    rep = package(a.src_dir, a.exe, a.out_dir, a.label, a.elevation,
                  crash_guard=not a.no_crash_guard)
    text = json.dumps(rep, indent=2, ensure_ascii=False)
    print(text)
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            f.write(text)


if __name__ == '__main__':
    main()

