#include <windows.h>
#include <stdio.h>
#include <stdarg.h>

/* wnaspi32 emulator: answers the ASPI calls the exe makes through 0x521000/0x521004.
   The 36-byte inquiry reply mirrors DAT_00517C5C (the template the exe compares against),
   so 0x4D22CC always matches. Data commands get status OK; store model can be extended
   later if the exe pushes data through ASPI. */

static unsigned char g_id[36] = {
    0x00, 0x80, 0x02, 0x02, 0x1F, 0x00, 0x00, 0x00,
    0x55, 0x53, 0x42, 0x4B, 0x65, 0x79, 0x00, 0x00,
    0x55, 0x53, 0x42, 0x4B, 0x65, 0x79, 0x43, 0x6F, 0x2E,
    0x2C, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x31, 0x2E, 0x30, 0x30
};

static FILE *g_log;
static char g_logp[MAX_PATH];

static void note(const char *fmt, ...)
{
    va_list ap;
    if (!g_logp[0]) {
        GetModuleFileNameA(NULL, g_logp, MAX_PATH);
        {
            char *s = strrchr(g_logp, '\\');
            if (s) s[1] = 0;
            lstrcatA(g_logp, "_aspi.log");
        }
    }
    g_log = fopen(g_logp, "a");
    if (!g_log) return;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fputc('\n', g_log);
    fclose(g_log);
}

DWORD __stdcall GetASPI32SupportInfo(void)
{
    note("GetASPI32SupportInfo -> 0x01000001");
    return 0x01000001;   /* HA count=1 (byte3), status=SS_COMP=1 (byte0) */
}

DWORD __stdcall GetASPI32DLLVersion(void)
{
    return 1;
}

DWORD __stdcall SendASPI32Command(void *srb)
{
    unsigned char *S = (unsigned char *)srb;
    DWORD dlen = *(DWORD *)(S + 0x0C);
    void *dbuf = *(void **)(S + 0x10);
    S[1] = 1;   /* SRB_Status = SS_COMP */
    if (dlen == 0x24 && dbuf) {
        memcpy(dbuf, g_id, 36);
        note("SendASPI32Command inquiry -> id template (36B)");
    } else {
        note("SendASPI32Command cmd=%02X dlen=%lu -> status OK", S[0], (unsigned long)dlen);
    }
    return 1;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID v)
{
    (void)h; (void)r; (void)v;
    return TRUE;
}
