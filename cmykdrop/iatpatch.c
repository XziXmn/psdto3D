/* 把每个已加载模块的 IAT 里的 CreateFileA / DeviceIoControl 换成自己的入口。
 * 后台线程每 200ms 扫一遍，覆盖后加载的 DLL（ok3d1.dll 这些自己也会查狗）。
 * 只改 IAT 槽，不动任何代码字节，所以不会像 inline hook 那样撕裂指令。
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>

extern void *g_h_cfa;
extern void *g_h_dio;
extern void *g_o_cfa;
extern void *g_o_dio;
extern void *g_real_cfa;
extern void *g_real_dio;
extern void *g_real_open;
extern void *g_real_save;
extern void *g_h_open;
extern void *g_h_save;
extern void iat_note(const char *fmt, ...);
void count_get3(unsigned *a, unsigned *b, unsigned *c);

/* mingw32 缺 tlhelp32.h，自己声明 */
#define TH32CS_SNAPMODULE_  0x00000008
#define TH32CS_SNAPMODULE32_ 0x00000010
typedef struct {
    DWORD dwSize, th32ModuleID, th32ProcessID, GlblcntUsage, ProccntUsage;
    BYTE *modBaseAddr; DWORD modBaseSize; HMODULE hModule;
    char szModule[256]; char szExePath[MAX_PATH];
} MODENTRY32_;
HANDLE WINAPI CreateToolhelp32Snapshot(DWORD, DWORD);
BOOL WINAPI Module32First(HANDLE, MODENTRY32_ *);
BOOL WINAPI Module32Next(HANDLE, MODENTRY32_ *);

static int name_is_import_dll(const char *p)
{
    const char *b = p, *s;
    for (s = p; *s; s++) if (*s == '\\' || *s == '/') b = s + 1;
    return !_stricmp(b, "kernel32.dll") || !_stricmp(b, "kernelbase.dll") ||
           !_stricmp(b, "comdlg32.dll");
}

static void patch_one(HMODULE m)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)m;
    IMAGE_NT_HEADERS *nt;
    IMAGE_IMPORT_DESCRIPTOR *imp;
    DWORD old;
    void *real_cfa, *real_dio;
    if (!m || dos->e_magic != IMAGE_DOS_SIGNATURE) return;
    nt = (IMAGE_NT_HEADERS *)((char *)m + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return;
    imp = (IMAGE_IMPORT_DESCRIPTOR *)((char *)m +
          nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    if (!imp) return;
    real_cfa = (void *)g_real_cfa;
    real_dio = (void *)g_real_dio;
    for (; imp->Name; imp++) {
        char dll[MAX_PATH];
        IMAGE_THUNK_DATA *ft;
        unsigned n;
        if (!imp->FirstThunk) continue;
        lstrcpynA(dll, (char *)m + imp->Name, MAX_PATH);
        if (!name_is_import_dll(dll)) continue;
        ft = (IMAGE_THUNK_DATA *)((char *)m + imp->FirstThunk);
        /* 不看名字表：直接比槽里的地址（Delphi 的 OriginalFirstThunk 常为 0） */
        for (n = 0; ft->u1.Function && n < 4096; ft++, n++) {
            void **slot = (void **)ft;
            void *cur = *slot;
            if (real_cfa && cur == real_cfa) {
                if (VirtualProtect(slot, 4, PAGE_READWRITE, &old)) {
                    *slot = g_h_cfa;
                    VirtualProtect(slot, 4, old, &old);
                }
            } else if (real_dio && cur == real_dio) {
                if (VirtualProtect(slot, 4, PAGE_READWRITE, &old)) {
                    *slot = g_h_dio;
                    VirtualProtect(slot, 4, old, &old);
                }
            } else if (g_real_open && cur == g_real_open) {
                if (VirtualProtect(slot, 4, PAGE_READWRITE, &old)) {
                    *slot = g_h_open;
                    VirtualProtect(slot, 4, old, &old);
                }
            } else if (g_real_save && cur == g_real_save) {
                if (VirtualProtect(slot, 4, PAGE_READWRITE, &old)) {
                    *slot = g_h_save;
                    VirtualProtect(slot, 4, old, &old);
                }
            }
        }
    }
}

static unsigned g_av_hits;

static LONG WINAPI veh(EXCEPTION_POINTERS *ep)
{
    if (ep->ExceptionRecord->ExceptionCode == 0xC0000005) {
        CONTEXT *c = ep->ContextRecord;
        unsigned base = (unsigned)(UINT_PTR)GetModuleHandleA(NULL);
        if (c->Eip == base + 0x1023BD && g_av_hits < 4) {
            unsigned cnt2 = *(unsigned short *)(base + 0x12315C);
            unsigned char *tb = (unsigned char *)(base + 0x1230B4);
            unsigned k;
            g_av_hits++;
            iat_note("AV@1023BD eax=%X ebx=%X esi=%X edi=%X cnt=%u",
                     c->Eax, c->Ebx, c->Esi, c->Edi, cnt2);
            for (k = 0; k < 8 && k < cnt2; k++)
                iat_note("   rec[%u] ptr=%08X  +2C=%02X",
                         k, *(unsigned *)(tb + k * 56), tb[k * 56 + 0x2C]);
        }
        if (c->Eip == base + 0x10A001 && g_av_hits < 8) {
            unsigned cnt = *(unsigned short *)(base + 0x12315C);
            unsigned ptr = *(unsigned *)(base + 0x1230B4);
            unsigned dst = *(unsigned *)(base + 0x12309C);
            g_av_hits++;
            iat_note("AV@10A001 ebx=%X edi=%X esi=%X ebp=%X eax=%X cnt=%u recs=%08X dst=%08X",
                     c->Ebx, c->Edi, c->Esi, c->Ebp, c->Eax, cnt, ptr, dst);
            if (ptr > 0x10000 && ptr < 0x80000000u && cnt < 200) {
                unsigned char *r = (unsigned char *)ptr;
                char b[210];
                unsigned i, k = 0;
                for (i = 0; i < cnt && i < 50; i++) {
                    k += wsprintfA(b + k, "%02X ", r[i * 56 + 0x2C]);
                    if (k > 190) break;
                }
                iat_note("  AV 时记录的 +2C: %s", b);
            }
            if (dst > 0x10000 && dst < 0x80000000u) {
                unsigned *d = (unsigned *)dst;
                unsigned n = d[-1];                   /* 动态数组长度在 -4 */
                iat_note("  dst len=%u  slots:", n);
                {
                    unsigned i;
                    for (i = 0; i < n && i < 12; i++) iat_note("    dst[%u]=%08X", i, d[i]);
                }
            }
        }
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

/* ---- 给 exe 里 0x109E44 那个函数做入口钩子（Delphi 序言 53 56 57 55 83 c4 f0） ----
 *
 * 这里顺手做一件必要的事：这张图层记录表的 +0x2C 是"状态位"，合法值只有
 *   00（未被工程初始化）/ FF（已读入）/ 64（预览中已派发）
 * 无狗路径下这块内存没被工程写过，残留 1..99 的脏值；而 0x109E44 会拿 +0x2C 当
 * "组号"去索引一张已经被 SetLength(…,0) 置空的动态数组 → 读地址 0 → AV 0x50A001。
 * 所以：只有当扫描到 1..99 这种**非法状态值**时才整表清 0（带狗时永远不会命中），
 * 清完这次渲染就成了空转，不会再解引用空数组。
 * 需要关闭时设 SANITIZE=0。
 */
static unsigned char *g_tr_109E44;
static int g_enter_n;

static int env_on(const char *name, int dflt)
{
    char v[8];
    if (!GetEnvironmentVariableA(name, v, sizeof(v))) return dflt;
    return !(v[0] == '0' && v[1] == 0);
}

void log_109E44(unsigned *regs)
{
    unsigned base = (unsigned)(UINT_PTR)GetModuleHandleA(NULL);
    unsigned cnt = *(unsigned short *)(base + 0x12315C);
    unsigned rec = *(unsigned *)(base + 0x1230B4);
    unsigned src = *(unsigned *)(base + 0x1230A0);
    unsigned dst = *(unsigned *)(base + 0x12309C);
    unsigned f0fc = *(unsigned *)(base + 0x1230FC);
    unsigned mx = 0, i, nz = 0, dirty = 0;
    int verbose = g_enter_n < 8;

    g_enter_n++;
    if (cnt == 0 || cnt > 512 || rec < 0x10000 || rec >= 0x80000000u) return;
    if (IsBadReadPtr((void *)rec, cnt * 56)) return;

    {
        unsigned char *r = (unsigned char *)rec;
        for (i = 0; i < cnt; i++) {
            unsigned v = r[i * 56 + 0x2C];
            if (v) nz++;
            if (v > mx && v < 100) mx = v;
            if (v >= 1 && v <= 0x63) dirty = 1;      /* 非法状态值 */
        }
    }
    if (verbose)
        iat_note("ENTER #%d ebx=%X eax=%X cnt=%u rec=%08X src=%08X dst=%08X f0fc=%u max2C=%u nz=%u dirty=%u",
                 g_enter_n, regs[4], regs[7], cnt, rec, src, dst, f0fc, mx, nz, dirty);

    if (dirty && env_on("SANITIZE", 1) && !IsBadWritePtr((void *)rec, cnt * 56)) {
        unsigned char *r = (unsigned char *)rec;
        for (i = 0; i < cnt; i++) r[i * 56 + 0x2C] = 0;
        iat_note("SANITIZE 清 +2C x%u（原 max2C=%u nz=%u）", cnt, mx, nz);
    }

    if (verbose) {
        if (src > 0x10000 && src < 0x80000000u && !IsBadReadPtr((void *)src, 8))
            iat_note("   src len=%u", ((unsigned *)src)[-1]);
        if (dst > 0x10000 && dst < 0x80000000u && !IsBadReadPtr((void *)dst, 8))
            iat_note("   dst len=%u", ((unsigned *)dst)[-1]);
    }
}

static void __attribute__((naked)) hook_109E44(void)
{
    __asm__ __volatile__("pushal; pushfl; movl %esp,%eax; addl $4,%eax;"
                         " pushl %eax; call _log_109E44; addl $4,%esp;"
                         " popfl; popal; jmp *_g_tr_109E44");
}

void hook_fn_109E44(void)
{
    unsigned base = (unsigned)(UINT_PTR)GetModuleHandleA(NULL);
    unsigned char *tgt = (unsigned char *)(base + 0x109E44);
    DWORD old;
    g_tr_109E44 = (unsigned char *)VirtualAlloc(0, 64, MEM_COMMIT | MEM_RESERVE,
                                                PAGE_EXECUTE_READWRITE);
    if (!g_tr_109E44) return;
    memcpy(g_tr_109E44, tgt, 7);
    g_tr_109E44[7] = 0xE9;
    *(int *)(g_tr_109E44 + 8) = (int)((tgt + 7) - (g_tr_109E44 + 12));
    if (VirtualProtect(tgt, 8, PAGE_EXECUTE_READWRITE, &old)) {
        tgt[0] = 0xE9;
        *(int *)(tgt + 1) = (int)((unsigned char *)hook_109E44 - (tgt + 5));
        VirtualProtect(tgt, 8, old, &old);
        FlushInstructionCache(GetCurrentProcess(), tgt, 8);
        iat_note("hooked 109E44 -> tramp %p", g_tr_109E44);
    }
}

void iat_start(void);

/* 主模块的这两个描述符被 Delphi 剥掉了 OriginalFirstThunk，按地址比对会漏掉，
 * 所以按 RVA 直接改。（RVA 来自 psdto3d101.exe 的导入表，见 docs/复盘） */
static void patch_main_rva(void)
{
    HMODULE m = GetModuleHandleA(NULL);
    static const unsigned rvas[3] = {0x1242bc, 0x12449c, 0x1244ac};
    static const int kinds[3] = {0, 1, 0};   /* 0=CreateFileA, 1=DeviceIoControl */
    unsigned i;
    DWORD old;
    if (!m) return;
    for (i = 0; i < 3; i++) {
        void **slot = (void **)((char *)m + rvas[i]);
        void *want = kinds[i] ? g_h_dio : g_h_cfa;
        if (!want || *slot == want) continue;
        if (VirtualProtect(slot, 4, PAGE_READWRITE, &old)) {
            *slot = want;
            VirtualProtect(slot, 4, old, &old);
        }
    }
}

void iat_patch_all(void)
{
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE_ | TH32CS_SNAPMODULE32_,
                                           GetCurrentProcessId());
    MODENTRY32_ me;
    patch_main_rva();
    if (snap == INVALID_HANDLE_VALUE) return;
    me.dwSize = sizeof(me);
    if (Module32First(snap, &me)) {
        do { patch_one((HMODULE)me.modBaseAddr); } while (Module32Next(snap, &me));
    }
    CloseHandle(snap);
}

static void dump_region(const char *tag, unsigned base, unsigned from, unsigned to)
{
    char path[MAX_PATH], exe[MAX_PATH], *s;
    FILE *f;
    GetModuleFileNameA(NULL, exe, MAX_PATH);
    s = exe; { char *q = exe; while (*q) { if (*q == 92) s = q + 1; q++; } if (s > exe) s[-1] = 0; }
    wsprintfA(path, "%s_mem_%s_%X.bin", exe, tag, from);
    f = fopen(path, "wb");
    if (!f) return;
    fwrite((void *)(base + from), 1, to - from, f);
    fclose(f);
    iat_note("dumped %s 0x%X..0x%X -> %s", tag, from, to, path);
}

static DWORD WINAPI iat_thread(LPVOID p)
{
    int n = 0;
    (void)p;
    for (;;) {
        iat_patch_all();
        Sleep(200);
        /* 注意：这里**不再**主动清 +0x2C。定时清会撞上程序正在写的中间态，
         * 上次实测直接把 borlndmm 的堆写坏（AV 0076460B）。需要兜底就用
         * log_109E44 里的按入口 SANITIZE（只在出现非法状态值时才动）。 */
        {
            static unsigned last_cnt, last_ptr;
            unsigned base = (unsigned)GetModuleHandleA(NULL);
            unsigned cnt = *(unsigned short *)(base + 0x12315C);
            unsigned ptr = *(unsigned *)(base + 0x1230B4);
            if (cnt != last_cnt || ptr != last_ptr) {
                last_cnt = cnt; last_ptr = ptr;
                iat_note("TBL n=%u cnt=%u ptr=%08X f0fc=%u f203=%u f204=%u", n, cnt, ptr,
                         *(unsigned *)(base + 0x1230FC),
                         ((unsigned char *)base)[0x123203],
                         ((unsigned char *)base)[0x123204]);
                if (ptr > 0x10000 && ptr < 0x80000000u) {
                    unsigned char *r = (unsigned char *)ptr;
                    char b[256];
                    unsigned i, k = 0;
                    for (i = 0; i < 50 && i < cnt; i++) {
                        k += wsprintfA(b + k, "%02X", r[i * 56 + 0x2C]);
                        if (k > 200) break;
                    }
                    iat_note("  +2C[0..%u] = %s", i, b);
                }
            }
        }
        {
            unsigned h3, h4, h5;
            static unsigned l3 = 0xFFFFFFFFu, l4 = 0xFFFFFFFFu, l5 = 0xFFFFFFFFu;
            count_get3(&h3, &h4, &h5);
            if (h3 != l3 || h4 != l4 || h5 != l5) { l3 = h3; l4 = h4; l5 = h5;
                iat_note("ANIM n=%d 55C9=%u 5E05=%u 6352=%u", n, h3, h4, h5); }
        }
        {
            /* dump 狗数据缓冲区 0x521008 起 0x120 字节 */
            static unsigned dgd;
            if (!dgd) {
                unsigned char *db = (unsigned char *)(GetModuleHandleA(NULL) + 0x121008);
                if (!IsBadReadPtr(db, 0x120)) {
                    unsigned k, nz = 0;
                    for (k = 0; k < 0x120; k++) if (db[k]) { nz = 1; break; }
                    if (nz) {
                        char p2[MAX_PATH]; FILE *f;
                        GetModuleFileNameA(NULL, p2, MAX_PATH);
                        { char *s = strrchr(p2, 92); if (s) s[1] = 0; }
                        strcat(p2, "_dogbuf.bin");
                        f = fopen(p2, "wb");
                        if (f) { fwrite(db, 1, 0x120, f); fclose(f); }
                        dgd = 1;
                        iat_note("DUMP 狗缓冲区 -> %s", p2);
                    }
                }
            }
        }
        {
            /* +0x2C 变化跟踪：谁把 FF 清回 0 的，一眼可见 */
            static unsigned lastSig = 0xFFFFFFFFu;
            unsigned base3 = (unsigned)(UINT_PTR)GetModuleHandleA(NULL);
            unsigned cnt3 = *(unsigned short *)(base3 + 0x12315C);
            unsigned rec3 = *(unsigned *)(base3 + 0x1230B4);
            if (rec3 > 0x10000u && rec3 < 0x80000000u && cnt3 > 0 && cnt3 < 512 &&
                !IsBadReadPtr((void *)rec3, cnt3 * 56)) {
                unsigned char *r3 = (unsigned char *)rec3;
                unsigned i3, sig3 = 2166136261u;
                char b3[400];
                int k3 = 0;
                for (i3 = 0; i3 < cnt3 && i3 < 100; i3++)
                    sig3 = (sig3 ^ r3[i3 * 56 + 0x2C]) * 16777619u;
                if (sig3 != lastSig) {
                    lastSig = sig3;
                    k3 = wsprintfA(b3, "ST t=%u cnt=%u +2C=", n / 5, cnt3);
                    for (i3 = 0; i3 < cnt3 && i3 < 60 && k3 < 360; i3++)
                        k3 += wsprintfA(b3 + k3, "%02X", r3[i3 * 56 + 0x2C]);
                    iat_note("%s", b3);
                }
            }
        }
        if (++n % 25 == 0 && n <= 150) {       /* 每 5 秒一份，到 30 秒 */
            unsigned base = (unsigned)GetModuleHandleA(NULL);
            char env[8];
            if (GetEnvironmentVariableA("MEM_DUMP", env, sizeof(env))) {
                char tag[16];
                wsprintfA(tag, "t%02d", n / 25 * 5);
                dump_region(tag, base, 0x115000, 0x11EE2C);
            }
        }
    }
    return 0;
}

void iat_start(void)
{
    HANDLE h;
    AddVectoredExceptionHandler(1, veh);
    hook_fn_109E44();
    h = CreateThread(0, 0, iat_thread, 0, 0, 0);
    if (h) CloseHandle(h);
}
