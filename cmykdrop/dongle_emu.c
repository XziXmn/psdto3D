/* 加密狗仿真器（无狗运行用）
 *
 * 记录显示这套"狗"其实是：一个 U 盘状设备 + 一条极小的私有 SCSI 命令通道。
 *   DD FE <addr> DataIn=0  -> 主机写（把授权块写进狗）
 *   D1 FE <addr> DataIn=1  -> 主机读（把授权块/状态读回来）
 * 整个会话只有 20 次调用、8 种形态；地址 0x001A 是 26 字节票据，
 * 0x01F0 是 496 字节授权参数块（头 4 个 dword 必须是 0x7B）。
 * 同时它还以"文件"的形式被读写：[26 字节票据][203 字节 INI][0x0C]。
 *
 * 所以这里不碰 exe、不碰算法：把 CreateFileA 换成开本地文件，
 * 把 SCSI ioctl 换成查表回答，程序照原路走完。
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include "dongle_table.h"
#include "replay_table.h"
static void log_preview_probe(void);
static int cfg_on(const char *key, int def, const char *marker);
static int psd_find_tempdir(char *out);
static int cfg_val(const char *key, int def);

#define RVA_CREATEFILE_A   0x1242BC
#define RVA_CREATEFILE_A2  0x1244AC
#define RVA_DEVICEIOCTL    0x12449C
#define RVA_READFILE       0x1242A8
#define RVA_READFILE2      0x12438C
#define RVA_WRITEFILE      0x124294
#define RVA_WRITEFILE2     0x124348
#define RVA_SETFILEPTR     0x12429C
#define RVA_SETFILEPTR2    0x12436C
#define RVA_GETFILESIZE    0x1242B4
#define RVA_GETFILESIZE2   0x12443C
#define RVA_SETUP_DESTROY   0x124A54

#define RVA_WRITEPSD_PTR    0x123278

#define RVA_WRITEPSD_CALL   0x10B17D

#define RVA_GETPROCADDR     0x124260

#define RVA_GETPROCADDR2    0x124418
#define RVA_SETUP_DETAIL    0x124A58
#define RVA_SETUP_ENUMIF    0x124A5C
#define RVA_SETUP_CLASSDEVS 0x124A60
#define RVA_ENABLEMENUITEM  0x124868
#define RVA_GETOPENFILENAMEA  0x1249F4
#define RVA_GETSAVEFILENAMEA  0x1249F0
#define RVA_CLOSEHANDLE1    0x1242C0
#define RVA_CLOSEHANDLE2    0x1244B8

typedef HANDLE (WINAPI *PF_CreateFileA)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES,
                                        DWORD, DWORD, HANDLE);
typedef BOOL (WINAPI *PF_DeviceIoControl)(HANDLE, DWORD, LPVOID, DWORD, LPVOID,
                                          DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL (WINAPI *PF_ReadFile)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL (WINAPI *PF_WriteFile)(HANDLE, LPCVOID, DWORD, LPDWORD, LPOVERLAPPED);
typedef BOOL (WINAPI *PF_SetFilePointer)(HANDLE, LONG, PLONG, DWORD);
typedef DWORD (WINAPI *PF_SetFilePointer2)(HANDLE, LONG, PLONG, DWORD);
typedef DWORD (WINAPI *PF_SetFilePointer_)(HANDLE, LONG, PLONG, DWORD);
typedef DWORD (WINAPI *PF_GetFileSize_)(HANDLE, LPDWORD);

static PF_CreateFileA     o_cfa;

static void * (WINAPI *o_gpa)(HMODULE, LPCSTR);
static PF_DeviceIoControl o_dio;
static PF_ReadFile        o_rf;
static PF_WriteFile       o_wf;
static PF_SetFilePointer_ o_sfp;
static PF_GetFileSize_    o_gfs;
static HANDLE             g_dev = INVALID_HANDLE_VALUE;
static HANDLE             g_devs[24];
static int                g_ndev;
static int is_dev_handle(HANDLE h)
{
    int i;
    for (i = 0; i < g_ndev; i++) if (g_devs[i] == h && h != NULL) return 1;
    return 0;
}
static unsigned char      g_rec[501];
static unsigned char      g_store[1049088];
static int                g_store_init;
static unsigned char      g_501resp[4][501] = {
    /* response 1 */
    {0x7B,0x00,0x00,0x00,0x7B,0x00,0x00,0x00,0x7B,0x00,0x00,0x00,0x7B,0x00,0x00,0x00,0x98,0x54,0x40,0x00,0x2B,0x00,0x00,0x00,0x2C,0x61,0x6C,0x02,0xF0,0xFB,0x1A,0x00,0x40,0x60,0x6E,0x02,0x2C,0x61,0x6C,0x02,0xF0,0xFB,0x1A,0x00,0x25,0x50,0x40,0x00,0xC8,0xFD,0x1A,0x00,0x0F,0x28,0x40,0x00,0x00,0x00,0x00,0x00,0x38,0x60,0x6E,0x02,0x2C,0x61,0x6C,0x02,0xF0,0xFB,0x1A,0x00,0xE7,0x44,0x94,0x00,0x1C,0x00,0x00,0x00,0xDF,0x44,0x94,0x00,0x74,0x66,0x94,0x00,0x2C,0x00,0x00,0x00,0x50,0xFB,0x1A,0x00,0x01,0x79,0x12,0x00,0x00,0x00,0x02,0x04,0x00,0x00,0xFE,0xFF,0xFF,0xFF,0x00,0x00,0x00,0x00,0x2C,0xFB,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x74,0x66,0x94,0x00,0x19,0x18,0x5B,0x77,0x1C,0x00,0x00,0x00,0x2C,0x61,0x6C,0x02,0x2C,0x00,0x00,0x00,0x2C,0x61,0x6C,0x02,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x80,0x40,0x03,0x00,0x22,0x22,0x22,0x00,0x00,0x00,0x97,0x00,0xA0,0x4D,0x00,0x00,0x04,0x57,0x97,0x00,0xD0,0xB0,0xD7,0xC0,0xA0,0xB7,0x9B,0x00,0x00,0x00,0x00,0x00,0xFC,0x11,0x3A,0x76,0x10,0x00,0x00,0x00,0x81,0x1D,0x6C,0x33,0x5C,0x70,0x73,0x64,0x74,0x6F,0x33,0x64,0x31,0x30,0x31,0x2E,0x65,0x78,0x65,0x00,0x00,0x00,0x00,0x00,0xE0,0xFA,0x1A,0x00,0x47,0x41,0xEB,0x76,0x00,0x00,0x00,0x00,0xB0,0x22,0x01,0x22,0xFB,0x01,0x00,0x00,0x00,0x00,0x00,0x00,0x80,0x0B,0x96,0x00,0x78,0xFA,0x1A,0x00,0x68,0x50,0x40,0x00,0xE0,0xDA,0x4F,0x00,0x00,0x00,0x00,0x00,0xEC,0xFB,0x1A,0x00,0xE4,0x2B,0x40,0x00,0x43,0x3A,0x5C,0x55,0x73,0x65,0x72,0x73,0x5C,0x6D,0x6F,0x79,0x75,0x65,0x5C,0x44,0x65,0x73,0x6B,0x74,0x6F,0x70,0x5C,0x72,0x65,0x61,0x94,0x00,0x74,0x66,0x94,0x00,0xE7,0x44,0x94,0x00,0x2B,0x00,0x00,0x00,0x78,0xFA,0x1A,0x00,0xEC,0xFB,0x1A,0x00,0x05,0x01,0x00,0x00,0x24,0x61,0x6C,0x02,0xC8,0xFD,0x1A,0x00,0x0F,0x28,0x40,0x00,0xEC,0xFB,0x1A,0x00,0x25,0x50,0x40,0x00,0x2C,0x61,0x6C,0x02,0x00,0x00,0x00,0x00,0x40,0x0D,0x5E,0x77,0x28,0xFA,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x74,0x66,0x94,0x00,0x19,0x18,0x5B,0x77,0x2B,0x00,0x00,0x00,0x78,0xFA,0x1A,0x00,0x38,0x00,0x00,0x00,0x78,0xFA,0x1A,0x00,0x38,0x00,0x00,0x00,0x4C,0xFA,0x1A,0x00,0xDF,0x44,0x9B,0x00,0xF0,0xF9,0x1A,0x00,0x00,0x00,0x97,0x00,0x87,0x4B,0x5C,0x77,0x0C,0xFA,0x1A,0x00,0xFA,0xD1,0x59,0x77,0x00,0x00,0x00,0x00,0x6F,0x99,0xC1,0x3A,0x05,0x01,0x00,0x00,0xF0,0x48,0x7E,0x75,0x00,0x00,0x00,0x00,0xE4,0xF9,0x1A,0x00,0xFE,0xFF,0xFF,0xFF,0xB8,0x2A,0x9B,0x00,0x00,0x00,0x97,0x00,0x00,0x00,0x00,0x00,0xC0,0xB8,0x69,0x77,0x78,0xFA,0x1A,0x00,0x04,0x01,0x00,0x00,0xF0,0xF9,0x1A,0x00,0xB8,0x2A,0x9B,0x00,0x56,0x00,0x00,0x00,0x10,0xFA,0x1A,0x00,0x5E,0x4B,0x5C,0x77,0x78,0xFA,0x1A,0x00,0xB8,0x2A,0xFB,0x00,0x00,0x00,0x00},
    /* response 2 */
    {0x7B,0x00,0x00,0x00,0x7B,0x00,0x00,0x00,0x7B,0x00,0x00,0x00,0x7B,0x00,0x00,0x00,0x98,0x54,0x40,0x00,0x2B,0x00,0x00,0x00,0x2C,0x61,0x6C,0x02,0xF0,0xFB,0x1A,0x00,0x40,0x60,0x6E,0x02,0x2C,0x61,0x6C,0x02,0xF0,0xFB,0x1A,0x00,0x25,0x50,0x40,0x00,0xC8,0xFD,0x1A,0x00,0x0F,0x28,0x40,0x00,0x00,0x00,0x00,0x00,0x38,0x60,0x6E,0x02,0x2C,0x61,0x6C,0x02,0xF0,0xFB,0x1A,0x00,0xE7,0x44,0x94,0x00,0x1C,0x00,0x00,0x00,0xDF,0x44,0x94,0x00,0x74,0x66,0x94,0x00,0x2C,0x00,0x00,0x00,0x50,0xFB,0x1A,0x00,0x01,0x79,0x12,0x00,0x00,0x00,0x02,0x04,0x00,0x00,0xFE,0xFF,0xFF,0xFF,0x00,0x00,0x00,0x00,0x2C,0xFB,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x74,0x66,0x94,0x00,0x19,0x18,0x5B,0x77,0x1C,0x00,0x00,0x00,0x2C,0x61,0x6C,0x02,0x2C,0x00,0x00,0x00,0x2C,0x61,0x6C,0x02,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x80,0x40,0x03,0x00,0x22,0x22,0x22,0x00,0x00,0x00,0x97,0x00,0xA0,0x4D,0x00,0x00,0x04,0x57,0x97,0x00,0xD0,0xB0,0xD7,0xC0,0xA0,0xB7,0x9B,0x00,0x00,0x00,0x00,0x00,0xFC,0x11,0x3A,0x76,0x10,0x00,0x00,0x00,0x81,0x1D,0x6C,0x33,0x5C,0x70,0x73,0x64,0x74,0x6F,0x33,0x64,0x31,0x30,0x31,0x2E,0x65,0x78,0x65,0x00,0x00,0x00,0x00,0x00,0xE0,0xFA,0x1A,0x00,0x47,0x41,0xEB,0x76,0x00,0x00,0x00,0x00,0xB0,0x22,0x01,0x22,0xFB,0x01,0x00,0x00,0x00,0x00,0x00,0x00,0x80,0x0B,0x96,0x00,0x78,0xFA,0x1A,0x00,0x68,0x50,0x40,0x00,0xE0,0xDA,0x4F,0x00,0x00,0x00,0x00,0x00,0xEC,0xFB,0x1A,0x00,0xE4,0x2B,0x40,0x00,0x43,0x3A,0x5C,0x55,0x73,0x65,0x72,0x73,0x5C,0x6D,0x6F,0x79,0x75,0x65,0x5C,0x44,0x65,0x73,0x6B,0x74,0x6F,0x70,0x5C,0x72,0x65,0x61,0x94,0x00,0x74,0x66,0x94,0x00,0xE7,0x44,0x94,0x00,0x2B,0x00,0x00,0x00,0x78,0xFA,0x1A,0x00,0xEC,0xFB,0x1A,0x00,0x05,0x01,0x00,0x00,0x24,0x61,0x6C,0x02,0xC8,0xFD,0x1A,0x00,0x0F,0x28,0x40,0x00,0xEC,0xFB,0x1A,0x00,0x25,0x50,0x40,0x00,0x2C,0x61,0x6C,0x02,0x00,0x00,0x00,0x00,0x40,0x0D,0x5E,0x77,0x28,0xFA,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x74,0x66,0x94,0x00,0x19,0x18,0x5B,0x77,0x2B,0x00,0x00,0x00,0x78,0xFA,0x1A,0x00,0x38,0x00,0x00,0x00,0x78,0xFA,0x1A,0x00,0x38,0x00,0x00,0x00,0x4C,0xFA,0x1A,0x00,0xDF,0x44,0x9B,0x00,0xF0,0xF9,0x1A,0x00,0x00,0x00,0x97,0x00,0x87,0x4B,0x5C,0x77,0x0C,0xFA,0x1A,0x00,0xFA,0xD1,0x59,0x77,0x00,0x00,0x00,0x00,0x6F,0x99,0xC1,0x3A,0x05,0x01,0x00,0x00,0xF0,0x48,0x7E,0x75,0x00,0x00,0x00,0x00,0xE4,0xF9,0x1A,0x00,0xFE,0xFF,0xFF,0xFF,0xB8,0x2A,0x9B,0x00,0x00,0x00,0x97,0x00,0x00,0x00,0x00,0x00,0xC0,0xB8,0x69,0x77,0x78,0xFA,0x1A,0x00,0x04,0x01,0x00,0x00,0xF0,0xF9,0x1A,0x00,0xB8,0x2A,0x9B,0x00,0x56,0x00,0x00,0x00,0x10,0xFA,0x1A,0x00,0x5E,0x4B,0x5C,0x77,0x78,0xFA,0x1A,0x00,0xB8,0x2A,0xFB,0x00,0x00,0x00,0x00},
    /* response 3 */
    {0x02,0x00,0x00,0x00,0x02,0x00,0x00,0x00,0x20,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x20,0x00,0x00,0x00,0x1F,0x00,0x00,0x00,0x02,0x00,0x00,0x00,0x02,0x00,0x00,0x00,0x16,0x8B,0xC5,0x62,0xB1,0x58,0x1C,0x40,0xAC,0x13,0x14,0x61,0xD4,0xDA,0x20,0x40,0x00,0x00,0x00,0x00,0x00,0x88,0xC3,0x40,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x88,0xC3,0x40,0xAC,0x13,0x14,0x61,0xD4,0xDA,0x20,0x40,0x16,0x8B,0xC5,0x62,0xB1,0x58,0x1C,0x40,0x00,0x00,0xA0,0xF7,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x74,0x66,0x94,0x00,0x19,0x18,0x5B,0x77,0x0F,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0xA7,0x3C,0x40,0x00,0x20,0x00,0x1A,0x00,0xBC,0xF7,0x1A,0x00,0x00,0x00,0x00,0x00,0xC0,0xF7,0x1A,0x00,0x00,0x00,0x00,0x00,0x00,0x81,0x99,0x00,0x20,0xCD,0x6E,0x02,0x0C,0x00,0x00,0x00,0xFB,0x26,0x5B,0x77,0xFE,0xFF,0xFF,0xFF,0x00,0x00,0x00,0x00,0x84,0xF7,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x74,0x66,0x94,0x00,0x19,0x18,0x5B,0x77,0xFE,0xFF,0xFF,0xFF,0x00,0x00,0x00,0x00,0x0C,0x00,0x00,0x34,0x3A,0x32,0x39,0x6F,0x36,0x31,0x35,0x31,0x34,0x73,0x40,0x6F,0x6B,0x33,0x64,0x2E,0x63,0x6F,0x6D,0x20,0x20,0x20,0x20,0x00,0xFE,0xFF,0xFF,0xFF,0x00,0x00,0x00,0x00,0x5C,0xF7,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x74,0x66,0x94,0x00,0x19,0x18,0x5B,0x77,0x00,0xFB,0x1A,0x00,0x25,0x50,0x40,0x00,0x74,0x65,0x60,0x0C,0x09,0xF7,0x1A,0x00,0x68,0x50,0x40,0x00,0x1C,0x83,0x01,0x00,0x10,0xFB,0x1A,0x00,0xA0,0xF8,0x1A,0x00,0x42,0x34,0x40,0x00,0x12,0x32,0x30,0x32,0x36,0x2F,0x39,0x2F,0x32,0x39,0x20,0x31,0x34,0x3A,0x00,0x00,0x20,0x00,0x00,0x00,0xDC,0xF6,0x1A,0x00,0xDF,0x44,0x94,0x00,0x74,0x66,0x94,0x00,0xE7,0x44,0x94,0x00,0x12,0x00,0x00,0x00,0x09,0xF7,0x1A,0x00,0x10,0xFB,0x1A,0x00,0xB0,0xF8,0x1A,0x00,0x6C,0x65,0x60,0x0C,0x44,0xFB,0x1A,0x00,0x0F,0x28,0x40,0x00,0x00,0x18,0x5B,0x77,0x0D,0xF7,0x1A,0x00,0xFE,0xFF,0xFF,0xFF,0x00,0x00,0x00,0x00,0x01,0x00,0x00,0x00,0xB8,0xF6,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x74,0x66,0x94,0x00,0x19,0x18,0x5B,0x77,0x12,0x00,0x00,0x00,0x09,0xF7,0x1A,0x00,0x20,0x00,0x00,0x00,0x09,0xF7,0x00,0x5C,0x14,0xF8,0x1A,0x00,0x20,0x93,0x28,0x75,0x0D,0xF7,0x1A,0x00,0x00,0x00,0x00,0x00,0x70,0xF6,0x1A,0x00,0xFC,0x54,0x25,0x75,0xFE,0xFF,0xFF,0xFF,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x98,0xF6,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x68,0x71,0xE0,0x5C,0x00,0x56,0x25,0x75,0x60,0xF6,0x1A,0x00,0xC1,0x55,0x25,0x75,0x98,0x07,0x99,0x00,0x60,0x55,0x25,0x75,0xC7,0x6E,0xE4,0xFD,0x0D,0xF7,0x1A,0x00,0x01,0x00,0x00,0x00,0xB0,0xF8,0x1A,0x00,0x78,0x07,0x99,0x00,0x00,0x00,0x00,0x00,0x30,0xF6,0x1A,0x00,0x08,0x30,0xFB,0x00,0x00,0x00,0x00},
    /* response 4 */
    {0x02,0x00,0x00,0x00,0x16,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x43,0x30,0x00,0x00,0x17,0x30,0x00,0x00,0xC9,0x19,0x00,0x00,0x05,0xE6,0x10,0x09,0x73,0x77,0xBB,0xC4,0x00,0x00,0x00,0x00,0x00,0xC0,0x72,0x40,0x33,0x33,0x33,0x33,0x33,0x33,0x39,0x40,0x7A,0x14,0xAE,0x47,0xE1,0xAD,0xB3,0x40,0x4A,0x0C,0x02,0x2B,0x07,0x92,0xBA,0x40,0xE1,0x7A,0x14,0xAE,0x47,0xF1,0x76,0x40,0x7A,0x14,0xAE,0x47,0xE1,0xAD,0xB3,0x40,0x4A,0x0C,0x02,0x2B,0x07,0x92,0xBA,0x40,0x00,0x00,0x00,0x00,0x00,0x4D,0xB4,0x40,0x73,0x61,0x6C,0x65,0x73,0x40,0x6F,0x6B,0x33,0x64,0x2E,0x63,0x6F,0x6D,0x00,0x00,0x00,0x00,0xE8,0x28,0x43,0x00,0x00,0xF4,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x74,0x66,0x94,0x00,0x19,0x18,0x5B,0x77,0x04,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x14,0x00,0x00,0x00,0x77,0x77,0x77,0x2E,0x33,0x64,0x39,0x39,0x2E,0x63,0x6F,0x6D,0x00,0xF3,0x1A,0x00,0x88,0x46,0x94,0x00,0x74,0x66,0x94,0x00,0x90,0x46,0x94,0x00,0xD5,0x0F,0x83,0x02,0x01,0x00,0x00,0x00,0x48,0xF4,0x1A,0x00,0x00,0x00,0x00,0x00,0x50,0xF4,0x1A,0x00,0x2F,0x28,0x6F,0x6B,0x33,0x64,0x00,0x00,0x54,0xEC,0x6E,0x02,0x31,0xE1,0x41,0x00,0xFE,0xFF,0xFF,0xFF,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0xA0,0xF3,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x74,0x66,0x94,0x00,0x19,0x18,0x5B,0x77,0xB0,0x1E,0x40,0x06,0x90,0x1E,0x40,0x06,0x77,0x77,0x77,0x2E,0x33,0x64,0x39,0x39,0x2E,0x63,0x6F,0x6D,0x6F,0x6B,0x33,0x64,0x73,0x61,0x6C,0x65,0x73,0x40,0x6F,0x6B,0x33,0x64,0x2E,0x63,0x6F,0x6D,0x00,0x00,0x18,0x21,0x36,0x06,0x84,0xF3,0x1A,0x00,0x89,0x28,0x40,0x00,0x64,0xEC,0x6E,0x02,0x8F,0xE3,0x30,0x31,0x73,0x74,0x2E,0x69,0x6E,0x69,0x00,0x00,0xFE,0xFF,0xFF,0xFF,0x30,0xF3,0x1A,0x00,0x5E,0x5C,0x5F,0x77,0x74,0x66,0x94,0x00,0x19,0x18,0x5B,0x77,0xAC,0x64,0x6F,0x02,0x04,0x00,0x00,0x00,0x24,0x00,0x00,0x00,0x04,0x00,0x00,0x00,0x24,0x00,0x00,0x00,0x5C,0x33,0x36,0x30,0x5C,0x31,0x00,0x00,0xDE,0x40,0x45,0x00,0x0C,0xB0,0x6C,0x02,0x30,0xF4,0x1A,0x00,0xC7,0x0E,0x46,0x00,0xC0,0xF5,0x1A,0x00,0x30,0xF4,0x1A,0x00,0x0C,0xB0,0x6C,0x02,0xA4,0x7E,0xBD,0x75,0x00,0x00,0x0C,0x00,0x00,0x00,0x00,0x00,0x10,0xF3,0x64,0x3A,0x5C,0x64,0x6F,0x77,0x6E,0x6C,0x6F,0x61,0x64,0x73,0x00,0x00,0x04,0xF4,0x1A,0x00,0x0C,0x40,0x46,0x00,0xA0,0x97,0x61,0x77,0xE0,0x05,0x20,0x00,0x0D,0x00,0x00,0x00,0x05,0x00,0x00,0x00,0x54,0x21,0x36,0x06,0x04,0xF4,0x1A,0x00,0xC0,0xF5,0x1A,0x00,0x64,0x3A,0x5C,0x64,0x6F,0x77,0x6E,0x6C,0x6F,0x61,0x64,0x73,0x5C,0x33,0x36,0x30,0x5C,0x31,0x30,0x31,0x73,0x74,0x2E,0x69,0x6E,0x69,0x00,0x00,0x00,0x00,0x00,0x00,0xE0,0x05,0x20,0x00,0x00,0x00,0x00,0x00,0xA8,0xF2,0x1A,0x00,0x7B,0x45,0xB9,0x75,0x0D,0x00,0xFB,0x00,0x00,0x00,0x00},
};
static int                g_501idx;
static unsigned long       g_pos;
static int                g_rp_idx;
static unsigned char      g_reply[16];
static int                g_reply_n;
static volatile LONG      g_done;
static char               g_dir[MAX_PATH];
static char               g_log[MAX_PATH];

static FILE *LF(void)
{
    if (!g_log[0]) {
        lstrcpyA(g_log, g_dir);
        lstrcatA(g_log, "_dongle.log");
    }
    return fopen(g_log, "a");
}

static int cfg_log_on(void)
{
    static int v = -1;
    if (v < 0) v = cfg_val("log", 1);
    return v;
}

static void note(const char *fmt, ...)
{
    FILE *f;
    if (!cfg_log_on()) return;
    f = LF();
    va_list ap;
    if (!f) return;
    va_start(ap, fmt);
    vfprintf(f, fmt, ap);
    va_end(ap);
    fputc('\n', f);
    fclose(f);
}

static int is_dongle_path(const char *n)
{
    if (!n) return 0;
    if (strstr(n, "MyUSBKey")) return 1;      /* 驱动通道：故意让它失败，逼程序走 SCSI */
    if (strstr(n, "ven_usbkey") || strstr(n, "usbstor")) return 1;
    return 0;
}

/* 生成冒充设备的文件：[26 票据][INI][0x0C] */
typedef HANDLE (WINAPI *PF_SDGCD)(void *, const char *, void *, unsigned long);
typedef BOOL   (WINAPI *PF_SDEIF)(HANDLE, void *, void *, unsigned long, void *);
typedef BOOL   (WINAPI *PF_SDDIDA)(HANDLE, void *, void *, unsigned long, unsigned long *, void *);
typedef BOOL   (WINAPI *PF_SDDIL)(HANDLE);

static PF_SDGCD   o_sdgcd;
static PF_SDEIF   o_sdeif;
static PF_SDDIDA  o_sddida;
static PF_SDDIL   o_sddil;
static void *o_gofna;
static void *o_gsfn;

#define EMU_SET_MAGIC ((HANDLE)0xDEAD0001)

static char EMU_DOG_PATH[] =
  "\\\\?\\usbstor#disk&ven_usbkey&prod_usbkeyco._&rev_2.00#6&af06fe2&0#{53f56307-b6bf-11d0-94f2-00a0c91efb8b}";

static int capture_mode(void);

static HANDLE WINAPI e_sdgcd(void *g, const char *en, void *hwnd, unsigned long flags)
{
    if (capture_mode() && o_sdgcd) return o_sdgcd(g, en, hwnd, flags);
    if (flags == 0x12) { note("EMU SetupDiGetClassDevs fake"); return EMU_SET_MAGIC; }
    return o_sdgcd(g, en, hwnd, flags);
}

static BOOL WINAPI e_sdeif(HANDLE set, void *d, void *g, unsigned long idx, void *ifd)
{
    if (capture_mode() && o_sdeif) return o_sdeif(set, d, g, idx, ifd);
    if (set == EMU_SET_MAGIC) {
        if (idx == 0) { note("EMU EnumIf idx=0 ok"); return TRUE; }
        SetLastError(0x103);
        return FALSE;
    }
    return o_sdeif(set, d, g, idx, ifd);
}

static BOOL WINAPI e_sddida(HANDLE set, void *ifd, void *detv, unsigned long len, unsigned long *req, void *di)
{
    if (capture_mode() && o_sddida) return o_sddida(set, ifd, detv, len, req, di);
    if (set == EMU_SET_MAGIC) {
        int need = 5 + lstrlenA(EMU_DOG_PATH) + 1;
        if (req) *req = (unsigned long)need;
        if (!detv || len < (unsigned long)need) { SetLastError(0x7A); return TRUE; }
        *(unsigned long *)detv = 5;
        lstrcpyA((char *)detv + 4, EMU_DOG_PATH);
        note("EMU Detail fake path");
        return TRUE;
    }
    return o_sddida(set, ifd, detv, len, req, di);
}

static BOOL WINAPI e_sddil(HANDLE set)
{
    if (capture_mode() && o_sddil) return o_sddil(set);
    if (set == EMU_SET_MAGIC) return TRUE;
    return o_sddil(set);
}

static BOOL (WINAPI *o_ch)(HANDLE);

static char  g_opens[8][MAX_PATH];
static char  g_saves[8][MAX_PATH];
static int   g_nopen, g_iopen, g_nsave, g_isave;

static void load_dlg_lists(void)
{
    char path[MAX_PATH], line[MAX_PATH];
    FILE *f;
    char *s;
    lstrcpyA(path, g_dir);
    lstrcatA(path, "_dlgopen.txt");
    f = fopen(path, "r");
    g_nopen = 0;
    if (f) { while (fgets(line, MAX_PATH, f) && g_nopen < 8) { s = line + lstrlenA(line) - 1; while (s >= line && (*s == 0x0A || *s == 0x0D || *s == 0x20)) *s-- = 0; if (line[0]) lstrcpyA(g_opens[g_nopen++], line); } fclose(f); }
    lstrcpyA(path, g_dir);
    lstrcatA(path, "_dlgsave.txt");
    f = fopen(path, "r");
    g_nsave = 0;
    if (f) { while (fgets(line, MAX_PATH, f) && g_nsave < 8) { s = line + lstrlenA(line) - 1; while (s >= line && (*s == 0x0A || *s == 0x0D || *s == 0x20)) *s-- = 0; if (line[0]) lstrcpyA(g_saves[g_nsave++], line); } fclose(f); }
    g_iopen = 0; g_isave = 0;
    note("dlg lists loaded: open=%d save=%d", g_nopen, g_nsave);
}


static char gxwj_filter[256];
static void gxwj_patch_filter(void *ofn)
{
    char **pf = (char **)((char *)ofn + 0x0C);   /* OPENFILENAME.lpstrFilter */
    if (!pf || !*pf) return;
    if (strstr(*pf, ".gxwj")) return;
    /* only project dialogs: 只有过滤器里含 tw3d 的才改，导入 PSD 的对话框保持原样 */
    if (!strstr(*pf, "tw3d")) return;
    if (!gxwj_filter[0]) {
        /* GBK 字节：工程文件 / 所有文件 */
        static const char label1[] = "\xB9\xA4\xB3\xCC" "\xCE\xC4\xBC\xFE";
        static const char label2[] = "\xCB\xF9\xD3\xD0" "\xCE\xC4\xBC\xFE";
        int p = 0;
        p += wsprintfA(gxwj_filter + p, "%s (*.tw3d2;*.gxwj;*.tw3d)", label1) + 1;
        p += wsprintfA(gxwj_filter + p, "*.tw3d2;*.gxwj;*.tw3d") + 1;
        p += wsprintfA(gxwj_filter + p, "%s (*.*)", label2) + 1;
        p += wsprintfA(gxwj_filter + p, "*.*") + 1;
        gxwj_filter[p] = 0;
    }
    *pf = gxwj_filter;
}


/* 程序实际能力：预览/渲染最多 33 层（第 34 层起会读一个从未分配的数组） */
#define PSD_MAX_LAYERS 33

static const unsigned char g_cn_body[] = {
    213,226,184,246,32,80,83,68,32,211,208,32,37,100,32,184,246,205,188,178,
    227,161,163,13,10,13,10,177,190,179,204,208,242,181,196,212,164,192,192,47,
    228,214,200,190,215,238,182,224,214,167,179,214,32,37,100,32,178,227,163,168,
    181,218,32,37,100,32,178,227,191,170,202,188,187,225,177,192,163,169,161,163,
    13,10,199,235,212,218,32,80,104,111,116,111,115,104,111,112,32,192,239,176,
    209,205,188,178,227,186,207,178,162,181,189,32,37,100,32,178,227,210,212,196,
    218,212,217,181,188,200,235,161,163,13,10,13,10,163,168,181,188,200,235,177,
    190,201,237,196,220,189,211,202,220,184,252,182,224,178,227,163,172,181,171,212,
    164,192,192,187,225,214,177,189,211,177,168,180,237,205,203,179,246,163,169,0
};
static const unsigned char g_cn_title[] = {
    205,188,178,227,202,253,179,172,179,246,179,204,208,242,196,220,193,166,0
};

static int psd_guard_dialog(const char *path)
{
    char msg[700];
    int layers = 0, ch = 0, mode = 0;
    HANDLE fh;
    unsigned char head[26];
    DWORD got = 0;
    if (!path) return 0;
    {
        int l = lstrlenA(path);
        if (l < 5 || lstrcmpiA(path + l - 4, ".psd") != 0) return 0;
    }
    if (!cfg_on("psd_limit", 0, "_psd_limit.txt")) return 0;
    fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (fh == INVALID_HANDLE_VALUE) return 0;
    if (!ReadFile(fh, head, 26, &got, 0) || got != 26 || memcmp(head, "8BPS", 4) != 0) {
        CloseHandle(fh);
        return 0;
    }
    ch = (head[12] << 8) | head[13];
    mode = (head[24] << 8) | head[25];
    {
        DWORD d = 0; long n;
        ReadFile(fh, &d, 4, &got, 0);
        n = (long)(((d) & 0xFF) << 24 | (((d) >> 8) & 0xFF) << 16 | (((d) >> 16) & 0xFF) << 8 | ((d) >> 24 & 0xFF));
        SetFilePointer(fh, n, 0, FILE_CURRENT);
        ReadFile(fh, &d, 4, &got, 0);
        n = (long)(((d) & 0xFF) << 24 | (((d) >> 8) & 0xFF) << 16 | (((d) >> 16) & 0xFF) << 8 | ((d) >> 24 & 0xFF));
        SetFilePointer(fh, n, 0, FILE_CURRENT);
    }
    { unsigned char z[8]; ReadFile(fh, z, 8, &got, 0); }
    { unsigned char c[2] = {0,0}; ReadFile(fh, c, 2, &got, 0);
      layers = (short)((c[0] << 8) | c[1]); if (layers < 0) layers = -layers; }
    CloseHandle(fh);
    note("PSD guard: %s 层=%d 通道=%d 模式=%d", path, layers, ch, mode);
    if (layers <= PSD_MAX_LAYERS) return 0;
    wsprintfA(msg, (const char *)g_cn_body,
              layers, PSD_MAX_LAYERS, PSD_MAX_LAYERS + 1, PSD_MAX_LAYERS);
    MessageBoxA(0, msg, (const char *)g_cn_title, MB_OK | MB_ICONWARNING);
    return 1;
}


/* ================= 非 ASCII 路径兼容 ================= */
static char g_alias_src[MAX_PATH];      /* 原始（含中文）路径 */
static char g_alias_dst[MAX_PATH];      /* 我们给程序的 ASCII 别名 */

static int has_non_ascii(const char *s)
{
    if (!s) return 0;
    for (; *s; s++) if ((unsigned char)*s >= 0x80) return 1;
    return 0;
}

static int ascii_alias(const char *src, char *out, int outsz)   /* alias_short_dir */
{
    char dir[MAX_PATH], name[MAX_PATH];
    const char *base = src, *q = src;
    int len;
    if (!cfg_val("ascii_alias", 1)) return 0;
    if (!src) return 0;
    len = lstrlenA(src);
    if (len <= 96) return 0;                     /* 短路径不用动 */

    /* 优先使用与源文件同驱动器的 ok3dtemp，以允许快速 CreateHardLink */
    if (src[1] == ':') {
        dir[0] = src[0]; dir[1] = ':'; dir[2] = '\\';
        lstrcpyA(dir + 3, "ok3dtemp\\");
        CreateDirectoryA(dir, NULL);
    } else {
        GetTempPathA(MAX_PATH, dir);
    }
    while (*q) { if (*q == '\\' || *q == '/') base = q + 1; q++; }
    lstrcpynA(name, base, MAX_PATH);
    if (lstrlenA(name) > 80) {                   /* 名字本身太长才退化成哈希名 */
        unsigned long hash = 2166136261UL;
        const char *dot = 0, *r;
        for (r = base; *r; r++) { if (*r == '.') dot = r; hash = (hash ^ (unsigned char)*r) * 16777619UL; }
        wsprintfA(name, "ok3d_ascii_%08lX%s", hash, dot ? dot : "");
    }
    lstrcpynA(out, dir, outsz - MAX_PATH / 2);
    lstrcatA(out, name);
    if (!lstrcmpiA(out, src)) return 0;
    DeleteFileA(out);
    if (!CreateHardLinkA(out, src, 0)) {
        if (!CopyFileA(src, out, FALSE)) {
            note("alias: 建立短路径失败 %s -> %s (err=%lu)", src, out, GetLastError());
            return 0;
        }
        note("alias: 复制 -> %s", out);
    } else {
        note("alias: 硬链接 -> %s（原名 %d 字符路径太长）", out, len);
    }
    lstrcpynA(g_alias_src, src, MAX_PATH);
    lstrcpynA(g_alias_dst, out, MAX_PATH);
    return 1;
}

static BOOL WINAPI e_gofna(void *p)
{
    if (p && cfg_on("gxwj", 1, "_gxwj.txt")) gxwj_patch_filter(p);
    if (capture_mode() && o_gofna) return ((BOOL (WINAPI *)(void *))o_gofna)(p);
    char *file = *(char **)((char *)p + 0x1C);
    unsigned maxfile = *(unsigned *)((char *)p + 0x20);
    if (g_iopen < g_nopen) {
        if (file && maxfile) lstrcpynA(file, g_opens[g_iopen], maxfile);
        if (file && maxfile && ascii_alias(g_opens[g_iopen], file, (int)maxfile)) {
            note("ascii_alias: 队列路径换成 %s", file);
        }
        if (psd_guard_dialog(g_opens[g_iopen])) {
            g_iopen++;
            if (g_iopen >= g_nopen) g_iopen = g_nopen - 1;
            return FALSE;
        }
        note("EMU gofn -> %s", g_opens[g_iopen]);
        g_iopen++;
        if (g_iopen >= g_nopen) g_iopen = g_nopen - 1;   /* repeat last */
        return TRUE;
    }
    note("EMU gofn exhausted");
    if (o_gofna) {
        if (p) *(DWORD *)((char *)p + 0x34) |= 0x00000008; /* OFN_NOCHANGEDIR */
        BOOL ok = ((BOOL (WINAPI *)(void *))o_gofna)(p);
        if (ok && file && psd_guard_dialog(file)) return FALSE;
        if (ok && file && maxfile && has_non_ascii(file)) {
            char alias[MAX_PATH];
            if (ascii_alias(file, alias, MAX_PATH))
                lstrcpynA(file, alias, maxfile);
        }
        return ok;
    }
    return FALSE;
}

/* ================= PSD 组装器（程序只写 3KB 骨架，这里补成完整 PSD） ================= */
static char g_psd_target[MAX_PATH];

static int psd_find_tempdir(char *out)
{
    static const char *tmpl = ":\\ok3dtemp\\vwd001.gjs";
    int d;
    char probe[MAX_PATH];
    for (d = 'C'; d <= 'Z'; d++) {
        probe[0] = (char)d;
        lstrcpyA(probe + 1, tmpl);          /* tmpl 以冒号开头 */
        if (GetFileAttributesA(probe) != INVALID_FILE_ATTRIBUTES) {
            lstrcpyA(out, "X:\\ok3dtemp\\");
            out[0] = (char)d;
            return 1;
        }
    }
    return 0;
}

static int psd_read_vwd(const char *dir, int idx, int w, int h, int *spp_out, unsigned char **pix)
{
    char path[MAX_PATH];
    HANDLE fh;
    DWORD got = 0;
    DWORD fsz = 0;
    unsigned long off = 332;
    int spp = (spp_out && *spp_out >= 3 && *spp_out <= 4) ? *spp_out : 3;
    unsigned long plane = (unsigned long)w * h;

    wsprintfA(path, "%svwd%03d.gjs", dir, idx);
    fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (fh == INVALID_HANDLE_VALUE) {
        wsprintfA(path, "%svwd%d.gjs", dir, idx);
        fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    }
    if (fh == INVALID_HANDLE_VALUE) return 0;
    fsz = GetFileSize(fh, 0);
    if (fsz == INVALID_FILE_SIZE || fsz < 1000) { CloseHandle(fh); return 0; }

    if (plane > 0) {
        if (fsz >= plane * 4 && (fsz - plane * 4) <= 2048) {
            spp = 4;
            off = fsz - plane * 4;
        } else if (fsz >= plane * 3 && (fsz - plane * 3) <= 2048) {
            spp = 3;
            off = fsz - plane * 3;
        }
    }
    if (spp_out) *spp_out = spp;

    unsigned long n = plane * spp;
    SetFilePointer(fh, off, 0, FILE_BEGIN);
    *pix = (unsigned char *)VirtualAlloc(0, n, MEM_COMMIT, PAGE_READWRITE);
    if (!*pix) { CloseHandle(fh); return 0; }
    if (!ReadFile(fh, *pix, n, &got, 0) || got != n) {
        CloseHandle(fh); VirtualFree(*pix, 0, MEM_RELEASE); *pix = 0; return 0;
    }
    CloseHandle(fh);
    return 1;
}

static int psd_read_alpha(const char *dir, int idx, int w, int h, unsigned char **alpha)
{
    char path[MAX_PATH];
    HANDLE fh;
    unsigned char head[54];
    DWORD got = 0;
    unsigned long off, stride, y;
    unsigned char *raw;
    wsprintfA(path, "%svwdt%03d.gjs", dir, idx);
    fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (fh == INVALID_HANDLE_VALUE) {
        wsprintfA(path, "%svwdt%d.gjs", dir, idx);
        fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    }
    if (fh == INVALID_HANDLE_VALUE) return 0;
    if (!ReadFile(fh, head, 54, &got, 0) || got != 54 || head[0] != 'B' || head[1] != 'M') {
        CloseHandle(fh); return 0;
    }
    off = *(unsigned long *)&head[10];
    stride = ((w * 8 / 8) + 3) & ~3u;
    raw = (unsigned char *)VirtualAlloc(0, stride * h, MEM_COMMIT, PAGE_READWRITE);
    *alpha = (unsigned char *)VirtualAlloc(0, (unsigned long)w * h, MEM_COMMIT, PAGE_READWRITE);
    if (!raw || !*alpha) { CloseHandle(fh); return 0; }
    SetFilePointer(fh, (LONG)off, 0, FILE_BEGIN);
    if (!ReadFile(fh, raw, stride * h, &got, 0)) { CloseHandle(fh); return 0; }
    CloseHandle(fh);
    for (y = 0; y < (unsigned long)h; y++) {
        memcpy(*alpha + y * w, raw + (h - 1 - y) * stride, w);
    }
    VirtualFree(raw, 0, MEM_RELEASE);
    return 1;
}


static int psd_count_views(const char *dir)
{
    int i, n = 0;
    for (i = 1; i <= 64; i++) {
        char p1[MAX_PATH], p2[MAX_PATH];
        wsprintfA(p1, "%svwd%03d.gjs", dir, i);
        wsprintfA(p2, "%svwdt%03d.gjs", dir, i);
        if (GetFileAttributesA(p1) == INVALID_FILE_ATTRIBUTES) break;
        if (GetFileAttributesA(p2) == INVALID_FILE_ATTRIBUTES) break;
        n = i;
    }
    return n;
}

static int psd_assemble(const char *out_path, const char *dir, int w, int h, int views)
{
    HANDLE fh;
    DWORD wr = 0;
    unsigned long plane = (unsigned long)w * h;
    int i, k;
    int spp = 3;
    unsigned short color_mode = 3;  /* 3 = RGB, 4 = CMYK */
    unsigned long name_pad, extra_len, rec_len, layer_info_len, lm_len;
    unsigned char hdr[64];
    unsigned char *pix = 0, *alpha = 0;
    char namebuf[100][8];

    {
        int avail = psd_count_views(dir);
        if (avail <= 0) {
            note("PSD build: 目录里没有 vwd*.gjs，放弃 (dir=%s)", dir ? dir : "(null)");
            return 0;
        }
        if (views != avail) {
            note("PSD build: 传入层数=%d，实际中间文件=%d → 以实际为准", views, avail);
            views = avail;
        }
    }
    if (views <= 0 || views > 64) return 0;

    /* Probe SPP from first view */
    {
        unsigned char *tmp_p = 0;
        if (psd_read_vwd(dir, 1, w, h, &spp, &tmp_p)) {
            if (tmp_p) VirtualFree(tmp_p, 0, MEM_RELEASE);
        }
        if (spp == 4) color_mode = 4;
    }
    int num_channels = spp + 1; /* Alpha + image channels */
    unsigned long chan_len = plane + 2;

    for (i = 0; i < views; i++) {
        wsprintfA(namebuf[i], "ghm%02d", i + 1);
    }
    name_pad = 4;
    extra_len = 4 + 4 + 8;
    rec_len = 16 + 2 + num_channels * 6 + 8 + 4 + 4 + extra_len;
    layer_info_len = 2 + (unsigned long)views * rec_len + (unsigned long)views * num_channels * chan_len;
    lm_len = 4 + layer_info_len + 4;

    fh = CreateFileA(out_path, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, 0, 0);
    if (fh == INVALID_HANDLE_VALUE) { note("PSD build: cannot create %s", out_path); return 0; }

    /* 头 + 颜色模式 + 图像资源 */
    memcpy(hdr, "8BPS", 4);
    hdr[4] = 0; hdr[5] = 1;
    memset(hdr + 6, 0, 6);
    hdr[12] = (unsigned char)(spp >> 8); hdr[13] = (unsigned char)spp;
    hdr[14] = (unsigned char)(h >> 24); hdr[15] = (unsigned char)(h >> 16);
    hdr[16] = (unsigned char)(h >> 8);  hdr[17] = (unsigned char)h;
    hdr[18] = (unsigned char)(w >> 24); hdr[19] = (unsigned char)(w >> 16);
    hdr[20] = (unsigned char)(w >> 8);  hdr[21] = (unsigned char)w;
    hdr[22] = 0; hdr[23] = 8;
    hdr[24] = (unsigned char)(color_mode >> 8); hdr[25] = (unsigned char)color_mode;
    WriteFile(fh, hdr, 26, &wr, 0);
    { unsigned char z[4] = {0,0,0,0}; WriteFile(fh, z, 4, &wr, 0); WriteFile(fh, z, 4, &wr, 0); }
    { unsigned char b[4] = {(unsigned char)(lm_len>>24),(unsigned char)(lm_len>>16),(unsigned char)(lm_len>>8),(unsigned char)lm_len};
      WriteFile(fh, b, 4, &wr, 0); }
    { unsigned char b[4] = {(unsigned char)(layer_info_len>>24),(unsigned char)(layer_info_len>>16),(unsigned char)(layer_info_len>>8),(unsigned char)layer_info_len};
      WriteFile(fh, b, 4, &wr, 0); }
    { unsigned char b[2] = {0, (unsigned char)views}; WriteFile(fh, b, 2, &wr, 0); }

    /* 层记录 */
    for (i = 0; i < views; i++) {
        unsigned char rec[128];
        int p = 0, c;
        rec[p++] = 0; rec[p++] = 0; rec[p++] = 0; rec[p++] = 0;           /* top */
        rec[p++] = 0; rec[p++] = 0; rec[p++] = 0; rec[p++] = 0;           /* left */
        rec[p++] = (unsigned char)(h >> 24); rec[p++] = (unsigned char)(h >> 16);
        rec[p++] = (unsigned char)(h >> 8);  rec[p++] = (unsigned char)h;
        rec[p++] = (unsigned char)(w >> 24); rec[p++] = (unsigned char)(w >> 16);
        rec[p++] = (unsigned char)(w >> 8);  rec[p++] = (unsigned char)w;
        rec[p++] = (unsigned char)(num_channels >> 8); rec[p++] = (unsigned char)num_channels;
        for (c = 0; c < num_channels; c++) {
            int cid = (c == 0) ? -1 : (c - 1);
            rec[p++] = (unsigned char)(cid >> 8); rec[p++] = (unsigned char)cid;
            rec[p++] = (unsigned char)(chan_len >> 24); rec[p++] = (unsigned char)(chan_len >> 16);
            rec[p++] = (unsigned char)(chan_len >> 8);  rec[p++] = (unsigned char)chan_len;
        }
        memcpy(rec + p, "8BIMnorm", 8); p += 8;
        rec[p++] = 255; rec[p++] = 0; rec[p++] = 0; rec[p++] = 0;
        rec[p++] = 0; rec[p++] = 0; rec[p++] = 0; rec[p++] = extra_len;
        rec[p++] = 0; rec[p++] = 0; rec[p++] = 0; rec[p++] = 0;           /* 蒙版 */
        rec[p++] = 0; rec[p++] = 0; rec[p++] = 0; rec[p++] = 0;           /* 混合范围 */
        rec[p++] = 5; memcpy(rec + p, namebuf[i], 5); p += 5;
        rec[p++] = 0; rec[p++] = 0;
        WriteFile(fh, rec, p, &wr, 0);
    }

    /* 每层通道：alpha(-1) + 分量通道 */
    for (i = 1; i <= views; i++) {
        int v_spp = 3;
        int okv = psd_read_vwd(dir, i, w, h, &v_spp, &pix);
        int oka = psd_read_alpha(dir, i, w, h, &alpha);
        if (!okv || !oka) {
            note("PSD build: 缺视图 %d (pix=%d alpha=%d)", i, okv, oka);
            if (pix) VirtualFree(pix, 0, MEM_RELEASE);
            if (alpha) VirtualFree(alpha, 0, MEM_RELEASE);
            CloseHandle(fh);
            return 0;
        }
        { unsigned char z[2] = {0,0};
          WriteFile(fh, z, 2, &wr, 0);
          WriteFile(fh, alpha, plane, &wr, 0); }
        for (k = 0; k < spp; k++) {
            unsigned long x;
            unsigned char *tmp = (unsigned char *)VirtualAlloc(0, plane, MEM_COMMIT, PAGE_READWRITE);
            if (!tmp) { VirtualFree(pix, 0, MEM_RELEASE); VirtualFree(alpha, 0, MEM_RELEASE); CloseHandle(fh); return 0; }
            for (x = 0; x < plane; x++) tmp[x] = pix[x * spp + k];
            { unsigned char z[2] = {0,0}; WriteFile(fh, z, 2, &wr, 0); }
            WriteFile(fh, tmp, plane, &wr, 0);
            VirtualFree(tmp, 0, MEM_RELEASE);
        }
        VirtualFree(pix, 0, MEM_RELEASE);
        VirtualFree(alpha, 0, MEM_RELEASE);
        note("PSD build: 层 %d/%d 完成", i, views);
    }
    { unsigned char z[4] = {0,0,0,0}; WriteFile(fh, z, 4, &wr, 0); }   /* 全局蒙版 */

    /* 合并图（第 1 个视图）*/
    if (psd_read_vwd(dir, 1, w, h, &spp, &pix)) {
        unsigned char *tmp = (unsigned char *)VirtualAlloc(0, plane, MEM_COMMIT, PAGE_READWRITE);
        if (tmp) {
            unsigned long x; int kk;
            for (kk = 0; kk < spp; kk++) {
                for (x = 0; x < plane; x++) tmp[x] = pix[x * spp + kk];
                { unsigned char z[2] = {0,0}; WriteFile(fh, z, 2, &wr, 0); }
                WriteFile(fh, tmp, plane, &wr, 0);
            }
            VirtualFree(tmp, 0, MEM_RELEASE);
        }
        VirtualFree(pix, 0, MEM_RELEASE);
    }
    CloseHandle(fh);
    note("PSD build: 完成 %s (spp=%d mode=%d)", out_path, spp, color_mode);
    return 1;
}

static DWORD WINAPI psd_rebuild_thread(LPVOID p)
{
    char dir[MAX_PATH];
    int w = 0, h = 0, views = 0, i;
    unsigned char head[64];
    HANDLE fh;
    DWORD got = 0;
    (void)p;
    /* 等程序把骨架写完：文件存在且连续两次大小不变（最多等 20 秒） */
    {
        unsigned long last = 0xFFFFFFFF, cur = 0;
        int stable = 0, tries;
        for (tries = 0; tries < 200; tries++) {
            HANDLE hf = CreateFileA(g_psd_target, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                    0, OPEN_EXISTING, 0, 0);
            cur = 0xFFFFFFFF;
            if (hf != INVALID_HANDLE_VALUE) {
                cur = GetFileSize(hf, 0);
                CloseHandle(hf);
            }
            if (cur == last && cur != 0xFFFFFFFF) {
                if (++stable >= 2) break;
            } else {
                stable = 0;
                last = cur;
            }
            Sleep(100);
        }
        note("PSD build: 骨架大小=%lu，开始补全", cur);
    }
    if (!psd_find_tempdir(dir)) { note("PSD build: 找不到 ok3dtemp"); return 0; }
    for (i = 1; i <= 64; i++) {
        char path[MAX_PATH];
        wsprintfA(path, "%svwd%03d.gjs", dir, i);
        if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) break;
        views = i;
    }
    wsprintfA((char *)head, "%svwdt001.gjs", dir);
    fh = CreateFileA((char *)head, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (fh == INVALID_HANDLE_VALUE) { note("PSD build: 没有 vwdt001"); return 0; }
    ReadFile(fh, head, 54, &got, 0);
    CloseHandle(fh);
    if (got == 54) { w = *(int *)&head[18]; h = *(int *)&head[22]; }
    note("PSD build: dir=%s views=%d w=%d h=%d", dir, views, w, h);
    if (views > 0 && w > 0 && h > 0) psd_assemble(g_psd_target, dir, w, h, views);
    return 0;
}

static void psd_maybe_schedule(const char *path)
{
    size_t n = lstrlenA(path);
    if (n > 4 && lstrcmpiA(path + n - 4, ".psd") == 0) {
        lstrcpynA(g_psd_target, path, MAX_PATH);
        CreateThread(0, 0, psd_rebuild_thread, 0, 0, 0);
        note("PSD build: 已排队 %s", path);
    }
}


/* ================= 原生 writepsd 替换 =================
 * 程序通过 GetProcAddress("writepsd") 拿到 zu06.dll 的导出地址；
 * 我们返回自己的实现，参数沿用 Delphi register 约定：
 *   参数1~3 在 EAX/EDX/ECX，其余在栈上（caller 清栈）。
 */

__attribute__((used)) typedef int (__stdcall *PF_WRITEPSD)(const char *, const char *, int, int, int, int, int, int, int, int);
static PF_WRITEPSD o_writepsd;

static char g_native_file[MAX_PATH], g_native_dir[MAX_PATH];
static volatile int g_main_closing = 0;

struct err_enum_ctx {
    DWORD pid;
    int closed;
};

static BOOL CALLBACK dismiss_app_err_cb(HWND w, LPARAM lp)
{
    struct err_enum_ctx *ctx = (struct err_enum_ctx *)lp;
    DWORD wpid = 0;
    char cls[64], title[128];
    if (!IsWindowVisible(w)) return TRUE;
    GetWindowThreadProcessId(w, &wpid);
    if (wpid != ctx->pid) return TRUE;
    cls[0] = 0; title[0] = 0;
    GetClassNameA(w, cls, sizeof(cls));
    GetWindowTextA(w, title, sizeof(title));
    if (lstrcmpA(cls, "#32770") == 0 && lstrcmpA(title, "Application Error") == 0) {
        PostMessageA(w, WM_COMMAND, IDOK, 0);
        PostMessageA(w, WM_CLOSE, 0, 0);
        ctx->closed++;
        note("AUTO_FIX: 自动关闭收尾弹窗 hwnd=%p", w);
    }
    return TRUE;
}

static int dismiss_app_error_dialog(void)
{
    struct err_enum_ctx ctx;
    ctx.pid = GetCurrentProcessId();
    ctx.closed = 0;
    EnumWindows(dismiss_app_err_cb, (LPARAM)&ctx);
    return ctx.closed;
}

int __stdcall writepsd_shim(const char *file, const char *dir,
                           int a3, int a4, int a5, int a6,
                           int layers, int w, int h, int spp)
{
    int r = 0;
    (void)a3; (void)a4; (void)a5; (void)a6; (void)spp;

    lstrcpynA(g_native_file, file ? file : "", MAX_PATH);
    lstrcpynA(g_native_dir, dir ? dir : "", MAX_PATH);

    note("NATIVE writepsd: file=%s dir=%s layers=%d w=%d h=%d spp=%d", 
         file ? file : "(null)", dir ? dir : "(null)", layers, w, h, spp);

    if (file && dir && layers > 0 && layers <= 64 && w > 0 && h > 0) {
        int avail = psd_count_views(dir);
        note("NATIVE writepsd: 当前可用切片数=%d (layers=%d)", avail, layers);
        psd_assemble(g_native_file, g_native_dir, w, h, avail > 0 ? avail : layers);
    }

    return r;
}

static void * WINAPI e_gpa(HMODULE mod, LPCSTR name)
{
    void *r = o_gpa ? o_gpa(mod, name) : 0;
    if (name && lstrcmpiA(name, "writepsd") == 0) {
        if (cfg_on("native_psd", 1, "_native_psd.txt")) {
            note("NATIVE writepsd: 拦截成功，返回本地实现 %p", (void *)writepsd_shim);
            return (void *)writepsd_shim;
        }
    }
    return r;
}

static BOOL WINAPI e_gsfn(void *p)
{
    if (capture_mode() && o_gsfn) return ((BOOL (WINAPI *)(void *))o_gsfn)(p);
    char *file = *(char **)((char *)p + 0x1C);
    unsigned maxfile = *(unsigned *)((char *)p + 0x20);
    /* 保存框不该继承 PSD 的 ASCII 别名（会跑到 ok3dtemp 且名字是哈希） */
    if (file && maxfile && g_alias_src[0]) {   /* alias_keep_suffix */
        const char *bn = file, *q = file;
        while (*q) { if (*q == '\\' || *q == '/') bn = q + 1; q++; }
        if (strncmp(bn, "ok3d_ascii_", 11) == 0) {
            const char *rest = bn + 11;
            const char *src = g_alias_src, *q2 = g_alias_src, *b2 = g_alias_src;
            char nm[MAX_PATH];
            int i = 0;
            int k;
            for (k = 0; k < 8 && rest[k]; k++) ;          /* 跳过 8 位哈希 */
            rest += k;
            while (*q2) { if (*q2 == '\\' || *q2 == '/') b2 = q2 + 1; q2++; }
            for (q2 = b2; *q2 && *q2 != '.' && i < MAX_PATH - 32; q2++) nm[i++] = *q2;
            nm[i] = 0;
            if (*rest) lstrcatA(nm, rest);                /* 保留程序加的后缀/扩展名 */
            else lstrcatA(nm, ".tif");
            lstrcpynA(file, nm, maxfile);
            note("gsfn: 别名 -> %s（保留后缀 %s）", nm, rest);
        }
    }
    if (g_isave < g_nsave) {
        if (file && maxfile) lstrcpynA(file, g_saves[g_isave], maxfile);
        note("EMU gsfn -> %s", g_saves[g_isave]);
        if (cfg_on("psd_build", 0, "_psd_build.txt"))
            psd_maybe_schedule(g_saves[g_isave]);
        g_isave++;
        if (g_isave >= g_nsave) g_isave = g_nsave - 1;
        return TRUE;
    }
    note("EMU gsfn exhausted");
    if (o_gsfn) {
        /* 防止系统保存框改变工作目录导致主程序找不到相对路径 DLL */
        if (p) *(DWORD *)((char *)p + 0x34) |= 0x00000008; /* OFN_NOCHANGEDIR */
        return ((BOOL (WINAPI *)(void *))o_gsfn)(p);
    }
    return FALSE;
}

static BOOL WINAPI e_ch(HANDLE h)
{
    if (is_dev_handle(h)) {
        int i;
        for (i = 0; i < g_ndev; i++) if (g_devs[i] == h) { g_devs[i] = g_devs[--g_ndev]; break; }
        note("EMU close dev handle");
    }
    return o_ch ? o_ch(h) : CloseHandle(h);
}

static void store_init(void)
{
    if (g_store_init) return;
    g_store_init = 1;
    memset(g_store, 0, sizeof(g_store));
    memcpy(g_store, K_RD9, 9);
    memcpy(g_store + 0x1A, K_BLOB26, 26);
}

static void make_dev_file(void)
{
    char inf[MAX_PATH], dev[MAX_PATH], buf[4096];
    FILE *f;
    HANDLE h;
    DWORD n = 0;
    lstrcpyA(inf, g_dir);
    lstrcatA(inf, "psdto3d104.inf");
    h = CreateFileA(inf, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0,
                    OPEN_EXISTING, 0, 0);
    n = 0;
    if (h != INVALID_HANDLE_VALUE) {
        ReadFile(h, buf + 26, sizeof(buf) - 32, &n, 0);
        CloseHandle(h);
    }
    if (n == 0) {                       /* 没有 INI 就退回记录里的默认值 */
        memset(buf + 26, 0, 203);
        n = 203;
    }
    memcpy(buf, K_BLOB26, 26);
    buf[26 + n] = 0x0C;
    lstrcpyA(dev, g_dir);
    lstrcatA(dev, "_dongle_dev.bin");
    f = fopen(dev, "wb");
    if (!f) return;
    fwrite(buf, 1, 27 + n, f);
    fclose(f);
}

static int g_cap = -1;
static int cap_io(void)
{
    static int v = -1;
    if (v < 0) {
        char cp[MAX_PATH];
        lstrcpyA(cp, g_dir);
        lstrcatA(cp, "_capio.txt");
        v = (GetFileAttributesA(cp) != INVALID_FILE_ATTRIBUTES) ? 1 : 0;
        note("EMU cap_io mode = %d", v);
    }
    return v;
}

static int capture_mode(void)
{
    if (g_cap < 0) {
        char cp[MAX_PATH];
        lstrcpyA(cp, g_dir); lstrcatA(cp, "_capture.txt");
        g_cap = (GetFileAttributesA(cp) != INVALID_FILE_ATTRIBUTES) ? 1 : 0;
        note("EMU capture mode = %d", g_cap);
    }
    return g_cap;
}


/* ================= 99 工程(.gxwj) 透明转换 ================= */
static int gxwj_read_psd(const char *path, int *w, int *h, int *layers)
{
    HANDLE fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    unsigned char head[26];
    DWORD got = 0;
    unsigned n;
    short cnt;
    if (fh == INVALID_HANDLE_VALUE) return 0;
    if (!ReadFile(fh, head, 26, &got, 0) || got != 26 ||
        memcmp(head, "8BPS", 4) != 0) { CloseHandle(fh); return 0; }
    *h = (head[14] << 24) | (head[15] << 16) | (head[16] << 8) | head[17];
    *w = (head[18] << 24) | (head[19] << 16) | (head[20] << 8) | head[21];
    { DWORD d = 0; ReadFile(fh, &d, 4, &got, 0); n = ((d&0xFF)<<24)|((d>>8&0xFF)<<16)|((d>>16&0xFF)<<8)|(d>>24&0xFF); }
    SetFilePointer(fh, n, 0, FILE_CURRENT);
    { DWORD d = 0; ReadFile(fh, &d, 4, &got, 0); n = ((d&0xFF)<<24)|((d>>8&0xFF)<<16)|((d>>16&0xFF)<<8)|(d>>24&0xFF); }
    SetFilePointer(fh, n, 0, FILE_CURRENT);
    { unsigned char z[8]; ReadFile(fh, z, 8, &got, 0); }
    { unsigned char c[2] = {0,0}; ReadFile(fh, c, 2, &got, 0);
      cnt = (short)((c[0] << 8) | c[1]); if (cnt < 0) cnt = -cnt; *layers = cnt; }
    CloseHandle(fh);
    return 1;
}


/* 在工程目录里尽量把 PSD 找出来 */

/* 把文件名主干规范化：1114 -1 / 1114(2) / 1114_3 / 1114  ->  1114 */
static void norm_stem(const char *name, char *out)
{
    char tmp[MAX_PATH];
    int len;
    const char *dot = 0, *q;
    lstrcpynA(tmp, name, MAX_PATH);
    for (q = tmp; *q; q++) if (*q == '.') dot = q;
    if (dot) tmp[(int)(dot - tmp)] = 0;
    len = lstrlenA(tmp);
    /* 去掉结尾的 (18) 这种括号尾巴 */
    if (len > 0 && tmp[len - 1] == ')') {
        int i;
        for (i = len - 2; i >= 0; i--) if (tmp[i] == '(') { len = i; break; }
        while (len > 0 && tmp[len - 1] == ' ') len--;
        tmp[len] = 0;
    }
    /* 去掉结尾的  -1 / -1 / _3 这种尾巴 */
    for (;;) {
        int cut = len;
        while (cut > 0 && tmp[cut - 1] >= '0' && tmp[cut - 1] <= '9') cut--;
        if (cut > 0 && cut < len &&
            (tmp[cut - 1] == ' ' || tmp[cut - 1] == '-' || tmp[cut - 1] == '_')) {
            cut--;
            while (cut > 0 && tmp[cut - 1] == ' ') cut--;
            len = cut;
            tmp[len] = 0;
            continue;
        }
        break;
    }
    while (len > 0 && (tmp[len - 1] == ' ' || tmp[len - 1] == '-' || tmp[len - 1] == '_')) tmp[--len] = 0;
    lstrcpynA(out, tmp, MAX_PATH);
}

static int gxwj_find_psd(const char *prjdir, const char *orig, char *out)
{
    char cand[MAX_PATH], stem[MAX_PATH], want[MAX_PATH];
    const char *b = orig, *q = orig;
    WIN32_FIND_DATAA fd;
    HANDLE hs;
    int n = 0;
    char only[MAX_PATH];

    while (*q) { if (*q == '\\' || *q == '/') b = q + 1; q++; }
    norm_stem(b, want);                              /* 目标主干 */

    /* 1) 原样同名 */
    wsprintfA(cand, "%s%s", prjdir, b);
    if (GetFileAttributesA(cand) != INVALID_FILE_ATTRIBUTES) { lstrcpynA(out, cand, MAX_PATH); return 1; }

    /* 2) 规范化后同名 */
    wsprintfA(cand, "%s*.psd", prjdir);
    hs = FindFirstFileA(cand, &fd);
    if (hs != INVALID_HANDLE_VALUE) {
        do {
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            n++;
            wsprintfA(only, "%s%s", prjdir, fd.cFileName);
            norm_stem(fd.cFileName, stem);
            if (!lstrcmpiA(stem, want)) {
                FindClose(hs);
                lstrcpynA(out, only, MAX_PATH);
                return 1;
            }
        } while (FindNextFileA(hs, &fd));
        FindClose(hs);
    }
    /* 3) 目录里只有一个 .psd */
    if (n == 1) { lstrcpynA(out, only, MAX_PATH); return 1; }
    return 0;
}


/* 把 a\\b\\\\c 这类重复分隔符压成一个 */
static void path_squeeze(const char *in, char *out, int outsz)
{
    int i = 0;
    int last_sep = 0;
    if (!in || !out || outsz <= 1) return;
    while (*in && i < outsz - 1) {
        if (*in == '\\' || *in == '/') {
            if (!last_sep) { out[i++] = '\\'; last_sep = 1; }
        } else {
            out[i++] = *in;
            last_sep = 0;
        }
        in++;
    }
    out[i] = 0;
}

static int gxwj_convert(const char *src, char *out, int outsz)
{
    HANDLE fh;
    DWORD size, got = 0;
    char *buf, *lines[4096];
    int nl = 0, i, w = 0, h = 0, layers = 0;
    char psdpath[MAX_PATH];
    HANDLE of;
    { char sq[MAX_PATH]; path_squeeze(src, sq, MAX_PATH); lstrcpynA((char *)src, sq, MAX_PATH); }
    fh = CreateFileA(src, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (fh == INVALID_HANDLE_VALUE) return 0;
    size = GetFileSize(fh, 0);
    if (size == 0 || size > 8 * 1024 * 1024) { CloseHandle(fh); return 0; }
    buf = (char *)VirtualAlloc(0, size + 1, MEM_COMMIT, PAGE_READWRITE);
    if (!buf) { CloseHandle(fh); return 0; }
    ReadFile(fh, buf, size, &got, 0);
    CloseHandle(fh);
    buf[got] = 0;

    /* 切行 */
    lines[nl++] = buf;
    for (i = 0; i < (int)got && nl < 4095; i++) {
        if (buf[i] == '\r' && i + 1 < (int)got && buf[i + 1] == '\n') {
            buf[i] = 0; buf[i + 1] = 0;
            lines[nl++] = buf + i + 2;
            i++;
        }
    }
    if (nl < 7) { VirtualFree(buf, 0, MEM_RELEASE); return 0; }
    if (lstrcmpA(lines[2], "39550 0 0 0") != 0 && strncmp(lines[2], "39550", 5) != 0) {
        VirtualFree(buf, 0, MEM_RELEASE);
        return 0;                     /* 不是 99 工程 */
    }

    /* PSD 路径：原样 → 同目录多种猜测（gxwj_find_psd） */
    lstrcpynA(psdpath, lines[0], MAX_PATH);
    if (GetFileAttributesA(psdpath) == INVALID_FILE_ATTRIBUTES) {
        char pdir[MAX_PATH], hit[MAX_PATH];
        const char *q0 = src, *b0 = src;
        while (*q0) { if (*q0 == '\\' || *q0 == '/') b0 = q0 + 1; q0++; }
        lstrcpynA(pdir, src, (int)(b0 - src) + 1);
        if (gxwj_find_psd(pdir, lines[0], hit)) {
            note("GXWJ: PSD 自动定位 %s -> %s", lines[0], hit);
            lstrcpynA(psdpath, hit, MAX_PATH);
        }
    }
    if (!gxwj_read_psd(psdpath, &w, &h, &layers)) {
        note("GXWJ: 读不到 PSD 头 (%s)，放弃转换", psdpath);
        VirtualFree(buf, 0, MEM_RELEASE);
        return 0;
    }

    /* 写转换结果：源文件没变就复用上次的产物，避免程序二次打开时文件被重写 */
    {
        static char gxwj_cached_src[MAX_PATH];
        static unsigned long gxwj_cached_size, gxwj_cached_time;
        HANDLE src2 = CreateFileA(src, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
        unsigned long sz = 0xFFFFFFFF, tm = 0;
        if (src2 != INVALID_HANDLE_VALUE) {
            sz = GetFileSize(src2, 0);
            {
                FILETIME ft;
                if (GetFileTime(src2, 0, 0, &ft)) tm = ft.dwLowDateTime;
            }
            CloseHandle(src2);
        }
        if (!lstrcmpiA(gxwj_cached_src, src) && sz == gxwj_cached_size &&
            tm == gxwj_cached_time) {
            wsprintfA(out, "%s_gxwj_conv.tw3d2", g_dir);
            if (GetFileAttributesA(out) != INVALID_FILE_ATTRIBUTES) {
                note("GXWJ: 复用上次转换结果 %s", out);
                VirtualFree(buf, 0, MEM_RELEASE);
                return 1;
            }
        }
        gxwj_cached_size = sz;
        gxwj_cached_time = tm;
        lstrcpynA(gxwj_cached_src, src, MAX_PATH);
    }
    wsprintfA(out, "%s_gxwj_conv.tw3d2", g_dir);
    of = CreateFileA(out, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, 0, 0);
    if (of == INVALID_HANDLE_VALUE) {
        char tmp[MAX_PATH];
        GetTempPathA(MAX_PATH, tmp);
        lstrcatA(tmp, "ok3d_gxwj_conv.tw3d2");
        of = CreateFileA(tmp, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, 0, 0);
        if (of != INVALID_HANDLE_VALUE) lstrcpynA(out, tmp, MAX_PATH);
    }
    if (of == INVALID_HANDLE_VALUE) { VirtualFree(buf, 0, MEM_RELEASE); return 0; }

    { char squeezed[MAX_PATH]; path_squeeze(psdpath, squeezed, MAX_PATH); lstrcpynA(psdpath, squeezed, MAX_PATH); }
    #define WLINE(p) WriteFile(of, (p), lstrlenA(p), &got, 0); WriteFile(of, "\r\n", 2, &got, 0)
    WLINE(psdpath);                       /* 0 路径 */
    WLINE(lines[1]);                      /* 1 参数 */
    { char t[128]; wsprintfA(t, "99100 %d %d %d", layers, w, h); WLINE(t); }
    WLINE(lines[3]);                      /* 3 banner1 */
    WLINE(lines[4]);                      /* 4 banner2 */
    WLINE("Author: ");                    /* 5 作者 */
    { char t[64]; SYSTEMTIME st;
      GetLocalTime(&st);
      wsprintfA(t, "%d/%d/%d %d:%02d:%02d", st.wYear, st.wMonth, st.wDay,
                st.wHour, st.wMinute, st.wSecond);
      WLINE(t); }                         /* 6 保存时间 */
    for (i = 6; i < nl; i++) {            /* 7+ DPI 行及其后 */
        if (i == nl - 1 && lines[i][0] == 0) break;
        WLINE(lines[i]);
    }
    #undef WLINE
    CloseHandle(of);
    VirtualFree(buf, 0, MEM_RELEASE);
    note("GXWJ: %s -> %s (层=%d %dx%d)", src, out, layers, w, h);
    return 1;
}


/* ================= PSD 层数上限保护（程序导入器只支持到 40 层） ================= */
static int psd_count_layers(const char *path, int *layers)
{
    HANDLE fh = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    unsigned char head[26];
    DWORD got = 0;
    short cnt;
    if (fh == INVALID_HANDLE_VALUE) return 0;
    if (!ReadFile(fh, head, 26, &got, 0) || got != 26 || memcmp(head, "8BPS", 4) != 0) {
        note("PSD count debug: %s 头部读取失败 (got=%lu)", path, (unsigned long)got);
        CloseHandle(fh);
        return 0;
    }
    {
        DWORD d = 0;
        ReadFile(fh, &d, 4, &got, 0);
        SetFilePointer(fh, (long)((((d) & 0xFF) << 24) | (((d) >> 8 & 0xFF) << 16) | (((d) >> 16 & 0xFF) << 8) | ((d) >> 24 & 0xFF)), 0, FILE_CURRENT);
        ReadFile(fh, &d, 4, &got, 0);
        SetFilePointer(fh, (long)((((d) & 0xFF) << 24) | (((d) >> 8 & 0xFF) << 16) | (((d) >> 16 & 0xFF) << 8) | ((d) >> 24 & 0xFF)), 0, FILE_CURRENT);
    }
    { unsigned char z[8]; ReadFile(fh, z, 8, &got, 0); }
    { unsigned char c[2] = {0, 0}; ReadFile(fh, c, 2, &got, 0);
      cnt = (short)((c[0] << 8) | c[1]);
      if (cnt < 0) cnt = -cnt;
      *layers = cnt; }
    note("PSD count debug: %s -> layers=%d", path, *layers);
    CloseHandle(fh);
    return 1;
}

static int psd_layers_guard(const char *name)
{
    static const char warn[] =
        "这个 PSD 有 %d 个图层，而程序的导入器最多只支持 40 层。\r\n\r\n"
        "继续导入会直接崩溃。请在 Photoshop 里合并部分图层，\r\n"
        "把图层数降到 40 以内再导入。";
    char msg[512];
    int layers = 0;
    if (!psd_count_layers(name, &layers)) return 0;
    wsprintfA(msg, warn, layers);
    MessageBoxA(0, msg, "图层数超出程序上限", MB_OK | MB_ICONWARNING);
    note("PSD guard: %s 有 %d 层 > 40，已拦截", name, layers);
    return 1;
}


/* ================= 工程文件 PSD 路径自动修复 ================= */
static int tw3d2_fix_psd(const char *prj, char *out, int outsz)
{
    HANDLE fh;
    DWORD got = 0, size;
    char *buf, line1[MAX_PATH], dir[MAX_PATH], cand[MAX_PATH];
    const char *b = prj, *q = prj;
    int i, len1;
    WIN32_FIND_DATAA fd;
    HANDLE hs;
    int found = 0;

    fh = CreateFileA(prj, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
    if (fh == INVALID_HANDLE_VALUE) return 0;
    size = GetFileSize(fh, 0);
    if (size == 0 || size > 4 * 1024 * 1024) { CloseHandle(fh); return 0; }
    buf = (char *)VirtualAlloc(0, size + 2, MEM_COMMIT, PAGE_READWRITE);
    if (!buf) { CloseHandle(fh); return 0; }
    ReadFile(fh, buf, size, &got, 0);
    CloseHandle(fh);
    buf[got] = 0;

    len1 = 0;
    while (len1 < (int)got && buf[len1] != '\r' && buf[len1] != '\n') len1++;
    if (len1 <= 0 || len1 >= MAX_PATH) { VirtualFree(buf, 0, MEM_RELEASE); return 0; }
    memcpy(line1, buf, len1); line1[len1] = 0;
    if (GetFileAttributesA(line1) != INVALID_FILE_ATTRIBUTES) {
        VirtualFree(buf, 0, MEM_RELEASE);
        return 0;                       /* PSD 存在，不动 */
    }

    /* 工程所在目录 */
    while (*q) { if (*q == '\\' || *q == '/') b = q + 1; q++; }
    lstrcpynA(dir, prj, (int)(b - prj) + 1);

    /* 1) 同名 .psd */
    {
        const char *lb = line1, *r = line1;
        while (*r) { if (*r == '\\' || *r == '/') lb = r + 1; r++; }
        lstrcpynA(cand, dir, MAX_PATH - 8);
        lstrcatA(cand, lb);
        if (lstrlenA(cand) <= 4 || lstrcmpiA(cand + lstrlenA(cand) - 4, ".psd") != 0) {
            lstrcatA(cand, ".psd");
        }
        if (GetFileAttributesA(cand) != INVALID_FILE_ATTRIBUTES) found = 1;
    }
    /* 2) 目录里只有一个 .psd 就用它 */
    if (!found) {
        wsprintfA(cand, "%s*.psd", dir);
        hs = FindFirstFileA(cand, &fd);
        if (hs != INVALID_HANDLE_VALUE) {
            int n = 0;
            char only[MAX_PATH];
            do {
                if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
                    n++;
                    lstrcpynA(only, dir, MAX_PATH - 8);
                    lstrcatA(only, fd.cFileName);
                }
            } while (FindNextFileA(hs, &fd));
            FindClose(hs);
            if (n == 1) { lstrcpynA(cand, only, MAX_PATH); found = 1; }
        }
    }
    if (!found) {
        note("tw3d2: %s 里写的 PSD 不存在（%s），同目录也没找到对应文件", prj, line1);
        VirtualFree(buf, 0, MEM_RELEASE);
        return 0;
    }

    /* 写修复副本：替换第一行 */
    wsprintfA(out, "%s_psdfix.tw3d2", g_dir);
    {
        HANDLE of = CreateFileA(out, GENERIC_WRITE, FILE_SHARE_READ, 0, CREATE_ALWAYS, 0, 0);
        DWORD wr = 0;
        if (of == INVALID_HANDLE_VALUE) { VirtualFree(buf, 0, MEM_RELEASE); return 0; }
        WriteFile(of, cand, lstrlenA(cand), &wr, 0);
        WriteFile(of, buf + len1, got - len1, &wr, 0);
        CloseHandle(of);
    }
    note("tw3d2: PSD 路径修复 %s -> %s（工程 %s）", line1, cand, prj);
    VirtualFree(buf, 0, MEM_RELEASE);
    return 1;
}

static HANDLE WINAPI e_cfa(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                           DWORD disp, DWORD flags, HANDLE tmpl)
{
    char p[MAX_PATH];
    HANDLE h;
    if (cap_io() && is_dongle_path(name)) {
        /* 设备路径直通真狗；普通文件仍要走 gxwj 转换/路径修复 */
        note("CAP cfa(dev) %s acc=%08lX share=%lX disp=%lu", name, acc, share, disp);
        h = o_cfa(name, acc, share, sa, disp, flags, tmpl);
        note("CAP cfa(dev) -> %p", h);
        return h;
    }
    if (name) {
        int l2 = lstrlenA(name);
        if (l2 > 4 && lstrcmpiA(name + l2 - 4, ".psd") == 0)
            note("PSD open seen: %s (limit=%d)", name,
                 cfg_on("psd_limit", 0, "_psd_limit.txt"));
    }
    if (name && cfg_on("psd_limit", 0, "_psd_limit.txt")) {
        int len = lstrlenA(name);
        if (len > 4 && lstrcmpiA(name + len - 4, ".psd") == 0 && psd_layers_guard(name))
            return INVALID_HANDLE_VALUE;
    }
    if (name) {                       /* tw3d2_fix_psd: 工程里 PSD 路径失效时自动修复 */
        int l3 = lstrlenA(name);
        if ((l3 > 6 && lstrcmpiA(name + l3 - 6, ".tw3d2") == 0) ||
            (l3 > 5 && lstrcmpiA(name + l3 - 5, ".tw3d") == 0)) {
            char fixed[MAX_PATH];
            if (tw3d2_fix_psd(name, fixed, MAX_PATH)) {
                HANDLE hf2 = o_cfa(fixed, GENERIC_READ | GENERIC_WRITE,
                                   FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, 0, 0);
                if (hf2 != INVALID_HANDLE_VALUE) {
                    note("tw3d2: 打开修复后的工程 %s", fixed);
                    return hf2;
                }
            }
        }
    }
    if (name && cfg_on("gxwj", 1, "_gxwj.txt")) {
        int len = lstrlenA(name);
        if (len > 5 && lstrcmpiA(name + len - 5, ".gxwj") == 0) {
            char conv[MAX_PATH];
            if (gxwj_convert(name, conv, MAX_PATH)) {
                /* GXWJ open safe: 只用只读+共享+OPEN_EXISTING，绝不截断程序正在读的文件 */
                HANDLE hc = o_cfa(conv, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                  0, OPEN_EXISTING, 0, 0);
                note("GXWJ open safe: %s -> %p", conv, hc);
                return hc;
            }
        }
    }
    if (is_dongle_path(name)) {
        if (cfg_on("gate_map", 0, "_gate_map.txt")) {
            void *ret = __builtin_return_address(0);
            const char *b = "?";
            char path[MAX_PATH];
            HMODULE hm = NULL;
            if (GetModuleHandleExA(0x6, (LPCSTR)ret, &hm) && hm &&
                GetModuleFileNameA(hm, path, MAX_PATH)) {
                const char *q = path;
                b = path;
                while (*q) { if (*q == '\\' || *q == '/') b = q + 1; q++; }
            }
            note("GATE[%s+%X] open %s", b, (unsigned)((char *)ret - (char *)hm), name);
        }
        lstrcpyA(p, g_dir);
        lstrcatA(p, "_dongle_dev.bin");
        h = CreateFileA(p, GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE, 0,
                        OPEN_EXISTING, 0, 0);
        if (h == INVALID_HANDLE_VALUE) {
            make_dev_file();
            h = CreateFileA(p, GENERIC_READ | GENERIC_WRITE,
                            FILE_SHARE_READ | FILE_SHARE_WRITE, 0,
                            OPEN_EXISTING, 0, 0);
        }
        g_dev = h;
        g_pos = 0;
        if (g_ndev < 24) g_devs[g_ndev++] = h;
        note("EMU open device <- %s -> %p", name, h);
        return h;
    }
    {
        static char seen[64][128];
        static int nseen;
        int i;
        for (i = 0; i < nseen; i++) if (!lstrcmpiA(seen[i], name)) break;
        if (i == nseen && nseen < 64) {
            lstrcpynA(seen[nseen], name, 128); nseen++;
            note("cfa %s", name);
        }
    }
    return o_cfa(name, acc, share, sa, disp, flags, tmpl);
}

static void fill(unsigned char *dst, const unsigned char *src, unsigned n, unsigned want)
{
    unsigned i;
    for (i = 0; i < n; i++) dst[i] = src[i];
    for (; i < want; i++) dst[i] = 0;
}

static unsigned long g_real_base;
static unsigned long g_zu06_base;
static HANDLE WINAPI e_cfa_logonly(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
static BOOL WINAPI e_wf_logonly(HANDLE, LPCVOID, DWORD, LPDWORD, LPOVERLAPPED);
static void sbp_arm_real(void);
static void ensure_real_patched(void);
static unsigned g_last_cmd_addr = 0;
static unsigned g_cnt_002a = 0;

static BOOL WINAPI e_dio(HANDLE h, DWORD code, LPVOID in, DWORD inlen, LPVOID out,
                         DWORD outlen, LPDWORD ret, LPOVERLAPPED ov)
{    unsigned char *p = (unsigned char *)in;
    if (cap_io()) {
        BOOL ok;
        unsigned char *q = (unsigned char *)in;
        ok = o_dio ? o_dio(h, code, in, inlen, out, outlen, ret, ov) : FALSE;
        note("CAP dio code=%08lX in=%lu out=%lu ret=%lu ok=%d", code, inlen, outlen,
             ret ? *ret : 0, ok);
        if (q && inlen >= 0x2C && *(unsigned short *)q == 0x002C) {
            unsigned op = q[28];
            unsigned addr = q[30] | (q[31] << 8);
            unsigned dtl = *(unsigned *)&q[12];
            void *db = *(void **)&q[20];
            note("CAP dio op=%02X addr=%04X dtl=%lu", op, addr, dtl);
            if (db && dtl && dtl <= 501 && !IsBadReadPtr(db, dtl)) {
                char *hx = (char *)LocalAlloc(0x40, dtl * 2 + 8);
                if (hx) {
                    unsigned k;
                    for (k = 0; k < dtl; k++) wsprintfA(hx + k * 2, "%02X", ((unsigned char *)db)[k]);
                    hx[dtl * 2] = 0;
                    note("CAP pay op=%02X addr=%04X len=%lu data=%s", op, addr, dtl, hx);
                    LocalFree(hx);
                }
            }
        }
        if (out && ret && *ret && *ret <= outlen) {
            char hx[200]; unsigned k; unsigned lim = *ret < 64 ? *ret : 64;
            for (k = 0; k < lim; k++) wsprintfA(hx + k * 2, "%02X", ((unsigned char *)out)[k]);
            hx[lim * 2] = 0;
            note("CAP dio out[%lu]=%s", (unsigned long)*ret, hx);
        }
        return ok;
    }
    unsigned char op, dash;
    unsigned dtl;
    void *dbuf;
    unsigned addr;
    {
        static int ndio;
        if (ndio < 40 && code != 0x0004D014) {
            ndio++;
            note("dio h=%p code=0x%08X inlen=%u (h==dev:%d)", h, code, inlen, h == g_dev);
        }
    }
    if (is_dev_handle(h)) {
        if (!(in && inlen >= 0x2C && *(unsigned short *)in == 0x002C)) {
            if (out && outlen) memset(out, 0, outlen);
            if (ret) *ret = outlen;
            note("EMU ioctl fake-ok code=0x%08X outlen=%u", code, outlen);
            return TRUE;
        }
        op = p[28];
        addr = p[30] | (p[31] << 8);
        dash = p[8];
        dtl = *(unsigned *)&p[12];
        dbuf = *(void **)&p[20];
        p[2] = 0;                        /* ScsiStatus = 0 */
        if (ret) *ret = 0;
        if (!dbuf || IsBadWritePtr(dbuf, dtl ? dtl : 1)) {
            note("EMU ioctl op=%02X addr=%04X dtl=%u dash=%u  bad buffer", op, addr, dtl, dash);
            return TRUE;
        }
        store_init();
        if (addr == 0x00C2 && op == 0xDD) ensure_real_patched();
        if (op == 0xDD && dtl == 0) {
            note("EMU zero-write addr=%04X -> ACK", addr);
            return TRUE;
        }
        if (op == 0xDD) {                /* write at address; record cmd state and store payload */
            if (addr == 0x001A || addr == 0x003A || addr == 0x002A || addr == 0x00C2 || addr == 0x0012) {
                g_last_cmd_addr = addr;
                if (addr == 0x001A) g_cnt_002a = 0;
                else if (addr == 0x002A) g_cnt_002a++;
            }
            if (addr < 1049088 && dtl <= 1049088 - addr - 5) {
                memcpy(g_store + addr, dbuf, dtl);
                memcpy(g_store + addr + dtl, K_ACK5, 5);
            }
            if (dtl == 496) { memcpy(g_rec, dbuf, 496); }
            return TRUE;
        }
        if (op == 0xD1) {                /* stateless repeatable dongle read */
            unsigned i;
            unsigned long a;
            unsigned char *b = (unsigned char *)dbuf;
            if (dtl == 9 && addr == 0x0000) {
                memcpy(b, g_rp[12].data, 9);
                if (ret) *ret = 9;
                return TRUE;
            }
            if (dtl == 5) {
                if (addr == 0x01F0) {
                    b[0]=0xFB; b[1]=0x00; b[2]=0x00; b[3]=0x00; b[4]=0x00;
                } else if (addr == 0x001A || addr == 0x003A || addr == 0x002A || addr == 0x00C2 || addr == 0x0012) {
                    b[0]=0xFB; b[1]=0x01; b[2]=0x00; b[3]=0x48; b[4]=0x01;
                } else {
                    memcpy(b, K_ACK5, 5);
                }
                if (ret) *ret = 5;
                return TRUE;
            }
            if (dtl == 501 && addr == 0x000A) {
                int idx = 5;
                if (g_last_cmd_addr == 0x001A) idx = 5;
                else if (g_last_cmd_addr == 0x003A) idx = 24;
                else if (g_last_cmd_addr == 0x002A) {
                    static const int tbl_2a[4] = {30, 36, 42, 48};
                    unsigned k2a = (g_cnt_002a > 0) ? (g_cnt_002a - 1) : 0;
                    if (k2a > 3) k2a = 3;
                    idx = tbl_2a[k2a];
                } else if (g_last_cmd_addr == 0x00C2) idx = 54;
                else if (g_last_cmd_addr == 0x0012) idx = 66;
                memcpy(b, g_rp[idx].data, 501);
                if (ret) *ret = 501;
                note("EMU statereplay R cmd=%04X idx=%d", g_last_cmd_addr, idx);
                return TRUE;
            }
            for (i = 0; i < dtl; i++) {
                a = addr + i;
                b[i] = (a < 1049088) ? g_store[a] : 0xFB;
            }
            if (ret) *ret = dtl;
            return TRUE;
        }
        note("EMU ioctl op=%02X addr=%04X dtl=%u (passthrough)", op, addr, dtl);
        return TRUE;
    }
    return o_dio(h, code, in, inlen, out, outlen, ret, ov);
}

static BOOL WINAPI e_rf(HANDLE h, LPVOID buf, DWORD n, LPDWORD got, LPOVERLAPPED ov)
{
    unsigned long i;
    unsigned char *b;
    if (cap_io() && !is_dev_handle(h)) {
        BOOL r;
        if (got) *got = 0;
        r = o_rf ? o_rf(h, buf, n, got, ov) : FALSE;
        {
            const unsigned char *bb = (const unsigned char *)buf;
            char hx[1200]; unsigned long k; unsigned long lim = (got && *got) ? *got : 0;
            if (lim > 501) lim = 501;
            if (bb) { for (k = 0; k < lim; k++) wsprintfA(hx + k * 2, "%02X", bb[k]); hx[lim * 2] = 0; }
            else hx[0] = 0;
            note("CAP rf n=%lu got=%lu data=%s", (unsigned long)n, got ? *got : 0, hx);
        }
        return r;
    }
    if (is_dev_handle(h)) {
        b = (unsigned char *)buf;
        if (n == 16) {
            static const unsigned char rcpt[16] = {0xFB,0x01,0x00,0x48,0x01,0,0,0,0,0,0,0,0,0,0,0};
            memcpy(b, rcpt, 16);
            if (got) *got = 16;
            note("EMU rf n=16 -> FB01004801 receipt (pos=%lu)", g_pos);
            return TRUE;
        }
        if (n == 496) {
            /* DLL-side geometry decode: answer with the captured export-session record */
            memcpy(b, g_501resp[3], 496);
            if (got) *got = 496;
            note("EMU rf n=496 -> captured export record (pos=%lu)", g_pos);
            g_pos += 496;
            return TRUE;
        }
        if (n == 501 && g_501idx < 4) {
            memcpy(b, g_501resp[g_501idx], 501);
            if (got) *got = 501;
            note("EMU rf n=501 -> captured resp %d", g_501idx);
            g_501idx++;
            return TRUE;
        }
        for (i = 0; i < n; i++) {
            unsigned long a = g_pos + i;
            b[i] = (a < 1049088) ? g_store[a] : 0xFB;
        }
        if (got) *got = n;
        {
            char hx[128]; unsigned long k;
            unsigned long lim = n < 16 ? n : 16;
            for (k = 0; k < lim; k++) {
                unsigned long a = g_pos + k;
                wsprintfA(hx + k * 2, "%02X", (a < 1049088) ? g_store[a] : 0xFB);
            }
            hx[lim * 2] = 0;
            note("EMU rf n=%lu pos=%lu data=%s", (unsigned long)n, g_pos, hx);
        }
        g_pos += n;
        return TRUE;
    }
    return o_rf ? o_rf(h, buf, n, got, ov) : FALSE;
}

static BOOL WINAPI e_wf(HANDLE h, LPCVOID buf, DWORD n, LPDWORD got, LPOVERLAPPED ov)
{
    unsigned long i;
    const unsigned char *b;
    if (cfg_on("exe_wf_log", 0, "_exe_wf_log.txt") && !is_dev_handle(h)) {
        const unsigned char *q = (const unsigned char *)buf;
        if (n >= 4096 && q && !IsBadReadPtr((void *)buf, 8)) {
            note("EXEWF n=%lu hdr=%02X%02X%02X%02X", (unsigned long)n, q[0], q[1], q[2], q[3]);
        }
    }
    if (cap_io() && !is_dev_handle(h)) {
        BOOL r;
        if (got) *got = 0;
        r = o_wf ? o_wf(h, buf, n, got, ov) : FALSE;
        {
            const unsigned char *bb = (const unsigned char *)buf;
            char hx[1200]; unsigned long k; unsigned long lim = n < 501 ? n : 501;
            if (bb) { for (k = 0; k < lim; k++) wsprintfA(hx + k * 2, "%02X", bb[k]); hx[lim * 2] = 0; }
            else hx[0] = 0;
            note("CAP wf n=%lu got=%lu data=%s", (unsigned long)n, got ? *got : 0, hx);
        }
        return r;
    }
    if (is_dev_handle(h)) {
        b = (const unsigned char *)buf;
        for (i = 0; i < n; i++) {
            unsigned long a = g_pos + i;
            if (a < 1049088) g_store[a] = b[i];
        }
        if (got) *got = n;
        {
            char hx[128]; unsigned long k;
            unsigned long lim = n < 16 ? n : 16;
            for (k = 0; k < lim; k++) wsprintfA(hx + k * 2, "%02X", b[k]);
            hx[lim * 2] = 0;
            note("EMU wf n=%lu pos=%lu cmd=%s", (unsigned long)n, g_pos, hx);
        }
        g_pos += n;
        return TRUE;
    }
    return o_wf ? o_wf(h, buf, n, got, ov) : FALSE;
}

static DWORD WINAPI e_sfp(HANDLE h, LONG lo, PLONG hi, DWORD method)
{
    if (is_dev_handle(h)) {
        if (method == 0) g_pos = (unsigned long)lo;
        else if (method == 1) g_pos += (unsigned long)lo;
        else if (method == 2) g_pos = 1049088 - (unsigned long)lo;
        note("EMU sfp method=%u -> pos=%lu", method, g_pos);
        return (DWORD)g_pos;
    }
    return o_sfp ? o_sfp(h, lo, hi, method) : 0xFFFFFFFF;
}

static DWORD WINAPI e_gfs(HANDLE h, LPDWORD hi)
{
    return o_gfs ? o_gfs(h, hi) : 0xFFFFFFFF;
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

/* ---- VEH software breakpoints: reliable even when Delphi SEH eats SIGTRAP ---- */
typedef struct { unsigned long va; unsigned char orig; int hits; } SBP;
static SBP g_sbp[24];
static int g_nsbp;
static int g_armed = -1;
static void *g_veh;

static unsigned long g_real_base;

static void sbp_arm(unsigned long va)
{
    unsigned char *pp = (unsigned char *)va;
    DWORD old;
    if (!cfg_val("exe_patches", 1)) return;      /* exe_patches: 0 = 不动目标 exe */
    if (g_nsbp >= 24) return;
    if (VirtualProtect(pp, 1, PAGE_EXECUTE_READWRITE, &old)) {
        g_sbp[g_nsbp].va = va;
        g_sbp[g_nsbp].orig = *pp;
        g_sbp[g_nsbp].hits = 0;
        *pp = 0xCC;
        VirtualProtect(pp, 1, old, &old);
        note("SBp armed %08lX orig=%02X", va, g_sbp[g_nsbp].orig);
        g_nsbp++;
    }
}

static int (WINAPI *o_wsastartup)(unsigned short, void *);
static void *(WINAPI *o_ghbn)(const char *);
static unsigned int (WINAPI *o_sock)(int, int, int);
static int (WINAPI *o_conn)(unsigned int, const void *, int);
static int WINAPI e_wsastartup(unsigned short v, void *d)
{
    int r = o_wsastartup ? o_wsastartup(v, d) : 0;
    note("WSK WSAStartup v=%u -> %d", v, r);
    return r;
}
static void *WINAPI e_ghbn(const char *n)
{
    void *r = o_ghbn ? o_ghbn(n) : 0;
    note("WSK gethostbyname [%s] -> %p", n ? n : "(null)", r);
    return r;
}
static unsigned int WINAPI e_sock(int a, int b, int c)
{
    unsigned int r = o_sock ? o_sock(a, b, c) : 0xFFFFFFFFu;
    note("WSK socket(%d,%d,%d) -> %u", a, b, c, r);
    return r;
}
static int WINAPI e_conn(unsigned int sk, const void *addr, int len)
{
    const unsigned char *p = (const unsigned char *)addr;
    int r;
    char desc[64];
    if (p && len >= 8)
        wsprintfA(desc, "fam=%u port=%u ip=%u.%u.%u.%u", p[0] | (p[1] << 8),
                  (p[2] << 8) | p[3], p[4], p[5], p[6], p[7]);
    else lstrcpyA(desc, "?"); 
    r = o_conn ? o_conn(sk, addr, len) : -1;
    note("WSK connect s=%u %s -> %d", sk, desc, r);
    return r;
}

static int g_real_patched;
static void patch_real_module(HMODULE m)
{
    char np[MAX_PATH];
    if (!m || g_real_patched) return;
    g_real_patched = 1;
    lstrcpyA(np, g_dir); lstrcatA(np, "_nopatch_real.txt");
    if (GetFileAttributesA(np) != INVALID_FILE_ATTRIBUTES) {
        note("EMU skip real-dll IAT patch (_nopatch_real.txt)");
        return;
    }
    patch_slot((void *)m, 0x903D8, (void *)e_cfa,  (void **)&o_cfa);
    patch_slot((void *)m, 0x903C8, (void *)e_dio,  (void **)&o_dio);
    patch_slot((void *)m, 0x902D0, (void *)e_rf,   (void **)&o_rf);
    patch_slot((void *)m, 0x901F0, (void *)e_wf,   (void **)&o_wf);
    patch_slot((void *)m, 0x90290, (void *)e_wf,   (void **)&o_wf);
    patch_slot((void *)m, 0x902B0, (void *)e_sfp,  (void **)&o_sfp);
    patch_slot((void *)m, 0x90374, (void *)e_gfs,  (void **)&o_gfs);
    patch_slot((void *)m, 0x903E4, (void *)e_ch,   (void **)&o_ch);
    patch_slot((void *)m, 0x9084C, (void *)e_sddil,  (void **)&o_sddil);
    patch_slot((void *)m, 0x90850, (void *)e_sddida, (void **)&o_sddida);
    patch_slot((void *)m, 0x90854, (void *)e_sdeif,  (void **)&o_sdeif);
    patch_slot((void *)m, 0x90858, (void *)e_sdgcd,  (void **)&o_sdgcd);
    patch_slot((void *)m, 0x90838, (void *)e_wsastartup, (void **)&o_wsastartup);
    patch_slot((void *)m, 0x90828, (void *)e_ghbn,        (void **)&o_ghbn);
    patch_slot((void *)m, 0x90834, (void *)e_sock,        (void **)&o_sock);
    patch_slot((void *)m, 0x90824, (void *)e_conn,        (void **)&o_conn);
    {
        char ff[MAX_PATH];
        lstrcpyA(ff, g_dir); lstrcatA(ff, "_force_licflag.txt");
        if (GetFileAttributesA(ff) != INVALID_FILE_ATTRIBUTES) {
            *(volatile int *)((char *)m + 0x88124) = 1;
            note("EMU forced [0x488124]=1");
        }
    }
    note("EMU patched real dll IAT base=%p", m);
}

static int g_real_hooks_installed;

static int install_inline_hook(void *target, const unsigned char *expected, size_t nbytes,
                               void (__cdecl *cb)(unsigned long ebp))
{
    unsigned char *src = (unsigned char *)target;
    unsigned char *tramp;
    DWORD oldp;
    size_t pos = 0;
    long rel;
    if (!src || nbytes < 5 || nbytes > 16 || IsBadReadPtr(src, nbytes)) {
        note("HOOK bad target=%p n=%u", target, (unsigned)nbytes);
        return 0;
    }
    if (memcmp(src, expected, nbytes) != 0) {
        note("HOOK mismatch at %p: %02X %02X %02X %02X", target, src[0], src[1], src[2], src[3]);
        return 0;
    }
    tramp = (unsigned char *)VirtualAlloc(NULL, 128, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tramp) return 0;
    tramp[pos++] = 0x60; /* pushad */
    tramp[pos++] = 0x9C; /* pushfd */
    tramp[pos++] = 0x55; /* push ebp */
    tramp[pos++] = 0xE8; /* call cb */
    rel = (long)((unsigned char *)cb - (tramp + pos + 4));
    memcpy(tramp + pos, &rel, 4); pos += 4;
    tramp[pos++] = 0x83; tramp[pos++] = 0xC4; tramp[pos++] = 0x04; /* add esp, 4 */
    tramp[pos++] = 0x9D; /* popfd */
    tramp[pos++] = 0x61; /* popad */
    memcpy(tramp + pos, src, nbytes); pos += nbytes;
    tramp[pos++] = 0xE9; /* jmp back */
    rel = (long)((src + nbytes) - (tramp + pos + 4));
    memcpy(tramp + pos, &rel, 4); pos += 4;
    if (!VirtualProtect(src, nbytes, PAGE_EXECUTE_READWRITE, &oldp)) {
        VirtualFree(tramp, 0, MEM_RELEASE);
        return 0;
    }
    src[0] = 0xE9;
    rel = (long)(tramp - (src + 5));
    memcpy(src + 1, &rel, 4);
    for (pos = 5; pos < nbytes; pos++) src[pos] = 0x90;
    VirtualProtect(src, nbytes, oldp, &oldp);
    FlushInstructionCache(GetCurrentProcess(), src, nbytes);
    FlushInstructionCache(GetCurrentProcess(), tramp, 128);
    note("HOOK installed %p -> tramp=%p cb=%p", target, tramp, cb);
    return 1;
}

static void __cdecl hook_merg_7f9bf(unsigned long ebp)
{
    double x1 = 0.0, x2 = 0.0;
    int dpi = 0, lpi = 0, w_in = 0, h_in = 0, real_w = 0, real_h = 0;
    unsigned char fmt = 0;
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp - 0x1b0), &x1, 8, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp - 0x1b8), &x2, 8, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp + 0x0C), &dpi, 4, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp + 0x14), &lpi, 4, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp + 0x1C), &w_in, 4, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp + 0x24), &h_in, 4, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp + 0x2C), &fmt, 1, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)0x5230D0, &real_w, 4, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)0x5230D4, &real_h, 4, NULL);

    if (dpi <= 0) {
        dpi = 720000;
        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp + 0x0C), &dpi, 4, NULL);
    }
    if (lpi <= 0) {
        lpi = 3200;
        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp + 0x14), &lpi, 4, NULL);
    }
    if (w_in <= 0 || (double)w_in * (double)lpi < 10000.0) {
        w_in = (10000 / lpi) + 1;
        if (w_in < 100) w_in = 100;
        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp + 0x1C), &w_in, 4, NULL);
    }
    if (h_in <= 0) {
        h_in = 100;
        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp + 0x24), &h_in, 4, NULL);
    }
    if (fmt < 1) {
        fmt = 1;
        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp + 0x2C), &fmt, 1, NULL);
    }
    if (x2 <= 0.0 || x2 < (double)fmt * 16.0) {
        double calc = (real_h > 0) ? (double)real_h : ((double)h_in * (double)dpi / 1000000.0);
        if (calc < (double)fmt * 16.0) calc = (double)fmt * 16.0;
        if (calc < 2336.0 && real_h <= 0) calc = 2336.0;
        x2 = calc;
        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp - 0x1b8), &x2, 8, NULL);
    }
    if (cfg_on("inject_x2", 0, "_inject_x2.txt")) {
        char inf[MAX_PATH];
        lstrcpyA(inf, g_dir); lstrcatA(inf, "_inject_x2.txt");
        HANDLE hf = CreateFileA(inf, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
        if (hf != INVALID_HANDLE_VALUE) {
            char tb[64]; DWORD gb = 0; int iv;
            memset(tb, 0, sizeof(tb));
            ReadFile(hf, tb, 63, &gb, 0);
            CloseHandle(hf);
            iv = atoi(tb);
            if (iv > 0) {
                double nv = (double)iv;
                WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp - 0x1b8), &nv, 8, NULL);
            }
        }
    }
    note("HOOK7F9BF dpi=%d lpi=%d fmt=%u X1=%.2f X2=%.2f real=%dx%d",
         dpi, lpi, (unsigned)fmt, x1, x2, real_w, real_h);
}

static int parse_gjs_tiff_header(const char *path, int *out_w, int *out_h, int *out_off)
{
    unsigned char buf[512];
    HANDLE hf;
    DWORD nr = 0, fsz = 0;
    unsigned ifd_off = 8, cnt = 0, i;
    int w = 0, h = 0, off = 0, rps = 0, spp = 0, sbc = 0;
    if (!path || IsBadReadPtr(path, 4)) return 0;
    hf = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, 0, 0);
    if (hf == INVALID_HANDLE_VALUE) return 0;
    fsz = GetFileSize(hf, NULL);
    ReadFile(hf, buf, sizeof(buf), &nr, NULL);
    CloseHandle(hf);
    if (nr < 24) return 0;
    if ((buf[0] == 'I' && buf[1] == 'I') || (buf[0] == 'M' && buf[1] == 'M')) {
        ifd_off = *(unsigned *)(buf + 4);
    } else {
        ifd_off = 8;
    }
    if (ifd_off + 2 > nr) return 0;
    cnt = *(unsigned short *)(buf + ifd_off);
    if (cnt > 40) cnt = 40;
    for (i = 0; i < cnt; i++) {
        unsigned pos = ifd_off + 2 + i * 12;
        unsigned short tag, typ;
        unsigned val;
        if (pos + 12 > nr) break;
        tag = *(unsigned short *)(buf + pos);
        typ = *(unsigned short *)(buf + pos + 2);
        val = *(unsigned *)(buf + pos + 8);
        if (typ == 3) val &= 0xFFFFu;
        if (tag == 0x0100) w = (int)val;
        else if (tag == 0x0103 && val > 10 && w == 0) w = (int)val;
        else if (tag == 0x0116 && val > 0 && rps == 0) rps = (int)val;
        else if (tag == 0x0101) h = (int)val;
        else if (tag == 0x0111) off = (int)val;
        else if (tag == 0x0112 && val > 16 && off == 0) off = (int)val;
        else if (tag == 0x0115) spp = (int)val;
        else if (tag == 0x0117) sbc = (int)val;
    }
    if (w <= 0 && rps > 0) w = rps;
    if (w <= 0 && h > 0 && spp > 0 && sbc > 0) w = sbc / (h * spp);
    if (off <= 0 && sbc > 0 && fsz > (DWORD)sbc) off = (int)(fsz - (DWORD)sbc);
    if (out_w) *out_w = w;
    if (out_h) *out_h = h;
    if (out_off) *out_off = off;
    return (w > 0 && h > 0);
}

static void __cdecl hook_merg_7fbf1(unsigned long ebp)
{
    unsigned char cnt = 0;
    char *arr = NULL;
    int real_w = 0, real_h = 0, min_w = 0, min_h = 0, off0 = 0;
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp - 0x133), &cnt, 1, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp - 0x1f4), &arr, 4, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)0x5230D0, &real_w, 4, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)0x5230D4, &real_h, 4, NULL);

    if (arr && cnt > 0 && !IsBadWritePtr(arr, (size_t)cnt * 16)) {
        int i2;
        for (i2 = 0; i2 < (int)cnt; i2++) {
            const char *fn = *(const char **)(arr + i2 * 16);
            int f4 = *(int *)(arr + i2 * 16 + 4);
            int f8 = *(int *)(arr + i2 * 16 + 8);
            int fc = *(int *)(arr + i2 * 16 + 12);
            if (f4 <= 0 || f8 <= 0 || fc <= 0) {
                int pw = 0, ph = 0, poff = 0;
                if (parse_gjs_tiff_header(fn, &pw, &ph, &poff)) {
                    if (f4 <= 0 && pw > 0) { f4 = pw; *(int *)(arr + i2 * 16 + 4) = f4; }
                    if (f8 <= 0 && ph > 0) { f8 = ph; *(int *)(arr + i2 * 16 + 8) = f8; }
                    if (fc <= 0 && poff > 0) { fc = poff; *(int *)(arr + i2 * 16 + 12) = fc; }
                }
            }
            if (i2 == 0) off0 = fc;
            if (f4 > 0 && (min_w == 0 || f4 < min_w)) min_w = f4;
            if (f8 > 0 && (min_h == 0 || f8 < min_h)) min_h = f8;
        }
    }
    if (min_w <= 0) min_w = (real_h > 0) ? real_h : ((real_w > 0) ? real_w : 1);
    if (min_h <= 0) min_h = (real_w > 0) ? real_w : ((real_h > 0) ? real_h : 1);
    WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp - 0x124), &min_w, 4, NULL);
    WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp - 0x128), &min_h, 4, NULL);
    note("HOOK7FBF1 cnt=%u min=%dx%d off0=%d", (unsigned)cnt, min_w, min_h, off0);
}

static void __cdecl hook_merg_7fdab(unsigned long ebp)
{
    int w10c = 0, w110 = 0, w124 = 0, x2i = 0;
    unsigned char fmt = 0;
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp - 0x10C), &w10c, 4, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp - 0x110), &w110, 4, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp - 0x124), &w124, 4, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp - 0x128), &x2i, 4, NULL);
    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(ebp + 0x2C), &fmt, 1, NULL);
    if (w10c <= 0) {
        int val = (w124 > 0) ? w124 : 1;
        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp - 0x10C), &val, 4, NULL);
    }
    if (w110 <= 0) {
        int val = (w124 > 0) ? w124 : 16;
        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp - 0x110), &val, 4, NULL);
    }
    if (w124 <= 0) {
        int val = (w10c > 0) ? w10c : 1;
        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp - 0x124), &val, 4, NULL);
    }
    if (x2i <= 0) {
        int val = 16;
        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp - 0x128), &val, 4, NULL);
    }
    if (fmt == 0) {
        unsigned char one = 1;
        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(ebp + 0x2C), &one, 1, NULL);
    }
}

static void ensure_real_patched(void)
{
    HMODULE h = GetModuleHandleA("cmyktiff2_real.dll");
    if (!h) return;
    g_real_base = (unsigned long)h;
    patch_real_module(h);
    if (capture_mode() || g_real_hooks_installed) return;
    {
        static const unsigned char exp_7f9bf[6] = {0xDD, 0x85, 0x58, 0xFE, 0xFF, 0xFF};
        static const unsigned char exp_7fbf1[8] = {0x33, 0xC0, 0x89, 0x85, 0xE0, 0xFE, 0xFF, 0xFF};
        static const unsigned char exp_7fdab[6] = {0xDB, 0x85, 0xD8, 0xFE, 0xFF, 0xFF};
        int ok1 = install_inline_hook((void *)(g_real_base + 0x7F9BF), exp_7f9bf, 6, hook_merg_7f9bf);
        int ok2 = install_inline_hook((void *)(g_real_base + 0x7FBF1), exp_7fbf1, 8, hook_merg_7fbf1);
        int ok3 = install_inline_hook((void *)(g_real_base + 0x7FDAB), exp_7fdab, 6, hook_merg_7fdab);
        if (ok1 && ok2 && ok3) g_real_hooks_installed = 1;
    }
    if (cfg_on("sbp_trace", 0, "_sbp_trace.txt")) {
        sbp_arm(g_real_base + 0x6289C);
        sbp_arm(g_real_base + 0x7FF98);
        sbp_arm(g_real_base + 0x80382);
        sbp_arm(g_real_base + 0x7E9D0);
        sbp_arm(g_real_base + 0x71FE5);
    }
}

static void sbp_arm_real(void)
{
    ensure_real_patched();
}

static LONG CALLBACK sbp_veh(EXCEPTION_POINTERS *ep)
{
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    if (code == 0x80000003 && ep->ContextRecord->Eip == 0x0050AD74 + 1 &&
        cfg_on("sbp_psd", 0, "_sbp_psd.txt"))
        log_preview_probe();
    if (code == 0xC0000005 && cfg_on("avdump", 0, "_avdump.txt")) {
        CONTEXT *c0 = ep->ContextRecord;
        HMODULE he = GetModuleHandleA(0);
        unsigned long *arrA = (unsigned long *)((char *)he + 0x1230A0);   /* [0x5230a0] */
        unsigned long *arrB = (unsigned long *)((char *)he + 0x12309C);   /* [0x52309c] */
        note("AVDUMP eip=%08lX ebx=%lX edi=%lX esi=%lX ecx=%lX edx=%lX actual=0x%08lX",
             (unsigned long)c0->Eip, (unsigned long)c0->Ebx, (unsigned long)c0->Edi,
             (unsigned long)c0->Esi, (unsigned long)c0->Ecx, (unsigned long)c0->Edx,
             (unsigned long)ep->ExceptionRecord->ExceptionInformation[1]);
        note("AVDUMP [5230a0]=%08lX [52309c]=%08lX layers=%u", *arrA, *arrB,
             (unsigned)(*(unsigned short *)((char *)he + 0x12315C)));
        {
            unsigned long *b = (unsigned long *)*arrA;
            char line[900];
            int o = 0, k;
            if (b) {
                for (k = 0; k < 64; k++) o += wsprintfA(line + o, "%s%lX", k ? "," : "", b[k]);
                note("AVDUMP B[0..63]=%s", line);
            }
            {
                unsigned long *c = (unsigned long *)((char *)he + 0x1230B4);
                unsigned long *pa = (unsigned long *)*arrB;
                unsigned long *pb = (unsigned long *)*arrA;
                unsigned long *pc = (unsigned long *)*c;
                note("AVDUMP len A=%ld B=%ld C=%ld",
                     pa ? (long)pa[-1] : -1, pb ? (long)pb[-1] : -1,
                     pc ? (long)pc[-1] : -1);
                if (pc) {
                    unsigned long idx = (unsigned long)c0->Eax;
                    (void)idx;
                    {
                        char el[400];
                        int o = 0, k;
                        unsigned short li = *(unsigned short *)((char *)he + 0x12315C);
                        unsigned long i2 = (li > 0 ? li - 1 : 0);
                        unsigned char *base = (unsigned char *)pc + i2 * 0x38;
                        for (k = 0; k < 0x38 && o < 380; k++) o += wsprintfA(el + o, "%02X", base[k]);
                        note("AVDUMP C[last] idx=%u bytes=%s", (unsigned)li, el);
                    }
                }
            }
            {
                unsigned long *a = (unsigned long *)*arrB;
                o = 0;
                if (a) {
                    for (k = 0; k < 64; k++) o += wsprintfA(line + o, "%s%lX", k ? "," : "", a[k]);
                    note("AVDUMP A[0..63]=%s", line);
                }
            }
        }
    }
    CONTEXT *c = ep->ContextRecord;
    int i;
    if (code == EXCEPTION_BREAKPOINT) {
        static int unmatched;
        for (i = 0; i < g_nsbp; i++) {
            if (c->Eip == g_sbp[i].va + 1 || c->Eip == g_sbp[i].va) {
                DWORD old;
                g_sbp[i].hits++;
                note("SBp HIT %08lX #%d eax=%08lX ebx=%08lX ecx=%08lX edx=%08lX esi=%08lX edi=%08lX",
                     g_sbp[i].va, g_sbp[i].hits,
                     c->Eax, c->Ebx, c->Ecx, c->Edx, c->Esi, c->Edi);
                if (g_zu06_base && g_sbp[i].va == g_zu06_base + 0xA4800) {
                    int k8; char lb2[400]; int o8 = 0;
                    int w15 = 4370, h15 = 5197;
                    /* geometry for the PSD layer rect: [ebp-0x14] = bottom, [ebp-0x18] = right */
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)0x5230D0, &w15, 4, NULL); /* 4370 */
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)0x5230D4, &h15, 4, NULL); /* 5197 */
                    for (k8 = 8; k8 <= 0x110; k8 += 4) {
                        int v = 0;
                        ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp - k8), &v, 4, NULL);
                        o8 += wsprintfA(lb2 + o8, "%X:%d ", k8, v);
                        if (o8 > 330) { note("PSDRECT %s", lb2); o8 = 0; }
                    }
                    if (o8) note("PSDRECT %s", lb2);
                    if (cfg_on("inject_psd_rect", 0, "_inject_psd_rect.txt")) {
                        int b = h15, r = w15;
                        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(c->Ebp - 0x14), &b, 4, NULL);
                        WriteProcessMemory(GetCurrentProcess(), (LPVOID)(c->Ebp - 0x18), &r, 4, NULL);
                        note("PSDRECT inject bottom=%d right=%d", b, r);
                    }
                }
                if (g_zu06_base && g_sbp[i].va == g_zu06_base + 0xA4504) {
                    unsigned long st[10]; int k9; char lb[260]; int o9 = 0;
                    memset(st, 0, sizeof(st));
                    if (c->Esp && !IsBadReadPtr((void *)c->Esp, sizeof(st)))
                        ReadProcessMemory(GetCurrentProcess(), (LPCVOID)c->Esp, st, sizeof(st), NULL);
                    for (k9 = 0; k9 < 10; k9++) o9 += wsprintfA(lb + o9, "%lu ", st[k9]);
                    note("WRITEPSD eax=%08lX edx=%08lX ecx=%08lX stack=[%s]",
                         c->Eax, c->Edx, c->Ecx, lb);
                    {
                        int ai;
                        for (ai = 1; ai <= 2; ai++) {
                            unsigned long sp = st[ai];
                            int slen = 0;
                            char sb[300];
                            memset(sb, 0, sizeof(sb));
                            if (sp && !IsBadReadPtr((void *)(sp - 4), 4))
                                ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(sp - 4), &slen, 4, NULL);
                            if (slen > 0 && slen < 280 && !IsBadReadPtr((void *)sp, slen))
                                ReadProcessMemory(GetCurrentProcess(), (LPCVOID)sp, sb, slen, NULL);
                            note("WRITEPSD arg%d ptr=%08lX len=%d [%s]", ai, sp, slen, sb);
                        }
                    }
                }
                if (g_real_base && g_sbp[i].va == g_real_base + 0x6289C) {
                    char *rs = NULL;
                    int rl = -1;
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp - 0xc), &rs, 4, NULL);
                    if (rs && !IsBadReadPtr(rs - 4, 4)) {
                        ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(rs - 4), &rl, 4, NULL);
                        if (rl < 0 || rl > 240) rl = 240;
                    }
                    note("DECODE ecx/ret=%08lX(%d) len=%d rec=[%.*s]",
                         c->Eax, (int)c->Eax, rl, (rl > 0 ? rl : 0), (rl > 0 ? rs : ""));
                }
                if (g_real_base && g_sbp[i].va == g_real_base + 0x7FF98) {
                    unsigned short mv = 0; int k4;
                    char lb[200]; int o6 = 0;
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp + 0x40), &mv, 2, NULL);
                    for (k4 = 0; k4 < 14; k4++) {
                        int vv = 0;
                        ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp + 8 + k4 * 4), &vv, 4, NULL);
                        o6 += wsprintfA(lb + o6, "%X ", vv);
                    }
                    note("MODE word[+40]=%u args=%s", mv, lb);
                    {
                        char ff2[MAX_PATH];
                        lstrcpyA(ff2, g_dir); lstrcatA(ff2, "_force_mode1.txt");
                        if (GetFileAttributesA(ff2) != INVALID_FILE_ATTRIBUTES) {
                            unsigned short one = 1;
                            WriteProcessMemory(GetCurrentProcess(), (LPVOID)(c->Ebp + 0x40), &one, 2, NULL);
                            note("MODE forced to 1");
                        }
                    }
                }
                if (g_real_base && g_sbp[i].va == g_real_base + 0x7FBF1) {
                    int cnt = 0, i2, v;
                    void *arr = NULL;
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp - 0x133), &cnt, 1, NULL);
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp - 0x1f4), &arr, 4, NULL);
                    if (arr) for (i2 = 0; i2 < cnt; i2++) {
                        ReadProcessMemory(GetCurrentProcess(), (LPCVOID)((char *)arr + i2 * 16 + 8), &v, 4, NULL);
                        WriteProcessMemory(GetCurrentProcess(), (LPVOID)((char *)arr + i2 * 16 + 4), &v, 4, NULL);
                    }
                    {
                        int real_w = 0;
                        ReadProcessMemory(GetCurrentProcess(), (LPCVOID)0x5230D0, &real_w, 4, NULL);
                        if (real_w > 0) {
                            int cur = 0;
                            ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp - 0x124), &cur, 4, NULL);
                            WriteProcessMemory(GetCurrentProcess(), (LPVOID)(c->Ebp - 0x124), &real_w, 4, NULL);
                            note("PATCH100 cnt=%d arr=%p min124 %d -> %d", cnt, arr, cur, real_w);
                        }
                    }
                }
                if (g_real_base && g_sbp[i].va == g_real_base + 0x80382) {
                    unsigned long st[8]; int k6; char lb[300]; int o7 = 0;
                    memset(st, 0, sizeof(st));
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)c->Esp, st, sizeof(st), NULL);
                    for (k6 = 0; k6 < 8; k6++) o7 += wsprintfA(lb + o7, "%lu(%08lX) ", st[k6], st[k6]);
                    note("STAICALL esp=%08lX args=%s | eax=%08lX ecx=%08lX edx=%08lX", c->Esp, lb, c->Eax, c->Ecx, c->Edx);
                }
                if (g_real_base && g_sbp[i].va == g_real_base + 0x7E9D0) {
                    unsigned long aa[10]; int k3; char lb[300]; int o5 = 0;
                    memset(aa, 0, sizeof(aa));
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp + 8), aa, sizeof(aa), NULL);
                    for (k3 = 0; k3 < 10; k3++) o5 += wsprintfA(lb + o5, "%lX ", aa[k3]);
                    note("SAVETIF eax=%08lX ebx=%08lX ecx=%08lX edx=%08lX args=%s", c->Eax, c->Ebx, c->Ecx, c->Edx, lb);
                }
                if (g_real_base && g_sbp[i].va == g_real_base + 0x71FE5) {
                    unsigned char raw[40];
                    char *ps = (char *)c->Edx;
                    memset(raw, 0, sizeof(raw));
                    if (ps && !IsBadReadPtr(ps, 40)) ReadProcessMemory(GetCurrentProcess(), (LPCVOID)ps, raw, 40, NULL);
                    raw[39] = 0;
                    note("LICCALL edx=%p ecx=%08lX eax=%p txt=[%s]", c->Edx, c->Ecx, c->Eax, (char *)raw);
                }
                if (g_real_base && g_sbp[i].va == g_real_base + 0x7F9BF) {
                    double x1 = 0.0, x2 = 0.0;
                    int A = 0, B = 0, fmt = 0, cnt = 0;
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp - 0x1b0), &x1, 8, NULL);
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp - 0x1b8), &x2, 8, NULL);
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp - 0x100), &A, 4, NULL);
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp - 0x104), &B, 4, NULL);
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp + 0x2c), &fmt, 1, NULL);
                    ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp - 0x133), &cnt, 1, NULL);
                    note("REALGEO X1=%.6f X2=%.6f A=%d B=%d fmt=%d count=%d", x1, x2, A, B, fmt, cnt);
                    if (cfg_on("inject_x2", 1, "_inject_x2.txt")) {
                        char inf[MAX_PATH];
                        lstrcpyA(inf, g_dir); lstrcatA(inf, "_inject_x2.txt");
                        {
                            int lines = 0, iv = 0;
                            double nv;
                            HANDLE hf = CreateFileA(inf, GENERIC_READ, FILE_SHARE_READ, 0, OPEN_EXISTING, 0, 0);
                            ReadProcessMemory(GetCurrentProcess(), (LPCVOID)0x5230FC, &lines, 4, NULL);
                            if (hf != INVALID_HANDLE_VALUE) {
                                char tb[64]; DWORD gb = 0;
                                memset(tb, 0, sizeof(tb));
                                ReadFile(hf, tb, 63, &gb, 0);
                                CloseHandle(hf);
                                iv = atoi(tb);
                            }
                            if (iv <= 0) iv = 2336;
                            nv = (double)iv;
                            WriteProcessMemory(GetCurrentProcess(), (LPVOID)(c->Ebp - 0x1b8), &nv, 8, NULL);
                            note("INJECT X2 := %d", iv);
                        }
                    }
                    {
                        unsigned long gv[] = {0x523154, 0x5230FC, 0x5230C9, 0x523114,
                                              0x5230F0, 0x523108, 0x52310C, 0x523160,
                                              0x5231A8, 0x5231AC, 0x52315E, 0x5230E4,
                                              0x523074, 0x52307C, 0x52306C, 0x523170,
                                              0x5230CB, 0x5230CD, 0x52315C, 0x5230F4};
                        char gb[400]; int o4 = 0; int k2;
                        for (k2 = 0; k2 < 20; k2++) {
                            int v = 0;
                            ReadProcessMemory(GetCurrentProcess(), (LPCVOID)gv[k2], &v, 4, NULL);
                            o4 += wsprintfA(gb + o4, "%lX=%d ", gv[k2], v);
                        }
                        note("REALGLOB %s", gb);
                    }
                    {
                        static const int so[8] = { -0x1c0, -0x1c4, -0x1c8, -0x1cc,
                                                   -0x1d0, -0x1d4, -0x1d8, -0x1dc };
                        char lbuf[400]; int o3 = 0; int k;
                        for (k = 0; k < 8; k++) {
                            unsigned char *sp = NULL;
                            char txt[64]; int slen = -1;
                            ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(c->Ebp + so[k]), &sp, 4, NULL);
                            if (sp && !IsBadReadPtr(sp - 4, 4)) {
                                ReadProcessMemory(GetCurrentProcess(), (LPCVOID)(sp - 4), &slen, 4, NULL);
                                if (slen < 0 || slen > 40) slen = 40;
                                memset(txt, 0, sizeof(txt));
                                if (slen > 0) ReadProcessMemory(GetCurrentProcess(), (LPCVOID)sp, txt, slen, NULL);
                                txt[slen] = 0;
                            } else {
                                lstrcpyA(txt, "<null>");
                            }
                            o3 += wsprintfA(lbuf + o3, "[%d]=%s ", so[k], txt);
                        }
                        note("REALSTR %s", lbuf);
                    }
                }
                VirtualProtect((void *)g_sbp[i].va, 1, PAGE_EXECUTE_READWRITE, &old);
                *(unsigned char *)g_sbp[i].va = g_sbp[i].orig;
                VirtualProtect((void *)g_sbp[i].va, 1, old, &old);
                c->Eip = g_sbp[i].va;
                c->EFlags |= 0x100;
                g_armed = i;
                return EXCEPTION_CONTINUE_EXECUTION;
            }
        }
        if (i == g_nsbp && unmatched < 4) { unmatched++; note("SBp unmatch eip=%08lX", c->Eip); }
    } else if (code == 0xC000008E || code == 0xC0000094) {
        static int ndiv;
        if (ndiv < 6) {
            ndiv++;
            {
                unsigned long sv[10]; int k; char line[256]; int off2=0;
                note("DIVZERO code=%08lX eip=%08lX esp=%08lX eax=%08lX ebx=%08lX ecx=%08lX edx=%08lX",
                     code, c->Eip, c->Esp, c->Eax, c->Ebx, c->Ecx, c->Edx);
                memset(sv,0,sizeof(sv));
                ReadProcessMemory(GetCurrentProcess(),(LPCVOID)c->Esp,sv,sizeof(sv),NULL);
                for (k=0;k<10;k++) off2 += wsprintfA(line+off2,"%08lX ",sv[k]);
                note("DIVZERO stack: %s", line);
                {
                    int d110=0, d124=0, d114=0, d11c=0, d1e4=0, d120=0;
                    ReadProcessMemory(GetCurrentProcess(),(LPCVOID)(c->Ebp-0x110),&d110,4,NULL);
                    ReadProcessMemory(GetCurrentProcess(),(LPCVOID)(c->Ebp-0x124),&d124,4,NULL);
                    ReadProcessMemory(GetCurrentProcess(),(LPCVOID)(c->Ebp-0x114),&d114,4,NULL);
                    ReadProcessMemory(GetCurrentProcess(),(LPCVOID)(c->Ebp-0x11c),&d11c,4,NULL);
                    ReadProcessMemory(GetCurrentProcess(),(LPCVOID)(c->Ebp-0x1e4),&d1e4,4,NULL);
                    ReadProcessMemory(GetCurrentProcess(),(LPCVOID)(c->Ebp-0x120),&d120,4,NULL);
                    note("DIVZERO locals -110=%d -124=%d -114=%d -11c=%d -1e4=%d -120=%d ebp=%08lX",
                         d110,d124,d114,d11c,d1e4,d120,(unsigned long)c->Ebp);
                    {
                        unsigned long sp9=0; int ln9=0; char sb9[300]; int k9=0,j9;
                        memset(sb9,0,sizeof(sb9));
                        ReadProcessMemory(GetCurrentProcess(),(LPCVOID)(c->Ebp-0x1EC),&sp9,4,NULL);
                        if (sp9>0x10000 && sp9<0x7FFF0000) {
                            ReadProcessMemory(GetCurrentProcess(),(LPCVOID)(sp9-4),&ln9,4,NULL);
                            if (ln9>0 && ln9<250)
                                ReadProcessMemory(GetCurrentProcess(),(LPCVOID)sp9,sb9,ln9,NULL);
                        }
                        for (j9=0;j9<250&&k9<200;j9++) if (sb9[j9]) sb9[k9++]=sb9[j9]; else if (j9>2) break;
                        sb9[k9]=0;
                        note("DIVZERO curstr ptr=%08lX len=%d [%s]",sp9,ln9,sb9);
                    }
                }
                {
                    MEMORY_BASIC_INFORMATION m1, m2; char md1[MAX_PATH], md2[MAX_PATH];
                    memset(&m1,0,sizeof(m1)); memset(&m2,0,sizeof(m2));
                    md1[0]=0; md2[0]=0;
                    if (VirtualQuery((LPCVOID)c->Eip,&m1,sizeof(m1)))
                        GetModuleFileNameA((HMODULE)m1.AllocationBase,md1,MAX_PATH);
                    if (sv[1] && VirtualQuery((LPCVOID)sv[1],&m2,sizeof(m2)))
                        GetModuleFileNameA((HMODULE)m2.AllocationBase,md2,MAX_PATH);
                    note("DIVZERO mod_eip=%s base=%p | mod_ret=%s base=%p",
                         md1, (void*)m1.AllocationBase, md2, (void*)m2.AllocationBase);
                }
            }
        }
        return EXCEPTION_CONTINUE_SEARCH;
    } else if (code == EXCEPTION_SINGLE_STEP && g_armed >= 0) {
        DWORD old;
        int k = g_armed;
        g_armed = -1;
        VirtualProtect((void *)g_sbp[k].va, 1, PAGE_EXECUTE_READWRITE, &old);
        *(unsigned char *)g_sbp[k].va = 0xCC;
        VirtualProtect((void *)g_sbp[k].va, 1, old, &old);
        c->EFlags &= ~0x100;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

static BOOL (WINAPI *o_emi)(HMENU, UINT, UINT);
static BOOL WINAPI e_emi(HMENU m, UINT id, UINT en)
{
    if (capture_mode() && o_emi) return o_emi(m, id, en);
    BOOL r = o_emi ? o_emi(m, id, en) : FALSE;
    if (id == 16 || id == 17 || id == 18 || id == 12 || id == 7)
        note("EMU EnableMenu id=%u en=%u ret=%d", id, en, r);
    return r;
}

/* Version-agnostic IAT patcher: match resolved API addresses instead of RVAs.
   Works even when OriginalFirstThunk == 0 (our exe) and across builds (10.1/10.4). */
static int patch_imports_by_addr(HMODULE m)
{
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS *nt;
    IMAGE_IMPORT_DESCRIPTOR *d;
    int patched = 0;
    HMODULE k32, u32, sp, cd;
    struct { void *addr; void *repl; void **save; } tab[16];
    int n = 0, i;

    if (!m) return 0;
    dos = (IMAGE_DOS_HEADER *)m;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    nt = (IMAGE_NT_HEADERS *)((char *)m + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return 0;

    k32 = GetModuleHandleA("kernel32.dll");
    u32 = GetModuleHandleA("user32.dll");
    sp  = GetModuleHandleA("setupapi.dll");
    cd  = GetModuleHandleA("comdlg32.dll");
#define ADD(h, nm, fn, sv) do { void *a = h ? (void *)GetProcAddress(h, nm) : 0;         if (a) { tab[n].addr = a; tab[n].repl = (void *)(fn); tab[n].save = (void **)(sv); n++; } } while (0)
    ADD(k32, "CreateFileA", e_cfa, &o_cfa);
    ADD(k32, "DeviceIoControl", e_dio, &o_dio);
    ADD(k32, "ReadFile", e_rf, &o_rf);
    ADD(k32, "WriteFile", e_wf, &o_wf);
    ADD(k32, "SetFilePointer", e_sfp, &o_sfp);
    ADD(k32, "GetFileSize", e_gfs, &o_gfs);
    ADD(k32, "CloseHandle", e_ch, &o_ch);
    ADD(u32, "EnableMenuItem", e_emi, &o_emi);
    ADD(cd,  "GetOpenFileNameA", e_gofna, &o_gofna);
    ADD(cd,  "GetSaveFileNameA", e_gsfn, &o_gsfn);
    ADD(sp,  "SetupDiDestroyDeviceInfoList", e_sddil, &o_sddil);
    ADD(sp,  "SetupDiGetDeviceInterfaceDetailA", e_sddida, &o_sddida);
    ADD(sp,  "SetupDiEnumDeviceInterfaces", e_sdeif, &o_sdeif);
    ADD(sp,  "SetupDiGetClassDevsA", e_sdgcd, &o_sdgcd);
    ADD(GetModuleHandleA("ws2_32.dll"), "connect", e_conn, &o_conn);
    ADD(GetModuleHandleA("ws2_32.dll"), "gethostbyname", e_ghbn, &o_ghbn);
#undef ADD
    if (!n) return 0;

    d = (IMAGE_IMPORT_DESCRIPTOR *)((char *)m + nt->OptionalHeader.DataDirectory[1].VirtualAddress);
    for (; d->Name; d++) {
        ULONG_PTR *iat = (ULONG_PTR *)((char *)m + d->FirstThunk);
        int k;
        if (!iat) continue;
        for (; *iat; iat++) {
            for (k = 0; k < n; k++) {
                if ((void *)*iat == tab[k].addr) {
                    DWORD old;
                    if (VirtualProtect(iat, 4, PAGE_READWRITE, &old)) {
                        if (!*tab[k].save) *tab[k].save = (void *)*iat;
                        *iat = (ULONG_PTR)tab[k].repl;
                        VirtualProtect(iat, 4, old, &old);
                        patched++;
                    }
                    break;
                }
            }
        }
    }
    return patched;
}

static void sbp_arm_checked(unsigned long va, unsigned char expect)
{
    const unsigned char *pp = (const unsigned char *)va;
    unsigned char got = 0;
    if (!IsBadReadPtr(pp, 1)) got = *pp;
    if (IsBadReadPtr(pp, 1) || got != expect) {
        note("SBp skip %08lX (byte %02X != %02X)", va, got, expect);
        return;
    }
    sbp_arm(va);
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
    load_dlg_lists();
    {
        char rp[MAX_PATH];
        FILE *rf;
        lstrcpyA(rp, g_dir); lstrcatA(rp, "_dongle_reply.bin");
        rf = fopen(rp, "rb");
        if (rf) { g_reply_n = (int)fread(g_reply, 1, 16, rf); fclose(rf); }
    }
    base = GetModuleHandleA(NULL);
    if (!base) return;
    {
        int np = patch_imports_by_addr((HMODULE)base);
        note("addr-based IAT patch: %d slots", np);
        if (np >= 6) goto imports_done;
    }
    patch_slot(base, RVA_CREATEFILE_A,  (void *)e_cfa, (void **)&o_cfa);
    patch_slot(base, RVA_CREATEFILE_A2, (void *)e_cfa, (void **)&o_cfa);
    patch_slot(base, RVA_DEVICEIOCTL,   (void *)e_dio, (void **)&o_dio);
    patch_slot(base, RVA_READFILE,      (void *)e_rf,  (void **)&o_rf);
    patch_slot(base, RVA_READFILE2,     (void *)e_rf,  (void **)&o_rf);
    patch_slot(base, RVA_WRITEFILE,     (void *)e_wf,  (void **)&o_wf);
    patch_slot(base, RVA_WRITEFILE2,    (void *)e_wf,  (void **)&o_wf);
    if (cfg_on("attr_log", 0, "_attr_log.txt")) {
        patch_slot(base, RVA_CREATEFILE_A,  (void *)e_cfa_logonly, (void **)&o_cfa);
        patch_slot(base, RVA_CREATEFILE_A2, (void *)e_cfa_logonly, (void **)&o_cfa);
        patch_slot(base, RVA_WRITEFILE,     (void *)e_wf_logonly,  (void **)&o_wf);
        patch_slot(base, RVA_WRITEFILE2,    (void *)e_wf_logonly,  (void **)&o_wf);
        note("EMU exe IAT switched to attribution logging");
    }
    patch_slot(base, RVA_SETFILEPTR,    (void *)e_sfp, (void **)&o_sfp);
    patch_slot(base, RVA_SETFILEPTR2,   (void *)e_sfp, (void **)&o_sfp);
    patch_slot(base, RVA_GETFILESIZE,   (void *)e_gfs, (void **)&o_gfs);
    patch_slot(base, RVA_GETFILESIZE2,  (void *)e_gfs, (void **)&o_gfs);
    patch_slot(base, RVA_SETUP_DESTROY,   (void *)e_sddil,  (void **)&o_sddil);

    patch_slot(base, RVA_GETPROCADDR,  (void *)e_gpa, (void **)&o_gpa);

    patch_slot(base, RVA_GETPROCADDR2, (void *)e_gpa, (void **)&o_gpa);

    note("EMU GetProcAddress hooked (writepsd replace ready)");
    if (cfg_on("native_psd", 1, "_native_psd.txt")) {
        unsigned char *cs = (unsigned char *)((char *)base + RVA_WRITEPSD_CALL);
        DWORD oldp;
        if (cs[0] == 0xFF && cs[1] == 0x15) {          /* call [0x523278] */
            long rel = (long)((char *)writepsd_shim - (char *)(cs + 5));
            if (VirtualProtect(cs, 6, PAGE_EXECUTE_READWRITE, &oldp)) {
                cs[0] = 0xE8;
                *(long *)(cs + 1) = rel;
                cs[5] = 0x90;
                VirtualProtect(cs, 6, oldp, &oldp);
                FlushInstructionCache(GetCurrentProcess(), cs, 6);
                note("NATIVE writepsd call patched at %p -> %p (rel=%ld)", cs, (void *)writepsd_shim, rel);
            }
        } else {
            note("NATIVE writepsd call site unexpected: %02X %02X", cs[0], cs[1]);
        }
    }
    patch_slot(base, RVA_SETUP_DETAIL,    (void *)e_sddida, (void **)&o_sddida);
    patch_slot(base, RVA_SETUP_ENUMIF,    (void *)e_sdeif,  (void **)&o_sdeif);
    patch_slot(base, RVA_SETUP_CLASSDEVS, (void *)e_sdgcd,  (void **)&o_sdgcd);
    patch_slot(base, RVA_CLOSEHANDLE1,    (void *)e_ch,      (void **)&o_ch);
    patch_slot(base, RVA_CLOSEHANDLE2,    (void *)e_ch,      (void **)&o_ch);
    patch_slot(base, RVA_ENABLEMENUITEM,  (void *)e_emi,     (void **)&o_emi);
imports_done:
    patch_slot(base, RVA_GETOPENFILENAMEA, (void *)e_gofna, (void **)&o_gofna);
    patch_slot(base, RVA_GETSAVEFILENAMEA, (void *)e_gsfn,  (void **)&o_gsfn);
    note("--- installed base=%p cfa=%p dio=%p ---", base, o_cfa, o_dio);
    if (capture_mode()) {
        HMODULE hr = GetModuleHandleA("cmyktiff2_real.dll");
        note("CAPTURE active; real dll=%p", hr);
        if (!hr) hr = GetModuleHandleA("cmyktiff2.dll");
        if (hr) patch_real_module(hr);
        note("CAPTURE ready (no VEH, no breakpoints)");
        return;
    }
    /* software breakpoints (optional debug trace only) */
    g_veh = AddVectoredExceptionHandler(1, sbp_veh);
    note("VEH installed = %p", g_veh);
    ensure_real_patched();
    if (cfg_on("sbp_trace", 0, "_sbp_trace.txt")) {
        sbp_arm_checked((unsigned long)base + 0x10B070, 0x53);  /* 0x50B070 GATE1 entry */
        sbp_arm_checked((unsigned long)base + 0x10B07E, 0x3C);  /* 0x50B07E cmp al,1 */
        sbp_arm_checked((unsigned long)base + 0x10B086, 0xE8);  /* 0x50B086 call 0x505A44 */
        sbp_arm_checked((unsigned long)base + 0x3265E, 0x8B);   /* 0x43265E Execute entry */
        sbp_arm_checked((unsigned long)base + 0x10B073, 0x8B);  /* 0x50B073 load btn obj */
    }
}


/* ---- zu06.dll (readpsd / writepsd) carries its own dongle stack ----
   It is loaded by the application on demand, so we watch for it and patch
   its IAT slots once it appears.  Originals are the same kernel32 entry
   points already saved by patch_real_module, so the globals are shared. */
static int g_zu06_patched;

static void log_preview_probe(void);

static HANDLE g_psd_handle;

static void caller_tag(char *out, size_t cap)
{
    HMODULE hm = NULL;
    char path[MAX_PATH];
    const char *base;
    void *ret = __builtin_return_address(0);
    out[0] = '?'; out[1] = 0;
    if (GetModuleHandleExA(0x00000004 /*FROM_ADDRESS*/ | 0x00000002 /*UNCHANGED_REFCOUNT*/,
                           (LPCSTR)ret, &hm) && hm) {
        if (GetModuleFileNameA(hm, path, MAX_PATH)) {
            base = path;
            {
                const char *q = path;
                while (*q) { if (*q == '\\' || *q == '/') base = q + 1; q++; }
            }
            lstrcpynA(out, base, (int)cap);
        }
    }
}

static HANDLE WINAPI e_cfa_logonly(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                   DWORD disp, DWORD flags, HANDLE tmpl)
{
    HANDLE h = o_cfa ? o_cfa(name, acc, share, sa, disp, flags, tmpl) : INVALID_HANDLE_VALUE;
    char who[64];
    caller_tag(who, sizeof(who));
    if (name && lstrlenA(name) > 4) {
        const char *ext = name + lstrlenA(name) - 4;
        if (lstrcmpiA(ext, ".psd") == 0) {
            g_psd_handle = h;
            note("CFA[%s] %s -> %p (PSD)", who, name, h);
            return h;
        }
    }
    note("CFA[%s] %s", who, name ? name : "(null)");
    return h;
}

static BOOL WINAPI e_wf_logonly(HANDLE h, LPCVOID buf, DWORD n, LPDWORD got, LPOVERLAPPED ov)
{
    if (n >= 1048576 && buf && !IsBadReadPtr((void *)buf, 8)) {
        const unsigned char *q = (const unsigned char *)buf;
        char who[64];
        caller_tag(who, sizeof(who));
        note("MODWF[%s] n=%lu hdr=%02X%02X%02X%02X", who, (unsigned long)n, q[0], q[1], q[2], q[3]);
    }
    /* Rewrite the "UG" TIFF variant in flight: the 10.1 writer emits
         header  55 47 A7 01 01 00 00 00   (should be II 2A 00 08 00 00 00)
         entry0  tag 0x19C9                (should be 0x00FE)
         entry1  tag 0x0103                (should be 0x0100 = ImageWidth)
         entry6  tag 0x0112                (should be 0x0111 = StripOffsets)
       Without a valid ImageWidth the PSD layer loader sees width 0 and writes
       empty layer channels. */
    if (n >= 8 && buf && !IsBadWritePtr((void *)buf, n)) {
        unsigned char *p = (unsigned char *)buf;
        if (p[0] == 0x55 && p[1] == 0x47 && p[2] == 0xA7 && p[3] == 0x01 &&
            cfg_on("ug_fix", 0, "_ug_fix.txt")) {
            p[0] = 'I'; p[1] = 'I'; p[2] = 0x2A; p[3] = 0x00;
            p[4] = 8; p[5] = 0; p[6] = 0; p[7] = 0;
            if (n > 84) {
                p[10] = 0xFE; p[11] = 0x00;
                p[22] = 0x00; p[23] = 0x01;
                p[82] = 0x11; p[83] = 0x01;
            }
            note("UGFIX n=%lu", (unsigned long)n);
        }
    }
    BOOL r = o_wf ? o_wf(h, buf, n, got, ov) : FALSE;
    if (g_psd_handle && h == g_psd_handle) {
        note("PSDWF n=%lu ok=%d", (unsigned long)n, r);
    } else if (n >= 512) {
        note("zu06 wf n=%lu ok=%d", (unsigned long)n, r);
    }
    return r;
}

static void patch_slot_raw(void **slot, void *repl, void **save)
{
    DWORD old;
    if (!slot) return;
    if (*save == NULL) *save = *slot;
    if (VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &old)) {
        *slot = repl;
        VirtualProtect(slot, sizeof(void *), old, &old);
        FlushInstructionCache(GetCurrentProcess(), slot, sizeof(void *));
    }
}

/* Walk a module's import table and hook CreateFileA / WriteFile with log-only stubs. */
static void patch_module_logonly(HMODULE m, const char *tag)
{
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)m;
    IMAGE_NT_HEADERS *nt;
    IMAGE_IMPORT_DESCRIPTOR *d;
    if (!m || dos->e_magic != IMAGE_DOS_SIGNATURE) return;
    nt = (IMAGE_NT_HEADERS *)((char *)m + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return;
    d = (IMAGE_IMPORT_DESCRIPTOR *)((char *)m + nt->OptionalHeader.DataDirectory[1].VirtualAddress);
    for (; d->Name; d++) {
        IMAGE_THUNK_DATA *th = (IMAGE_THUNK_DATA *)((char *)m + (d->OriginalFirstThunk ? d->OriginalFirstThunk : d->FirstThunk));
        IMAGE_THUNK_DATA *ft = (IMAGE_THUNK_DATA *)((char *)m + d->FirstThunk);
        int i;
        for (i = 0; th[i].u1.AddressOfData; i++) {
            IMAGE_IMPORT_BY_NAME *nm;
            if (IMAGE_SNAP_BY_ORDINAL(th[i].u1.Ordinal)) continue;
            nm = (IMAGE_IMPORT_BY_NAME *)((char *)m + th[i].u1.AddressOfData);
            if (!nm->Name[0]) continue;
            if (!lstrcmpiA((const char *)nm->Name, "CreateFileA"))
                patch_slot_raw((void **)&ft[i], (void *)e_cfa_logonly, (void **)&o_cfa);
            else if (!lstrcmpiA((const char *)nm->Name, "WriteFile"))
                patch_slot_raw((void **)&ft[i], (void *)e_wf_logonly, (void **)&o_wf);
        }
    }
    note("EMU %s hooked (cfa+wf, log only)", tag);
}


/* ================= 配置：psdto3d_green.ini（旧版 _xxx.txt 仍兼容） ================= */
static int cfg_val(const char *key, int def)
{
    static char ini[MAX_PATH];
    static int inited;
    if (!inited) {
        inited = 1;
        lstrcpynA(ini, g_dir, MAX_PATH - 32);
        lstrcatA(ini, "psdto3d_green.ini");
    }
    return GetPrivateProfileIntA("green", key, def, ini);
}

static int cfg_on(const char *key, int def, const char *marker)
{
    if (marker && GetFileAttributesA(marker) != INVALID_FILE_ATTRIBUTES) return 1;   /* 老包兼容 */
    return cfg_val(key, def) != 0;
}

static int writepsd_slot_hooked;
static void inline_cfa_install(void);
static HANDLE WINAPI e_cfa_inline(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);


/* ================= 界面汉化（运行期按文本替换） ================= */
typedef struct { const wchar_t *en; const wchar_t *cn; } CN_PAIR;
static const CN_PAIR g_cn[] = {
    /* 顶层菜单 */
    { L"File", L"文件" }, { L"Edit", L"编辑" }, { L"View", L"视图" }, { L"Help", L"帮助" },
    /* 文件 */
    { L"Open project", L"打开工程" },
    { L"Save project", L"保存工程" },
    { L"Save as project", L"工程另存为" },
    { L"Import *.psd", L"导入 PSD" },
    { L"Import settings", L"导入设置" },
    { L"Preview 3D animation", L"预览 3D 动画" },
    { L"Stop preview", L"停止预览" },
    { L"Red/Blue Glasses preview", L"红蓝眼镜预览" },
    { L"Export *.tiff", L"导出 TIFF" },
    { L"Export PSD", L"导出 PSD" },
    { L"Export Gif", L"导出 GIF" },
    { L"Quit", L"退出" },
    /* 编辑 */
    { L"Begin draw line", L"开始画线" },
    { L"Undo", L"撤销" },
    { L"Delete Layer", L"删除图层" },
    { L"Delete All", L"全部删除" },
    { L"Delete Select", L"删除选中" },
    { L"Select All", L"全选" },
    { L"Free Transition", L"自由变换" },
    { L"Cut", L"剪切" }, { L"Copy", L"复制" }, { L"Pastup", L"粘贴" },
    /* 视图 / 帮助 */
    { L"Zoom In", L"放大" }, { L"Zoom Out", L"缩小" },
    { L"Show work folder", L"打开工作目录" },
    { L"About", L"关于" },
    { L"Clear Registered information", L"清除注册信息" },
    /* 页签与面板 */
    { L"SetLayer", L"图层设置" },
    { L"Output Sets", L"输出设置" },
    { L"3DSets", L"3D 设置" },
    { L"DrawLine", L"画线" },
    { L"Layer View", L"图层视图" },
    { L"All", L"全部" }, { L"One", L"单个" },
    { L"Layer", L"图层" }, { L"Group", L"组" }, { L"Offset", L"偏移" },
    { L"LPI", L"线数" }, { L"Angles", L"角度数" },
    { L"Layer D", L"层深" }, { L"Depth", L"深度" },
    { L"Original Info", L"原始信息" },
    { L"Size (cm)", L"尺寸(厘米)" },
    { L"DPI", L"分辨率" }, { L"Color", L"颜色" }, { L"Layers", L"层数" },
    { L"Please import *.psd.", L"请先导入 PSD 文件" },
    { 0, 0 }
};

static const wchar_t *cn_lookup(const wchar_t *en)
{
    int i;
    wchar_t buf[160];
    int n = 0;
    while (en[n] && n < 159) { buf[n] = en[n]; n++; }
    buf[n] = 0;
    /* 去掉 & 与快捷键后缀 \tCtrl+X */
    {
        int a = 0, b;
        for (b = 0; buf[b]; b++) if (buf[b] != L'&') buf[a++] = buf[b];
        buf[a] = 0;
        for (b = 0; buf[b]; b++) if (buf[b] == L'\t') { buf[b] = 0; break; }
        while (a > 0 && (buf[a - 1] == L' ' || buf[a - 1] == L'.')) buf[--a] = 0;
    }
    for (i = 0; g_cn[i].en; i++)
        if (lstrcmpiW(buf, g_cn[i].en) == 0) return g_cn[i].cn;
    return 0;
}

static void cn_menu_pass(HMENU h, int depth)
{
    int n, i;
    if (!h || depth > 3) return;
    n = GetMenuItemCount(h);
    for (i = 0; i < n; i++) {
        wchar_t buf[160];
        HMENU sub = GetSubMenu(h, i);
        buf[0] = 0;
        GetMenuStringW(h, i, buf, 160, MF_BYPOSITION);
        if (sub) {
            const wchar_t *cn = cn_lookup(buf);
            if (cn) ModifyMenuW(h, i, MF_BYPOSITION | MF_POPUP | MF_STRING, (UINT_PTR)sub, cn);
            cn_menu_pass(sub, depth + 1);
        } else {
            int id = GetMenuItemID(h, i);
            const wchar_t *cn = cn_lookup(buf);
            if (cn && id > 0) ModifyMenuW(h, i, MF_BYPOSITION | MF_STRING, (UINT)id, cn);
        }
    }
}

static void cn_child_pass(HWND w)
{
    wchar_t buf[200];
    HWND c = NULL;
    buf[0] = 0;
    GetWindowTextW(w, buf, 200);
    if (buf[0]) {
        const wchar_t *cn = cn_lookup(buf);
        if (cn) SetWindowTextW(w, cn);
    }
    for (;;) {
        c = FindWindowExA(w, c, NULL, NULL);
        if (!c) break;
        cn_child_pass(c);
    }
}


static void cn_status_pass(HWND w)
{
    static const wchar_t *panels[] = {
        L"官网 3d99.com", L"原始信息", L"尺寸(厘米)", L"分辨率", L"颜色", L"层数", L"请先导入 PSD 文件"
    };
    HWND sb = FindWindowExA(w, NULL, "TStatusBar", NULL);
    int n, i;
    if (!sb) return;
    n = (int)SendMessageA(sb, 0x0400 + 6, 0, 0);      /* SB_GETPARTS */
    for (i = 0; i < n && i < 7; i++) {
        SendMessageW(sb, 0x0401, (WPARAM)i, (LPARAM)panels[i]);   /* SB_SETTEXTW */
    }
}

static void cn_tabs_pass(HWND w)
{
    static const struct { const wchar_t *en; const wchar_t *cn; } tabs[] = {
        { L"SetLayer", L"图层设置" }, { L"Output Sets", L"输出设置" },
        { L"3DSets", L"3D 设置" }, { L"DrawLine", L"画线" },
    };
    HWND pc = NULL;
    int guard;
    for (guard = 0; guard < 8; guard++) {
        int n, i, k;
        pc = FindWindowExA(w, pc, "TPageControl", NULL);
        if (!pc) break;
        n = (int)SendMessageA(pc, 0x1304, 0, 0);
        for (i = 0; i < n; i++) {
            wchar_t buf[128];
            buf[0] = 0;
            /* TCM_GETITEMW: 直接传 TCITEMW 指针 */
            struct { UINT mask; int iImage; LPWSTR pszText; int cch; int iImage2; LPARAM lParam; } it;
            it.mask = 0x1; it.iImage = 0; it.pszText = buf; it.cch = 128; it.iImage2 = 0; it.lParam = 0;
            if (SendMessageW(pc, 0x1300 + 60, i, (LPARAM)&it)) {
                for (k = 0; k < 4; k++) {
                    if (lstrcmpiW(buf, tabs[k].en) == 0) {
                        struct { UINT mask; int iImage; LPWSTR pszText; int cch; int iImage2; LPARAM lParam; } st;
                        st.mask = 0x1; st.iImage = 0; st.pszText = (LPWSTR)tabs[k].cn; st.cch = 0; st.iImage2 = 0; st.lParam = 0;
                        SendMessageW(pc, 0x1300 + 61, i, (LPARAM)&st);
                        break;
                    }
                }
            }
        }
        InvalidateRect(pc, NULL, TRUE);
    }
}


/* ================= 原生中文：调用程序自己的语言应用例程 ================= */
typedef void (__attribute__((regparm(3))) *PF_APPLYLANG)(void *self);

static int cn_native_apply(HWND form)
{
    HMODULE he = GetModuleHandleA(0);
    unsigned char *flag;
    PF_APPLYLANG fn;
    DWORD oldp;
    if (!he || !form) return 0;
    flag = (unsigned char *)((char *)he + 0x1230C9);      /* DAT_005230c9 */
    fn = (PF_APPLYLANG)((char *)he + 0x10CCF8);           /* FUN_0050ccf8 */
    if (!VirtualProtect(flag, 1, PAGE_READWRITE, &oldp)) return 0;
    if (*flag != 1) {
        note("CN native: flag %d -> 1, 调用 0050CCF8", *flag);
        *flag = 1;
        VirtualProtect(flag, 1, oldp, &oldp);
        fn((void *)form);
        return 1;
    }
    VirtualProtect(flag, 1, oldp, &oldp);
    return 0;
}

static DWORD WINAPI cn_ui_thread(LPVOID p)
{
    int round;
    (void)p;
    for (round = 0; round < 6; round++) {
        HWND w = FindWindowA("TForm1", NULL);
        if (w) {
            HMENU h;
            if (cfg_on("cn_native", 0, "_cn_native.txt"))
                cn_native_apply(w);
            h = GetMenu(w);
            cn_menu_pass(h, 0);
            DrawMenuBar(w);
            cn_child_pass(w);
            cn_status_pass(w);
            cn_tabs_pass(w);
            note("CN UI round %d", round);
        }
        Sleep(2500);
    }
    return 0;
}


/* ================= 修"导入设置取消后崩溃" =================
 * 原码 0x5125EE 起：mov edx,[0x523230]; mov ecx,[0x523104]; mov edx,[edx+ecx*4]; call ...
 * 用户取消时 [0x523230] 为空 -> 空指针读崩。
 * 改成：先判空，空则跳过这一句调用。
 */
static int cancel_guard_applied;

static void patch_cancel_guard(void *base)
{
    unsigned char *p = (unsigned char *)base + 0x1125EE;
    DWORD oldp;
    static const unsigned char expect[] = { 0x8B,0x15,0x30,0x32,0x52,0x00 };
    if (cancel_guard_applied) return;
    if (memcmp(p, expect, sizeof(expect)) != 0) {
        note("CANCEL guard: 指令不匹配，跳过");
        return;
    }
    if (!VirtualProtect(p, 32, PAGE_EXECUTE_READWRITE, &oldp)) return;
    /* mov edx,[0x523230] ; test edx,edx ; jz +0x14 ; mov ecx,[0x523104] ;
       mov edx,[edx+ecx*4] ; mov ecx,[0x4fd9e0] ; call 0x4064dc ; nop nop */
    p[0] = 0x8B; p[1] = 0x15; p[2] = 0x30; p[3] = 0x32; p[4] = 0x52; p[5] = 0x00;
    p[6] = 0x85; p[7] = 0xD2;                          /* test edx,edx */
    p[8] = 0x74; p[9] = 0x14;                          /* jz +0x14 -> 0x51260A */
    p[10] = 0x8B; p[11] = 0x0D; p[12] = 0x04; p[13] = 0x31; p[14] = 0x52; p[15] = 0x00;
    p[16] = 0x8B; p[17] = 0x14; p[18] = 0x8A;          /* mov edx,[edx+ecx*4] */
    p[19] = 0x8B; p[20] = 0x0D; p[21] = 0xE0; p[22] = 0xD9; p[23] = 0x4F; p[24] = 0x00;
    p[25] = 0xE8;                                      /* call rel32 */
    { long rel = (long)(0x004064DC - (0x0051260A + 5)); *(long *)(p + 26) = rel; }
    p[30] = 0x90; p[31] = 0x90;
    VirtualProtect(p, 32, oldp, &oldp);
    FlushInstructionCache(GetCurrentProcess(), p, 32);
    cancel_guard_applied = 1;
    note("CANCEL guard: 已修 0x5125EE（取消导入设置不再崩）");
}


static HANDLE WINAPI e_cfa_probe(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                 DWORD disp, DWORD flags, HANDLE tmpl)
{
    if (name) {
        int l = lstrlenA(name);
        if (l > 4 && lstrcmpiA(name + l - 4, ".psd") == 0)
            note("RIP3D CFA: %s", name);
    }
    return o_cfa(name, acc, share, sa, disp, flags, tmpl);
}


/* ================= 容忍空层指针（41+ 层时原版会 AV） ================= */
static int nil_tolerant_applied;

static void patch_nil_tolerant(void *base)
{
    unsigned char *p = (unsigned char *)base + 0x109FFE;
    static const unsigned char expect[] = { 0x8B, 0x04, 0x98, 0x8B, 0x04, 0xB8 };
    DWORD oldp;
    if (nil_tolerant_applied) return;
    if (memcmp(p, expect, sizeof(expect)) != 0) {
        note("NIL tolerant: 指令不匹配，跳过");
        return;
    }
    if (!VirtualProtect(p, 22, PAGE_EXECUTE_READWRITE, &oldp)) return;
    /* mov eax,[eax+ebx*4] ; test eax,eax ; jz +0x0F ; mov eax,[eax+edi*4] ;
       mov edx,[0x52309c] ; mov edx,[edx+ebx*4] ; mov [edx+esi*4],eax */
    p[0] = 0x8B; p[1] = 0x04; p[2] = 0x98;
    p[3] = 0x85; p[4] = 0xC0;
    p[5] = 0x74; p[6] = 0x0F;
    p[7] = 0x8B; p[8] = 0x04; p[9] = 0xB8;
    p[10] = 0x8B; p[11] = 0x15; p[12] = 0x9C; p[13] = 0x30; p[14] = 0x52; p[15] = 0x00;
    p[16] = 0x8B; p[17] = 0x14; p[18] = 0x9A;
    p[19] = 0x89; p[20] = 0x04; p[21] = 0xB2;
    VirtualProtect(p, 22, oldp, &oldp);
    FlushInstructionCache(GetCurrentProcess(), p, 22);
    nil_tolerant_applied = 1;
    note("NIL tolerant: 已修 0x509FFE（空层指针跳过）");
}


static int sppreview_armed;

static void arm_preview_probe(void)
{
    if (sppreview_armed) return;
    sppreview_armed = 1;
    sbp_arm(0x0050AD74);            /* SpeedButton9Click = 预览入口 */
    note("sppreview: 已在 0x50AD74 打点");
}

static void log_preview_probe(void)
{
    HMODULE he = GetModuleHandleA(0);
    unsigned long *p = (unsigned long *)((char *)he + 0x123230);
    unsigned long *pa = (unsigned long *)*p;
    note("sppreview: [523230]=%08lX len=%ld layers=%u",
         (unsigned long)*p, pa ? (long)pa[-1] : -1,
         (unsigned)(*(unsigned short *)((char *)he + 0x12315C)));
}


/* ================= 自动补跑 TabSheet2Show（层数组分配） ================= */
typedef void (__attribute__((regparm(3))) *PF_TABSHEETSHOW)(void *self, void *sender);

static int tabfix_last_layers = -1;

static void tabfix_try(void)
{
    HMODULE he = GetModuleHandleA(0);
    HWND formw = FindWindowA("TForm1", NULL);
    unsigned long *arrp, *arr;
    unsigned short layers;
    void *self;
    PF_TABSHEETSHOW fn;
    if (!he || !formw) return;
    arrp = (unsigned long *)((char *)he + 0x123230);
    arr = (unsigned long *)*arrp;
    layers = *(unsigned short *)((char *)he + 0x12315C);
    if (arr || layers == 0) return;              /* 已分配或无层 */
    if ((int)layers == tabfix_last_layers) return;
    self = (void *)(unsigned long)GetWindowLongA(formw, 0);   /* VCL 把 Self 存在窗口附加字节 0 */
    if (!self) return;
    fn = (PF_TABSHEETSHOW)((char *)he + 0x107A7C);
    note("tabfix: 层数=%u 数组为空，调用 TabSheet2Show(self=%p)", layers, self);
    fn(self, 0);
    tabfix_last_layers = (int)layers;
    note("tabfix: 调用完成，[523230]=%08lX", (unsigned long)*arrp);
}


static unsigned long arrwatch_last_p, arrwatch_last_len;
static unsigned short arrwatch_last_layers;

static void arrwatch_tick(void)
{
    HMODULE he = GetModuleHandleA(0);
    unsigned long *p, *a;
    unsigned long len;
    unsigned short layers;
    if (!he) return;
    p = (unsigned long *)((char *)he + 0x123230);
    a = (unsigned long *)*p;
    len = a ? (unsigned long)a[-1] : 0xFFFFFFFF;
    layers = *(unsigned short *)((char *)he + 0x12315C);
    if (*p != arrwatch_last_p || len != arrwatch_last_len || layers != arrwatch_last_layers) {
        arrwatch_last_p = *p; arrwatch_last_len = len; arrwatch_last_layers = layers;
        note("arrwatch: [523230]=%08lX len=%ld layers=%u", *p, (long)len, (unsigned)layers);
    }
}


static int selfprobe_done;

static void selfprobe_tick(void)
{
    HWND w = FindWindowA("TForm1", NULL);
    long a, b, c;
    if (!w || selfprobe_done) return;
    a = GetWindowLongA(w, 0);
    b = GetWindowLongA(w, -21);          /* GWL_USERDATA */
    c = GetWindowLongA(w, -16);          /* GWL_HINSTANCE */
    note("selfprobe: win0=%08lX userdata=%08lX hinst=%08lX", (unsigned long)a,
         (unsigned long)b, (unsigned long)c);
    selfprobe_done = 1;
}


/* ================= 补分配 [0x523230]（array of string，每层一个） ================= */
typedef void * (__attribute__((regparm(3))) *PF_GETMEM)(int size);

static int g_layerstr_layers;

static int alloc_layer_strs(void)
{
    HMODULE he = GetModuleHandleA(0);
    unsigned long *slot;
    unsigned short layers;
    PF_GETMEM getmem;
    int *mem;
    unsigned i;

    if (!he) return 0;
    slot = (unsigned long *)((char *)he + 0x123230);
    layers = *(unsigned short *)((char *)he + 0x12315C);
    /* 合理性守卫：层数必须在 1..200 之间，避免读到临时未初始化脏数据 */
    if (*slot || layers == 0 || layers > 200) return 0;
    if ((int)layers == g_layerstr_layers) return 0;

    (void)getmem;
    mem = (int *)HeapAlloc(GetProcessHeap(), 0, 8 + layers * 4);
    if (!mem) { note("layerstr: HeapAlloc 失败"); return 0; }
    memset(mem, 0, 8 + layers * 4);
    mem[0] = -1;                    /* refcount = -1：静态数组，Delphi 不会释放 */
    mem[1] = layers;                /* length */
    for (i = 0; i < layers; i++) {
        /* 每层一个内部动态数组：refcount=-1、长度=0，但预留 0x60 字节可读 */
        int *inner = (int *)HeapAlloc(GetProcessHeap(), 0, 8 + 0x60);
        if (!inner) { ((int *)(mem + 2))[i] = 0; continue; }
        memset(inner, 0, 8 + 0x60);
        inner[0] = -1;
        inner[1] = 0;
        ((int *)(mem + 2))[i] = (int)(inner + 2);
    }
    *slot = (unsigned long)(mem + 2);
    g_layerstr_layers = layers;
    note("layerstr: 已为 %u 层分配内部数组 @%p", (unsigned)layers, (void *)(mem + 2));
    return 1;
}


/* ================= 启动清理：别名文件 + 过大的日志 ================= */
static void startup_cleanup(void)
{
    static int done;
    char log[MAX_PATH], pat[MAX_PATH], dir[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE h;
    if (done) return;
    done = 1;

    if (g_dir[0]) {
        wsprintfA(log, "%s_dongle.log", g_dir);
        h = CreateFileA(log, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, 0, OPEN_EXISTING, 0, 0);
        if (h != INVALID_HANDLE_VALUE) {
            DWORD sz = GetFileSize(h, 0);
            CloseHandle(h);
            if (sz != INVALID_FILE_SIZE && sz > 4 * 1024 * 1024) {
                DeleteFileA(log);
                note("cleanup: _dongle.log 已超过 %lu 字节，清空重来", (unsigned long)sz);
            }
        }
    }

    if (psd_find_tempdir(dir)) {
        wsprintfA(pat, "%sok3d_ascii_*.*", dir);
        h = FindFirstFileA(pat, &fd);
        if (h != INVALID_HANDLE_VALUE) {
            int n = 0;
            do {
                char full[MAX_PATH];
                wsprintfA(full, "%s%s", dir, fd.cFileName);
                if (DeleteFileA(full)) n++;
            } while (FindNextFileA(h, &fd));
            FindClose(h);
            if (n) note("cleanup: 删掉 %d 个旧的别名文件", n);
        }
    }
}


/* ================= 对话框汉化（就地替换 exe 里的英文提示） ================= */
static void patch_bytes(void *dst, const char *src, int n)
{
    DWORD oldp;
    if (!VirtualProtect(dst, n, PAGE_EXECUTE_READWRITE, &oldp)) return;
    memcpy(dst, src, n);
    VirtualProtect(dst, n, oldp, &oldp);
}

static const struct { const char *en; const char *cn; int maxn; } cn_msg_table[] = {
    { "Can not found the specified psd file!", "\xD5\xD2\xB2\xBB\xB5\xBD\xD6\xB8\xB6\xA8\xB5\xC4\x20\x50\x53\x44\x20\xCE\xC4\xBC\xFE\xA3\xA1", 38 },
    { "All layers must be simple layer", "\xCD\xBC\xB2\xE3\xB1\xD8\xD0\xEB\xCA\xC7\xC6\xD5\xCD\xA8\xCD\xBC\xB2\xE3", 32 },
    { 0, 0, 0 }
};

static void localize_dialogs(void)
{
    int mi; int confirm_found = 0;
    static int done;
    HMODULE he = GetModuleHandleA(0);
    unsigned char *base;
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS *nt;
    unsigned char *p, *end;
    static const char pat[] = "Confirm\0continue?";
    static const char cn_caption[] = "\xC8\xB7\xC8\xCF";                        /* 确认 */
    static const char cn_text[]    = "\xBC\xCC\xD0\xF8\xC2\xF0\xA3\xBF";        /* 继续吗？ */
    if (done || !cfg_val("cn_dialogs", 1)) return;
    done = 1;
    if (!he) return;
    base = (unsigned char *)he;
    dos = (IMAGE_DOS_HEADER *)base;
    nt = (IMAGE_NT_HEADERS *)(base + dos->e_lfanew);
    end = base + nt->OptionalHeader.SizeOfImage;

    for (p = base; p + sizeof(pat) < end; p++) {
        if (memcmp(p, pat, sizeof(pat)) == 0) {
            patch_bytes(p, cn_caption, sizeof(cn_caption));          /* 覆盖 "Confirm" + NUL */
            patch_bytes(p + 8, cn_text, sizeof(cn_text));            /* 覆盖 "continue?" 前 8 字节 */
            note("cn_dialogs: 已把 Confirm/continue? 改为中文");
            confirm_found = 1;
            break;
        }
    }
    if (!confirm_found) note("cn_dialogs: 没找到 Confirm/continue? 字符串");

    for (mi = 0; cn_msg_table[mi].en; mi++) {
        const char *en = cn_msg_table[mi].en;
        int n = lstrlenA(en);
        unsigned char *q;
        for (q = base; q + n < end; q++) {
            if (memcmp(q, en, n) == 0) {
                patch_bytes(q, cn_msg_table[mi].cn, lstrlenA(cn_msg_table[mi].cn) + 1);
                note("cn_dialogs: %s -> 中文", en);
                break;
            }
        }
    }
}

static DWORD WINAPI load_watch(LPVOID p)
{
    static const char *names[] = {"ok3d.dll","ok3d1.dll","ok3d4.dll","zu6.dll","zu06.dll","zu61.dll",
                                  "my32.dll","dspr.dll","save3d.dll","8602.dll","rip3d.dll","cmyktiff2_real.dll", NULL};
    unsigned char seen[16]; int i;
    (void)p;
    memset(seen, 0, sizeof(seen));
    static int seen_hmain = 0;
    for (;;) {
        if (g_main_closing) {
            note("AUTO_FIX: 主窗体关闭，退出监控线程");
            return 0;
        }
        if (cfg_on("arrwatch", 0, "_arrwatch.txt"))
            arrwatch_tick();
        startup_cleanup();
        localize_dialogs();
        ensure_real_patched();

        HWND hmain = FindWindowA("TForm1", NULL);
        if (seen_hmain && (!hmain || !IsWindow(hmain))) {
            g_main_closing = 1;
            note("AUTO_FIX: 主窗体已销毁，退出监控线程");
            return 0;
        }
        if (hmain) {
            seen_hmain = 1;
            /* 静默清理 cmyktiff2_real.DLL 写完 TIFF 收尾可能弹出的 Application Error 弹窗 */
            dismiss_app_error_dialog();
            /* 仅当已有切片缓存时（已导出过 TIFF）同步启用 PSD1，防止 EReadError 跳过 0x506147 导致菜单仍灰 */
            if (GetFileAttributesA("C:\\ok3dtemp\\vwd001.gjs") != INVALID_FILE_ATTRIBUTES) {
                char *form = NULL;
                if (!IsBadReadPtr((void *)0x005230B8, 4))
                    form = *(char **)0x005230B8;
                if (form && !IsBadReadPtr(form, 0x500)) {
                    char *psd1 = *(char **)(form + 0x4DC);
                    if (psd1 && !IsBadWritePtr(psd1 + 0x39, 1) && *(unsigned char *)(psd1 + 0x39) == 0) {
                        *(unsigned char *)(psd1 + 0x39) = 1;
                        HMENU hm = GetMenu(hmain);
                        if (hm) {
                            HMENU sm = GetSubMenu(hm, 1);
                            if (sm) EnableMenuItem(sm, 17, 0);
                        }
                        note("LAYER_UNLOCK: 检测到切片缓存，已启用【输出PSD】菜单");
                    }
                }
            }
            /* 无模态弹窗时再非阻塞更新主窗口标题，防止保存框期间跨线程阻塞 */
            if (GetLastActivePopup(hmain) == hmain) {
                char title[512];
                DWORD_PTR res = 0;
                title[0] = 0;
                if (SendMessageTimeoutA(hmain, WM_GETTEXT, sizeof(title), (LPARAM)title,
                                        SMTO_ABORTIFHUNG | SMTO_BLOCK, 100, &res) && title[0]) {
                    if (strncmp(title, "Psdto3d 10", 10) == 0 && !strstr(title, "2026.11.26")) {
                        char new_title[512];
                        const char *rest = title + 10;
                        while (*rest && (*rest == '.' || *rest == '1' || *rest == ' ')) rest++;
                        if (*rest) {
                            wsprintfA(new_title, "Psdto3d 10.1 (2026.11.26) - %s", rest);
                        } else {
                            lstrcpyA(new_title, "Psdto3d 10.1 (2026.11.26)");
                        }
                        SendMessageTimeoutA(hmain, WM_SETTEXT, 0, (LPARAM)new_title,
                                            SMTO_ABORTIFHUNG | SMTO_BLOCK, 100, &res);
                    }
                }
            }
        }
        if (cfg_on("layers_up", 0, "_layers_up.txt") ||
            cfg_on("layerstr", 0, "_layerstr.txt"))
            alloc_layer_strs();
        if (cfg_on("selfprobe", 0, "_selfprobe.txt"))
            selfprobe_tick();
        if (cfg_on("tabfix", 0, "_tabfix.txt"))
            tabfix_try();
        if (cfg_on("sbp_psd", 0, "_sbp_psd.txt"))
            arm_preview_probe();
        if (cfg_on("nil_tolerant", 0, "_nil_tolerant.txt")) {
            HMODULE he3 = GetModuleHandleA(0);
            if (he3) patch_nil_tolerant(he3);
        }
        if (cfg_on("inline_cfa", 0, "_inline_cfa.txt"))
            inline_cfa_install();
        /* fix_cancel_removed: 该补丁会破坏打开工程，已停用 */
        if (cfg_on("native_probe", 0, "_native_probe.txt")) {
            static int probe_done;
            if (!probe_done) {
                probe_done = 1;
                sbp_arm(0x0050B17D);            /* writepsd 调用点 */
                note("PROBE armed at 0050B17D");
            }
        }
        if (cfg_on("native_psd", 1, "_native_psd.txt")) {
            static int writepsd_callsite_done;
            HMODULE he = GetModuleHandleA(0);
            if (!writepsd_callsite_done && he) {
                unsigned char *cs = (unsigned char *)((char *)he + 0x10B17D);
                DWORD oldp2;
                if (cs[0] == 0xFF && cs[1] == 0x15 &&
                    VirtualProtect(cs, 6, PAGE_EXECUTE_READWRITE, &oldp2)) {
                    long rel = (long)((char *)writepsd_shim - (char *)(cs + 5));
                    cs[0] = 0xE8;
                    *(long *)(cs + 1) = rel;
                    cs[5] = 0x90;
                    VirtualProtect(cs, 6, oldp2, &oldp2);
                    FlushInstructionCache(GetCurrentProcess(), cs, 6);
                    note("NATIVE callsite patched %p -> %p rel=%ld", cs, (void *)writepsd_shim, rel);
                } else {
                    note("NATIVE callsite bytes: %02X %02X", cs[0], cs[1]);
                }
                /* 保持原版按操作层级启用 PSD 导出菜单与 N7Click/N26Click 按钮守卫 (不强行修改) */
                /* FormClose 写完配置后将 [0x5230B4] 清零而不调用 DynArrayClear，兼顾消除退出与 Finalization 报错 */
                unsigned char *p_fc = (unsigned char *)((char *)he + 0xFF66B);
                if (p_fc[0] == 0x6A && p_fc[1] == 0x00 && p_fc[2] == 0xB8 &&
                    p_fc[3] == 0xB4 && p_fc[4] == 0x30 && p_fc[5] == 0x52 && p_fc[6] == 0x00 &&
                    p_fc[23] == 0x83 && p_fc[24] == 0xC4 && p_fc[25] == 0x04) {
                    DWORD oldp6;
                    if (VirtualProtect(p_fc, 26, PAGE_EXECUTE_READWRITE, &oldp6)) {
                        /* mov dword ptr [0x5230B4], 0 (10 bytes) + 16 * nop */
                        static const unsigned char z_b4[10] = { 0xC7,0x05,0xB4,0x30,0x52,0x00,0x00,0x00,0x00,0x00 };
                        memcpy(p_fc, z_b4, 10);
                        memset(p_fc + 10, 0x90, 16);
                        VirtualProtect(p_fc, 26, oldp6, &oldp6);
                        FlushInstructionCache(GetCurrentProcess(), p_fc, 26);
                        note("EXIT_FIX: FormClose [5230B4] := nil patched at %p", p_fc);
                    }
                }
                writepsd_callsite_done = 1;
            }
            if (he) {
                void **slot = (void **)((char *)he + 0x123278);
                if (*slot != (void *)writepsd_shim) {
                    DWORD oldp;
                    if (VirtualProtect(slot, 4, PAGE_READWRITE, &oldp)) {
                        if (writepsd_slot_hooked != (int)(unsigned long)*slot) {
                            writepsd_slot_hooked = (int)(unsigned long)*slot;
                            note("NATIVE writepsd slot -> shim (was %08lX)", (unsigned long)*slot);
                        }
                        *slot = (void *)writepsd_shim;
                        VirtualProtect(slot, 4, oldp, &oldp);
                    }
                }
            }
        }
        if (cfg_on("psd_limit", 0, "_psd_limit.txt")) {
            static int rip3d_hooked;
            HMODULE hr = GetModuleHandleA("rip3d.dll");
            if (hr && !rip3d_hooked) {
                PF_CreateFileA dummy2 = 0;
                rip3d_hooked = 1;
                patch_slot(hr, 0x15264, (void *)e_cfa_probe, (void **)&dummy2);
                note("RIP3D CFA hooked");
            }
        }
        for (i = 0; names[i]; i++) {
            if (!seen[i]) {
                HMODULE m = GetModuleHandleA(names[i]);
                if (m) {
                    if (cfg_on("modload", 0, "_modload.txt"))
                        note("MODLOAD %s base=%08lX", names[i], (unsigned long)m);
                    seen[i] = 1;
                }
            }
        }
        Sleep(120);
    }
    return 0;
}

static DWORD WINAPI mod_watch(LPVOID p)
{
    static const char *names[] = {"rip3d.dll", "ok3d1.dll", NULL};
    unsigned char done[8];
    int i;
    (void)p;
    memset(done, 0, sizeof(done));
    for (;;) {
        for (i = 0; names[i]; i++) {
            if (!done[i]) {
                HMODULE m = GetModuleHandleA(names[i]);
                if (m) {
                    Sleep(2000);              /* let the module finish loading */
                    patch_module_logonly(m, names[i]);
                    done[i] = 1;
                }
            }
        }
        Sleep(200);
    }
    return 0;
}

static int g_zu06_cfa_seen;


/* ================= 内联 hook CreateFileA（覆盖所有模块） ================= */
static void *g_cfa_tramp;
static int g_inline_cfa_ok;
static int g_inline_cfa_seen;

static void inline_cfa_install(void)
{
    FARPROC orig = GetProcAddress(GetModuleHandleA("kernel32.dll"), "CreateFileA");
    unsigned char *p = (unsigned char *)orig;
    unsigned char *t;
    DWORD oldp;
    long rel;
    if (!orig || g_inline_cfa_ok) return;
    g_cfa_tramp = VirtualAlloc(0, 64, MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    if (!g_cfa_tramp) return;
    t = (unsigned char *)g_cfa_tramp;
    if (p[0] == 0xE9) {                                /* tramp resolves forwarder: jmp rel32 */
        unsigned char *target = p + 5 + *(long *)(p + 1);
        t[0] = 0xE9;
        *(long *)(t + 1) = (long)(target - (t + 5));
    } else {
        memcpy(t, p, 5);                               /* 复制原开头 5 字节，再跳回 +5 */
        t[5] = 0xE9;
        *(long *)(t + 6) = (long)((p + 5) - (t + 10));
    }
    if (!VirtualProtect(p, 8, PAGE_EXECUTE_READWRITE, &oldp)) return;
    rel = (long)((unsigned char *)e_cfa_inline - (p + 5));
    p[0] = 0xE9;
    *(long *)(p + 1) = rel;
    VirtualProtect(p, 8, oldp, &oldp);
    FlushInstructionCache(GetCurrentProcess(), p, 8);
    g_inline_cfa_ok = 1;
    note("INLINE CFA: 已挂钩 kernel32!CreateFileA -> %p, tramp=%p", (void *)e_cfa_inline, g_cfa_tramp);
}

static HANDLE WINAPI e_cfa_inline(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                  DWORD disp, DWORD flags, HANDLE tmpl)
{
    HANDLE (WINAPI *real)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
    real = (HANDLE (WINAPI *)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE))g_cfa_tramp;
    if (name && g_inline_cfa_seen < 60) {
        int l = lstrlenA(name);
        if (l > 4 && lstrcmpiA(name + l - 4, ".psd") == 0) {
            g_inline_cfa_seen++;
            note("INLINE CFA: %s", name);
        }
    }
    if (name && cfg_on("psd_limit", 0, "_psd_limit.txt")) {
        int l = lstrlenA(name);
        if (l > 4 && lstrcmpiA(name + l - 4, ".psd") == 0 && psd_layers_guard(name)) {
            SetLastError(5);
            return INVALID_HANDLE_VALUE;
        }
    }
    return real(name, acc, share, sa, disp, flags, tmpl);
}

static HANDLE WINAPI e_cfa_guard(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                 DWORD disp, DWORD flags, HANDLE tmpl)
{
    if (g_zu06_cfa_seen < 40) {
        g_zu06_cfa_seen++;
        note("ZU06 CFA CALL: %s", name ? name : "(null)");
    }
    if (name) {
        int len = lstrlenA(name);
        if (len > 4 && lstrcmpiA(name + len - 4, ".psd") == 0 &&
            cfg_on("psd_limit", 0, "_psd_limit.txt")) {
            int layers = 0;
            if (psd_count_layers(name, &layers) && layers > 40) {
                char msg[512];
                wsprintfA(msg,
                    "这个 PSD 有 %d 个图层，而程序的导入器最多只支持 40 层。\r\n\r\n"
                    "继续导入会直接崩溃。请在 Photoshop 里合并部分图层，\r\n"
                    "把图层数降到 40 以内再导入。", layers);
                note("PSD guard: %s 有 %d 层 > 40，已拦截", name, layers);
                MessageBoxA(0, msg, "图层数超出程序上限", MB_OK | MB_ICONWARNING);
                SetLastError(5);
                return INVALID_HANDLE_VALUE;
            }
        }
    }
    return o_cfa(name, acc, share, sa, disp, flags, tmpl);
}

static void patch_zu06(HMODULE m)
{
    if (!m || g_zu06_patched) return;
    g_zu06_patched = 1;
    /* Full set (experiment A re-run on a clean temp dir): the module's device
       session must be answered end-to-end, otherwise its licence values come
       back as zero and the caller divides by zero. */
    if (cfg_on("psd_limit", 0, "_psd_limit.txt")) {
        PF_CreateFileA dummy = 0;
        patch_slot((void *)m, 0xB421C, (void *)e_cfa_guard, (void **)&dummy);
        patch_slot((void *)m, 0xB43F8, (void *)e_cfa_guard, (void **)&dummy);
        note("PSD guard: zu06 CreateFileA 已挂钩");
    }
    if (cfg_on("zu06_patch_iat", 0, "_zu06_patch_iat.txt")) {
    patch_slot((void *)m, 0xB421C, (void *)e_cfa,    (void **)&o_cfa);
    patch_slot((void *)m, 0xB43F8, (void *)e_cfa,    (void **)&o_cfa);
    patch_slot((void *)m, 0xB43E8, (void *)e_dio,    (void **)&o_dio);
    patch_slot((void *)m, 0xB4208, (void *)e_rf,     (void **)&o_rf);
    patch_slot((void *)m, 0xB42F0, (void *)e_rf,     (void **)&o_rf);
    patch_slot((void *)m, 0xB41F4, (void *)e_wf,     (void **)&o_wf);
    patch_slot((void *)m, 0xB42B0, (void *)e_wf,     (void **)&o_wf);
    patch_slot((void *)m, 0xB41FC, (void *)e_sfp,    (void **)&o_sfp);
    patch_slot((void *)m, 0xB42D0, (void *)e_sfp,    (void **)&o_sfp);
    patch_slot((void *)m, 0xB4220, (void *)e_ch,     (void **)&o_ch);
    patch_slot((void *)m, 0xB4404, (void *)e_ch,     (void **)&o_ch);
    patch_slot((void *)m, 0xB486C, (void *)e_sddil,  (void **)&o_sddil);
    patch_slot((void *)m, 0xB4870, (void *)e_sddida, (void **)&o_sddida);
    patch_slot((void *)m, 0xB4874, (void *)e_sdeif,  (void **)&o_sdeif);
    patch_slot((void *)m, 0xB4878, (void *)e_sdgcd,  (void **)&o_sdgcd);
    note("EMU patched zu06.dll IAT (full) base=%08lX", (unsigned long)m);
    }
    g_zu06_base = (unsigned long)m;
    if (cfg_on("zu06_sbp", 0, "_zu06_sbp.txt")) {
        sbp_arm(g_zu06_base + 0xA4504);   /* writepsd entry: log args + call count */
        sbp_arm(g_zu06_base + 0xA4800);   /* just before the first PSD stream write */
        sbp_arm(g_zu06_base + 0xA497D);   /* per-layer loop head */
    }
    if (cfg_on("zu06_pathlog", 0, "_zu06_pathlog.txt")) {
        static int logged;
        if (!logged) {
            const char *sp = (const char *)((char *)m + 0xB1D14);
            logged = 1;
            note("zu06 pathbuf @B1D14: '%s'", sp);
        }
    }
    if (cfg_on("zu06_flag", 0, "_zu06_flag.txt")) {
        int *flag = (int *)((char *)m + 0xAB0A0);   /* DAT_004ab0a0 */
        DWORD oldp;
        if (VirtualProtect(flag, 4, PAGE_READWRITE, &oldp)) {
            note("zu06 flag 4AB0A0: %d -> 1", *flag);
            *flag = 1;
            VirtualProtect(flag, 4, oldp, &oldp);
        }
    }
    if (cfg_on("zu06_cfa_only", 0, "_zu06_cfa_only.txt")) {
        patch_slot((void *)m, 0xB421C, (void *)e_cfa_logonly, (void **)&o_cfa);
        patch_slot((void *)m, 0xB43F8, (void *)e_cfa_logonly, (void **)&o_cfa);
        note("EMU zu06 CreateFileA hooked (log only)");
    }
    if (cfg_on("zu06_wf_log", 0, "_zu06_wf_log.txt")) {
        patch_slot((void *)m, 0xB41F4, (void *)e_wf_logonly, (void **)&o_wf);
        patch_slot((void *)m, 0xB42B0, (void *)e_wf_logonly, (void **)&o_wf);
        note("EMU zu06 WriteFile hooked (log only)");
    }
}

static DWORD WINAPI zu06_watch(LPVOID p)
{
    (void)p;
    for (;;) {
        HMODULE m = GetModuleHandleA("zu06.dll");
        if (m) {
            patch_zu06(m);
            if (g_zu06_patched) return 0;
        }
        Sleep(120);
    }
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID reserved)
{
    (void)hinst; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        HMODULE hpin = NULL;
        GetModuleHandleExA(0x00000004 | 0x00000001, (LPCSTR)DllMain, &hpin); /* FROM_ADDRESS | PIN */
        dongle_spy_install();
        CreateThread(NULL, 0, zu06_watch, NULL, 0, NULL);

        CreateThread(NULL, 0, load_watch, NULL, 0, NULL);

        if (cfg_on("cn_ui", 0, "_cn_ui.txt"))

            CreateThread(NULL, 0, cn_ui_thread, NULL, 0, NULL);
    }
    return TRUE;
}


