"""Rewrite the two caves so the loop count is the saved layer count minus 1."""
import pefile

EXE = r"_work\2022\psdto3d101.exe"
IB = 0x400000

def stub(back_va, stub_va):
    body = bytes.fromhex("8b45ac4885c0")  # mov eax,[ebp-0x54]; dec eax; test eax,eax
    src = stub_va + len(body) + 5
    rel = (back_va - src) & 0xFFFFFFFF
    return body + b"\xe9" + rel.to_bytes(4, "little")

def main():
    pe = pefile.PE(EXE)
    data = bytearray(open(EXE, "rb").read())

    def off(va):
        return pe.get_offset_from_rva(va - IB)

    for cave, back in ((0x514324, 0x511A08), (0x514331, 0x511A86)):
        blob = stub(back, cave)
        co = off(cave)
        data[co:co + 16] = b"\x00" * 16
        data[co:co + len(blob)] = blob
        print("cave %X %s -> %X" % (cave, blob.hex(), back))

    pe = pefile.PE(data=bytes(data))
    pe.OPTIONAL_HEADER.CheckSum = pe.generate_checksum()
    pe.write(EXE)
    print("checksum", hex(pe.OPTIONAL_HEADER.CheckSum))

if __name__ == "__main__":
    main()
