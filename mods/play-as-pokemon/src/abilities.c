/* Play as Pokemon (emulator / Switch): the Pokemon's ability. GPL-3.0-or-later.
 *
 * The same logic as the Recompia mod's abilities (recompia/play-as-pokemon/src/play_as_pokemon.c), compiled to AArch64 and placed
 * by the IPS patch at the end of main's code (build_abilities.py). It runs inside the game, so game memory is read directly and the
 * game's functions are called directly; every game address is a symbol main+offset the linker resolves PC-relative, so the code
 * works wherever main is loaded.
 *
 * Entry: ability_entry, reached by `bl` from the player update (main+0x2FACE0, which was `blr x8`). It runs ability_tick(character)
 * and then jumps on to the patch's existing per-frame hook (tick_next), which ends with the original call.
 *
 * The A to Z list the cheat's ZL + D-pad Left / Right steps through lives in game RAM (u16 FLAG+0x100.., AZ_COUNT entries): the
 * patch ships it packed (9 bits a Pokemon) in the padding after main's read-only data, and ability_tick unpacks it once. The
 * end of main's code holds this code, and the Unlimited Crafting Storage Range mod's patch right after it: there is no room
 * for the list there as well.
 *
 * Buttons come from the cheat (the cheat VM sees the controller ~12 times a second): u8 FLAG+0x08 ZR held, +0x09 ZL held,
 * +0x0A a D-pad direction or L3 held, +0x1D ZL + D-pad Down held. u16 FLAG+0 = the form held (0 = not transformed).
 *
 * Abilities (see the Recompia source for how each was found):
 *   Grow      action 706 animation, then FN_GROW(farm, &cell): crops and plants around the cell grow a stage
 *   Burn      action 700 animation, then FN_OBJECT_ACT(objects, &town Pokemon id, cell, 120): the object there burns
 *   Water     sludge not bubbled yet in reach: action 705 animation, then Bubble (action 705's handler, a town Pokemon's
 *             controller as owner); otherwise action 703 animation, then FN_WATER (the Water Gun's hit) on the ground
 *   Generate  action 709 animation, then FN_OBJECT_ACT(..., 122): the light or machine there is powered
 */
typedef unsigned long u64;
typedef unsigned int u32;
typedef unsigned short u16;
typedef short s16;
typedef unsigned char u8;
typedef float v4f __attribute__((vector_size(16)));

/* main+offset symbols (build_abilities.py passes them to the linker) */
extern u8 G_PLAYER[], G_ENTITIES[], G_FIELD[], G_OBJECTS[], G_WORLD[], G_GAMEMGR[], FLAG[];
extern u32 fn_grow(void *farm, s16 *cell);
extern u64 fn_object_act(u64 objects, u16 *by, u64 x, u64 y, u32 z, u32 kind);
extern u32 fn_water(s16 *cell, u32 power, u32 by_player, u32 zero, u32 id, u32 flag);
extern u64 fn_bubble(u64 handler, u64 controller, u32 *args);
extern u32 fn_has_layer(u64 world, u8 *kind, s16 *cell);
extern void tick_next(void);
extern const u8 AZ_PACKED[];   /* main+AZ_AT, in the read-only padding */
#include "abilities_table.h"   /* ABILITY_BITS[]: 3 bits a character-definition id, 0 none, 1 + AB_* */

enum { AB_GROW, AB_BURN, AB_WATER, AB_GENERATE };
#define R64(a) (*(volatile u64 *)(a))
#define R32(a) (*(volatile u32 *)(a))
#define R16(a) (*(volatile u16 *)(a))
#define R8(a) (*(volatile u8 *)(a))
#define TICKS_MS 19200ull   /* the system counter runs at 19.2 MHz */

typedef struct {
    u8 phase, kind, bubble, prev_zr, prev_combo, pad[3];
    u64 at, ready;
    s16 cell[4];
} State;
#define ST ((State *)(FLAG + 0x40))   /* free bytes after the patch's own state */
#define AZ ((volatile u16 *)(FLAG + 0x100))

static void fill_az(void) {
    if (AZ[0]) return;
    for (u32 i = 0; i < AZ_COUNT; i++) {
        u32 b = i * 9;
        AZ[i] = (u16)((AZ_PACKED[b >> 3] | AZ_PACKED[(b >> 3) + 1] << 8) >> (b & 7) & 0x1FF);
    }
}

static u64 now(void) {
    u64 t;
    __asm__ volatile("mrs %0, cntpct_el0" : "=r"(t));
    return t;
}
static u64 vf(u64 obj, u32 off) { return R64(R64(obj) + off); }

static int motion_kind(u64 rec) {   /* info byte 0 of a motion record (0x22 = a flying motion), -1 none */
    u64 info = rec ? R64(rec + 8) : 0;
    return info ? R8(info) : -1;
}
static u64 entity(void) {
    u64 t = R64(G_ENTITIES);
    return t ? R64(t + 0x58) : 0;
}
static int can_fly(void) {
    u64 E = entity(), set = E ? R64(E + 0x260) : 0, recs = set ? R64(set + 0xC8) : 0;
    return recs && R32(set + 0xD0) > 7 && motion_kind(R64(recs + 8 * 7)) == 0x22;
}
static int in_flight(void) {
    u64 E = entity();
    return E && motion_kind(R64(E + 0x228)) == 0x22;
}
/* A town Pokemon (id top nibble 2) with an action controller: the player's species if one lives here, else any. */
static u64 town_pokemon(u16 form) {
    u64 t = R64(G_ENTITIES), any = 0;
    for (int i = 1; t && i < 0x4B; i++) {
        u64 e = R64(t + 0x58 + 8ul * i), o = e ? R64(e + 0x10) : 0;
        if (!o || R16(o + 0x27FE) >> 12 != 2 || !R64(o + 0x18B8)) continue;
        if (R16(o + 0x398C) == form) return o;
        if (!any) any = o;
    }
    return any;
}
static int request_action(u64 P, u32 id) {
    u64 (*f)(u64, u32, u64, u64, u32, u32, u32, u32) = (void *)vf(P, 0x338);
    return (int)(f(P, id, 0, 0, 1, 0, 0, 0) & 1);
}
static int has_sludge(s16 *c) {
    u64 world = R64(G_WORLD);
    u8 kind = 8;
    for (int dy = -1; dy <= 0; dy++)
        for (int dx = -2; dx <= 2; dx++)
            for (int dz = -2; dz <= 2; dz++) {
                int ax = dx < 0 ? -dx : dx, az = dz < 0 ? -dz : dz;
                s16 cell[3] = {(s16)(c[0] + dx), (s16)(c[1] + dy), (s16)(c[2] + dz)};
                if (ax + az <= 2 && world && (fn_has_layer(world, &kind, cell) & 1)) return 1;
            }
    return 0;
}

static void effect(u64 P, State *s) {
    u16 form = R16(FLAG);
    s16 *c = s->cell;
    u64 o = town_pokemon(form);
    if (s->bubble) {   /* Water on sludge: Bubble, as a town Pokemon */
        u64 gm = R64(G_GAMEMGR), ht = gm ? R64(gm + 0xA8) : 0, h = ht ? R64(ht + 0x4470 + 8 * 121) : 0;
        u32 args[5] = {(u16)c[0], (u16)c[1], (u16)c[2], 0, 4};
        if (o && h) fn_bubble(h, R64(o + 0x18B8), args);
        return;
    }
    for (int i = 0; i < 3; i++) {
        int dy = s->kind == AB_WATER ? (i == 0 ? -1 : i == 1 ? 0 : 1) : (i == 0 ? 0 : i == 1 ? -1 : 1);
        s16 cell[3] = {c[0], (s16)(c[1] + dy), c[2]};
        u64 r;
        if (s->kind == AB_GROW) {
            u64 field = R64(G_FIELD);
            r = field ? fn_grow((void *)(field + 0x11058), cell) : 0;
        } else if (s->kind == AB_WATER) {
            r = fn_water(cell, 1, 1, 0, R16(P + 0x27FE), 0);
        } else {   /* Burn / Generate: the object at the cell, as a town Pokemon */
            u64 objects = R64(G_OBJECTS);
            u16 by = o ? R16(o + 0x27FE) : 0;
            if (!objects || !by) return;
            r = fn_object_act(objects, &by, (u16)cell[0], (u16)cell[1], (u16)cell[2], s->kind == AB_BURN ? 120 : 122);
        }
        if (r & 1) return;
    }
}

static void start(u64 P, State *s, u64 t) {
    u16 form = R16(FLAG), a;
    u64 ctl = R64(P + 0x18B8);
    int kind = -1;
    if ((u32)form < 8 * sizeof ABILITY_BITS / 3) {
        u32 bit = form * 3u, v = (ABILITY_BITS[bit >> 3] | ABILITY_BITS[(bit >> 3) + 1] << 8) >> (bit & 7) & 7;
        kind = (int)v - 1;
    }
    if (kind < 0 || in_flight() || !ctl) return;
    a = R16(ctl + 0x984);
    if (!(a == 0 || a == 100 || a == 101 || a == 103 || a == 318)) return;   /* an action plays (e.g. still transforming) */
    /* the cell in front, as the game finds its moves' target (main+0x2E19A0) */
    v4f (*pos)(u64) = (void *)vf(P, 0x140);
    float (*yaw_of)(u64) = (void *)vf(P, 0x18);
    v4f p = pos(P);
    float yaw = yaw_of(P), ay = yaw < 0 ? -yaw : yaw;
    int dir = yaw >= 0.7853982f && yaw < 2.3561945f ? 1 : yaw > -2.3561945f && yaw <= -0.7853982f ? 3 : ay >= 2.3561945f ? 2 : 0;
    s->cell[0] = (s16)((int)((p[0] + 102400.0f) / 100.0f) + (dir == 1 ? 1 : dir == 3 ? -1 : 0));
    s->cell[1] = (s16)(int)(p[1] / 100.0f);
    s->cell[2] = (s16)((int)((p[2] + 102400.0f) / 100.0f) + (dir == 0 ? 1 : dir == 2 ? -1 : 0));
    s->kind = (u8)kind;
    s->bubble = kind == AB_WATER && has_sludge(s->cell);
    static const u16 ACT[4] = {706, 700, 703, 709};
    if (!request_action(P, s->bubble ? 705 : ACT[kind]) && s->bubble) request_action(P, 703);
    s->phase = 1;
    s->at = t + 700 * TICKS_MS;
}

void ability_tick(u64 ch) {
    u64 g = R64(G_PLAYER), P = g ? R64(g + 0x30) : 0;
    State *s = ST;
    fill_az();
    if (!P || ch != P) return;
    u8 zr = FLAG[8], zl = FLAG[9], dpad = FLAG[0xA], combo = FLAG[0x1D];
    int press = combo && !s->prev_combo ? 2 : zr && !s->prev_zr && !zl && !dpad ? 1 : 0;
    s->prev_combo = combo, s->prev_zr = zr;
    if (!R16(FLAG)) {
        s->phase = 0;
        return;
    }
    u64 t = now();
    if (s->phase) {
        if (t >= s->at) {
            s->phase = 0;
            effect(P, s);
            s->ready = t + 600 * TICKS_MS;
        }
        return;
    }
    if (!press || t < s->ready || (press == 1 && can_fly())) return;
    start(P, s, t);
}

/* reached by `bl` from main+0x2FACE0 (was `blr x8`): x0 = the character, x8 = the call's target, x30 = the update */
__asm__(".globl ability_entry\n"
        "ability_entry:\n"
        "  stp x29, x30, [sp, #-32]!\n"
        "  stp x0, x8, [sp, #16]\n"
        "  bl ability_tick\n"
        "  ldp x0, x8, [sp, #16]\n"
        "  ldp x29, x30, [sp], #32\n"
        "  b tick_next\n");
