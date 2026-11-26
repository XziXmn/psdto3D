/* 用工程文件直接填图层记录表，绕过原程序那个会崩的"导入设置"。
 *
 * 记录表（56 字节/条）字段（实测）：
 *   +0x00 top   +0x04 left   +0x08 bottom  +0x0C right  +0x10 width  +0x14 height
 *   +0x2C BYTE  状态：00=未初始化 / FF=已读入 / 64=预览中已派发
 *   +0x2D BYTE  角度 angle      ← 工程每层表第 1 列
 *   +0x2E WORD  分组 group      ← 第 2 列
 *   +0x30 QWORD 缩放 ×10000     ← 第 3 列
 *
 * 工程文件（.tw3d2 / .gxwj）：
 *   第 3 行   "99100|39550 <layers> <w> <h>"
 *   其后       <layers> 行：每层一个整数
 *   再 <layers> 行： " <angle> <group>  <scale>"
 *
 * 环境变量 FILL_PROJ 指向工程文件；FILL_ONLY=1 时只填表、不碰全局。
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define RVA_REC_PTR 0x1230B4
#define RVA_REC_CNT 0x12315C
#define RVA_F0FC    0x1230FC
#define REC_SIZE    56

extern void fill_note(const char *fmt, ...);
void fill_arrays(unsigned char *base, unsigned cnt);

static int parse_project(const char *path, unsigned *n_out, unsigned char *angle,
                         unsigned short *group, unsigned *scale10000, unsigned *angles_out,
                         unsigned *lpi_out, unsigned *x_out)
{
    FILE *f = fopen(path, "rb");
    long sz;
    char *buf;
    char *lines[4096];
    int nlines = 0, i, n = 0;

    if (!f) return -1;
    fseek(f, 0, SEEK_END);
    sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz <= 0 || sz > (16 << 20)) { fclose(f); return -1; }
    buf = (char *)malloc(sz + 1);
    if (!buf) { fclose(f); return -1; }
    if (fread(buf, 1, sz, f) != (size_t)sz) { free(buf); fclose(f); return -1; }
    fclose(f);
    buf[sz] = 0;

    lines[nlines++] = buf;
    for (i = 0; i < sz && nlines < 4096; i++)
        if (buf[i] == '\n') {
            buf[i] = 0;
            if (i + 1 < sz) lines[nlines++] = buf + i + 1;
        }

    /* 第 2 行： LPI angles ... */
    if (nlines >= 2) {
        double lpi = 0, ang = 0, xval = 0;
        if (sscanf(lines[1], "%lf %lf %lf", &lpi, &ang, &xval) >= 2) {
            if (lpi_out) *lpi_out = (unsigned)(lpi + 0.5);
            if (angles_out) *angles_out = (unsigned)(ang + 0.5);
            if (x_out) *x_out = (unsigned)(xval + 0.5);
        }
    }
    /* 第 3 行： 99100/39550 <layers> ... */
    if (nlines >= 3) {
        unsigned magic = 0;
        if (sscanf(lines[2], "%u %d", &magic, &n) >= 2 && n > 0 && n < 1024) {
            int base = 3 + n;          /* 每层整数的第一行是第 4 行（0 基 3） */
            if (base + n > nlines) return -2;
            for (i = 0; i < n; i++) {
                const char *p = lines[base + i];
                int ang = 0, grp = 0;
                double sc = 1.0;
                if (sscanf(p, "%d %d %lf", &ang, &grp, &sc) < 2) {
                    ang = 0; grp = 0; sc = 1.0;
                }
                angle[i] = (unsigned char)(ang < 0 ? 0 : (ang > 255 ? 255 : ang));
                group[i] = (unsigned short)(grp < 0 ? 0 : (grp > 65535 ? 65535 : grp));
                scale10000[i] = (unsigned)(sc * 10000.0 + 0.5);
            }
            *n_out = (unsigned)n;
            free(buf);
            return 0;
        }
    }
    free(buf);
    return -3;
}

/* ---- 用 Delphi 自己的堆分配：程序会拿这些指针去 FreeMem/Realloc，
 * 用 VirtualAlloc 造的内存会报 "Invalid pointer operation." ---- */
typedef void *(*PF_Gm)(void);

static PF_Gm g_sysgetmem;

static void *heap_alloc(unsigned size)
{
    void *r;
    if (!g_sysgetmem) {
        /* @Borlndmm@SysGetMem$qqri：Borland register 约定，参数在 eax */
        HMODULE h = LoadLibraryA("borlndmm.dll");
        if (h) g_sysgetmem = (PF_Gm)GetProcAddress(h, "@Borlndmm@SysGetMem$qqri");
        if (!g_sysgetmem) g_sysgetmem = (PF_Gm)GetProcAddress(GetModuleHandleA("borlndmm.dll"),
                                                              "@Borlndmm@SysGetMem$qqri");
    }
    if (!g_sysgetmem) return VirtualAlloc(0, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    __asm__ __volatile__("movl %1, %%eax\n\tcall *%2\n\tmovl %%eax, %0"
                         : "=r"(r)
                         : "r"(size), "r"(g_sysgetmem)
                         : "eax", "ecx", "edx", "memory");
    return r;
}

void fill_start(void)
{
    char proj[MAX_PATH];
    unsigned n = 0, angles = 0, lpi = 0, xv = 0;
    unsigned char angle[1024];
    unsigned short group[1024];
    unsigned scale10000[1024];
    unsigned char *base;
    unsigned cnt, rec;
    int i;
    if (!GetEnvironmentVariableA("FILL_PROJ", proj, sizeof(proj))) return;
    if (parse_project(proj, &n, angle, group, scale10000, &angles, &lpi, &xv) != 0) {
        fill_note("FILL 解析工程失败: %s", proj);
        return;
    }
    fill_note("FILL 工程 N=%u angles=%u lpi=%u x=%u", n, angles, lpi, xv);

    base = (unsigned char *)GetModuleHandleA(NULL);
    if (!base) return;
    cnt = *(unsigned short *)(base + RVA_REC_CNT);
    rec = *(unsigned *)(base + RVA_REC_PTR);
    if (!rec || cnt == 0 || cnt > 512) { fill_note("FILL 记录表还没准备好 cnt=%u rec=%08X", cnt, rec); return; }
    if (cnt != n) fill_note("FILL 注意：记录数 %u 与工程层数 %u 不一致，按较小者填", cnt, n);
    if (IsBadWritePtr((void *)rec, cnt * REC_SIZE)) { fill_note("FILL 记录表不可写"); return; }

    for (i = 0; i < (int)cnt && i < (int)n; i++) {
        unsigned char *r = (unsigned char *)(rec + i * REC_SIZE);
        r[0x2C] = 0xFF;
        r[0x2D] = angle[i];
        *(unsigned short *)(r + 0x2E) = group[i];
        *(unsigned *)(r + 0x30) = scale10000[i];
        *(unsigned *)(r + 0x34) = 0;
    }
    if (!GetEnvironmentVariableA("FILL_ONLY", proj, sizeof(proj))) {
        *(unsigned *)(base + RVA_F0FC) = angles;
        fill_note("FILL 已填 %d 条，并把视图数设为 %u", i, angles);
    } else {
        fill_note("FILL 已填 %d 条（FILL_ONLY：不动全局）", i);
    }
    fill_arrays(base, cnt);
}

/* 复刻装载器创建的两个动态数组（带狗侧实测：g230 = 每层一个 72 字节空壳的指针表，
 * g218 = 5 个整数）。绘制循环第一句就是 edx=[0x523230]; edx=[edx+ebx*4]，
 * 空指针必然读地址 0 → 动画第一帧就死。这里用"静态数组"头（refcount=-1）自建。 */
void fill_arrays(unsigned char *base, unsigned cnt)
{
    const unsigned HDR = 8;
    unsigned need = HDR + cnt * 4 + 64;
    unsigned char *blk;
    unsigned i;
    unsigned *arr;

    if (*(unsigned *)(base + 0x123230)) {           /* 已经有了就不动 */
        fill_note("FILL g230 已存在（%08X），跳过", *(unsigned *)(base + 0x123230));
        return;
    }
    if (cnt == 0 || cnt > 512) return;

    blk = (unsigned char *)heap_alloc(need + cnt * 72 + 256);
    if (!blk) { fill_note("FILL VirtualAlloc 失败"); return; }
    arr = (unsigned *)(blk + HDR);
    ((int *)arr)[-1] = (int)cnt;                    /* 长度 */
    ((int *)arr)[-2] = -1;                          /* 引用计数 -1 = 静态，RTL 不会释放 */
    {
        unsigned char *ent = blk + HDR + cnt * 4 + 8;
        for (i = 0; i < cnt; i++) arr[i] = (unsigned)(ent + i * 72);
    }
    *(unsigned *)(base + 0x123230) = (unsigned)arr;
    fill_note("FILL 建 g230：%u 个条目 @%08X（数组 %08X）", cnt, arr, (unsigned)blk);

    /* g218：用带狗侧抓到的值；没有就填 0 */
    if (!*(unsigned *)(base + 0x123218)) {
        char p[MAX_PATH];
        FILE *f;
        unsigned char *b2 = (unsigned char *)heap_alloc(8 + 5 * 4 + 16);
        if (b2) {
            unsigned *a2 = (unsigned *)(b2 + 8);
            unsigned k;
            ((int *)a2)[-1] = 5;
            ((int *)a2)[-2] = -1;
            for (k = 0; k < 5; k++) a2[k] = 0;
            GetModuleFileNameA(NULL, p, MAX_PATH);
            {
                char *s = strrchr(p, '\\');
                if (s) s[1] = 0;
            }
            strcat(p, "_g218_5.bin");
            f = fopen(p, "rb");
            if (f) {
                if (fread(a2, 1, 20, f) != 20) { }
                fclose(f);
                fill_note("FILL 建 g218：5 个值来自抓包");
            } else {
                fill_note("FILL 建 g218：5 个 0（没抓到值）");
            }
            *(unsigned *)(base + 0x123218) = (unsigned)a2;
        }
    }
}
