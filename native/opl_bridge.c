/* Open Reunion's opaque C ABI for the separately licensed Nuked OPL3 core. */
#include <stdlib.h>
#include "opl3.h"
#if defined(_WIN32)
#define API __declspec(dllexport)
#else
#define API __attribute__((visibility("default")))
#endif

API unsigned reunion_opl_abi(void) { return 1; }
API void *reunion_opl_create(unsigned rate) {
    if (rate < 8000 || rate > 192000) return NULL;
    opl3_chip *chip = calloc(1, sizeof(opl3_chip));
    if (chip) OPL3_Reset(chip, rate);
    return chip;
}
API void reunion_opl_destroy(void *chip) { free(chip); }
API void reunion_opl_write(void *chip, unsigned reg, unsigned value) {
    if (chip && reg < 512 && value < 256)
        OPL3_WriteRegBuffered(chip, (uint16_t)reg, (uint8_t)value);
}
API void reunion_opl_generate(void *chip, int16_t *samples, unsigned frames) {
    if (chip && samples) OPL3_GenerateStream(chip, samples, frames);
}
