/* usbip_stub.c - export one synthetic USB mass-storage device over USB/IP.
 *
 * PSDTO3D talks to a USBKey dongle that enumerates as
 *   USBSTOR\DISK&VEN_USBKEY&PROD_USBKEYCO._&REV_2.00
 * and is driven through SCSI pass-through. Windows cannot create such a device
 * in user mode, but usbip-win2 ships a signed UDE driver (usbip2_ude) and a
 * client (usbip.exe). This program is the *server* side: it presents the USB
 * device, its descriptors, Bulk-Only Transport and the SCSI answers.
 *
 * Build:
 *   gcc -O2 -o usbip_stub.exe usbip_stub.c -lws2_32
 * Run:
 *   usbip_stub.exe [port] [image]
 * Client:
 *   "C:\Program Files\USBip\usbip.exe" attach -r 127.0.0.1 -b 1-1
 */
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

/* ------------------------------------------------------------ usbip */
#define OP_REQ_DEVLIST 0x8005
#define OP_REP_DEVLIST 0x0005
#define OP_REQ_IMPORT  0x8003
#define OP_REP_IMPORT  0x0003
#define USBIP_VERSION  0x0111
#define CMD_SUBMIT     0x00000001
#define RET_SUBMIT     0x00000003
#define HDR_LEN 48

static u16 rd16(const u8 *p) { return (u16)(p[0] | (p[1] << 8)); }
static u32 rd32(const u8 *p)
{
    return (u32)p[0] | ((u32)p[1] << 8) | ((u32)p[2] << 16) | ((u32)p[3] << 24);
}
static void wr16(u8 *p, u16 v) { p[0] = (u8)v; p[1] = (u8)(v >> 8); }
static void wr32(u8 *p, u32 v)
{
    p[0] = (u8)v; p[1] = (u8)(v >> 8); p[2] = (u8)(v >> 16); p[3] = (u8)(v >> 24);
}

static int g_verbose = 1;
static void note(const char *fmt, ...)
{
    va_list ap;
    if (!g_verbose) return;
    va_start(ap, fmt);
    vfprintf(stdout, fmt, ap);
    va_end(ap);
    fputc('\n', stdout);
    fflush(stdout);
}

/* ----------------------------------------------------- the dongle */
static const char VENDOR_ID[8]    = "USBKey  ";
static const char PRODUCT_ID[16]  = "USBKeyCo.,      ";
static const char PRODUCT_REV[4]  = "2.00";

#define SECTOR 512u

static u8 *g_image;
static u32 g_image_len;

static u8  g_blk[496];
static int g_have_blk;
static u8  g_cmd[10];
static int g_have_cmd;

/* ---- BOT state ---- */
static u32 g_tag;
static int g_stage;          /* 0 = expect CBW, 1 = data-in pending, 2 = csw */
static u8  g_dbuf[65536];
static u32 g_dlen, g_doff;
static u8  g_wbuf[65536];
static u32 g_wlen;

/* ------------------------------------------------------- descriptors */
static u8 g_dev_desc[18] = {
    18, 0x01, 0x00, 0x02,
    0, 0, 0, 64,
    0x25, 0x05, 0xA9, 0xA4,
    0x00, 0x01,
    1, 2, 3, 1
};

static u8 g_cfg_desc[] = {
    9, 0x02, 32, 0, 1, 1, 0, 0x80, 50,
    9, 0x04, 0, 0, 2, 0x08, 0x06, 0x50, 0,
    7, 0x05, 0x01, 0x02, 0x00, 0x02, 0,
    7, 0x05, 0x82, 0x02, 0x00, 0x02, 0
};

static const char *g_strs[4] = { "", "USBKey", "USBKeyCo., USB Device", "000000000001" };

static int build_string_desc(int idx, u8 *out)
{
    const char *s = (idx >= 0 && idx < 4) ? g_strs[idx] : "";
    int n = (int)strlen(s), i;
    out[0] = (u8)(2 + n * 2);
    out[1] = 0x03;
    for (i = 0; i < n; i++) { out[2 + i * 2] = (u8)s[i]; out[3 + i * 2] = 0; }
    return out[0];
}

/* usbip_usb_device = path[256] busid[32] busnum devnum speed vid pid bcd
 *                    class sub proto cfg numcfg numif  (312 bytes)      */
static void fill_dev(u8 *d)
{
    memset(d, 0, 312);
    memcpy(d, "/sys/devices/usbip_stub/1-1", 27);
    memcpy(d + 256, "1-1", 3);
    wr32(d + 288, 1);
    wr32(d + 292, 1);
    wr32(d + 296, 2);
    wr16(d + 300, 0x0525);
    wr16(d + 302, 0xA4A9);
    wr16(d + 304, 0x0001);
    d[306] = 8; d[307] = 6; d[308] = 0x50;
    d[309] = 1; d[310] = 1; d[311] = 1;
}

/* ------------------------------------------------------------- SCSI */
static void scsi_inquiry(u8 *o, u32 *n)
{
    memset(o, 0, 36);
    o[0] = 0x00; o[1] = 0x80; o[2] = 0x04; o[3] = 0x02; o[4] = 31;
    memcpy(o + 8, VENDOR_ID, 8);
    memcpy(o + 16, PRODUCT_ID, 16);
    memcpy(o + 32, PRODUCT_REV, 4);
    *n = 36;
}

static void scsi_capacity(u8 *o, u32 *n)
{
    u32 blocks = g_image_len / SECTOR;
    memset(o, 0, 8);
    wr32(o, blocks ? blocks - 1 : 0);
    wr32(o + 4, SECTOR);
    *n = 8;
}

/* vendor channel: CDB[2..3] = length, CDB[4..5] = slot address */
static void vendor_write(const u8 *cb, const u8 *buf, u32 dtl)
{
    u32 addr = (u32)cb[4] | ((u32)cb[5] << 8);
    if (dtl == 496) { memcpy(g_blk, buf, 496); g_have_blk = 1; }
    if (addr == 0x1F0 && dtl >= 8 && dtl <= 10) { memcpy(g_cmd, buf, dtl); g_have_cmd = 1; }
    note("  vendor write addr=%04X dtl=%u", addr, dtl);
}

static int vendor_read(const u8 *cb, u8 *o, u32 dtl)
{
    u32 len  = (u32)cb[2] | ((u32)cb[3] << 8);
    u32 addr = (u32)cb[4] | ((u32)cb[5] << 8);

    if (addr == 0x1F0 && dtl >= 500) {
        memset(o, 0, 501);
        memset(o, 0x7B, 16);
        if (g_have_blk) memcpy(o + 16, g_blk + 16, 480);
        o[496] = 0xFB;
        note("  vendor read 501 echo");
        return 501;
    }
    if (dtl == 5) {
        o[0] = 0xFB;
        if (len == 26 || len == 42 || len == 58 || len == 194) {
            o[1] = 0x01; o[2] = 0x00; o[3] = 0x48; o[4] = 0x01;
        } else if (len == 0) {
            o[1] = 0x2D;
        }
        note("  vendor status len=%u -> %02X", len, o[1]);
        return 5;
    }
    if (dtl == 9) {
        o[0] = 0x01; o[1] = 0xBD; o[2] = 0x0C; o[3] = 0x00;
        o[4] = 0xFB; o[5] = 0x2D;
        note("  vendor slot 9");
        return 9;
    }
    note("  vendor read unhandled dtl=%u addr=%04X", dtl, addr);
    return 0;
}

/* parse a CBW: stage the answer (data-in) or expect write data (data-out) */
static void bot_cbw(const u8 *cbw)
{
    const u8 *cb = cbw + 15;
    u8 op = cb[0];
    u32 xfer = rd32(cbw + 8);
    int dir_in = (cbw[12] & 0x80) != 0;

    g_tag = rd32(cbw + 4);
    g_doff = 0;
    g_dlen = 0;
    g_wlen = 0;
    if (xfer > sizeof(g_dbuf)) xfer = sizeof(g_dbuf);

    switch (op) {
    case 0x00:                                        /* TEST UNIT READY */
        g_stage = 2;
        break;
    case 0x12:                                        /* INQUIRY */
        scsi_inquiry(g_dbuf, &g_dlen);
        g_stage = 1;
        break;
    case 0x25:                                        /* READ CAPACITY */
        scsi_capacity(g_dbuf, &g_dlen);
        g_stage = 1;
        break;
    case 0x1A:                                        /* MODE SENSE(6) */
        memset(g_dbuf, 0, 4); g_dbuf[0] = 3;
        g_dlen = 4; g_stage = 1;
        break;
    case 0x03:                                        /* REQUEST SENSE */
        memset(g_dbuf, 0, 18); g_dlen = 18; g_stage = 1;
        break;
    case 0x28: {                                      /* READ(10) */
        u32 lba = ((u32)cb[2] << 24) | ((u32)cb[3] << 16) | ((u32)cb[4] << 8) | cb[5];
        u32 n = ((u32)cb[7] << 8) | cb[8];
        u32 off = lba * SECTOR, bytes = n * SECTOR;
        if (off + bytes <= g_image_len && bytes <= sizeof(g_dbuf)) {
            memcpy(g_dbuf, g_image + off, bytes);
            g_dlen = bytes;
        }
        g_stage = 1;
        break;
    }
    case 0x2A:                                        /* WRITE(10) */
        g_wlen = 0;
        g_stage = 1;    /* data comes as OUT URBs; CSW after them */
        g_dlen = 0;
        g_wlen = xfer;
        break;
    default:
        if (dir_in) {
            int n = vendor_read(cb, g_dbuf, xfer);
            g_dlen = (u32)(n > 0 ? n : 0);
        }
        g_stage = 1;
        break;
    }

    if (g_dlen > xfer && xfer) g_dlen = xfer;
}

static void bot_data_out(const u8 *buf, u32 len)
{
    u8 op = 0;   /* only sector writes carry data in this protocol */
    u32 off;
    (void)op;
    if (g_wlen == 0) { vendor_write(g_cmd, buf, len); return; }
    off = 0;
    if (off + len <= g_image_len) memcpy(g_image + off, buf, len);
    g_wlen = 0;
}

/* -------------------------------------------------------------- net */
static int send_all(SOCKET s, const void *b, int len)
{
    const char *p = (const char *)b;
    while (len > 0) {
        int n = send(s, p, len, 0);
        if (n <= 0) return -1;
        p += n; len -= n;
    }
    return 0;
}

static int recv_all(SOCKET s, void *b, int len)
{
    char *p = (char *)b;
    while (len > 0) {
        int n = recv(s, p, len, 0);
        if (n <= 0) return -1;
        p += n; len -= n;
    }
    return 0;
}

static void serve(SOCKET cli)
{
    u8 hdr[HDR_LEN];
    u8 out[65536];

    for (;;) {
        u8 opc[8];
        u32 code;
        if (recv_all(cli, opc, 8) != 0) return;
        code = rd16(opc + 2);

        if (code == OP_REQ_DEVLIST) {
            u8 rep[8 + 4 + 312];
            memset(rep, 0, sizeof(rep));
            wr16(rep, USBIP_VERSION);
            wr16(rep + 2, OP_REP_DEVLIST);
            wr32(rep + 4, 0);
            wr32(rep + 8, 1);
            fill_dev(rep + 12);
            if (send_all(cli, rep, sizeof(rep)) != 0) return;
            note("devlist sent");
            continue;
        }
        if (code == OP_REQ_IMPORT) {
            u8 busid[32];
            u8 rep[8 + 312];
            memset(busid, 0, sizeof(busid));
            if (recv_all(cli, busid, 32) != 0) return;
            note("import %s", busid);
            memset(rep, 0, sizeof(rep));
            wr16(rep, USBIP_VERSION);
            wr16(rep + 2, OP_REP_IMPORT);
            wr32(rep + 4, 0);
            fill_dev(rep + 8);
            if (send_all(cli, rep, sizeof(rep)) != 0) return;
            note("imported");
            break;
        }
        note("unexpected op %04X", code);
        return;
    }

    for (;;) {
        u32 cmd, dir, ep, len, outlen = 0;
        u8 epnum;
        if (recv_all(cli, hdr, HDR_LEN) != 0) return;
        cmd = rd32(hdr);
        dir = rd32(hdr + 12);
        ep  = rd32(hdr + 16);
        len = rd32(hdr + 24);
        epnum = (u8)(ep & 0x7F);
        if (cmd != CMD_SUBMIT) continue;
        if (len > sizeof(out)) len = sizeof(out);

        memset(out, 0, sizeof(out));

        if (epnum == 0) {                                  /* control */
            const u8 *setup = hdr + 40;
            u8 bm = setup[0], br = setup[1];
            u16 wv = rd16(setup + 2);
            u32 wl = rd16(setup + 6);
            if (br == 6 && (bm & 0x60) == 0) {
                u8 type = (u8)(wv >> 8), idx = (u8)wv;
                if (type == 1) { memcpy(out, g_dev_desc, 18); outlen = 18; }
                else if (type == 2) { memcpy(out, g_cfg_desc, sizeof(g_cfg_desc)); outlen = sizeof(g_cfg_desc); }
                else if (type == 3) outlen = (u32)build_string_desc(idx, out);
                if (wl < outlen) outlen = wl;
            } else if ((bm & 0x60) == 0x20 && br == 0xFE) {
                out[0] = 0; outlen = 1;
                if (wl < 1) outlen = wl;
            }
        } else if (dir == 0) {                             /* bulk IN */
            if (g_stage == 1 && g_doff < g_dlen) {
                u32 n = g_dlen - g_doff;
                if (n > len) n = len;
                memcpy(out, g_dbuf + g_doff, n);
                g_doff += n;
                outlen = n;
                if (g_doff >= g_dlen) g_stage = 2;
            } else if (g_stage == 2 || g_stage == 0) {
                u8 csw[13];
                wr32(csw, 0x53425355u);
                wr32(csw + 4, g_tag);
                wr32(csw + 8, g_dlen > g_doff ? g_dlen - g_doff : 0);
                csw[12] = 0;
                memcpy(out, csw, 13);
                outlen = 13;
                g_stage = 0;
                g_dlen = g_doff = 0;
            }
        } else {                                           /* bulk OUT */
            if (len) {
                if (recv_all(cli, out, (int)len) != 0) return;
            }
            if (len >= 31 && rd32(out) == 0x43425355u) bot_cbw(out);
            else if (len) bot_data_out(out, len);
            outlen = 0;
        }

        wr32(hdr + 0, RET_SUBMIT);
        wr32(hdr + 20, 0);
        wr32(hdr + 24, outlen);
        if (send_all(cli, hdr, HDR_LEN) != 0) return;
        if (outlen) { if (send_all(cli, out, (int)outlen) != 0) return; }
    }
}

int main(int argc, char **argv)
{
    WSADATA wsa;
    SOCKET srv;
    struct sockaddr_in a;
    int port = (argc > 1) ? atoi(argv[1]) : 3240;
    const char *img = (argc > 2) ? argv[2] : "dongle/phys1.bin";
    FILE *f;

    setvbuf(stdout, NULL, _IONBF, 0);

    f = fopen(img, "rb");
    if (!f) { printf("cannot open %s\n", img); return 1; }
    fseek(f, 0, SEEK_END); g_image_len = (u32)ftell(f); fseek(f, 0, SEEK_SET);
    g_image = (u8 *)calloc(1, g_image_len);
    if (!g_image || fread(g_image, 1, g_image_len, f) != g_image_len) { printf("read fail\n"); return 1; }
    fclose(f);
    note("image %s %u bytes", img, g_image_len);

    WSAStartup(MAKEWORD(2, 2), &wsa);
    srv = socket(AF_INET, SOCK_STREAM, 0);
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_addr.s_addr = inet_addr("127.0.0.1");
    a.sin_port = htons((u16)port);
    if (bind(srv, (struct sockaddr *)&a, sizeof(a)) != 0) { printf("bind %d\n", WSAGetLastError()); return 1; }
    listen(srv, 4);
    note("listening 127.0.0.1:%d", port);

    for (;;) {
        SOCKET cli = accept(srv, NULL, NULL);
        if (cli == INVALID_SOCKET) break;
        note("client in");
        serve(cli);
        closesocket(cli);
        note("client out");
    }
    return 0;
}
