/* The Switch / emulator stand-in for the Modtopia SDK header (recompia/play-as-pokemon/include/modtopia/modtopia.h).
 *
 * The emulator build compiles the same play_as_pokemon.c as the Recompia mod, with PAP_SWITCH defined. The code then runs inside
 * the game itself (an IPS patch places it in main), so the "host" is switch_host.c: guest memory is plain memory, a guest call is
 * a branch, a hook is a branch from the game's instruction to a trampoline (build_emulator.py), and there is no log, no message
 * box and no settings. Only what play_as_pokemon.c uses is here. Freestanding: no libc. */
#pragma once
#include <stddef.h>
#include <stdint.h>

#define MT_API_VERSION 0
#define MT_EXPORT
#define MT_DECLARE_MOD()

typedef struct MtHost MtHost;
typedef struct MtMod MtMod;
/* One stop at a hook point: the trampoline's saved registers (x0..x30, then nzcv), on its stack. */
typedef struct MtHookCtx { uint64_t x[31]; uint64_t nzcv; } MtHookCtx;

enum { MT_OK = 0, MT_ERR = -1, MT_ERR_UNKNOWN = -2, MT_ERR_FAULT = -3, MT_ERR_STATE = -4, MT_ERR_VERSION = -5 };
enum { MT_LOG_DEBUG = 0, MT_LOG_INFO = 1, MT_LOG_WARN = 2, MT_LOG_ERROR = 3 };
enum { MT_CONTINUE = 0, MT_HANDLED = 1 };

typedef struct MtCall {
    uint64_t x[8];
    uint8_t v[8][16];
} MtCall;

/* The Switch's own button bits (nn::hid::NpadButton), which Modtopia's are. */
enum {
    MT_PAD_A = 1u << 0, MT_PAD_B = 1u << 1, MT_PAD_X = 1u << 2, MT_PAD_Y = 1u << 3, MT_PAD_LSTICK = 1u << 4, MT_PAD_RSTICK = 1u << 5,
    MT_PAD_L = 1u << 6, MT_PAD_R = 1u << 7, MT_PAD_ZL = 1u << 8, MT_PAD_ZR = 1u << 9, MT_PAD_PLUS = 1u << 10, MT_PAD_MINUS = 1u << 11,
    MT_PAD_LEFT = 1u << 12, MT_PAD_UP = 1u << 13, MT_PAD_RIGHT = 1u << 14, MT_PAD_DOWN = 1u << 15
};
typedef struct MtPad {
    uint32_t buttons;
    int16_t lx, ly, rx, ry;
} MtPad;

typedef int (*MtHookFn)(MtHookCtx *c, void *user);

/* Filled in at run time by switch_host.c (a table in the patch would need absolute addresses). Unset entries are 0. */
struct MtHost {
    uint32_t size;
    int (*mem_read)(uint64_t addr, void *out, size_t n);
    int (*mem_write)(uint64_t addr, const void *in, size_t n);
    int (*call_guest)(uint64_t addr, MtCall *regs);
    uint64_t (*reg_get)(MtHookCtx *c, int reg);
    int (*reg_set)(MtHookCtx *c, int reg, uint64_t value);
    uint64_t (*module_base)(const char *name);
    uint64_t (*frame)(void);
    int (*pad_read)(MtMod *mod, int player, MtPad *out);
    int (*notify)(MtMod *mod, const char *text, double seconds);
    int (*key_down)(MtMod *mod, const char *key);
    int (*pad_block)(MtMod *mod, int player, const MtPad *mask);
    const char *(*config_string)(MtMod *mod, const char *key);   /* no settings: never set */
    int (*config_bool)(MtMod *mod, const char *key);
};

#define MT_HOST_HAS(host, field) ((host)->field != 0)
/* No log on a Switch: the arguments are not even evaluated. */
#define mt_logf(...) ((void)0)
