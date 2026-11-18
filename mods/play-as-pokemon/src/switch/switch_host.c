/* The "host" of the Switch / emulator build of Play as Pokemon: what Modtopia does for the Recompia mod, done inside the game.
 *
 * build_emulator.py links this with play_as_pokemon.c (compiled with PAP_SWITCH) and the hook trampolines into an unused function
 * of main (main+0x6B32C0, which nothing calls or points to), and the mod's variables into unused bss (main+0x3D15000..). Every
 * address is reached PC-relative, so it runs wherever the system loads main.
 *
 *   memory      plain loads and stores (addresses outside the 39-bit user range are refused)
 *   guest call  a branch with x0..x7 / v0..v7 from the MtCall, which gets x0..x7 / v0..v7 back
 *   controller  nn::hid::GetNpadState of the handheld console and of controller 1, every frame (the game's own imports)
 *   time        the system counter (CNTPCT_EL0)
 *
 * The mod's initialised variables are copied into their bss home at the first hook (the patch can only hold read-only bytes). */
#include <modtopia/modtopia.h>
#include <stdatomic.h>
#include <stdint.h>

/* linker script symbols (build_emulator.py) */
extern char pap_main_base[];                     /* main + 0 */
extern char pap_data_load[], pap_data_start[], pap_data_end[];
/* the game's nn::hid imports (PLT entries in main) */
extern uint32_t hid_style_set(const uint32_t *id);
extern void hid_state_fullkey(void *state, const uint32_t *id);
extern void hid_state_handheld(void *state, const uint32_t *id);
extern void hid_state_joydual(void *state, const uint32_t *id);

void pap_mod_start(const MtHost *host);          /* play_as_pokemon.c */

/* ---------------------------------------------------------------- libc bits (no builtins: these are the real ones) */
void *memset(void *s, int c, size_t n) {
    volatile uint8_t *p = s;
    while (n--) *p++ = (uint8_t)c;
    return s;
}
void *memcpy(void *d, const void *s, size_t n) {
    volatile uint8_t *o = d;
    const uint8_t *i = s;
    while (n--) *o++ = *i++;
    return d;
}
int strcmp(const char *a, const char *b) {
    while (*a && *a == *b) a++, b++;
    return (unsigned char)*a - (unsigned char)*b;
}

/* ---------------------------------------------------------------- the host table */
static int ok_addr(uint64_t a, size_t n) { return a >= 0x8000000ull && a + n <= 0x8000000000ull && a + n >= a; }
static int sw_mem_read(uint64_t a, void *out, size_t n) {
    if (!ok_addr(a, n)) return MT_ERR_FAULT;
    memcpy(out, (const void *)a, n);
    return MT_OK;
}
static int sw_mem_write(uint64_t a, const void *in, size_t n) {
    if (!ok_addr(a, n)) return MT_ERR_FAULT;
    memcpy((void *)a, in, n);
    return MT_OK;
}
static uint64_t sw_reg_get(MtHookCtx *c, int r) { return r >= 0 && r < 31 ? c->x[r] : 0; }
static int sw_reg_set(MtHookCtx *c, int r, uint64_t v) {
    if (r < 0 || r >= 31) return MT_ERR;
    c->x[r] = v;
    return MT_OK;
}
static uint64_t sw_module_base(const char *name) { return name && !strcmp(name, "main") ? (uint64_t)pap_main_base : 0; }
static uint64_t sw_frame(void) { return 0; }

/* x0 = the function, x1 = the MtCall: x0..x7 and q0..q7 in, the same out. */
int sw_call_asm(uint64_t fn, MtCall *c);
__asm__(".text\n.p2align 2\n.type sw_call_asm, %function\nsw_call_asm:\n"
        "  stp x29, x30, [sp, #-32]!\n  mov x29, sp\n  str x19, [sp, #16]\n"
        "  mov x19, x1\n  mov x16, x0\n"
        "  ldp q0, q1, [x19, #64]\n  ldp q2, q3, [x19, #96]\n  ldp q4, q5, [x19, #128]\n  ldp q6, q7, [x19, #160]\n"
        "  ldp x0, x1, [x19]\n  ldp x2, x3, [x19, #16]\n  ldp x4, x5, [x19, #32]\n  ldp x6, x7, [x19, #48]\n"
        "  blr x16\n"
        "  stp x0, x1, [x19]\n  stp x2, x3, [x19, #16]\n  stp x4, x5, [x19, #32]\n  stp x6, x7, [x19, #48]\n"
        "  stp q0, q1, [x19, #64]\n  stp q2, q3, [x19, #96]\n  stp q4, q5, [x19, #128]\n  stp q6, q7, [x19, #160]\n"
        "  mov w0, #0\n  ldr x19, [sp, #16]\n  ldp x29, x30, [sp], #32\n  ret\n"
        ".size sw_call_asm, .-sw_call_asm\n");
static int sw_call_guest(uint64_t fn, MtCall *c) {
    if (!ok_addr(fn, 4) || (fn & 3)) return MT_ERR_FAULT;
    return sw_call_asm(fn, c);
}

/* The controller: the console in handheld mode and controller 1 (Pro Controller or both Joy-Con), merged. */
typedef struct {
    int64_t sampling;
    uint64_t buttons;
    int32_t lx, ly, rx, ry;
    uint32_t attributes, pad;
} NpadState;
enum { STYLE_FULLKEY = 1u << 0, STYLE_HANDHELD = 1u << 1, STYLE_JOYDUAL = 1u << 2 };
static void merge(MtPad *out, const NpadState *s) {
    out->buttons |= (uint32_t)(s->buttons & 0xFFFF);
    int32_t l = (s->lx < 0 ? -s->lx : s->lx) + (s->ly < 0 ? -s->ly : s->ly), have = (out->lx < 0 ? -out->lx : out->lx) + (out->ly < 0 ? -out->ly : out->ly);
    if (l > have) out->lx = (int16_t)s->lx, out->ly = (int16_t)s->ly;
    int32_t r = (s->rx < 0 ? -s->rx : s->rx) + (s->ry < 0 ? -s->ry : s->ry), rh = (out->rx < 0 ? -out->rx : out->rx) + (out->ry < 0 ? -out->ry : out->ry);
    if (r > rh) out->rx = (int16_t)s->rx, out->ry = (int16_t)s->ry;
}
static int sw_pad_read(MtMod *m, int player, MtPad *out) {
    (void)m;
    memset(out, 0, sizeof *out);
    if (player != 0) return MT_ERR;
    static const uint32_t IDS[2] = {0x20, 0};   /* Handheld, No1 */
    for (int i = 0; i < 2; i++) {
        uint32_t style = hid_style_set(&IDS[i]);
        NpadState s;
        memset(&s, 0, sizeof s);
        if (style & STYLE_HANDHELD) hid_state_handheld(&s, &IDS[i]), merge(out, &s);
        if (style & STYLE_FULLKEY) memset(&s, 0, sizeof s), hid_state_fullkey(&s, &IDS[i]), merge(out, &s);
        if (style & STYLE_JOYDUAL) memset(&s, 0, sizeof s), hid_state_joydual(&s, &IDS[i]), merge(out, &s);
    }
    return MT_OK;
}

/* ---------------------------------------------------------------- start-up: at the first hook, on whichever thread gets there */
static MtHost g_host;
static _Atomic int g_ready;   /* 0 not yet, 1 being set up, 2 ready (bss starts at 0) */
int pap_ready(void) {
    int s = atomic_load_explicit(&g_ready, memory_order_acquire);
    if (s == 2) return 1;
    int expect = 0;
    if (atomic_compare_exchange_strong(&g_ready, &expect, 1)) {
        memcpy(pap_data_start, pap_data_load, (size_t)(pap_data_end - pap_data_start));
        g_host.size = sizeof g_host;
        g_host.mem_read = sw_mem_read, g_host.mem_write = sw_mem_write, g_host.call_guest = sw_call_guest;
        g_host.reg_get = sw_reg_get, g_host.reg_set = sw_reg_set, g_host.module_base = sw_module_base;
        g_host.frame = sw_frame, g_host.pad_read = sw_pad_read;
        pap_mod_start(&g_host);
        atomic_store_explicit(&g_ready, 2, memory_order_release);
        return 1;
    }
    return 0;   /* another thread is setting up right now: this one stop goes through untouched */
}
