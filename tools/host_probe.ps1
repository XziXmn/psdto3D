# host_probe.ps1 - talk to the USBKey dongle directly (no usbip needed).
#
# Run on the machine the dongle is physically plugged into, in an elevated shell:
#   .\host_probe.ps1                 # read-only: READ CAPACITY only
#   .\host_probe.ps1 -Write -Block .\block496.bin
#
# Why: usbipd can export the device but pass-through through it has been
# unreliable; this goes straight to the disk interface like the app does.

param(
    [switch]$Write,
    [string]$Block = "",
    [string]$OutDir = "."
)

$ErrorActionPreference = "Stop"
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class Spti
{
    [StructLayout(LayoutKind.Sequential)]
    public struct SPTD
    {
        public ushort Length;
        public byte ScsiStatus;
        public byte PathId;
        public byte TargetId;
        public byte Lun;
        public byte CdbLength;
        public byte SenseInfoLength;
        public byte DataIn;
        public uint DataTransferLength;
        public uint TimeOutValue;
        public IntPtr DataBuffer;
        public uint SenseInfoOffset;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 16)]
        public byte[] Cdb;
    }

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern IntPtr CreateFileW(string name, uint access, uint share,
        IntPtr sec, uint disp, uint flags, IntPtr tmpl);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool DeviceIoControl(IntPtr h, uint code, IntPtr inBuf, uint inSize,
        IntPtr outBuf, uint outSize, out uint ret, IntPtr ov);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(IntPtr h);

    public const uint IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x4D014;

    public static IntPtr Open(string path)
    {
        return CreateFileW(path, 0xC0000000, 3, IntPtr.Zero, 3, 0, IntPtr.Zero);
    }

    // returns 0 on success, otherwise the Win32 error
    public static uint Direct(IntPtr dev, byte op, ushort addr, ushort len,
                              bool dataIn, byte[] buf, out byte scsi, out uint xfer)
    {
        SPTD p = new SPTD();
        p.Length = (ushort)Marshal.SizeOf(typeof(SPTD));
        p.CdbLength = 16;
        p.DataIn = (byte)(dataIn ? 1 : 0);
        p.DataTransferLength = (uint)buf.Length;
        p.TimeOutValue = 10;
        p.Cdb = new byte[16];
        p.Cdb[0] = op;
        p.Cdb[2] = (byte)(len & 0xFF);
        p.Cdb[3] = (byte)(len >> 8);
        p.Cdb[4] = (byte)(addr & 0xFF);
        p.Cdb[5] = (byte)(addr >> 8);

        IntPtr pkt = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(SPTD)));
        IntPtr data = IntPtr.Zero;
        try
        {
            if (!dataIn && buf.Length > 0)
            {
                data = Marshal.AllocHGlobal(buf.Length);
                Marshal.Copy(buf, 0, data, buf.Length);
                p.DataBuffer = data;
            }
            else if (dataIn && buf.Length > 0)
            {
                data = Marshal.AllocHGlobal(buf.Length);
                p.DataBuffer = data;
            }
            Marshal.StructureToPtr(p, pkt, false);

            uint ret;
            bool ok = DeviceIoControl(dev, IOCTL_SCSI_PASS_THROUGH_DIRECT, pkt,
                                      (uint)Marshal.SizeOf(typeof(SPTD)), pkt,
                                      (uint)Marshal.SizeOf(typeof(SPTD)), out ret, IntPtr.Zero);
            SPTD q = (SPTD)Marshal.PtrToStructure(pkt, typeof(SPTD));
            scsi = q.ScsiStatus;
            xfer = q.DataTransferLength;
            if (!ok) return (uint)Marshal.GetLastWin32Error();
            if (dataIn && buf.Length > 0) Marshal.Copy(data, buf, 0, buf.Length);
            return 0;
        }
        finally
        {
            if (data != IntPtr.Zero) Marshal.FreeHGlobal(data);
            Marshal.FreeHGlobal(pkt);
        }
    }
}
"@

# find the USBKey disk interface
$path = $null
$set = [IntPtr]::Zero
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class DevEnum
{
    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr SetupDiGetClassDevsW(ref Guid g, IntPtr e, IntPtr h, uint f);
    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool SetupDiEnumDeviceInterfaces(IntPtr set, IntPtr info, ref Guid g, uint idx, byte[] data);
    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool SetupDiGetDeviceInterfaceDetailW(IntPtr set, byte[] ifd, IntPtr detail, uint size, out uint need, IntPtr info);
    [DllImport("setupapi.dll")]
    public static extern bool SetupDiDestroyDeviceInfoList(IntPtr set);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr LocalAlloc(uint flags, UIntPtr size);
    [DllImport("kernel32.dll")]
    public static extern IntPtr LocalFree(IntPtr h);
}
"@

$guid = [Guid]"53f56307-b6bf-11d0-94f2-00a0c91efb8b"
$set = [DevEnum]::SetupDiGetClassDevsW([ref]$guid, [IntPtr]::Zero, [IntPtr]::Zero, 0x12)
if ($set -eq [IntPtr]::Zero -or $set -eq [IntPtr](-1)) { throw "SetupDiGetClassDevs failed" }

try {
    $ifd = New-Object byte[] 32
    $i = 0
    while ($true) {
        if (-not [DevEnum]::SetupDiEnumDeviceInterfaces($set, [IntPtr]::Zero, [ref]$guid, [uint32]$i, $ifd)) { break }
        $need = 0
        [void][DevEnum]::SetupDiGetDeviceInterfaceDetailW($set, $ifd, [IntPtr]::Zero, 0, [ref]$need, [IntPtr]::Zero)
        if ($need -le 0) { $i++; continue }
        $buf = [DevEnum]::LocalAlloc(0x40, [UIntPtr]$need)
        # cbSize of SP_DEVICE_INTERFACE_DETAIL_DATA_W is 8 on x64
        $cb = if ([IntPtr]::Size -eq 8) { 8 } else { 6 }
        [System.Runtime.InteropServices.Marshal]::WriteInt32($buf, $cb)
        if ([DevEnum]::SetupDiGetDeviceInterfaceDetailW($set, $ifd, $buf, [uint32]$need, [ref]$need, [IntPtr]::Zero)) {
            $p = [System.Runtime.InteropServices.Marshal]::PtrToStringUni([IntPtr]::Add($buf, 4))
            if ($p -match 'usbkey' -or $p -match 'usbstor') { $path = $p; [void][DevEnum]::LocalFree($buf); break }
        }
        [void][DevEnum]::LocalFree($buf)
        $i++
    }
}
finally { [void][DevEnum]::SetupDiDestroyDeviceInfoList($set) }

if (-not $path) { throw "没找到 USBKey 接口（设备可能没插好）" }
Write-Host "device: $path"

$dev = [Spti]::Open($path)
if ($dev -eq [IntPtr](-1)) { throw ("打开失败: " + [ComponentModel.Win32Exception]::new([Runtime.InteropServices.Marshal]::GetLastWin32Error()).Message) }

try {
    $cap = New-Object byte[] 8
    $scsi = [byte]0; $xfer = [uint32]0
    $e = [Spti]::Direct($dev, 0x25, 0, 0, $true, $cap, [ref]$scsi, [ref]$xfer)
    if ($e -ne 0) { Write-Host ("READ CAPACITY 失败, Win32 错误 {0}: {1}" -f $e, [ComponentModel.Win32Exception]::new([int]$e).Message); return }
    $blocks = [BitConverter]::ToUInt32($cap, 0) + 1
    $size = [BitConverter]::ToUInt32($cap, 4)
    Write-Host ("READ CAPACITY ok: blocks={0} sectorsize={1} total={2}" -f $blocks, $size, ($blocks * $size))

    if (-not $Write) {
        Write-Host "只读模式结束（加 -Write -Block <file> 才会走厂商通道）"
        return
    }

    if (-not $Block -or -not (Test-Path $Block)) { throw "缺少 -Block 指定的 496 字节块文件" }
    $blk = [IO.File]::ReadAllBytes((Resolve-Path $Block))
    if ($blk.Length -ne 496) { throw ("块文件长度应为 496，实际 " + $blk.Length) }

    $e = [Spti]::Direct($dev, 0xDD, 0, 496, $false, $blk, [ref]$scsi, [ref]$xfer)
    if ($e -ne 0) { Write-Host ("厂商写失败 {0}，停止（不再继续，避免写挂设备）" -f $e); return }
    Write-Host "厂商写 ok"

    $ack = New-Object byte[] 5
    $e = [Spti]::Direct($dev, 0xD1, 0, 5, $true, $ack, [ref]$scsi, [ref]$xfer)
    Write-Host ("状态读: err={0} ack={1}" -f $e, (($ack | ForEach-Object { $_.ToString('X2') }) -join ''))
    if ($e -ne 0) { return }

    $cmd = [byte[]](0x00,0x00,0x10,0xFA,0x1A,0x00,0xCE,0x5D,0x26,0x77)
    $e = [Spti]::Direct($dev, 0xDD, 0x01F0, 10, $false, $cmd, [ref]$scsi, [ref]$xfer)
    if ($e -ne 0) { Write-Host ("命令写失败 {0}" -f $e); return }

    $rep = New-Object byte[] 501
    $e = [Spti]::Direct($dev, 0xD1, 0x01F0, 501, $true, $rep, [ref]$scsi, [ref]$xfer)
    if ($e -ne 0) { Write-Host ("501 读失败 {0}" -f $e); return }

    if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
    [IO.File]::WriteAllBytes((Join-Path $OutDir "r501.bin"), $rep)
    [IO.File]::WriteAllBytes((Join-Path $OutDir "w496.bin"), $blk)
    Write-Host ("501 已保存到 {0}: {1}" -f $OutDir, (($rep[0..15] | ForEach-Object { $_.ToString('X2') }) -join ''))
}
finally { [void][Spti]::CloseHandle($dev) }
