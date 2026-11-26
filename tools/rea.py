"""Thin wrapper around the REA CLI for this workspace.

Every call stores the complete JSON under _work/rea/ and prints only the part
that is useful in the terminal, so the Ghidra evidence stays inspectable.

    python tools/rea.py decompile 0x4DDEA4
    python tools/rea.py xrefs     0x4D6FF0
    python tools/rea.py func      0x4E2054
    python tools/rea.py show      _work/rea/decompile_4DDEA4.json
"""
import json
import os
import subprocess
import sys
from pathlib import Path

EXE = r'_work/2022d/psdto3d101.exe'
OUT = Path('_work/rea')
ENV = dict(os.environ)
ENV['GHIDRA_INSTALL_DIR'] = r'C:\Users\moo\AppData\Local\ghidra\ghidra_12.2_PUBLIC'
ENV['JAVA_HOME'] = r'C:\Users\moo\AppData\Local\jdk25\jdk-25.0.5+8'
ENV['PATH'] = ENV['JAVA_HOME'] + r'\bin;' + ENV.get('PATH', '')


def run(op, arg, tag):
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = ['rea', op, EXE, arg, '--provider', 'ghidra', '--format', 'json']
    proc = subprocess.run(cmd, capture_output=True, text=True, env=ENV, shell=True)
    text = proc.stdout.strip() or proc.stderr.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(text[:2000])
        return None
    path = OUT / (tag + '.json')
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')
    print('# saved', path)
    return data


def norm(data):
    if not isinstance(data, dict):
        return data
    for key in ('normalized_result', 'raw_result', 'result'):
        val = data.get(key)
        if isinstance(val, dict):
            return val
        if isinstance(val, str) and val.strip():
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return val
    return data


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    op, arg = sys.argv[1], sys.argv[2]
    if op == 'show':
        data = json.loads(Path(arg).read_text(encoding='utf-8'))
        print(json.dumps(norm(data), indent=1, ensure_ascii=False)[:8000])
        return 0
    if op == 'decompile':
        data = run('decompile', arg, 'decompile_' + arg.replace('0x', ''))
    elif op == 'xrefs':
        data = run('xrefs', arg, 'xrefs_' + arg.replace('0x', ''))
    elif op == 'func':
        data = run('function', arg, 'function_' + arg.replace('0x', ''))
    else:
        print(__doc__)
        return 1
    if data is None:
        return 1
    body = norm(data)
    if isinstance(body, str):
        print(body[:6000])
        return 0
    for key in ('pseudocode', 'code', 'c_code', 'source'):
        if isinstance(body.get(key), str):
            print(body[key][:8000])
            return 0
    print(json.dumps(body, indent=1, ensure_ascii=False)[:8000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
