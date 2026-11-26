/* 精确计数"预览动画步进"：三处写 off(0x523090) 的指令各 5 字节
 *   0x5055C9  a3 90 30 52 00   mov [0x523090], eax     (off = Round(x) + 0x0A)
 *   0x505E05  a3 90 30 52 00   mov [0x523090], eax     (off = Round(x) + 0x05)
 *   0x506352  a3 90 30 52 00   mov [0x523090], eax
 *
 * 换成 5 字节 jmp 到桩：桩里累加计数 → 补做原指令 → 跳回下一条。
 * 目的：带狗时预览会一路推进（临时目录 1263 个文件），无狗时几乎不动；
 * 数出这三处各被执行多少次，就能判定动画到底有没有跑、卡在哪一处。
 *
 * 环境变量 COUNT_ANIM=1 才安装。
 */
#include <windows.h>

void count_note(const char *fmt, ...);

static volatile unsigned g_hit55c9, g_hit5e05, g_hit6352;

__attribute__((naked)) static void stub_55c9(void)
{
    __asm__ __volatile__(
        "pushfl\n\t"
        "incl _g_hit55c9\n\t"
        "popfl\n\t"
        "movl %eax, 0x523090\n\t"
        "jmp 0x5055CE\n\t");
}

__attribute__((naked)) static void stub_5e05(void)
{
    __asm__ __volatile__(
        "pushfl\n\t"
        "incl _g_hit5e05\n\t"
        "popfl\n\t"
        "movl %eax, 0x523090\n\t"
        "jmp 0x505E0A\n\t");
}

__attribute__((naked)) static void stub_6352(void)
{
    __asm__ __volatile__(
        "pushfl\n\t"
        "incl _g_hit6352\n\t"
        "popfl\n\t"
        "movl %eax, 0x523090\n\t"
        "jmp 0x506357\n\t");
}

static void patch_jmp5(unsigned char *tgt, void *stub)
{
    DWORD old;
    if (VirtualProtect(tgt, 8, PAGE_EXECUTE_READWRITE, &old)) {
        tgt[0] = 0xE9;
        *(int *)(tgt + 1) = (int)((unsigned char *)stub - (tgt + 5));
        VirtualProtect(tgt, 8, old, &old);
        FlushInstructionCache(GetCurrentProcess(), tgt, 8);
    }
}

void count_get(unsigned *a, unsigned *b)
{
    if (a) *a = g_hit55c9;
    if (b) *b = g_hit5e05;
}

void count_get3(unsigned *a, unsigned *b, unsigned *c)
{
    if (a) *a = g_hit55c9;
    if (b) *b = g_hit5e05;
    if (c) *c = g_hit6352;
}

void count_install(void)
{
    char env[8];
    unsigned char *base;
    if (!GetEnvironmentVariableA("COUNT_ANIM", env, sizeof(env))) return;
    base = (unsigned char *)GetModuleHandleA(NULL);
    if (!base) return;
    patch_jmp5(base + 0x1055C9, (void *)stub_55c9);
    patch_jmp5(base + 0x105E05, (void *)stub_5e05);
    patch_jmp5(base + 0x106352, (void *)stub_6352);
    count_note("COUNT 已挂钩 0x5055C9 / 0x505E05 / 0x506352");
}
