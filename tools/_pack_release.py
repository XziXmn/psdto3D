import os, sys, zipfile, hashlib

src_dir = r"C:\Home\Workspace\UGit\psdto\_work\交付_10.1"
out_zip = r"C:\Home\Workspace\UGit\psdto\_work\PSDTO3D_10.1_2026-11-26.zip"

if os.path.exists(out_zip):
    os.remove(out_zip)

print(f"Packing {src_dir} -> {out_zip} ...")
file_count = 0
total_raw = 0

with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for root, dirs, files in os.walk(src_dir):
        # 排除临时文件
        for fn in sorted(files):
            if (fn.endswith('.orig') or fn.endswith('.log') or fn.startswith('_dlg') or
                    fn.startswith('test_') or fn.startswith('sample_out.') or
                    fn in ('_dongle_dev.bin', '_psdfix.tw3d2', '_gxwj_conv.tw3d2',
                           'autocache.tif', 'manual_save_test.tif')):
                continue
            abs_path = os.path.join(root, fn)
            rel_path = os.path.relpath(abs_path, src_dir)
            zf.write(abs_path, rel_path)
            file_count += 1
            total_raw += os.path.getsize(abs_path)

zip_size = os.path.getsize(out_zip)

# 计算哈希
md5 = hashlib.md5()
sha256 = hashlib.sha256()
with open(out_zip, 'rb') as f:
    while chunk := f.read(65536):
        md5.update(chunk)
        sha256.update(chunk)

print("="*60)
print("打包完成！")
print(f"发布包文件: {out_zip}")
print(f"压缩包大小: {zip_size:,} 字节 ({zip_size / (1024*1024):.2f} MB)")
print(f"解压文件数: {file_count} 个文件 (原始总计: {total_raw:,} 字节)")
print(f"MD5 哈希  : {md5.hexdigest().upper()}")
print(f"SHA256哈希: {sha256.hexdigest().upper()}")
print("="*60)
