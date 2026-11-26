/* 伪造加密狗设备：让 SetupAPI 枚举出一个 USBKey 磁盘接口，
 * 再把 CreateFileA / DeviceIoControl 接住，用记录下来的 SCSI 应答回答。
 *
 * 依据：exe 只导入了 4 个 SetupAPI 函数（GetClassDevs / EnumDeviceInterfaces /
 * GetDeviceInterfaceDetail / DestroyDeviceInfoList），正好是枚举"磁盘接口类"
 * 的完整组合；带狗时它拿到的路径是
 *   \\?\usbstor#disk&ven_usbkey&prod_usbkeyco._&rev_2.00#...#{53f56307-...}
 * 这个 GUID 就是 GUID_DEVINTERFACE_DISK。而设备是普通 U 盘（USBSTOR），
 * 没有任何厂商驱动，所以整条链都能在用户态仿出来。
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include "dongle_table.h"
#include "dongle_mem.h"
#include "dongle_blobs.h"
#include "echo_blobs.h"
#include "echo_diff.h"

/* ---- 协议状态（由真实会话推导，见 tools/scsi_layout.py） ----
 * 程序先 write(addr=0, 496, 自己的内存块)，再 write(addr=0x1F0, 10, 命令)，
 * 然后 read(addr=0x1F0, 501)：
 *   · 命令键 ∈ K_ECHO_KEYS（后 4 字节是 0x77xxxxxx 代码指针）→ 回显刚写的块：
 *         16×(7B 00 00 00) + 块[16:496](480B) + FB 00 00 00 00
 *   · 命令键 ∈ K_DATA_KEYS（后 4 字节是栈指针）→ 返回该命令固定的 501 字节参数块
 * 回放式仿真返回的是"别人进程里的内存"，exe 一比对就发现不对，后面的状态全乱——
 * 这就是无狗时 +0x2C 变脏、渲染解引用空的根因。
 */
static unsigned char g_blk496[496];
static unsigned char g_cmd10[10];
static int g_have_blk, g_have_cmd;

static int key_is_echo(unsigned k)
{
    unsigned i;
    for (i = 0; i < K_ECHO_COUNT; i++) if (K_ECHO_KEYS[i] == k) return 1;
    return 0;
}

/* 十六进制转储（只给日志用） */
static const char *hexstr(const void *p, unsigned n)
{
    static char buf[128];
    const unsigned char *b = (const unsigned char *)p;
    unsigned i, k = 0;
    if (!p || IsBadReadPtr(p, n ? n : 1)) return "<unmapped>";
    for (i = 0; i < n && k < 110; i++) {
        static const char hx[] = "0123456789ABCDEF";
        buf[k++] = hx[b[i] >> 4];
        buf[k++] = hx[b[i] & 15];
        if (i + 1 < n) buf[k++] = ' ';
    }
    buf[k] = 0;
    return buf;
}

static const unsigned char *key_data_blob(unsigned k)
{
    unsigned i;
    for (i = 0; i < K_DATA_COUNT; i++) if (K_DATA_KEYS[i] == k) return K_DATA_BLOBS[i];
    return 0;
}

/* mingw32 没有 setupapi.h，这几个结构自己声明（32 位布局） */
typedef HANDLE HDEVINFO_;
typedef struct {
    DWORD cbSize;
    GUID  InterfaceClassGuid;
    DWORD Flags;
    DWORD Reserved;
} SP_IFACE_DATA;
typedef struct {
    DWORD cbSize;
    GUID  ClassGuid;
    DWORD DevInst;
    DWORD Reserved;
} SP_DEINFO_DATA;
typedef struct {
    DWORD cbSize;
    char  DevicePath[1];
} SP_IFACE_DETAIL_A;
#define SPINT_ACTIVE 1
#ifndef ERROR_NO_MORE_ITEMS
#define ERROR_NO_MORE_ITEMS 259
#endif

#define RVA_CREATEFILE_A   0x1242BC
#define RVA_CREATEFILE_A2  0x1244AC
#define RVA_DEVICEIOCTL    0x12449C
#define RVA_SETUP_GETCLS   0x124A60
#define RVA_SETUP_ENUM     0x124A5C
#define RVA_SETUP_DETAIL   0x124A58
#define RVA_SETUP_DESTROY  0x124A54
#define RVA_GETVOLINFO     0x1243E8
#define RVA_GETDRVSTR      0x124428
#define RVA_GETDRVTYPE     0x124448
#define RVA_GETFREESPACE   0x12444C
#define RVA_DLG_SAVE       0x1249F0
#define RVA_DLG_OPEN       0x1249F4

static const unsigned char K_DISK_GUID[16] = {
    0x07, 0x63, 0xF5, 0x53, 0xBF, 0xB6, 0xD0, 0x11,
    0x94, 0xF2, 0x00, 0xA0, 0xC9, 0x1E, 0xFB, 0x8B
};

typedef HANDLE (WINAPI *PF_CreateFileA)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES,
                                        DWORD, DWORD, HANDLE);
typedef BOOL (WINAPI *PF_DeviceIoControl)(HANDLE, DWORD, LPVOID, DWORD, LPVOID,
                                          DWORD, LPDWORD, LPOVERLAPPED);
typedef HDEVINFO_ (WINAPI *PF_GetClassDevsA)(const GUID *, PCSTR, HWND, DWORD);
typedef BOOL (WINAPI *PF_EnumDevIface)(HDEVINFO_, SP_DEINFO_DATA *, const GUID *,
                                       DWORD, SP_IFACE_DATA *);
typedef BOOL (WINAPI *PF_GetDetailA)(HDEVINFO_, SP_IFACE_DATA *,
                                     SP_IFACE_DETAIL_A *, DWORD,
                                     DWORD *, SP_DEINFO_DATA *);
typedef BOOL (WINAPI *PF_DestroyList)(HDEVINFO_);

static PF_CreateFileA     o_cfa;
static PF_DeviceIoControl o_dio;
static PF_GetClassDevsA   o_gcd;
static PF_EnumDevIface    o_enum;
static PF_GetDetailA      o_det;
static PF_DestroyList     o_dest;

static HANDLE             g_devs[8];
static int                g_ndev;
static unsigned char      g_rec[501];
static unsigned           g_rec_len;
static unsigned char      g_ack[5] = { 0xFB, 0x00, 0x00, 0x00, 0x00 };
static volatile LONG      g_done;
static char               g_dir[MAX_PATH];
static char               g_log[MAX_PATH];

#define FAKE_HANDLE ((HDEVINFO_)0x0DEC0DE1)
static const char K_PATH[] =
    "\\\\?\\usbstor#disk&ven_usbkey&prod_usbkeyco._&rev_2.00#3&3ad7ba7f&0"
    "#{53f56307-b6bf-11d0-94f2-00a0c91efb8b}";

static FILE *LF(void)
{
    if (!g_log[0]) { lstrcpyA(g_log, g_dir); lstrcatA(g_log, "_dongle.log"); }
    return fopen(g_log, "a");
}

static void note(const char *fmt, ...)
{
    FILE *f = LF();
    va_list ap;
    if (!f) return;
    va_start(ap, fmt);
    vfprintf(f, fmt, ap);
    va_end(ap);
    fputc('\n', f);
    fclose(f);
}

static int is_disk_guid(const GUID *g)
{
    if (!g) return 0;
    return memcmp(g, K_DISK_GUID, 16) == 0;
}

static const char *strstri_(const char *h, const char *nd)
{
    size_t ln;
    if (!h || !nd) return NULL;
    ln = strlen(nd);
    for (; *h; h++) if (!_strnicmp(h, nd, ln)) return h;
    return NULL;
}

static int is_fake_path(const char *n)
{
    return n && (strstri_(n, "ven_usbkey") || strstri_(n, "usbstor"));
}

static int is_driver_path(const char *n)
{
    return n && strstri_(n, "MyUSBKey");
}

/* ---------------- SetupAPI 伪造 ---------------- */

static HDEVINFO_ WINAPI h_gcd(const GUID *cls, PCSTR enumr, HWND parent, DWORD flags)
{
    {
        char env[8];
        /* 默认走真设备；只有显式 FAKE_DEV=1 才伪造 */
        if (!GetEnvironmentVariableA("FAKE_DEV", env, sizeof(env)))
            return o_gcd ? o_gcd(cls, enumr, parent, flags) : (HDEVINFO_)INVALID_HANDLE_VALUE;
    }
    if (cls) {
        const unsigned char *g = (const unsigned char *)cls;
        note("GetClassDevs guid=%02X%02X%02X%02X-%02X%02X-%02X%02X-%02X%02X-%02X%02X%02X%02X%02X%02X en=%s flags=0x%X",
             g[0],g[1],g[2],g[3],g[4],g[5],g[6],g[7],g[8],g[9],g[10],g[11],g[12],g[13],g[14],g[15],
             enumr ? enumr : "(null)", flags);
    } else {
        note("GetClassDevs guid=NULL");
    }
    if (is_disk_guid(cls)) {
        note("SETUP GetClassDevs(disks) -> 伪造句柄");
        return FAKE_HANDLE;
    }
    return o_gcd ? o_gcd(cls, enumr, parent, flags) : (HDEVINFO_)INVALID_HANDLE_VALUE;
}

static BOOL WINAPI h_enum(HDEVINFO_ devs, SP_DEINFO_DATA *dinfo, const GUID *cls,
                          DWORD idx, SP_IFACE_DATA *ifd)
{
    if (devs == FAKE_HANDLE) {
        if (idx > 0) { SetLastError(ERROR_NO_MORE_ITEMS); return FALSE; }
        if (ifd && ifd->cbSize >= sizeof(SP_IFACE_DATA)) {
            ifd->Flags = SPINT_ACTIVE;
            memcpy(&ifd->InterfaceClassGuid, K_DISK_GUID, 16);
            ifd->Reserved = 0;
        }
        note("SETUP EnumDeviceInterfaces(0) -> TRUE");
        return TRUE;
    }
    return o_enum ? o_enum(devs, dinfo, cls, idx, ifd) : FALSE;
}

static BOOL WINAPI h_det(HDEVINFO_ devs, SP_IFACE_DATA *ifd,
                         SP_IFACE_DETAIL_A *det, DWORD size,
                         DWORD *needed, SP_DEINFO_DATA *dinfo)
{
    if (devs == FAKE_HANDLE) {
        DWORD req = (DWORD)(sizeof(DWORD) + strlen(K_PATH) + 1);
        if (needed) *needed = req;
        if (det) {
            if (size < req) { SetLastError(ERROR_INSUFFICIENT_BUFFER); return FALSE; }
            det->cbSize = sizeof(DWORD) + 1;
            lstrcpyA(det->DevicePath, K_PATH);
            if (dinfo && dinfo->cbSize >= sizeof(SP_DEINFO_DATA)) {
                memcpy(&dinfo->ClassGuid, K_DISK_GUID, 16);
                dinfo->DevInst = 1;
                dinfo->Reserved = 0;
            }
            note("SETUP GetDeviceInterfaceDetail -> %s", K_PATH);
            return TRUE;
        }
        SetLastError(ERROR_INSUFFICIENT_BUFFER);
        return FALSE;
    }
    return o_det ? o_det(devs, ifd, det, size, needed, dinfo) : FALSE;
}

static BOOL WINAPI h_dest(HDEVINFO_ devs)
{
    if (devs == FAKE_HANDLE) { note("SETUP DestroyDeviceInfoList(fake)"); return TRUE; }
    return o_dest ? o_dest(devs) : FALSE;
}

/* ---------------- 设备句柄 ---------------- */

static HANDLE WINAPI h_cfa(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                           DWORD disp, DWORD flags, HANDLE tmpl)
{
#ifdef SCSI_LOG_ONLY
    /* 探针模式：绝不改写路径，保证真狗被真正打开 */
    {
        HANDLE h = o_cfa(name, acc, share, sa, disp, flags, tmpl);
        if (is_fake_path(name)) {
            if (g_ndev < 8) g_devs[g_ndev++] = h;
            note("LOG 打开真设备 %s -> %p", name, h);
        }
        return h;
    }
#endif
    if (is_fake_path(name)) {
        char p[MAX_PATH];
        char env[8];
        if (GetEnvironmentVariableA("DENY_DEV", env, sizeof(env))) {
            note("DENY_DEV: 拒绝打开设备 %s", name);
            SetLastError(ERROR_FILE_NOT_FOUND);
            return INVALID_HANDLE_VALUE;
        }
        HANDLE h;
        lstrcpyA(p, g_dir);
        lstrcatA(p, "_dongle_dev.bin");
        h = CreateFileA(p, GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, 0, 0);
        if (h == INVALID_HANDLE_VALUE) {
            h = CreateFileA(p, GENERIC_READ | GENERIC_WRITE,
                            FILE_SHARE_READ | FILE_SHARE_WRITE, 0, CREATE_ALWAYS, 0, 0);
        }
        if (h != INVALID_HANDLE_VALUE && g_ndev < 8) g_devs[g_ndev++] = h;
        note("设备打开 %s -> %p (共 %d)", name, h, g_ndev);
        return h;
    }
    if (is_driver_path(name)) {
        static int ndrv;
        if (ndrv < 3) { ndrv++; note("探测驱动通道 %s -> 让它失败", name); }
        SetLastError(ERROR_FILE_NOT_FOUND);
        return INVALID_HANDLE_VALUE;
    }
    if (name && name[0] == 92) note("DEV-PATH %s", name);
    if (name && strstri_(name, ".gjs") && (acc & 0x40000000)) {
        void *ra = __builtin_return_address(0);
        HMODULE hm; char mod[MAX_PATH];
        if (GetModuleHandleExA(0x4, (LPCSTR)ra, &hm)) {
            GetModuleFileNameA(hm, mod, MAX_PATH);
            note("GJS-WRITE %s  <- %s+0x%X", name, mod,
                 (unsigned)ra - (unsigned)(UINT_PTR)hm);
        }
    }
    {
        static char seen[80][160];
        static int nseen;
        int i;
        for (i = 0; i < nseen; i++) if (!lstrcmpiA(seen[i], name)) break;
        if (i == nseen && nseen < 80 && name) {
            lstrcpynA(seen[nseen], name, 160); nseen++;
            note("cfa %s", name);
        }
    }
    return o_cfa(name, acc, share, sa, disp, flags, tmpl);
}

static SLOT *find_slot(unsigned addr, unsigned dtl)
{
    int i, last = -1;
    for (i = 0; i < K_SLOT_COUNT; i++) {
        SLOT *t = &K_SLOTS[i];
        if (t->len == 0 || t->addr != addr || t->len + 5 != dtl) continue;
        last = i;
        if (!t->used) { t->used = 1; return t; }
    }
    return last >= 0 ? &K_SLOTS[last] : NULL;
}

static void fillbuf(void *dst, const unsigned char *src, unsigned n, unsigned want)
{
    unsigned i;
    for (i = 0; i < n && i < want; i++) ((unsigned char *)dst)[i] = src[i];
    for (; i < want; i++) ((unsigned char *)dst)[i] = 0;
}

/* per-handle written block: the device echoes the block written on the same handle */
typedef struct { HANDLE h; unsigned char blk[496]; int have; } BLKSLOT;
static BLKSLOT g_blk_h[8];
static BLKSLOT *blk_slot(HANDLE h, int create)
{
    int i, free_i = -1;
    for (i = 0; i < 8; i++) {
        if (g_blk_h[i].have && g_blk_h[i].h == h) return &g_blk_h[i];
        if (!g_blk_h[i].have && free_i < 0) free_i = i;
    }
    if (!create) return NULL;
    if (free_i < 0) free_i = 0;
    g_blk_h[free_i].h = h; g_blk_h[free_i].have = 1;
    return &g_blk_h[free_i];
}
static const unsigned char *blk_cur(HANDLE h)
{
    BLKSLOT *s = blk_slot(h, 0);
    return s ? s->blk : g_blk496;
}

static BOOL WINAPI h_dio(HANDLE h, DWORD code, LPVOID in, DWORD inlen, LPVOID out,
                         DWORD outlen, LPDWORD ret, LPOVERLAPPED ov)
{
    unsigned char *p = (unsigned char *)in;

    {
        int i, isdev = 0;
        for (i = 0; i < g_ndev; i++) if (g_devs[i] == h) { isdev = 1; break; }
        if (!isdev) return o_dio(h, code, in, inlen, out, outlen, ret, ov);
    }

#ifdef SCSI_LOG_ONLY
    /* 探针模式：原样转给真狗，只把请求/应答记下来（用来录一份完整基准会话） */
    {
        BOOL r = o_dio(h, code, in, inlen, out, outlen, ret, ov);
        if (in && inlen >= 0x2C && *(unsigned short *)in == 0x002C) {
            unsigned char *q = (unsigned char *)in;
            unsigned op = q[28];
            unsigned len = q[30] | (q[31] << 8);
            unsigned addr = q[32] | (q[33] << 8);
            unsigned dtl = *(unsigned *)&q[12];
            void *dbuf = *(void **)&q[20];
            note("SPT %s", hexstr(in, 20));
            note("SPT %s", hexstr((const char *)in + 20, 24));
            if (op == 0xDD) {
                if (dbuf && dtl >= 16) {
                    static int wn;
                    char wp[MAX_PATH]; FILE *wf;
                    lstrcpyA(wp, g_dir);
                    wsprintfA(wp + lstrlenA(wp), "_w_%02d_%u.bin", wn++, dtl);
                    wf = fopen(wp, "wb");
                    if (wf) { fwrite(dbuf, 1, dtl, wf); fclose(wf); }
                }
                note("LOG 写 addr=%04X len=%u dtl=%u data=%s", addr, len, dtl,
                     hexstr(dbuf, dtl > 24 ? 24 : dtl));
                            if (addr == 0x1F0 && dbuf && dtl >= 8) {
                    unsigned cn = dtl > 10 ? 10 : dtl;
                    memcpy(g_cmd10, dbuf, cn);
                }
            } else if (op == 0xD1) {
                /* dump full reply so the replayer can be byte-exact */
                if (dtl >= 64 && dbuf) {
                    static int dn;
                    char fp[MAX_PATH]; FILE *ff;
                    lstrcpyA(fp, g_dir);
                    wsprintfA(fp + lstrlenA(fp), "_resp_%02d_%u_%02X%02X%02X%02X.bin", dn++, dtl,
                          g_cmd10[0], g_cmd10[1], g_cmd10[2], g_cmd10[3]);
                    ff = fopen(fp, "wb");
                    if (ff) { fwrite(dbuf, 1, dtl, ff); fclose(ff); }
                }
                note("LOG 读 addr=%04X dtl=%u ret=%u data=%s", addr, dtl,
                     ret ? *ret : 0, hexstr(dbuf, dtl > 24 ? 24 : dtl));
            } else {
                note("LOG 其它 op=%02X addr=%04X", op, addr);
            }
        }
        return r;
    }
#endif

    /* 磁盘类的常规查询：给个合理答复，别让程序在这里放弃 */
    if (code == 0x00070000 && out && outlen >= 24) {
        unsigned *q = (unsigned *)out;
        memset(out, 0, outlen);
        q[0] = 1049088; q[1] = 0;
        q[2] = 0; q[3] = 1; q[4] = 16; q[5] = 512;
        if (ret) *ret = 24;
        note("磁盘几何查询 -> 已答复");
        return TRUE;
    }
    if (code == 0x2D1080 && out && outlen >= 12) {
        memset(out, 0, outlen);
        ((unsigned *)out)[0] = 1;
        if (ret) *ret = 12;
        note("设备号查询 -> 已答复");
        return TRUE;
    }

    /* 厂商私有通道：CDB[2..3]=长度, CDB[4..5]=槽位地址 */
    if (in && inlen >= 0x2C && *(unsigned short *)in == 0x002C) {
        unsigned char op = p[28];
        unsigned len = p[30] | (p[31] << 8);
        unsigned addr = p[32] | (p[33] << 8);
        unsigned dtl = *(unsigned *)&p[12];
        void *dbuf = *(void **)&p[20];
        SLOT *s;
        p[2] = 0;
        if (ret) *ret = 0x2C;
        if (!dbuf || IsBadWritePtr(dbuf, dtl ? dtl : 1)) return TRUE;

        {
            char env[8];
            if (GetEnvironmentVariableA("GARBAGE_DEV", env, sizeof(env))) {
                memset(dbuf, 0xAA, dtl ? dtl : 1);
                note("GARBAGE_DEV: 返回垃圾");
                return TRUE;
            }
        }
        if (op == 0xDD) {                        /* 写 */
            { static int ewn; char ep[MAX_PATH]; FILE *ef;
              lstrcpyA(ep, g_dir);
              wsprintfA(ep + lstrlenA(ep), "_ew_%02d_%u.bin", ewn++, dtl);
              ef = fopen(ep, "wb");
              if (ef) { if (dbuf && dtl) fwrite(dbuf, 1, dtl, ef); fclose(ef); } }
            if (dtl == 496) {
                { BLKSLOT *bs = blk_slot(h, 1);
                  memcpy(bs->blk, dbuf, 496);
                  memcpy(g_blk496, dbuf, 496); }
                g_have_blk = 1;
            }
            if (addr == 0x1F0 && dtl == 10) {
                memcpy(g_cmd10, dbuf, 10);
                g_have_cmd = 1;
                note("SCSI 命令 = %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X",
                     g_cmd10[0], g_cmd10[1], g_cmd10[2], g_cmd10[3], g_cmd10[4],
                     g_cmd10[5], g_cmd10[6], g_cmd10[7], g_cmd10[8], g_cmd10[9]);
            }
            if (dtl == 26 || dtl == 42 || dtl == 58 || dtl == 194) memcpy(g_ack, "\xFB\x01\x00\x48\x01", 5);
            else if (dtl == 0)             memcpy(g_ack, "\xFB\x2D\x00\x00\x00", 5);
            else                           memcpy(g_ack, "\xFB\x00\x00\x00\x00", 5);
            note("SCSI 写 addr=%04X len=%u dtl=%u", addr, len, dtl);
            return TRUE;
        }
        if (op == 0xD1) {                        /* 读 */
            {
                int kb;
                for (kb = 0; kb < K_ECHO_BY_KEY_N; kb++) {
                    if (addr == 0x1F0 && dtl >= 501 && g_have_blk &&
                        *(unsigned *)blk_cur(h) == 2u &&
                        K_ECHO_BY_KEY[kb].key == 0x3EF30000u) {
                        /* base: echo the current write, then overlay the device bytes */
                        memset(dbuf, 0, 501);
                        if (g_have_blk) memcpy(dbuf, blk_cur(h), 496);
                        memcpy((char *)dbuf + 496, "\xFB\x00\x00\x00\x00", 5);
                        { int kd; for (kd = 0; kd < K_ECHO_DIFF_N; kd++) {
                            if (K_ECHO_DIFF[kd].key != *(unsigned *)g_cmd10) continue;
                            { int t2; for (t2 = 0; t2 < K_ECHO_DIFF[kd].n; t2++)
                                ((unsigned char *)dbuf)[K_ECHO_DIFF[kd].off[t2]] = K_ECHO_DIFF[kd].val[t2]; }
                        } }
                        { static int on; char op2[MAX_PATH]; FILE *of;
                          lstrcpyA(op2, g_dir);
                          wsprintfA(op2 + lstrlenA(op2), "_ov_%02d_%08X.bin", on++, K_ECHO_BY_KEY[kb].key);
                          of = fopen(op2, "wb");
                          if (of) { fwrite(dbuf, 1, 501, of); fclose(of); } }
                        note("overlay blob %08X", K_ECHO_BY_KEY[kb].key);
                        return TRUE;
                    }
                }
            }
            /* 501 字节块：按命令**结构**分类（不能按固定 4 字节，里面混着每次都变的栈地址）
             *   命令布局：len(2) | ptr1(4) | ptr2(4)
             *   ptr2 落在代码段（>= 0x00400000）→ 回显型
             *   ptr2 落在栈上（小地址）        → 参数型，按 len 选块
             */
            if (addr == 0x1F0 && dtl == 501 && g_have_cmd) {
                unsigned len2 = g_cmd10[0] | (g_cmd10[1] << 8);
                unsigned p2 = *(unsigned *)(g_cmd10 + 6);
                /* 计算型优先判定：cmd[6..7]=D5 0F 是层数查询（带狗实测，ptr2 落在栈上）
                 * 必须在"回显型"分支之前拦下，否则永远走不到。 */
                if (g_cmd10[6] == 0xD5 && g_cmd10[7] == 0x0F && g_have_blk) {
                    int i;
                    memset(dbuf, 0, 501);
                    for (i = 0; i < 4; i++) ((unsigned *)dbuf)[i] = 0x7B;
                    memcpy((char *)dbuf + 16, blk_cur(h) + 16, 480);
                    memcpy((char *)dbuf + 496, "\xFB\x00\x00\x00\x00", 5);
                    /* 前 16 字节按带狗实测：write[0..2] 原样，write[3] 置 0 */
                    memcpy((char *)dbuf + 16, g_blk496, 12);
                    *(unsigned *)((char *)dbuf + 16 + 12) = 0;
                    {
                        /* 层数：带狗实测 resp16 = write[2]（=32）、resp20 = 层数-1（=31） */
                        unsigned n = *(unsigned *)(blk_cur(h) + 8);
                        *(unsigned *)((char *)dbuf + 16 + 16) = n;
                        *(unsigned *)((char *)dbuf + 16 + 20) = n ? n - 1 : 0;
                        note("计算型 层数查询：n=%u → resp16=%u resp20=%u", n, n, n ? n - 1 : 0);
                    }
                    return TRUE;
                }
                if (p2 >= 0x00400000u && g_have_blk) {
                    int i;
                    memset(dbuf, 0, 501);
                    for (i = 0; i < 4; i++) ((unsigned *)dbuf)[i] = 0x7B;
                    memcpy((char *)dbuf + 16, blk_cur(h) + 16, 480);
                    memcpy((char *)dbuf + 496, "\xFB\x00\x00\x00\x00", 5);
                    { static int en; char fp[MAX_PATH]; FILE *ff;
                      lstrcpyA(fp, g_dir);
                      wsprintfA(fp + lstrlenA(fp), "_resp_echo_%02d_501.bin", en++);
                      ff = fopen(fp, "wb");
                      if (ff) { fwrite(dbuf, 1, 501, ff); fclose(ff); }
                      note("DUMP echo reply -> %s", fp); }
                    /* ---- 计算型应答：按带狗实测的 (命令 → 应答前24字节) 精确覆盖 ---- */
                    {
                        int q, hit = -1;
                        for (q = 0; q < K_RESP_N; q++) {
                            unsigned char want[10];
                            int t;
                            for (t = 0; t < 10; t++) {
                                char hx[3] = { K_RESP_HEADS[q][t * 2], K_RESP_HEADS[q][t * 2 + 1], 0 };
                                want[t] = (unsigned char)strtoul(hx, 0, 16);
                            }
                            if (!memcmp(want, g_cmd10, 10)) { hit = q; break; }
                        }
                        if (hit >= 0 && GetEnvironmentVariableA("RESP_OVERRIDE", (char[8]){0}, 8)) {
                            const char *src = K_RESP_HEADS[hit] + 21;   /* 跳过 "cmd(20) " */
                            int t;
                            for (t = 0; t < 24; t++) {
                                char hx[3] = { src[t * 2], src[t * 2 + 1], 0 };
                                ((unsigned char *)dbuf)[16 + t] = (unsigned char)strtoul(hx, 0, 16);
                            }
                            note("实测应答覆盖 #%d（cmd=%02X %02X %02X %02X）",
                                 hit, g_cmd10[0], g_cmd10[1], g_cmd10[2], g_cmd10[3]);
                        }
                    }
                    note("SCSI 读 回显型501 len=%u p2=%08X（16头+480块+5尾）", len2, p2);
                    return TRUE;
                }
                {
                    int kb;
                    for (kb = 0; kb < K_ECHO_BY_KEY_N; kb++) {
                        if (K_ECHO_BY_KEY[kb].key == *(unsigned *)g_cmd10) {
                            memcpy(dbuf, K_ECHO_BY_KEY[kb].data, 501);
                            note("keyed blob hit %08X", K_ECHO_BY_KEY[kb].key);
                            return TRUE;
                        }
                    }
                }
                {
                    const unsigned char *blob = 0;
                    unsigned i;
                    for (i = 0; i < K_DATA_COUNT; i++) {
                        if (K_DATA_KEYS[i] == *(unsigned *)g_cmd10) { blob = K_DATA_BLOBS[i]; break; }
                    }
                    if (!blob) blob = (len2 == 0) ? K_DATA_BLOBS[0] : K_DATA_BLOBS[1 % K_DATA_COUNT];
                    if (blob) {
                        memcpy(dbuf, blob, 501);
                        note("SCSI 读 参数型501 len=%u p2=%08X（按结构选块）", len2, p2);
                        return TRUE;
                    }
                }
                note("SCSI 读 501 无法分类 len=%u p2=%08X → 回退录制表", len2, p2);
            }
            s = find_slot(addr, dtl);
            if (s) {
                memcpy(dbuf, s->data, s->len);
                memcpy((char *)dbuf + s->len, s->st, 5);
                note("SCSI 读 槽位 addr=%04X dtl=%u len=%u", addr, dtl, s->len);
                return TRUE;
            }
            if (dtl == 5) {
                memcpy(dbuf, g_ack, 5);
                note("SCSI 读 状态 addr=%04X ack=%02X%02X", addr, g_ack[0], g_ack[1]);
                return TRUE;
            }
            memset(dbuf, 0, dtl);
            memcpy((char *)dbuf + dtl - 5, "\xFB\x00\x00\x00\x00", 5);
            note("SCSI 读 未知 addr=%04X len=%u dtl=%u", addr, len, dtl);
            return TRUE;
        }
        note("SCSI 其它 op=%02X addr=%04X len=%u dtl=%u", op, addr, len, dtl);
        return TRUE;
    }
    note("ioctl 未知 code=0x%08X inlen=%u outlen=%u", code, inlen, outlen);
    if (out && outlen) memset(out, 0, outlen);
    if (ret) *ret = 0;
    return TRUE;
}

/* ---- 盘符类 API 只做记录 ---- */
static DWORD (WINAPI *o_drvstr)(DWORD, LPSTR);
static UINT  (WINAPI *o_drvtype)(LPCSTR);
static BOOL  (WINAPI *o_volinfo)(LPCSTR, LPSTR, DWORD, DWORD *, DWORD *, DWORD *, LPSTR, DWORD);
static BOOL  (WINAPI *o_freesp)(LPCSTR, DWORD *, DWORD *, DWORD *, DWORD *);

static DWORD WINAPI h_drvstr(DWORD n, LPSTR buf)
{
    DWORD r = o_drvstr ? o_drvstr(n, buf) : 0;
    note("GetLogicalDriveStrings -> %lu [%s]", r, buf ? buf : "");
    return r;
}

static UINT WINAPI h_drvtype(LPCSTR root)
{
    UINT r = o_drvtype ? o_drvtype(root) : 0;
    note("GetDriveType(%s) -> %u", root ? root : "(null)", r);
    return r;
}

static BOOL WINAPI h_volinfo(LPCSTR root, LPSTR name, DWORD nname, DWORD *serial,
                             DWORD *maxlen, DWORD *flags, LPSTR fs, DWORD nfs)
{
    BOOL r = o_volinfo ? o_volinfo(root, name, nname, serial, maxlen, flags, fs, nfs) : FALSE;
    note("GetVolumeInformation(%s) -> %d label=%s serial=%08X",
         root ? root : "(null)", r, (name && r) ? name : "", (serial && r) ? *serial : 0);
    return r;
}

static BOOL WINAPI h_freesp(LPCSTR root, DWORD *a, DWORD *b, DWORD *c, DWORD *d)
{
    BOOL r = o_freesp ? o_freesp(root, a, b, c, d) : FALSE;
    note("GetDiskFreeSpace(%s) -> %d", root ? root : "(null)", r);
    return r;
}

/* ---- inline hook：在 kernel32 函数本体上打 5 字节 jmp，覆盖所有模块 ---- */
static unsigned char *g_tramp_cfa;
static unsigned char *g_tramp_dio;

static void make_tramp(const char *dll, const char *fn, void *handler,
                       unsigned char **out_tramp)
{
    HMODULE k = GetModuleHandleA(dll);
    unsigned char *tgt;
    unsigned char *tr;
    DWORD old;
    if (!k || !out_tramp) return;
    tgt = (unsigned char *)GetProcAddress(k, fn);
    if (!tgt) return;
    {
        int guard = 0;
        while (guard++ < 8) {                      /* 穿透 E9 / FF25 转发桩 */
            if (tgt[0] == 0xE9) { tgt = tgt + 5 + *(int *)(tgt + 1); continue; }
            if (tgt[0] == 0xFF && tgt[1] == 0x25) { tgt = *(unsigned char **)(tgt + 2); continue; }
            break;
        }
    }
    if (tgt[0] == 0xE9 || (tgt[0] == 0xFF && tgt[1] == 0x25)) return;
    tr = (unsigned char *)VirtualAlloc(0, 32, MEM_COMMIT | MEM_RESERVE,
                                       PAGE_EXECUTE_READWRITE);
    if (!tr) return;
    memcpy(tr, tgt, 5);                            /* 搬运被覆盖的 5 字节 */
    tr[5] = 0xE9;
    *(int *)(tr + 6) = (int)((tgt + 5) - (tr + 10));
    if (VirtualProtect(tgt, 8, PAGE_EXECUTE_READWRITE, &old)) {
        tgt[0] = 0xE9;
        *(int *)(tgt + 1) = (int)((unsigned char *)handler - (tgt + 5));
        VirtualProtect(tgt, 8, old, &old);
        FlushInstructionCache(GetCurrentProcess(), tgt, 8);
    }
    *out_tramp = tr;
}

static void patch_slot(void *base, DWORD rva, void *repl, void **save)
{
    void **slot = (void **)((char *)base + rva);
    DWORD old;
    if (*save == NULL) *save = *slot;
    if (VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &old)) {
        *slot = repl;
        VirtualProtect(slot, sizeof(void *), old, &old);
        FlushInstructionCache(GetCurrentProcess(), slot, sizeof(void *));
    }
}

/* 给 iatpatch.c 用的共享符号 */
void *g_h_cfa = (void *)h_cfa;
void *g_h_dio = (void *)h_dio;
void *g_o_cfa;
void *g_o_dio;
void *g_real_cfa;
void *g_real_dio;
void *g_real_open;
void *g_real_save;
void *g_h_open;
void *g_h_save;
void dlg_stub_start(const char *exe_dir, void *o, void *s);
BOOL WINAPI h_dlg_open(LPOPENFILENAMEA);
BOOL WINAPI h_dlg_save(LPOPENFILENAMEA);
void dlg_note(const char *fmt, ...)
{
    char b[256];
    va_list ap;
    va_start(ap, fmt);
    wvsprintfA(b, fmt, ap);
    va_end(ap);
    note("%s", b);
}
void iat_note(const char *fmt, ...)
{
    char b[512];
    va_list ap;
    va_start(ap, fmt);
    wvsprintfA(b, fmt, ap);
    va_end(ap);
    note("%s", b);
}
void iat_start(void);
void count_get(unsigned *a, unsigned *b);
void count_install(void);
void count_note(const char *fmt, ...)
{
    char b[256];
    va_list ap;
    va_start(ap, fmt);
    wvsprintfA(b, fmt, ap);
    va_end(ap);
    note("%s", b);
}

/* ---- 用工程文件直接填记录表（绕过会崩的"导入设置"） ---- */
void fill_start(void);

void fill_note(const char *fmt, ...)
{
    char b[512];
    va_list ap;
    va_start(ap, fmt);
    wvsprintfA(b, fmt, ap);
    va_end(ap);
    note("%s", b);
}

static DWORD WINAPI fill_thread(LPVOID p)
{
    char env[MAX_PATH];
    char pinv[16];
    unsigned pin_views = 0;
    int grp_fix[64], grp_n = 0, grp_done = 0;
    char gf[256];
    (void)p;
    if (GetEnvironmentVariableA("PIN_VIEWS", pinv, sizeof(pinv)))
        pin_views = (unsigned)atoi(pinv);
    if (GetEnvironmentVariableA("GROUP_FIX", gf, sizeof(gf))) {
        char *s = gf;
        while (s && *s && grp_n < 64) {
            int v = atoi(s);
            if (v >= 0 && v < 512) grp_fix[grp_n++] = v;
            s = strchr(s, ',');
            if (s) s++;
        }
    }
    if (!GetEnvironmentVariableA("FILL_PROJ", env, sizeof(env)) && !pin_views && !grp_n &&
        !GetEnvironmentVariableA("CM_G3", env, sizeof(env))) return 0;
    note("fill_thread 启动：grp_n=%d pin=%u", grp_n, pin_views);
    for (;;) {
        unsigned char *base;
        unsigned cnt, rec, i;
        int allzero = 1;
        Sleep(200);
        base = (unsigned char *)GetModuleHandleA(NULL);
        if (!base) continue;
        { static long long g4; char e[32];
          if (GetEnvironmentVariableA("CM_AVCLR", e, sizeof(e))) {
              unsigned *arr = *(unsigned **)(base + 0x123230);
              if (arr && !IsBadWritePtr(arr - 1, 4)) *(arr - 1) = 0;
          }
          if (GetEnvironmentVariableA("CM_G3", e, sizeof(e))) {
              long long v = (long long)atoll(e);
              *(long long *)(base + 0x123190) = v;
              if (v != g4) { g4 = v; note("CM_G3 -> %I64d", v); }
          }
          if (GetEnvironmentVariableA("CM_AV", e, sizeof(e))) {
              static int done;
              *(unsigned *)(base + 0x123104) = (unsigned)atoll(e);
              if (!done) { done = 1; note("CM_AV -> idx=%u", *(unsigned *)(base + 0x123104)); }
          } }
        /* 持续把视图数钉住：程序每帧都会从界面 Edit 现读覆盖这个全局 */
        if (pin_views && ((unsigned char *)base)[0x123203] == 1)
            *(unsigned *)(base + 0x1230FC) = pin_views;
        if (pin_views) ((unsigned char *)base)[0x123204] = 1;
        /* 分组守护：带狗实测有 10 层分组=9，无狗时程序只写 5（狗应答参与的部分）。
         * 等 +0x2C 被程序写成 FF/64（导入设置完成）后照实机值改。 */
        if (grp_n && !grp_done) {
            unsigned c2 = *(unsigned short *)(base + 0x12315C);
            unsigned r2 = *(unsigned *)(base + 0x1230B4);
            static unsigned diag;
            if (diag < 30 && r2 > 0x10000u) {
                static DWORD lastDiagTick;
                DWORD now = GetTickCount();
                if (now - lastDiagTick > 2000) {
                    int k2;
                    char b2[256];
                    int p2 = 0;
                    lastDiagTick = now;
                    diag++;
                    for (k2 = 0; k2 < grp_n && p2 < 240; k2++) {
                        unsigned char *rr = (unsigned char *)(r2 + grp_fix[k2] * 56);
                        p2 += wsprintfA(b2 + p2, "%u:%02X/%u ",
                                        grp_fix[k2], rr[0x2C],
                                        *(unsigned short *)(rr + 0x2E));
                    }
                    note("GRPSTAT %s", b2);
                }
            }
            if (r2 > 0x10000u && r2 < 0x80000000u && c2 > 0 && c2 < 512 &&
                !IsBadWritePtr((void *)r2, c2 * 56)) {
                int ready = 1, k;
                for (k = 0; k < grp_n; k++) {
                    unsigned char *rr = (unsigned char *)(r2 + grp_fix[k] * 56);
                    if ((unsigned)grp_fix[k] >= c2 || rr[0x2C] == 0x00) { ready = 0; break; }
                }
                if (ready) {
                    int nch = 0;
                    for (k = 0; k < grp_n; k++) {
                        unsigned char *rr = (unsigned char *)(r2 + grp_fix[k] * 56);
                        unsigned short g = *(unsigned short *)(rr + 0x2E);
                        if (g != 9) { *(unsigned short *)(rr + 0x2E) = 9; nch++; }
                    }
                    if (nch) note("GROUP_FIX：改了 %d 层分组=9", nch);
                    grp_done = 1;
                }
            }
        }
        if (!GetEnvironmentVariableA("FILL_PROJ", env, sizeof(env))) continue;
        cnt = *(unsigned short *)(base + 0x12315C);
        rec = *(unsigned *)(base + 0x1230B4);
        if (!rec || cnt < 4 || cnt > 512) continue;
        if (IsBadReadPtr((void *)rec, cnt * 56)) continue;
        for (i = 0; i < cnt; i++)
            if (((unsigned char *)rec)[i * 56 + 0x2C]) { allzero = 0; break; }
        /* 程序在导入后会整块重建记录（把我们的 FF 冲成 0），所以这里持续守护：
         * 只要又变成全 0 就重填一次。带狗时程序自己会写 FF，这里不会触发。 */
        if (allzero) fill_start();
    }
    return 0;
}

void dongle_spy_install(void)
{
    void *base;
    char *s;
    if (InterlockedExchange(&g_done, 1)) return;
    GetModuleFileNameA(NULL, g_dir, MAX_PATH);
    s = strrchr(g_dir, '\\');
    if (s) s[1] = 0;
    memcpy(g_rec, K_BLOB496, 496);
    base = GetModuleHandleA(NULL);
    if (!base) return;
    patch_slot(base, RVA_CREATEFILE_A,  (void *)h_cfa,  (void **)&o_cfa);
    patch_slot(base, RVA_CREATEFILE_A2, (void *)h_cfa,  (void **)&o_cfa);
    patch_slot(base, RVA_DEVICEIOCTL,   (void *)h_dio,  (void **)&o_dio);
    patch_slot(base, RVA_SETUP_GETCLS,  (void *)h_gcd,  (void **)&o_gcd);
    patch_slot(base, RVA_SETUP_ENUM,    (void *)h_enum, (void **)&o_enum);
    patch_slot(base, RVA_SETUP_DETAIL,  (void *)h_det,  (void **)&o_det);
    patch_slot(base, RVA_SETUP_DESTROY, (void *)h_dest, (void **)&o_dest);
    patch_slot(base, RVA_GETVOLINFO,    (void *)h_volinfo, (void **)&o_volinfo);
    patch_slot(base, RVA_GETDRVSTR,     (void *)h_drvstr,  (void **)&o_drvstr);
    patch_slot(base, RVA_GETDRVTYPE,    (void *)h_drvtype, (void **)&o_drvtype);
    patch_slot(base, RVA_GETFREESPACE,  (void *)h_freesp,  (void **)&o_freesp);
    /* 先取原始指针，再挂 inline hook（handler 相同，但链路变为全局） */
    g_o_cfa = (void *)o_cfa;
    g_o_dio = (void *)o_dio;
    g_real_cfa = (void *)GetProcAddress(GetModuleHandleA("kernel32.dll"), "CreateFileA");
    g_real_dio = (void *)GetProcAddress(GetModuleHandleA("kernel32.dll"), "DeviceIoControl");
    g_real_open = (void *)GetProcAddress(LoadLibraryA("comdlg32.dll"), "GetOpenFileNameA");
    g_real_save = (void *)GetProcAddress(GetModuleHandleA("comdlg32.dll"), "GetSaveFileNameA");
    g_h_open = (void *)h_dlg_open;
    g_h_save = (void *)h_dlg_save;
    dlg_stub_start(g_dir, g_real_open, g_real_save);
    note("dlg slot before: open=%p save=%p (my open=%p)",
         *(void **)((char *)base + RVA_DLG_OPEN),
         *(void **)((char *)base + RVA_DLG_SAVE), (void *)h_dlg_open);
    patch_slot(base, RVA_DLG_OPEN, (void *)h_dlg_open, (void **)&g_real_open);
    patch_slot(base, RVA_DLG_SAVE, (void *)h_dlg_save, (void **)&g_real_save);
    note("dlg slot after : open=%p save=%p",
         *(void **)((char *)base + RVA_DLG_OPEN),
         *(void **)((char *)base + RVA_DLG_SAVE));
    count_install();
    iat_start();                       /* 后台线程补挂后加载的模块 */
    {
        HANDLE th = CreateThread(0, 0, fill_thread, 0, 0, 0);
        if (th) CloseHandle(th);
    }
    note("--- 仿真器安装 base=%p iat-thread started ---", base);
}
