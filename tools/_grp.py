lines = open(r"C:\bio\a.tw3d2", "rb").read().decode("gbk", "replace").splitlines()
n = int(lines[2].split()[1])
i = 8 + 2 * n
print("curve start line", i + 1, "total", len(lines))
layers = set()
while i < len(lines):
    s = lines[i].strip()
    i += 1
    if not s:
        continue
    p = s.split()
    if len(p) >= 4 and all(x.lstrip("-").isdigit() for x in p[:4]):
        layers.add(int(p[0]))
print("curve file-layers", sorted(layers))
print("ui", sorted(n + 1 - x for x in layers))
