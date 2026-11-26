/* dongle_probe.c - talk to the USBKey dongle directly through SCSI pass-through
 * and record how it answers, so the reply function can be derived.
 *
 * The app's structure was recovered from the hooked IOCTLs: a 44-byte
 * SCSI_PASS_THROUGH whose CDB carries the length at CDB[2..3] and the slot
 * address at CDB[4..5]; the data buffer pointer sits at offset 20.
 *
 * Build: gcc -O2 -o dongle_probe.exe dongle_probe.c
 * Run:   dongle_probe.exe <outdir>
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define IOCTL_SCSI_PASS_THROUGH 0x4D004

typedef struct {
    USHORT Length;
    UCHAR  ScsiStatus;
    UCHAR  PathId;
    UCHAR  TargetId;
    UCHAR  Lun;
    UCHAR  CdbLength;
    UCHAR  SenseInfoLength;
    UCHAR  DataIn;
    ULONG  DataTransferLength;
    ULONG  TimeOutValue;
    ULONG_PTR DataBufferOffset;
    ULONG  SenseInfoOffset;
    UCHAR  Cdb[16];
} SPT;

#pragma pack(push, 8)
typedef struct {
    USHORT Length;
    UCHAR  ScsiStatus;
    UCHAR  PathId;
    UCHAR  TargetId;
    UCHAR  Lun;
    UCHAR  CdbLength;
    UCHAR  SenseInfoLength;
    UCHAR  DataIn;
    ULONG  DataTransferLength;
    ULONG  TimeOutValue;
    PVOID  DataBuffer;
    ULONG  SenseInfoOffset;
    UCHAR  Cdb[16];
} SPTD;
#pragma pack(pop)

#define IOCTL_SCSI_PASS_THROUGH_DIRECT 0x4D014

static const char *DEVPATH =
    "\\\\?\\usbstor#disk&ven_usbkey&prod_usbkeyco._&rev_2.00#3&3ad7ba7f&0"
    "#{53f56307-b6bf-11d0-94f2-00a0c91efb8b}";


/* Safety: a write with an implausible block wedges the dongle firmware (observed:
 * 496-byte all-zero write -> the next read times out with 121 and the device
 * drops off the bus with 1167). So writes are opt-in and stop on first error. */
static int g_allow_write = 0;
static unsigned char g_cdb_w[16];   /* write CDB override */
static unsigned char g_cdb_r[16];   /* read CDB override */
static int g_has_cdb_w, g_has_cdb_r;
static int g_stop_on_error = 1;

static HANDLE g_dev;
static char g_path[MAX_PATH];

/* one request: cdb op, slot address, payload (write) or expected length (read) */
static int do_spti_direct(UCHAR op, USHORT addr, USHORT len, UCHAR data_in,
                          void *buf, ULONG buflen, DWORD *ret)
{
    SPTD pkt;
    DWORD got = 0;
    BOOL ok;
    memset(&pkt, 0, sizeof(pkt));
    pkt.Length = (USHORT)sizeof(SPTD);
    pkt.CdbLength = 16;
    pkt.DataIn = data_in;
    pkt.DataTransferLength = buflen;
    pkt.TimeOutValue = 10;
    pkt.DataBuffer = buf;
    memcpy(pkt.Cdb, data_in ? g_cdb_r : g_cdb_w, 16);
    if (!(data_in ? g_has_cdb_r : g_has_cdb_w)) {
        memset(pkt.Cdb, 0, 16);
        pkt.Cdb[0] = op;
        pkt.Cdb[2] = (UCHAR)(len & 0xFF);
        pkt.Cdb[3] = (UCHAR)(len >> 8);
        pkt.Cdb[4] = (UCHAR)(addr & 0xFF);
        pkt.Cdb[5] = (UCHAR)(addr >> 8);
    }
    ok = DeviceIoControl(g_dev, IOCTL_SCSI_PASS_THROUGH_DIRECT, &pkt, sizeof(pkt),
                         &pkt, sizeof(pkt), &got, NULL);
    if (ret) *ret = got;
    {
        static int n;
        printf("    [%02d] DIRECT op=%02X addr=%04X len=%u in=%u -> ok=%d err=%lu scsi=%02X xfer=%lu\n",
               n++, op, addr, len, buflen, ok, ok ? 0UL : GetLastError(),
               pkt.ScsiStatus, pkt.DataTransferLength);
    }
    if (!ok && g_stop_on_error) {
        printf("    --- 出错即停，避免把固件写挂 ---\n");
        exit(3);
    }
    return ok ? 0 : -1;
}

static int do_spti(UCHAR op, USHORT addr, USHORT len, UCHAR data_in,
                   void *buf, ULONG buflen, DWORD *ret)
{
    return do_spti_direct(op, addr, len, data_in, buf, buflen, ret);
}

static int do_spti_old(UCHAR op, USHORT addr, USHORT len, UCHAR data_in,
                       void *buf, ULONG buflen, DWORD *ret)
{
    UCHAR pkt[2048];
    SPT *s = (SPT *)pkt;
    DWORD got = 0;
    BOOL ok;

    memset(pkt, 0, sizeof(pkt));
    s->Length = (USHORT)sizeof(SPT);
    s->CdbLength = 16;
    s->SenseInfoLength = 0;
    s->DataIn = data_in;
    s->DataTransferLength = buflen;
    s->TimeOutValue = 10;
    s->DataBufferOffset = (ULONG_PTR)(pkt + 64);
    s->SenseInfoOffset = 0;
    s->Cdb[0] = op;
    s->Cdb[2] = (UCHAR)(len & 0xFF);
    s->Cdb[3] = (UCHAR)(len >> 8);
    s->Cdb[4] = (UCHAR)(addr & 0xFF);
    s->Cdb[5] = (UCHAR)(addr >> 8);
    if (!data_in && buflen) memcpy(pkt + 64, buf, buflen);

    ok = DeviceIoControl(g_dev, IOCTL_SCSI_PASS_THROUGH, pkt, sizeof(pkt),
                         pkt, sizeof(pkt), &got, NULL);
    if (ret) *ret = got;
    {
        static int n;
        printf("    [%02d] op=%02X addr=%04X len=%u in=%u -> ok=%d err=%lu got=%lu scsi=%02X xfer=%lu\n",
               n++, op, addr, len, buflen, ok, ok ? 0UL : GetLastError(), got,
               s->ScsiStatus, s->DataTransferLength);
    }
    if (!ok) return -1;
    if (data_in && buflen) memcpy(buf, pkt + 64, buflen);
    return 0;
}

static void dump(const char *dir, const char *tag, const void *p, unsigned n)
{
    char path[MAX_PATH];
    FILE *f;
    sprintf(path, "%s\\%s.bin", dir, tag);
    f = fopen(path, "wb");
    if (!f) return;
    fwrite(p, 1, n, f);
    fclose(f);
}


/* Enumerate disk interfaces and pick the USBKey one, like the app does. */
#include <setupapi.h>
#include <initguid.h>
DEFINE_GUID(GUID_DEVINTERFACE_DISK_, 0x53f56307L,0xb6bf,0x11d0,0x94,0xf2,0x00,0xa0,0xc9,0x1e,0xfb,0x8b);

static int find_dev(char *out, int cap)
{
    HDEVINFO set = SetupDiGetClassDevsA(&GUID_DEVINTERFACE_DISK_, NULL, NULL,
                                        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    SP_DEVICE_INTERFACE_DATA ifd;
    DWORD i;
    int found = 0;
    if (set == INVALID_HANDLE_VALUE) return 0;
    ifd.cbSize = sizeof(ifd);
    for (i = 0; SetupDiEnumDeviceInterfaces(set, NULL, &GUID_DEVINTERFACE_DISK_, i, &ifd); i++) {
        DWORD need = 0;
        PSP_DEVICE_INTERFACE_DETAIL_DATA_A det;
        SetupDiGetDeviceInterfaceDetailA(set, &ifd, NULL, 0, &need, NULL);
        if (!need) continue;
        det = (PSP_DEVICE_INTERFACE_DETAIL_DATA_A)malloc(need);
        det->cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_A);
        if (SetupDiGetDeviceInterfaceDetailA(set, &ifd, det, need, NULL, NULL)) {
            if (_strnicmp(det->DevicePath, "\\\\?\\usbstor", 11) == 0 ||
                strstr(det->DevicePath, "usbkey") || strstr(det->DevicePath, "USBKEY")) {
                lstrcpynA(out, det->DevicePath, cap);
                found = 1;
                free(det);
                break;
            }
        }
        free(det);
    }
    SetupDiDestroyDeviceInfoList(set);
    return found;
}

int main(int argc, char **argv)
{
    const char *dir = (argc > 1) ? argv[1] : ".";
    const char *blockfile = NULL;
    int i2;
    int limit = 4;
    for (i2 = (argc > 2 && argv[2][0] != '-') ? 3 : 2; i2 < argc; i2++) {
        if (!strcmp(argv[i2], "--write")) g_allow_write = 1;
        else if (!strcmp(argv[i2], "--block") && i2 + 1 < argc) blockfile = argv[++i2];
        else if (!strcmp(argv[i2], "--keep-going")) g_stop_on_error = 0;
        else if (!strcmp(argv[i2], "--limit") && i2 + 1 < argc) limit = atoi(argv[++i2]);
        else if (!strcmp(argv[i2], "--cdbw") && i2 + 1 < argc) {
            const char *h = argv[++i2]; int t;
            for (t = 0; t < 16 && h[t*2] && h[t*2+1]; t++) {
                char b2[3] = { h[t*2], h[t*2+1], 0 };
                g_cdb_w[t] = (unsigned char)strtoul(b2, 0, 16);
            }
            g_has_cdb_w = (t == 16); }
        else if (!strcmp(argv[i2], "--cdbr") && i2 + 1 < argc) {
            const char *h = argv[++i2]; int t;
            for (t = 0; t < 16 && h[t*2] && h[t*2+1]; t++) {
                char b2[3] = { h[t*2], h[t*2+1], 0 };
                g_cdb_r[t] = (unsigned char)strtoul(b2, 0, 16);
            }
            g_has_cdb_r = (t == 16); }
    }
    static UCHAR blk[496];
    static UCHAR rep[501];
    DWORD ret = 0;
    int i;

    {
        char found[MAX_PATH];
        if (argc > 2 && argv[2][0] != '-') {
            printf("dev(arg): %s\n", argv[2]);
            lstrcpynA(g_path, argv[2], MAX_PATH);
        } else if (find_dev(found, MAX_PATH)) {
            printf("dev: %s\n", found);
            lstrcpynA(g_path, found, MAX_PATH);
        } else {
            printf("no usbkey interface found; trying the recorded path\n");
            lstrcpynA(g_path, DEVPATH, MAX_PATH);
        }
    }
    g_dev = CreateFileA(g_path, GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
                        OPEN_EXISTING, 0, NULL);
    if (g_dev == INVALID_HANDLE_VALUE) {
        printf("open failed %lu\n", GetLastError());
        return 1;
    }
    printf("device open (sizeof SPT = %u)\n", (unsigned)sizeof(SPT));

    /* sanity: does SCSI pass-through work at all on this handle? */
    {
        UCHAR cap[8];
        memset(cap, 0, sizeof(cap));
        printf("  READ CAPACITY test:\n");
        do_spti(0x25, 0, 0, 1, cap, 8, &ret);
        printf("  cap=%02X%02X%02X%02X %02X%02X%02X%02X\n",
               cap[0],cap[1],cap[2],cap[3],cap[4],cap[5],cap[6],cap[7]);
    }

    if (!g_allow_write) {
        printf("  只读模式（未加 --write）：只做了 READ CAPACITY，不碰厂商通道。\n");
        CloseHandle(g_dev);
        return 0;
    }

    /* Follow the sequence the real app uses:
     *   write 496 -> read 5 -> write 10 @0x1F0 -> read 501 @0x1F0
     * and also the slot exchange: write 0 @4 -> read 9 @4.               */
    {
        const char *names[4] = { "real", "zero", "ff", "seq" };
        int n;
        UCHAR cmd[10];
        static UCHAR blkseq[496];
        memcpy(cmd, "\x00\x00\x10\xFA\x1A\x00\xCE\x5D\x26\x77", 10);

        for (n = 0; n < 4 && n < limit; n++) {
            char tag[64];
            UCHAR ack[5];

            memset(blk, 0, sizeof(blk));
            if (n == 0) {
                const char *src = blockfile ? blockfile : "block496.bin";
                FILE *f = fopen(src, "rb");
                if (!f) { printf("  [fatal] \u7f3a\u5c11 %s\uff0c\u62d2\u7edd\u7528\u5168\u96f6\u5757\u5199\u8bbe\u5907\n", src); return 2; }
                if (fread(blk, 1, 496, f) != 496) { fclose(f); printf("  [fatal] \u5757\u6587\u4ef6\u957f\u5ea6\u4e0d\u8db3\n"); return 2; }
                fclose(f);
                printf("  [ok] block from %s\n", src);
            }
            else if (n == 2) memset(blk, 0xFF, sizeof(blk));
            else if (n == 3) { int k; for (k = 0; k < 496; k++) blk[k] = (UCHAR)k; }
            (void)blkseq;

            sprintf(tag, "p_w_%s", names[n]); dump(dir, tag, blk, sizeof(blk));

            Sleep(200);
            do_spti(0xDD, 0x0000, 496, 0, blk, 496, &ret);
            Sleep(200);
            memset(ack, 0, sizeof(ack));
            do_spti(0xD1, 0x0000, 5, 1, ack, 5, &ret);
            sprintf(tag, "p_ack1_%s", names[n]); dump(dir, tag, ack, 5);

            do_spti(0xDD, 0x01F0, 10, 0, cmd, 10, &ret);
            memset(rep, 0, sizeof(rep));
            do_spti(0xD1, 0x01F0, 501, 1, rep, 501, &ret);
            sprintf(tag, "p_r_%s", names[n]); dump(dir, tag, rep, 501);

            {
                UCHAR none[1], slot[9];
                do_spti(0xDD, 0x0004, 0, 0, none, 0, &ret);
                memset(slot, 0, sizeof(slot));
                do_spti(0xD1, 0x0004, 9, 1, slot, 9, &ret);
                sprintf(tag, "p_slot_%s", names[n]); dump(dir, tag, slot, 9);
            }
            printf("  %s done\n", names[n]);
        }
    }

    CloseHandle(g_dev);
    printf("done\n");
    return 0;
}
