/* Play as Pokemon for Recompia (Modtopia code mod). GPL-3.0-or-later.
 *
 * The same mod as the emulator version (mods/play-as-pokemon: an IPS patch plus a cheat file), rebuilt on Modtopia:
 * every code patch of the IPS is a take_over hook point here (mod.toml), and the cheat's button combos and memory writes
 * run in the player's per-frame hook with the player's pad (pad_read). All offsets are for game 2.0.1 (main build
 * 76a489f3bd3642fa), the same build the emulator version targets.
 *
 * The state the IPS kept in the game's memory (main+0x3D14C00..) lives in this library instead:
 *   g_form       the form the player is turned into (a character-definition ID, 0 = not transformed)
 *   g_requested  the animation resource the player's model asked for while transformed (0 = none)
 *   g_acquired   the one whose motion set this mod acquired
 *
 * Hook points (see mod.toml and re/build/build_v06.py / build_v07.py for the original patches):
 *   form_get       desired-form getter: returns g_form while transformed
 *   form_set       desired-form setter: stores g_form while transformed
 *   request_state  RequestState: drops the request for state 1 (human) while transformed
 *   probe          animation condition 0x56 (wall probe): true for the player while transformed (no stretch / flashing)
 *   to_human       the game's "turn the player human for an interaction" (talking): noted, the player turns back after it
 *   char_setup     the character's model setup: requests / releases the form's animation package for the player
 *   player_tick    the player's update: buttons, binding the animations (and rebuilding the model once), flying, and
 *                  turning the player back into the Pokemon when the game changed the form some other way (talking to a Pokemon)
 *
 * Every hook acts on the player's own character only. In Link Play the other players are characters of the same kind, and
 * RequestState runs for every character, so without that check a transformed player's game would also keep the others from
 * turning back and hand them its own form.
 */
#include <modtopia/modtopia.h>

#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#endif

#include "forms.h"

MT_DECLARE_MOD()

/* ---------------------------------------------------------------- game offsets (main-relative, 2.0.1) */
#define PLAYER_GLOBAL 0x3561928ull   /* [[main+0x3561928] + 0x30] = the player character */
#define ENTITY_TABLE  0x356A778ull   /* [[main+0x356A778] + 0x58] = the player's entity */
#define MGR_GLOBAL    0x3561738ull   /* [main+0x3561738] + 0x8C830 = the animation package manager */
#define MOTION_DAT    0x35619E8ull   /* [main+0x35619E8] = the motion-set table (+0x18 entries, +0x20 count, +0x22 used) */
#define FN_MSET_ACQ   0x8D11C0ull    /* (x0, w1 resource): acquire a motion set, binding its animations on the first use */
#define FN_MSET_REL   0x8D1380ull    /* (x0, w1 resource, w2 0): release it */
#define FN_PKG_REQ    0x8D20A0ull    /* (mgr, w1 package): request an animation package */
#define FN_PKG_READY  0x8D1130ull    /* (mgr, w1 package) -> w0 1 when loaded */
#define FN_PKG_REL    0x8D2420ull    /* (mgr, w1 package, w2 0): release it */
#define MGR_OFFSET    0x8C830ull
#define PKG_MAP       0x4E08ull      /* mgr + 0x4E08: u16 package per resource ID */
#define GAME_MGR      0x3561710ull   /* [main+0x3561710] = the game manager: +0x8C its permission mask, 0 until the world is up */
#define GM_PERMISSIONS 0x8C

/* player character */
#define P_STATE       0x3778   /* the state machine RequestState gets (x0) */
#define P_FORM_NOW    0x5A44   /* u16 current form */
#define P_FORM_WANT   0x5A46   /* u16 desired form */
#define P_REQ_STATE   0x3788   /* u16 pending state */
#define P_REQ_ANIM    0x378A   /* u16 transition animation */
#define P_REQ_GO      0x378C   /* u8 request */
#define TRANSFORM_ANIM 0x3B2
#define HUMAN 1

/* player entity (flying) */
#define E_MOTION 0x228   /* current motion record */
#define E_MSET   0x260   /* motion set: +0xC8 records, +0xD0 count */
#define E_VY     0xBCC   /* vertical speed, cm per frame */
#define E_Y      0xBE4   /* height */
#define MOTION_IDLE  1
#define MOTION_HOVER 7
#define INFO_FLYING  0x22

/* ---------------------------------------------------------------- state */
static const MtHost *H;
static MtMod *M;
static uint64_t MAIN;

static _Atomic uint16_t g_form;        /* read by hooks on any game thread */
static uint16_t g_requested, g_acquired; /* the player's own threads only (model setup, update) */
static _Atomic uint16_t g_selected = DEFAULT_FORM;   /* what the combo turns the player into */
static _Atomic int g_settings_changed;
static _Atomic int g_fly = 1, g_cycle = 1, g_messages = 1;
static uint32_t g_prev_buttons;
static int g_prev_key_on, g_prev_key_off;
/* Everything timed is in milliseconds, never in frames: Recompia's frame rate is whatever the player set (60, 120, unlimited). */
#define REQUEST_GAP_MS   700   /* least time between two form requests */
#define SETTLED_MS       250   /* how long the last form change must have been complete */
#define REQUEST_MAX_MS  3000   /* a form change that never settles does not block the next one for longer */
#define CYCLE_PAUSE_MS   350   /* ZL + D-pad Left / Right: transform once the player stops flicking through the list */
#define DROP_HOLD_MS     120   /* ZL + ZR held this long = drop (a shorter overlap is a change of direction) */
#define LAND_STILL_MS     70   /* descending without losing height for this long = standing on something */
#define HOP_MS            50   /* the landing hop */
#define REVERT_WAIT_MS   500   /* the game changed the form: let its own change finish this long before turning back */
#define REVERT_LIMIT       3   /* turn back at most this often within REVERT_WINDOW_MS, then leave the form as the game wants it */
#define REVERT_WINDOW_MS 20000
#define INTERACTION_QUIET_MS 1000   /* an interaction is over once the game stopped asking for the human form this long ... */
#define WALK_MS           250   /* ... and the player has walked (left stick past WALK_STICK) this long */
#define WALK_STICK      12000
static _Atomic uint64_t g_interaction_at;   /* the game's last "turn the player human for an interaction" while transformed (0 = none) */
static uint64_t g_interaction_start, g_walk_since;
static int16_t g_lx, g_ly;                  /* the left stick, as buttons() last read it */
static int g_want = -1;                 /* the form to turn into once the last change is done (0 = human, -1 = nothing waiting) */
static uint64_t g_want_after;           /* not before this time */
static uint64_t g_last_request, g_settled_since;
static int g_zr_was, g_takeoff, g_descending;
static uint64_t g_both_since, g_still_since, g_hop_until;
static float g_ref_y;
static uint64_t g_wrong_since, g_revert_window;   /* keep_form */
static int g_reverts;

static uint64_t now_ms(void) {
#ifdef _WIN32
    static LARGE_INTEGER f;
    LARGE_INTEGER c;
    if (!f.QuadPart) QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return (uint64_t)(c.QuadPart / f.QuadPart) * 1000 + (uint64_t)(c.QuadPart % f.QuadPart) * 1000 / (uint64_t)f.QuadPart + 1;
#else
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000 + (uint64_t)t.tv_nsec / 1000000 + 1;
#endif
}

/* ---------------------------------------------------------------- guest memory */
static int rd(uint64_t a, void *out, size_t n) { return a && H->mem_read(a, out, n) == MT_OK; }
static uint64_t r64(uint64_t a) { uint64_t v = 0; return rd(a, &v, 8) ? v : 0; }
static int r16(uint64_t a, uint16_t *v) { return rd(a, v, 2); }
static void w8(uint64_t a, uint8_t v) { H->mem_write(a, &v, 1); }
static void w16(uint64_t a, uint16_t v) { H->mem_write(a, &v, 2); }
static void w64(uint64_t a, uint64_t v) { H->mem_write(a, &v, 8); }
static void wf(uint64_t a, float v) { H->mem_write(a, &v, 4); }

static uint64_t player(void) {
    uint64_t g = r64(MAIN + PLAYER_GLOBAL);
    return g ? r64(g + 0x30) : 0;
}
/* 1 when a hooked function is working on the player's own character (x0 = the character) */
static int is_player(uint64_t obj) {
    uint64_t P = player();
    return P && obj == P;
}
static uint64_t pkg_mgr(void) {
    uint64_t g = r64(MAIN + MGR_GLOBAL);
    return g ? g + MGR_OFFSET : 0;
}
static uint16_t pkg_of(uint64_t mgr, uint16_t res) {
    uint16_t p = 0;
    r16(mgr + PKG_MAP + (uint64_t)res * 2, &p);
    return p;
}
static uint64_t call(uint64_t fn, uint64_t x0, uint64_t x1, uint64_t x2) {
    MtCall c;
    memset(&c, 0, sizeof c);
    c.x[0] = x0, c.x[1] = x1, c.x[2] = x2;
    if (H->call_guest(MAIN + fn, &c) != MT_OK) return 0;
    return c.x[0];
}
/* The motion set of a resource as FN_MSET_ACQ finds it (0 when it has none). */
static uint64_t motion_set(uint16_t res) {
    uint64_t dat = r64(MAIN + MOTION_DAT);
    uint16_t n = 0, used = 0;
    if (!dat || !r16(dat + 0x20, &n) || !r16(dat + 0x22, &used) || !n || !used) return 0;
    uint64_t table = r64(dat + 0x18);
    for (uint32_t i = 0, seen = 0; i < n && seen < used; i++) {
        uint64_t e = r64(table + 8ull * i);
        int32_t id = 0;
        if (!e || !rd(e + 8, &id, 4) || id < 0) continue;
        if (id == res) return r64(e);
        seen++;
    }
    return 0;
}
static int motion_set_uses(uint64_t set) {
    uint8_t loaded = 0;
    uint16_t count = 0;
    if (!set || !rd(set + 0x1076, &loaded, 1) || !loaded || !r16(set + 0x1074, &count)) return -1;
    return count;
}

/* ---------------------------------------------------------------- forms */
static const char *form_name(uint16_t id) {
    for (int i = 0; i < FORM_COUNT; i++)
        if (FORMS[i].id == id) return FORMS[i].name;
    return "?";
}
static int form_by_name(const char *name) {
    for (int i = 0; name && i < FORM_COUNT; i++)
        if (!strcmp(FORMS[i].name, name)) return FORMS[i].id;
    return -1;
}
static void say(const char *fmt, const char *a) {
    if (!atomic_load(&g_messages) || !MT_HOST_HAS(H, notify) || !H->notify) return;
    char t[160];
    snprintf(t, sizeof t, fmt, a);
    H->notify(M, t, 2.5);
}

static void request(uint64_t P, uint16_t state) {
    w16(P + P_FORM_WANT, state);
    w16(P + P_REQ_STATE, state);
    w16(P + P_REQ_ANIM, TRANSFORM_ANIM);
    w8(P + P_REQ_GO, 1);
    g_last_request = now_ms();
    g_settled_since = 0;
}
static void transform(uint64_t P, uint16_t form) {
    atomic_store(&g_form, form);
    request(P, form);
    g_wrong_since = g_revert_window = 0, g_reverts = 0;
    atomic_store(&g_interaction_at, 0);
    uint16_t id = 0;
    r16(P + 0x27FE, &id);
    mt_logf(H, M, MT_LOG_INFO, "transform: player id 0x%x into %s (form %u)", id, form_name(form), form);
    say("Play as Pokemon: %s", form_name(form));
}
static void turn_back(uint64_t P) {
    atomic_store(&g_form, 0);
    request(P, HUMAN);
    g_hop_until = 0;
    g_takeoff = g_descending = 0;
    g_wrong_since = 0;
    atomic_store(&g_interaction_at, 0);
}

/* A form change rebuilds the player's model over several frames, partly on the game's worker threads. A second request
   while that is under way can free the model under a worker (the crash when switching fast), so requests are queued:
   the newest one waits until the last change is complete and has been for a moment. */
static void want(int form, uint64_t delay) {
    g_want = form;
    g_want_after = now_ms() + delay;
}
static int settled(uint64_t P, uint64_t now) {
    uint64_t since = now - g_last_request;
    if (!g_last_request) return 1;
    if (since < REQUEST_GAP_MS) return 0;
    if (since > REQUEST_MAX_MS) return 1;
    uint16_t cur = 0, form = atomic_load(&g_form);
    uint8_t go = 1;
    if (!r16(P + P_FORM_NOW, &cur) || !rd(P + P_REQ_GO, &go, 1) || go || cur != (form ? form : HUMAN) || g_requested != g_acquired) {
        g_settled_since = 0;
        return 0;
    }
    if (!g_settled_since) g_settled_since = now;
    return now - g_settled_since >= SETTLED_MS;
}
static void apply_wanted(uint64_t P) {
    if (g_want < 0) return;
    uint64_t now = now_ms();
    if (now < g_want_after || !settled(P, now)) return;
    int form = g_want;
    g_want = -1;
    if (form == atomic_load(&g_form)) return;
    if (form) transform(P, (uint16_t)form);
    else turn_back(P);
}

/* ---------------------------------------------------------------- settings */
static void read_settings(void) {
    const char *list = H->config_string(M, "list");
    const char *key = list && !strcmp(list, LIST_M_Z) ? "pokemon_m_z" : list && !strcmp(list, LIST_EXPERIMENTAL) ? "experimental" : "pokemon_a_l";
    int id = form_by_name(H->config_string(M, key));
    atomic_store(&g_selected, (uint16_t)(id > 0 ? id : DEFAULT_FORM));
    atomic_store(&g_fly, H->config_bool(M, "fly"));
    atomic_store(&g_cycle, H->config_bool(M, "cycle"));
    atomic_store(&g_messages, H->config_bool(M, "messages"));
}
static void on_config(MtMod *mod, const char *key, void *user) {
    (void)mod, (void)key, (void)user;
    read_settings();
    atomic_store(&g_settings_changed, 1);   /* the player's next update applies it (game thread) */
}

/* ZL + D-pad Right / Left: the next / previous Pokemon in the A-Z list (experimental forms are left out). */
static void cycle(int dir) {
    uint16_t cur = atomic_load(&g_selected);
    int at = -1;
    for (int i = 0; i < POKEMON_COUNT; i++)
        if (FORMS[i].id == cur) at = i;
    at = at < 0 ? 0 : (at + dir + POKEMON_COUNT) % POKEMON_COUNT;
    uint16_t form = FORMS[at].id;
    atomic_store(&g_selected, form);
    if (atomic_load(&g_form) || g_want > 0) {   /* transformed: turn into it once the player stops flicking through */
        want(form, CYCLE_PAUSE_MS);
        say("Play as Pokemon: %s", FORMS[at].name);
    } else say("Play as Pokemon: %s (ZL + L3 to transform)", FORMS[at].name);
}

static int key_down(const char *setting) {
    if (!MT_HOST_HAS(H, key_down) || !H->key_down) return 0;
    const char *k = H->config_string(M, setting);
    return k && *k && H->key_down(M, k);
}

/* A combo fires once when it becomes held (ZL and the button, in either order). */
static int combo(uint32_t now, uint32_t before, uint32_t dir) {
    uint32_t m = MT_PAD_ZL | dir;
    return (now & m) == m && (before & m) != m;
}

/* Which of the player's input the game does not get (pad_block), told to the host only when it changes. */
static void block(uint32_t buttons, int sticks) {
    static uint32_t cur_buttons;
    static int cur_sticks;
    if (buttons == cur_buttons && sticks == cur_sticks) return;
    cur_buttons = buttons, cur_sticks = sticks;
    if (!MT_HOST_HAS(H, pad_block) || !H->pad_block) return;
    MtPad m;
    memset(&m, 0, sizeof m);
    m.buttons = buttons;
    if (sticks) m.lx = m.ly = m.rx = m.ry = 1;
    H->pad_block(M, 0, buttons || sticks ? &m : NULL);
}

/* ---------------------------------------------------------------- the menu
 * Modtopia has no drawing for mods, so the menu is its message box: a list of a few lines around the cursor, shown again
 * whenever it changes. While it is open the game gets no input from the player. Entry 0 is the player's own character,
 * entries 1.. are FORMS (the Pokemon A to Z, then the experimental forms). */
#define MENU_LINES 9
#define MENU_ENTRIES (FORM_COUNT + 1)
enum { NAV_UP = 1, NAV_DOWN = 2, NAV_LEFT = 4, NAV_RIGHT = 8, NAV_OK = 16, NAV_BACK = 32, NAV_PREV = 64, NAV_NEXT = 128 };
static int g_menu;   /* 0 closed, 1 open, 2 closed but waiting for the buttons to be let go */
static int g_menu_at, g_prev_key_menu;
static uint32_t g_nav_was;
static uint64_t g_nav_repeat, g_menu_shown;

static const char *menu_name(int i) { return i ? FORMS[i - 1].name : "Your own character"; }
static int any_key(const char *a, const char *b) {
    if (!MT_HOST_HAS(H, key_down) || !H->key_down) return 0;
    return H->key_down(M, a) || (b && H->key_down(M, b));
}
static void menu_show(void) {
    char t[640];
    int n = snprintf(t, sizeof t, "Play as Pokemon  (%d / %d)\n", g_menu_at + 1, MENU_ENTRIES);
    int first = g_menu_at - MENU_LINES / 2;
    if (first > MENU_ENTRIES - MENU_LINES) first = MENU_ENTRIES - MENU_LINES;
    if (first < 0) first = 0;
    for (int i = first; i < first + MENU_LINES && i < MENU_ENTRIES && n < (int)sizeof t; i++)
        n += snprintf(t + n, sizeof t - (size_t)n, i == g_menu_at ? ">  %s  <\n" : "    %s\n", menu_name(i));
    if (n < (int)sizeof t)
        snprintf(t + n, sizeof t - (size_t)n, "Up/Down: move   Left/Right: 10   L/R: letter   A/Enter: choose   B/Esc: close");
    if (MT_HOST_HAS(H, notify) && H->notify) H->notify(M, t, 2.0);
    g_menu_shown = now_ms();
}
static void menu_open(void) {
    uint16_t cur = atomic_load(&g_form) ? atomic_load(&g_selected) : 0;
    g_menu_at = 0;
    for (int i = 0; cur && i < FORM_COUNT; i++)
        if (FORMS[i].id == cur) g_menu_at = i + 1;
    g_menu = 1;
    g_nav_was = ~0u;   /* what is held now does not count as a press */
    block(0xFFFF, 1);
    menu_show();
}
static void menu_close(const char *text) {
    g_menu = 2;
    if (MT_HOST_HAS(H, notify) && H->notify) H->notify(M, text, 1.5);
}
/* The first entry whose name starts with another letter than the cursor's, forwards or backwards (Pokemon only). */
static int menu_letter(int dir) {
    int i = g_menu_at;
    if (i < 1 || i > POKEMON_COUNT) return dir > 0 ? 1 : POKEMON_COUNT;
    char c = FORMS[i - 1].name[0];
    while (i >= 1 && i <= POKEMON_COUNT && FORMS[i - 1].name[0] == c) i += dir;
    if (i < 1) return 0;
    if (i > POKEMON_COUNT) return i <= FORM_COUNT ? i : 0;
    if (dir < 0)   /* backwards: to the first name of that letter */
        while (i > 1 && FORMS[i - 2].name[0] == FORMS[i - 1].name[0]) i--;
    return i;
}
static void menu_tick(const MtPad *pad, uint32_t was, int key_menu) {
    uint32_t b = pad->buttons, nav = 0;
    uint64_t now = now_ms();
    (void)was;
    if (g_menu == 2) {   /* closed: give the game its input back once nothing is held (or A / B would act in the game) */
        if (!b && !any_key("Return", "Escape")) {
            g_menu = 0;
            block(0, 0);
        }
        return;
    }
    if ((b & MT_PAD_UP) || pad->ly > 20000 || any_key("Up", NULL)) nav |= NAV_UP;
    if ((b & MT_PAD_DOWN) || pad->ly < -20000 || any_key("Down", NULL)) nav |= NAV_DOWN;
    if ((b & MT_PAD_LEFT) || any_key("Left", "PageUp")) nav |= NAV_LEFT;
    if ((b & MT_PAD_RIGHT) || any_key("Right", "PageDown")) nav |= NAV_RIGHT;
    if ((b & MT_PAD_A) || any_key("Return", "Keypad Enter")) nav |= NAV_OK;
    if ((b & MT_PAD_B) || any_key("Escape", "Backspace") || key_menu) nav |= NAV_BACK;
    if (b & MT_PAD_L) nav |= NAV_PREV;
    if (b & MT_PAD_R) nav |= NAV_NEXT;
    uint32_t pressed = nav & ~g_nav_was, moves = NAV_UP | NAV_DOWN | NAV_LEFT | NAV_RIGHT;
    if (g_nav_was == ~0u) pressed = 0;
    if (pressed & moves) g_nav_repeat = now + 350;
    else if ((nav & moves) && (nav & moves) == (g_nav_was & moves) && now >= g_nav_repeat) {   /* held: repeat */
        pressed |= nav & moves;
        g_nav_repeat = now + 70;
    }
    g_nav_was = nav;

    if (pressed & NAV_BACK) {
        menu_close("Play as Pokemon: closed");
        return;
    }
    if (pressed & NAV_OK) {
        if (g_menu_at) {
            atomic_store(&g_selected, FORMS[g_menu_at - 1].id);
            want(FORMS[g_menu_at - 1].id, 0);
        } else want(0, 0);
        menu_close(menu_name(g_menu_at));
        return;
    }
    int at = g_menu_at;
    if (pressed & NAV_UP) at--;
    if (pressed & NAV_DOWN) at++;
    if (pressed & NAV_LEFT) at = at == 0 ? -1 : at < 10 ? 0 : at - 10;
    if (pressed & NAV_RIGHT) at = at == MENU_ENTRIES - 1 ? MENU_ENTRIES : at + 10 > MENU_ENTRIES - 1 ? MENU_ENTRIES - 1 : at + 10;
    if (pressed & NAV_PREV) at = menu_letter(-1);
    if (pressed & NAV_NEXT) at = menu_letter(1);
    at = (at + MENU_ENTRIES) % MENU_ENTRIES;   /* off one end: to the other */
    if (at != g_menu_at) {
        g_menu_at = at;
        menu_show();
    } else if (now - g_menu_shown >= 1000) menu_show();   /* keep the message up */
}

static void buttons(uint64_t P) {
    MtPad pad;
    memset(&pad, 0, sizeof pad);
    if (MT_HOST_HAS(H, pad_read) && H->pad_read) H->pad_read(M, 0, &pad);
    uint32_t b = pad.buttons, was = g_prev_buttons;
    g_prev_buttons = b;
    g_lx = pad.lx, g_ly = pad.ly;
    int kon = key_down("key_transform"), koff = key_down("key_turn_back");
    int key_on = kon && !g_prev_key_on, key_off = koff && !g_prev_key_off;
    g_prev_key_on = kon, g_prev_key_off = koff;

    int kmenu = key_down("key_menu"), key_menu = kmenu && !g_prev_key_menu;
    g_prev_key_menu = kmenu;

    if (g_menu) {
        menu_tick(&pad, was, key_menu);
        apply_wanted(P);
        return;
    }
    /* The stick clicks belong to the combos while ZL is held: the game does not see them then. */
    block((b & MT_PAD_ZL) ? MT_PAD_LSTICK | MT_PAD_RSTICK : 0, 0);
    int transformed = atomic_load(&g_form) || g_want > 0;
    if (key_menu || combo(b, was, MT_PAD_RSTICK)) menu_open();
    else if (combo(b, was, MT_PAD_LSTICK)) want(transformed ? 0 : atomic_load(&g_selected), 0);   /* ZL + L3: there and back */
    else if (key_on) want(atomic_load(&g_selected), 0);
    else if (key_off) want(0, 0);
    else if (atomic_load(&g_cycle) && combo(b, was, MT_PAD_RIGHT)) cycle(1);
    else if (atomic_load(&g_cycle) && combo(b, was, MT_PAD_LEFT)) cycle(-1);
    else if (atomic_exchange(&g_settings_changed, 0) && atomic_load(&g_form) && atomic_load(&g_selected) != atomic_load(&g_form))
        want(atomic_load(&g_selected), 0);   /* a new Pokemon picked in the settings while transformed */
    apply_wanted(P);
}

/* ---------------------------------------------------------------- the form's animations (v0.6)
 * The game attaches animation data to a species' motion set only while its animation package is loaded and the set is
 * acquired. Residents do both when they spawn; the player's form change does neither, so a species that does not live in
 * the town would be invisible. char_setup requests the package, this binds the set once it is loaded, and when that was
 * the set's first use (the model was built without animations) it builds the form again. */
static void bind_animations(uint64_t P) {
    uint16_t req = g_requested;
    if (!req || req == g_acquired) return;
    uint64_t mgr = pkg_mgr();
    if (!mgr) return;
    uint16_t pkg = pkg_of(mgr, req);
    if (pkg && !(uint32_t)call(FN_PKG_READY, mgr, pkg, 0)) return;   /* still loading */
    uint64_t set = motion_set(req);
    int before = motion_set_uses(set);
    call(FN_MSET_ACQ, mgr, req, 0);
    g_acquired = req;
    if (before == 0 && motion_set_uses(set) == 1) {
        uint16_t form = atomic_load(&g_form);
        if (!form) return;
        w16(P + P_FORM_NOW, HUMAN);   /* the current form is stale: request it again */
        w16(P + P_REQ_STATE, form);
        w16(P + P_REQ_ANIM, TRANSFORM_ANIM);
        w8(P + P_REQ_GO, 1);
        g_last_request = now_ms();
        g_settled_since = 0;
    }
}

/* Some of the game's form changes skip RequestState. Talking to most Pokemon turns the player human through h_to_human's
   function (the ones that comment on the transformation don't): the player stays human until the game stopped asking for
   INTERACTION_QUIET_MS and the player walks off, then turns back into the Pokemon. Any other time, a form other than the chosen
   one that stays for REVERT_WAIT_MS with no request under way is undone, as ZL + L3 would. If the game keeps doing it (more than REVERT_LIMIT times in REVERT_WINDOW_MS),
   the player is left as the game wants and counts as turned back: ZL + L3 transforms again. */
static void keep_form(uint64_t P) {
    uint16_t form = atomic_load(&g_form), cur = 0;
    uint8_t go = 1;
    uint32_t perms = 0;
    uint64_t now = now_ms(), gm = r64(MAIN + GAME_MGR), ia = atomic_load(&g_interaction_at);
    if (!ia) g_interaction_start = 0;
    if (form && ia) {   /* an interaction (talking) turned the player human: back once it is over and the player walks off */
        if (!g_interaction_start) g_interaction_start = ia;
        g_wrong_since = 0;
        int walking = g_lx > WALK_STICK || g_lx < -WALK_STICK || g_ly > WALK_STICK || g_ly < -WALK_STICK;
        if (now - ia < INTERACTION_QUIET_MS || g_menu || !walking) {
            g_walk_since = 0;
            return;
        }
        if (!g_walk_since) g_walk_since = now;
        if (now - g_walk_since < WALK_MS) return;
        atomic_store(&g_interaction_at, 0);
        mt_logf(H, M, MT_LOG_INFO, "the interaction is over (%llu ms): back into %s", (unsigned long long)(ia - g_interaction_start), form_name(form));
        g_interaction_start = g_walk_since = 0;
        if (g_want < 0 && r16(P + P_FORM_NOW, &cur) && cur != form && rd(P + P_REQ_GO, &go, 1) && !go) request(P, form);
        return;
    }
    if (!form || g_want >= 0 || !gm || !rd(gm + GM_PERMISSIONS, &perms, 4) || !perms || !r16(P + P_FORM_NOW, &cur)
        || !rd(P + P_REQ_GO, &go, 1) || go || cur == form || now - g_last_request < REQUEST_GAP_MS) {
        g_wrong_since = 0;
        return;
    }
    if (!g_wrong_since) g_wrong_since = now;
    if (now - g_wrong_since < REVERT_WAIT_MS) return;
    g_wrong_since = 0;
    if (!g_revert_window || now - g_revert_window > REVERT_WINDOW_MS) g_revert_window = now, g_reverts = 0;
    if (++g_reverts > REVERT_LIMIT) {
        mt_logf(H, M, MT_LOG_INFO, "the game keeps turning the player into form %u: leaving it", cur);
        atomic_store(&g_form, 0);
        g_hop_until = 0;
        g_takeoff = g_descending = 0;
        say("Play as Pokemon: the game turned you back (%s to transform again)", "ZL + L3");
        return;
    }
    mt_logf(H, M, MT_LOG_INFO, "the game turned the player into form %u: back into %s (form %u)", cur, form_name(form), form);
    request(P, form);
}

static void remote_model(uint64_t ch, uint16_t res);   /* Link Play diagnostics, below */

static int h_char_setup(MtHookCtx *c, void *u) {   /* strh w8, [x25, #0xe94]: w8 = resource ID, x19 = character */
    (void)u;
    uint64_t P = player();
    if (!P || H->reg_get(c, 19) != P) {
        if (P) remote_model(H->reg_get(c, 19), (uint16_t)H->reg_get(c, 8));
        return MT_CONTINUE;
    }
    uint16_t res = (uint16_t)H->reg_get(c, 8), form = atomic_load(&g_form), now = form ? res : 0, old = g_requested;
    if (now == old) return MT_CONTINUE;
    g_requested = now;
    if (form) mt_logf(H, M, MT_LOG_DEBUG, "the player's model: animation resource %u (form %u)", res, form);
    w16(H->reg_get(c, 25) + 0xE94, res);   /* the patch ran after this store: do it first (the game repeats it) */
    uint64_t x0 = H->reg_get(c, 0);
    if (old) {
        if (g_acquired == old) {
            g_acquired = 0;
            call(FN_MSET_REL, x0, old, 0);
        }
        uint64_t mgr = pkg_mgr();
        if (!mgr) return MT_CONTINUE;
        uint16_t pkg = pkg_of(mgr, old);
        if (pkg) call(FN_PKG_REL, mgr, pkg, 0);
    }
    if (now) {
        uint64_t mgr = pkg_mgr();
        if (!mgr) return MT_CONTINUE;
        uint16_t pkg = pkg_of(mgr, now);
        if (pkg) call(FN_PKG_REQ, mgr, pkg, 0);
    }
    return MT_CONTINUE;
}

/* ---------------------------------------------------------------- flying (v0.7)
 * Species whose motion 7 is a flying motion (info byte 0x22) can fly: ZR on foot starts the native hover (no gravity),
 * ZR while flying rises, ZL descends and lands once the height stops changing, ZL + ZR drops. A held D-pad direction or stick click
 * belongs to the combos. */
static void fly(uint64_t P) {
    (void)P;
    /* The emulator version saw the buttons about 12 times a second; here they are read every frame, so a few frames of
       both triggers down while changing direction, or of ZR alone while letting go after a drop, must not count as a drop
       or a take-off: a drop needs both held for DROP_HOLD_MS, and after a drop or a landing only a new press of ZR
       takes off. */
    uint64_t now = now_ms();
    uint32_t b = g_prev_buttons;
    int zr = (b & MT_PAD_ZR) != 0, zl = (b & MT_PAD_ZL) != 0, zr_pressed = zr && !g_zr_was, descending = 0;
    uint64_t t, E, set, recs, hover, info, cur, ci, idle;
    uint32_t count = 0;
    uint8_t kind = 0, motion = 0;
    float y = 0, d;
    g_zr_was = zr;
    if (!zr) g_takeoff = 0;
    else if (zr_pressed && !zl) g_takeoff = 1;
    if (!(zr && zl)) g_both_since = 0;

    t = r64(MAIN + ENTITY_TABLE), E = t ? r64(t + 0x58) : 0;
    set = E ? r64(E + E_MSET) : 0;
    if (!set || !rd(set + 0xD0, &count, 4) || count < MOTION_HOVER + 1) goto out;
    recs = r64(set + 0xC8), hover = recs ? r64(recs + 8 * MOTION_HOVER) : 0, info = hover ? r64(hover + 8) : 0;
    if (!info || !rd(info, &kind, 1) || kind != INFO_FLYING) goto out;   /* this species cannot fly */
    if (g_hop_until) {   /* the landing hop: a moment up so the game plays its own fall and landing */
        if (now < g_hop_until) {
            wf(E + E_VY, 4.0f);
            goto out;
        }
        g_hop_until = 0;
    }
    if (b & (MT_PAD_LEFT | MT_PAD_UP | MT_PAD_RIGHT | MT_PAD_DOWN | MT_PAD_LSTICK | MT_PAD_RSTICK)) {
        g_both_since = 0;
        goto out;
    }
    cur = r64(E + E_MOTION), ci = cur ? r64(cur + 8) : 0, idle = r64(recs + 8 * MOTION_IDLE);
    if (!ci || !rd(ci, &motion, 1)) goto out;
    if (motion != INFO_FLYING) {   /* on foot or falling: ZR pressed (not just still held) takes off */
        if (g_takeoff && !zl) w64(E + E_MOTION, hover);
        goto out;
    }
    if (zr && zl) {   /* drop, once both are really held; until then hover */
        if (!g_both_since) g_both_since = now;
        if (now - g_both_since >= DROP_HOLD_MS && idle) {
            w64(E + E_MOTION, idle);
            g_takeoff = 0;
            g_both_since = 0;
        }
        goto out;
    }
    if (zr) {   /* rise */
        wf(E + E_VY, 7.0f);
        goto out;
    }
    if (!zl) goto out;   /* hover */
    wf(E + E_VY, -7.0f);   /* descend; land once standing on something */
    descending = 1;
    rd(E + E_Y, &y, 4);
    d = y - g_ref_y;
    if (d < 0) d = -d;
    if (!g_descending || d >= 1.0f) {
        g_ref_y = y;
        g_still_since = now;
    } else if (now - g_still_since >= LAND_STILL_MS && idle) {
        w64(E + E_MOTION, idle);
        g_hop_until = now + HOP_MS;
        g_takeoff = 0;
        descending = 0;
    }
out:
    g_descending = descending;
}

/* Diagnostics: while transformed (and 10 s after), each change of the player's form fields goes to pkp.log. The transition
   animation (+0x378A) the game writes is a constant at each place in its code, so it shows where a form change came from. */
static uint64_t g_trace_until;
static void trace(uint64_t P) {
    static uint16_t last[4];
    static uint8_t lastb[3];
    static int have;
    uint16_t v[4] = {0};
    uint8_t b[3] = {0};
    uint64_t now = now_ms();
    if (atomic_load(&g_form)) g_trace_until = now + 10000;
    if (now >= g_trace_until) { have = 0; return; }
    r16(P + P_FORM_NOW, &v[0]), r16(P + P_FORM_WANT, &v[1]), r16(P + P_REQ_STATE, &v[2]), r16(P + P_REQ_ANIM, &v[3]);
    rd(P + P_REQ_GO, b, 3);   /* +0x378C request, +0x378D isDitto, +0x378E transform motion playing */
    int same = have;
    for (int i = 0; i < 4; i++) same &= v[i] == last[i], last[i] = v[i];
    for (int i = 0; i < 3; i++) same &= b[i] == lastb[i], lastb[i] = b[i];
    have = 1;
    if (same) return;
    mt_logf(H, M, MT_LOG_INFO, "trace f%llu: form %u want %u | request %u anim 0x%x go %u ditto %u playing %u | mod form %u",
            (unsigned long long)(H->frame ? H->frame() : 0), v[0], v[1], v[2], v[3], b[0], b[1], b[2], atomic_load(&g_form));
}

/* Link Play diagnostics: the other players' characters run the same update. While online, each change of their form fields
   (and each model setup, in h_char_setup) goes to pkp.log, to see whether a transform reaches the other players' games. */
#define REMOTE_MAX 4
static struct { uint64_t ch; uint16_t id, v[4]; uint8_t b[3]; } g_remote[REMOTE_MAX];
static int online(void) {
    uint64_t gm = r64(MAIN + GAME_MGR);
    uint8_t f = 0;
    return gm && rd(gm + 0x90, &f, 1) && (f & 1);   /* GameMgr.online, bit 0 */
}
static int remote_slot(uint64_t ch) {
    for (int i = 0; i < REMOTE_MAX; i++)
        if (ch && g_remote[i].ch == ch) return i;
    return -1;
}
static void remote_model(uint64_t ch, uint16_t res) {
    int i = remote_slot(ch);
    if (i >= 0) mt_logf(H, M, MT_LOG_INFO, "remote model id 0x%x: animation resource %u", g_remote[i].id, res);
}
static void trace_remote(uint64_t ch) {
    if (!online()) return;
    int i = remote_slot(ch);
    if (i < 0) {
        uint16_t id = 0;
        if (!r16(ch + 0x27FE, &id) || (id & 0x800) || (unsigned)((id >> 12) - 1) >= 4) return;   /* not a player's id */
        for (i = 0; i < REMOTE_MAX && g_remote[i].ch; i++) {}
        if (i == REMOTE_MAX) return;
        g_remote[i].ch = ch, g_remote[i].id = id;
        g_remote[i].v[0] = 0xFFFF;   /* log the first state */
        mt_logf(H, M, MT_LOG_INFO, "remote player id 0x%x", id);
    }
    uint16_t v[4] = {0};
    uint8_t b[3] = {0};
    r16(ch + P_FORM_NOW, &v[0]), r16(ch + P_FORM_WANT, &v[1]), r16(ch + P_REQ_STATE, &v[2]), r16(ch + P_REQ_ANIM, &v[3]);
    rd(ch + P_REQ_GO, b, 3);
    int same = 1;
    for (int k = 0; k < 4; k++) same &= v[k] == g_remote[i].v[k], g_remote[i].v[k] = v[k];
    for (int k = 0; k < 3; k++) same &= b[k] == g_remote[i].b[k], g_remote[i].b[k] = b[k];
    if (same) return;
    mt_logf(H, M, MT_LOG_INFO, "remote trace id 0x%x f%llu: form %u want %u | request %u anim 0x%x go %u ditto %u playing %u", g_remote[i].id,
            (unsigned long long)(H->frame ? H->frame() : 0), v[0], v[1], v[2], v[3], b[0], b[1], b[2]);
}

static int h_player_tick(MtHookCtx *c, void *u) {   /* blr x8 near the top of the player's update: x0 = the character */
    (void)u;
    uint64_t P = player(), ch = H->reg_get(c, 0);
    if (P && ch && ch != P) trace_remote(ch);
    if (!P || ch != P) return MT_CONTINUE;
    trace(P);
    buttons(P);
    bind_animations(P);
    keep_form(P);
    if (!g_menu && atomic_load(&g_form) && atomic_load(&g_fly)) fly(P);
    return MT_CONTINUE;
}

/* ---------------------------------------------------------------- the form patches (v0.3 - v0.5) */
static int h_form_get(MtHookCtx *c, void *u) {   /* entry of the desired-form getter (x0 = character): return the form */
    (void)u;
    uint16_t f = atomic_load(&g_form);
    if (!f || !is_player(H->reg_get(c, 0))) return MT_CONTINUE;
    H->reg_set(c, 0, f);
    return MT_HANDLED;
}
static int h_form_set(MtHookCtx *c, void *u) {   /* entry of the desired-form setter (x0 = character, w1): store the form instead */
    (void)u;
    uint16_t f = atomic_load(&g_form);
    if (f && is_player(H->reg_get(c, 0))) H->reg_set(c, 1, f);
    return MT_CONTINUE;
}
/* RequestState(x0 = character + P_STATE, w1 state): drop "back to human" for the player. While transformed, the game's other
   requests for the player are logged once per state and caller, to find what changes the form (pkp.log). */
static int h_request_state(MtHookCtx *c, void *u) {
    (void)u;
    uint16_t form = atomic_load(&g_form);
    uint64_t P = player();
    if (!form || !P || H->reg_get(c, 0) != P + P_STATE) return MT_CONTINUE;
    uint32_t state = (uint32_t)H->reg_get(c, 1) & 0xFFFF;
    uint64_t from = H->reg_get(c, 30);
    static uint32_t last_state;
    static uint64_t last_from;
    if (state != form && (state != last_state || from != last_from)) {
        last_state = state, last_from = from;
        mt_logf(H, M, MT_LOG_INFO, "the game asked to turn the player into form %u (from main+0x%llx)%s", state,
                (unsigned long long)(from >= MAIN ? from - MAIN : from), state == HUMAN ? ": ignored" : "");
    }
    return state == HUMAN ? MT_HANDLED : MT_CONTINUE;
}
/* main+0x455580 (w0 = local player slot 0 / 1, ...) -> w0 1: turns that player human for an interaction, writing "state 1,
   animation 0x3AF" into its state machine itself (RequestState inlined). Talking to most Pokemon calls it every frame, and the
   conversation waits for the human form (keeping the player transformed here left it stuck). So the game gets its way: this
   only notes the time, and keep_form turns the player back into the Pokemon once the interaction is over. */
static int h_to_human(MtHookCtx *c, void *u) {
    (void)u;
    uint64_t P = player(), g = r64(MAIN + PLAYER_GLOBAL);
    if (!atomic_load(&g_form) || !P || !g || r64(g + (((uint32_t)H->reg_get(c, 0) & 0xFF) ? 0x38 : 0x30)) != P) return MT_CONTINUE;
    uint64_t now = now_ms(), last = atomic_load(&g_interaction_at), from = H->reg_get(c, 30);
    if (!last || now - last > INTERACTION_QUIET_MS)
        mt_logf(H, M, MT_LOG_INFO, "an interaction turns the player human (from main+0x%llx)", (unsigned long long)(from >= MAIN ? from - MAIN : from));
    atomic_store(&g_interaction_at, now);
    return MT_CONTINUE;
}
/* Animation condition 0x56 = not (wall probe). Function entry: (x0 = &controller, w1 = mode); returns probe ^ (mode == 1).
   For the player while transformed the probe counts as true, so the idle -> stand-up transition never fires. */
static int h_probe(MtHookCtx *c, void *u) {
    (void)u;
    if (!atomic_load(&g_form)) return MT_CONTINUE;
    uint64_t ctl = r64(H->reg_get(c, 0)), owner = ctl ? r64(ctl + 8) : 0;
    uint16_t idx = 0xFFFF;
    if (!owner || !r16(owner + 0x1C, &idx) || idx != 0) return MT_CONTINUE;
    H->reg_set(c, 0, (uint32_t)H->reg_get(c, 1) == 1 ? 0 : 1);
    return MT_HANDLED;
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
        {"form_get", h_form_get},       {"form_set", h_form_set}, {"request_state", h_request_state},
        {"probe", h_probe},
        {"char_setup", h_char_setup},   {"player_tick", h_player_tick}, {"to_human", h_to_human},
    };
    for (size_t i = 0; i < sizeof hooks / sizeof hooks[0]; i++) {
        int rc = H->hook(M, hooks[i].point, hooks[i].fn, NULL);
        if (rc != MT_OK) {
            mt_logf(H, M, MT_LOG_ERROR, "cannot hook %s (%d)", hooks[i].point, rc);
            return MT_ERR;
        }
    }
    read_settings();
    H->on_config_changed(M, on_config, NULL);
    mt_logf(H, M, MT_LOG_INFO, "ready: ZL + L3 turns into %s and back, ZL + D-pad Left / Right picks another, %s or ZL + R3 opens the list", form_name(atomic_load(&g_selected)), H->config_string(M, "key_menu"));
    return MT_OK;
}
