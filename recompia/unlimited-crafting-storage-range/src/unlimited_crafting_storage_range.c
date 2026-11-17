/* Unlimited Crafting Storage Range for Recompia (Modtopia code mod). GPL-3.0-or-later.
 *
 * The same mod as the emulator version (mods/unlimited-crafting-storage-range: an IPS patch), rebuilt on Modtopia. Every
 * code patch of the IPS is a take_over hook point here (mod.toml). All offsets are for game 2.0.1 (main build
 * 76a489f3bd3642fa), the build the emulator version targets.
 *
 * Crafting stations use the boxes in a 9-entry list on the player (P+0xAABC, 8 bytes each: u32 packed grid position,
 * u16 storage index, u8 storage kind, u8 flags). The game fills it with a scan of the one-block ring around the station
 * (main+0x7514E0, at most 4 boxes). After that scan this mod turns the list into "whole kind" entries:
 *   index 0xFFFE = every placed box of that kind, index 0xFFFD = nothing (a second box of a kind already covered),
 * and adds one box of a kind when none stands next to the station. The two slot-range functions the craft code uses
 * (count: main+0x5B1C84, check / take: main+0x2EE4BC) are taught those two indexes: the caller gets the slot range of
 * all boxes of the kind. Kinds 1 (20-slot boxes, chests, crates) and 2 (the big storage box) are the storage boxes.
 *
 * Hook points:
 *   scan_local    main+0x7504F0, right after the station's own scan (station x19)
 *   scan_shared   main+0x7505E8, right after the scan for a station in use by a player (station x20, flag w21, player w19)
 *   range_count   main+0x5B1C84, entry: (x0 pool, w1 kind, w2 index, w3, x4 *start, x5 *count) -> slot array
 *   range_take    main+0x2EE4BC, entry: (w0 kind, w1 index, x2 *start, x3 *count) -> 1 for a known kind
 */
#include <modtopia/modtopia.h>

#include <stdatomic.h>
#include <stdint.h>

MT_DECLARE_MOD()

/* ---------------------------------------------------------------- game offsets (main-relative, 2.0.1) */
#define G_HOLDER   0x3561928ull   /* u64: player holder (+0x30 / +0x38 = player objects) */
#define G_SAVE     0x3483B60ull   /* GOT: pointer to the save-data root pointer */
#define G_MGR      0x35616F0ull   /* u64: gimmick manager (+0x46D0 = std::map position -> gimmick) */
#define T_SIZE     0x280BAF0ull   /* u16[kind]: slots per storage instance */
#define T_BASE     0x280BB2Eull   /* u16[kind]: first slot of the kind */
#define T_NINST    0x280BB6Cull   /* u16[kind]: registry entries per kind */
#define T_REGBASE  0x280BBAAull   /* u16[kind]: first registry entry of the kind */
#define SCRATCH    0x3D14E00ull   /* unused bss: the original range functions write their own answer here instead */
#define F_IS_GUEST      0x207D4ull
#define F_PLAYER_BY_IDX 0x2815C4ull
#define F_ADD_BOX       0x7526C0ull  /* (station, gimmick, w2 flag, w3 player): adds one storage gimmick to the list */

#define REGISTRY   0xA0EE28ull    /* save + this: placed-container registry, 16 bytes each (+8 x,y,z u16, +0xE bit0 placed) */
#define GIMMICK_MAP 0x46D0ull
#define LIST       0xAABCull      /* player + this: the station's box list */
#define LIST_N     9
#define ALL        0xFFFE
#define NONE       0xFFFD

static const MtHost *H;
static MtMod *M;
static uint64_t MAIN;
static _Atomic uint16_t g_extent[3];   /* per kind: highest placed instance + 1 (read by the range hooks on any thread) */

/* ---------------------------------------------------------------- guest memory */
static int rd(uint64_t a, void *out, size_t n) { return a && H->mem_read(a, out, n) == MT_OK; }
static uint64_t r64(uint64_t a) { uint64_t v = 0; return rd(a, &v, 8) ? v : 0; }
static uint16_t r16(uint64_t a) { uint16_t v = 0; return rd(a, &v, 2) ? v : 0; }
static uint8_t r8(uint64_t a) { uint8_t v = 0; return rd(a, &v, 1) ? v : 0; }
static void w16(uint64_t a, uint16_t v) { H->mem_write(a, &v, 2); }
static void w32(uint64_t a, uint32_t v) { H->mem_write(a, &v, 4); }

static uint64_t call(uint64_t fn, uint64_t x0, uint64_t x1, uint64_t x2, uint64_t x3) {
    MtCall c = {{x0, x1, x2, x3}, {{0}}};
    if (H->call_guest(MAIN + fn, &c) != MT_OK) return 0;
    return c.x[0];
}

/* The player whose list the station fills: the local one (flag bit 0), or a remote player by index. */
static uint64_t list_owner(uint64_t station, uint32_t flag, uint32_t who) {
    uint64_t holder = r64(MAIN + G_HOLDER);
    if (!holder) return 0;
    if (!(flag & 1)) return call(F_PLAYER_BY_IDX, holder, (uint64_t)(int64_t)(int8_t)who, 0, 0);
    if ((r16(station + 10) & 0x2000) && (call(F_IS_GUEST, station, flag, who, 0) & 1)) return r64(holder + 0x38);
    return r64(holder + 0x30);
}

/* The gimmick standing at a grid position (the game's std::map of gimmicks by position), 0 if none. */
static uint64_t gimmick_at(uint64_t key) {
    uint64_t mgr = r64(MAIN + G_MGR);
    if (!mgr) return 0;
    uint64_t header = mgr + GIMMICK_MAP, node = r64(header), best = header;
    for (int depth = 0; node && depth < 64; depth++) {   /* lower_bound */
        if (r64(node + 0x20) >= key) best = node, node = r64(node);
        else node = r64(node + 8);
    }
    if (best == header || r64(best + 0x20) != key) return 0;
    return r64(best + 0x28);
}

/* ---------------------------------------------------------------- after the station's scan */
static void post(uint64_t station, uint32_t flag, uint32_t who) {
    flag &= 1;
    uint64_t P = list_owner(station, flag, who);
    if (!P) return;
    uint64_t list = P + LIST;
    for (uint32_t kind = 1; kind <= 2; kind++) {
        uint32_t first = r16(MAIN + T_REGBASE + 2 * kind), n = r16(MAIN + T_NINST + 2 * kind);
        uint64_t root = r64(r64(MAIN + G_SAVE));
        if (!root) return;
        uint64_t reg = root + REGISTRY;

        uint32_t extent = 0;   /* highest placed instance + 1 */
        for (uint32_t i = 0; i < n; i++)
            if (r8(reg + 16ull * (first + i) + 0xE) & 1) extent = i + 1;
        atomic_store(&g_extent[kind], (uint16_t)extent);

        int covered = 0;   /* entries of this kind: the first -> every box, the others -> nothing */
        for (int i = 0; i < LIST_N; i++) {
            uint64_t e = list + 8ull * i;
            if (r8(e + 6) != kind) continue;
            w16(e + 4, covered ? NONE : ALL);
            covered = 1;
        }
        if (covered) continue;

        /* no box of this kind next to the station: add the first placed one the game accepts */
        for (uint32_t i = 0; i < n && !covered; i++) {
            uint64_t r = reg + 16ull * (first + i);
            if (!(r8(r + 0xE) & 1)) continue;
            uint64_t key = r16(r + 8) | (uint64_t)r16(r + 0xA) << 16 | (uint64_t)r16(r + 0xC) << 32;
            uint64_t g = gimmick_at(key);
            if (!g) continue;
            call(F_ADD_BOX, station, g, flag, who);
            for (int j = 0; j < LIST_N; j++) {
                uint64_t e = list + 8ull * j;
                if (r8(e + 6) != kind) continue;
                w16(e + 4, ALL);
                covered = 1;
                break;
            }
        }
    }
}

static int h_scan_local(MtHookCtx *c, void *u) {
    (void)u;
    post(H->reg_get(c, 19), 1, 0xFF);
    return MT_CONTINUE;
}
static int h_scan_shared(MtHookCtx *c, void *u) {
    (void)u;
    post(H->reg_get(c, 20), (uint32_t)H->reg_get(c, 21), (uint32_t)H->reg_get(c, 19));
    return MT_CONTINUE;
}

/* ---------------------------------------------------------------- the slot ranges
 * For an entry of ours the caller gets the range of every box of the kind (or none), written here. The game's own
 * function still runs, for index 0, for its result and anything else it does, but writes its range to SCRATCH. */
static int ours(uint32_t kind, uint32_t index) { return (kind == 1 || kind == 2) && (index == ALL || index == NONE); }
static void give_range(uint32_t kind, uint32_t index, uint64_t start, uint64_t count) {
    uint32_t size = r16(MAIN + T_SIZE + 2 * kind);
    w32(start, r16(MAIN + T_BASE + 2 * kind));
    w32(count, index == ALL ? size * atomic_load(&g_extent[kind]) : 0);
}
static int h_range_count(MtHookCtx *c, void *u) {
    (void)u;
    uint32_t kind = (uint32_t)H->reg_get(c, 1) & 0xFF, index = (uint32_t)H->reg_get(c, 2) & 0xFFFF;
    if ((uint32_t)H->reg_get(c, 2) > 0xFFFF || !ours(kind, index)) return MT_CONTINUE;
    give_range(kind, index, H->reg_get(c, 4), H->reg_get(c, 5));
    H->reg_set(c, 2, 0);
    H->reg_set(c, 4, MAIN + SCRATCH);
    H->reg_set(c, 5, MAIN + SCRATCH + 4);
    return MT_CONTINUE;
}
static int h_range_take(MtHookCtx *c, void *u) {
    (void)u;
    uint32_t kind = (uint32_t)H->reg_get(c, 0) & 0xFF, index = (uint32_t)H->reg_get(c, 1) & 0xFFFF;
    if ((uint32_t)H->reg_get(c, 1) > 0xFFFF || !ours(kind, index)) return MT_CONTINUE;
    give_range(kind, index, H->reg_get(c, 2), H->reg_get(c, 3));
    H->reg_set(c, 1, 0);
    H->reg_set(c, 2, MAIN + SCRATCH + 8);
    H->reg_set(c, 3, MAIN + SCRATCH + 12);
    return MT_CONTINUE;
}

/* ---------------------------------------------------------------- entry */
MT_EXPORT int mod_init(const MtHost *host, MtMod *mod) {
    H = host, M = mod;
    MAIN = H->module_base("main");
    if (!MAIN) {
        H->log(M, MT_LOG_ERROR, "no main module");
        return MT_ERR;
    }
    static const struct { const char *point; MtHookFn fn; } hooks[] = {
        {"scan_local", h_scan_local}, {"scan_shared", h_scan_shared},
        {"range_count", h_range_count}, {"range_take", h_range_take},
    };
    for (size_t i = 0; i < sizeof hooks / sizeof hooks[0]; i++) {
        int rc = H->hook(M, hooks[i].point, hooks[i].fn, NULL);
        if (rc != MT_OK) {
            mt_logf(H, M, MT_LOG_ERROR, "cannot hook %s (%d)", hooks[i].point, rc);
            return MT_ERR;
        }
    }
    H->log(M, MT_LOG_INFO, "ready: crafting stations use every storage box, at any distance");
    return MT_OK;
}
