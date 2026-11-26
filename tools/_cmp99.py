import importlib.util
import capstone
spec = importlib.util.spec_from_file_location("pmod", r"tools\peasm.py")
pmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pmod)
m = pmod.Mod(r"_work\2022\psdto3d101.exe")
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
off = m.va2off(0x504D40)
for ins in md.disasm(m.raw[off:off+70], 0x504D40):
    print("%08X  %s %s" % (ins.address, ins.mnemonic, ins.op_str))
