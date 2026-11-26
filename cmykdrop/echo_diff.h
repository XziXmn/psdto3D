/* Device-side bytes for parameter-type replies: offsets where the real reply
   differs from the real write. Everything else is the current write echoed back. */
#ifndef ECHO_DIFF_H
#define ECHO_DIFF_H

static const unsigned short K_DIFF_OFF_S3[62] = {
    4, 5, 12, 13, 48, 49, 50, 51, 52, 53, 54, 56,
    57, 58, 59, 60, 62, 296, 297, 298, 299, 304, 305, 306,
    307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318,
    319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330,
    331, 332, 333, 334, 335, 336, 337, 338, 339, 340, 341, 342,
    343, 344,
};
static const unsigned char K_DIFF_VAL_S3[62] = {
    0x02, 0x04, 0xA4, 0x08, 0x13, 0x3C, 0x98, 0x27, 0xEA, 0x7F, 0x42, 0x42,
    0xF4, 0x91, 0x81, 0x29, 0x46, 0x38, 0x36, 0x30, 0x32, 0x30, 0x37, 0x35,
    0x35, 0x2D, 0x32, 0x36, 0x31, 0x37, 0x35, 0x37, 0x35, 0x36, 0x68, 0x74,
    0x74, 0x70, 0x3A, 0x2F, 0x2F, 0x77, 0x77, 0x77, 0x2E, 0x33, 0x64, 0x39,
    0x39, 0x2E, 0x63, 0x6F, 0x6D, 0x6C, 0x63, 0x64, 0x33, 0x64, 0x2E, 0x63,
    0x6E, 0x00,
};

static const unsigned short K_DIFF_OFF_S4[23] = {
    16, 20, 24, 28, 77, 78, 79, 80, 81, 82, 83, 84,
    85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95,
};
static const unsigned char K_DIFF_VAL_S4[23] = {
    0x20, 0x1F, 0x02, 0x02, 0x88, 0xC3, 0x40, 0xAC, 0x13, 0x14, 0x61, 0xD4,
    0xDA, 0x20, 0x40, 0x16, 0x8B, 0xC5, 0x62, 0xB1, 0x58, 0x1C, 0x40,
};

typedef struct { unsigned key; const unsigned short *off; const unsigned char *val; int n; } ECHODIFF;
static const ECHODIFF K_ECHO_DIFF[] = {
    { 0x663304FFu, K_DIFF_OFF_S3, K_DIFF_VAL_S3, 62 },
    { 0x3EF30000u, K_DIFF_OFF_S4, K_DIFF_VAL_S4, 23 },
    { 0xF25D0000u, K_DIFF_OFF_S4, K_DIFF_VAL_S4, 23 },
};
#define K_ECHO_DIFF_N (int)(sizeof(K_ECHO_DIFF)/sizeof(K_ECHO_DIFF[0]))

#endif