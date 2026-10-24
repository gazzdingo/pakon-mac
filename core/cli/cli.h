#ifndef PAKON_CLI_H
#define PAKON_CLI_H
/* The minimal `pakon` command line (Task 10, ruling C18). Task 22 extends it and replaces hw1.c with real commands.
 * Everything here reaches the scanner only through the public library (the pakon/ headers) and therefore through the write guard.
 * The internal headers used are for reading trace files back (transport/trace.h), the saved calibration image (calib/eeprom.h, device/eeprom_store.h) and sha256/file helpers (util/util.h). */
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include "pakon/boards.h"
#include "pakon/device.h"
#include "pakon/vendor.h"

typedef struct {
    const char *trace;       /* --trace DIR: record every transfer into this new trace directory */
    const char *replay;      /* --replay DIR: run the command against a recorded trace instead of the scanner */
    const char *home;        /* --home DIR (default $PAKON_HOME, else ~/pakon-data): vendor store and unit store live here */
    const char *unit;        /* --unit KEY: override the remembered unit key */
    const char *model;       /* --model plus|f135: only when the calibration chip gives no scanner type */
    bool no_leds;            /* --no-leds */
    bool no_keepalive;       /* --no-keepalive (hw1 lamp: the idle-timeout test) */
    bool confirm_reread;     /* --confirm-reread (hw1 eeprom-read: HW-2's one confirming re-read) */
    bool no_lamp;            /* --no-lamp (hw1 dx: the extra observation without the lamp) */
    int image;               /* --image 2004 (pakon load only): the diagnostic second-retry image; 0 = the model's default (2006) */
    bool do_register;        /* --register (hw1 replay: add the trace to corpus/manifest.json when it replays green) */
    int speed;               /* --speed N (film moves; 0 = the board's maximum) */
    unsigned seconds;        /* --seconds N */
    bool ir;                 /* --ir (hw2e calibrate / scan) */
    int base;                /* --base 4|8|16 (hw2e scan); 0 = 16 */
    int strips;              /* --strips 0|4|5|6 (hw2e scan) */
    const char *out;         /* --out PATH, -o PATH (hw2e scan, decode) */
    bool colour;             /* --colour (decode): also write the finished colour pictures */
    bool ice;                /* --ice (decode, with --colour): IR frames also get a Digital ICE picture, frame_NN_ice.tif, beside the plain one */
    const char *film;        /* --film P/G (decode): a hand-picked DX product / specifier */
    bool fast;               /* the CLI's own waits are skipped (set by --replay and --fake); library waits are real */
#ifndef NDEBUG
    bool fake;               /* --fake: a simulated scanner behind the real guard (debug builds only, see docs/hw1-checklist.md) */
    unsigned fake_damage;    /* --fake-damage MASK: bit i damages copy i (default 1 = CalWiz A) */
    int fake_unplug;         /* --fake-unplug N: the fake scanner vanishes after N packets (0 = never) */
    bool fake_unloaded;      /* set by cli_open for a step that needs an unloaded scanner: the fake starts as an unloaded FX2 */
#endif
    char home_buf[1024];
} cli_opts;

/* args.c */
int cli_parse(int argc, char **argv, cli_opts *o, const char **pos, int cap, int *npos);   /* 0 ok, 2 usage */
void cli_usage(FILE *f);

/* A session: transport (real, replay or fake) -> record -> guard, optionally link and boards. */
enum { CLI_LOADED = 1, CLI_UNLOADED = 2, CLI_BOARDS = 4 };
typedef struct {
    cli_opts *o;
    pk_transport *t;             /* guarded */
    pk_transport *fake_raw;      /* a raw fake kept alive under a borrowing guard, else NULL */
    pk_link *link;
    pk_boards *b;
    const pk_model *usb_model, *model;
    pk_dev_entry dev;
    char serial[32];
    char unit[80];
} cli_session;

int cli_open(cli_opts *o, unsigned flags, cli_session *s);   /* prints its own explanation; non-zero = exit code */
void cli_close(cli_session *s);

/* pakon.c */
extern volatile sig_atomic_t g_cli_intr;
void cli_install_signals(void);
bool cli_wait(const cli_opts *o, unsigned ms);       /* CLI-level wait; false if Ctrl-C was pressed. Skipped when o->fast. */
void cli_real_sleep(unsigned ms);
unsigned long long cli_now_ms(void);
void cli_say(const char *fmt, ...);                  /* a plain sentence */
void cli_detail(const char *fmt, ...);               /* technical detail line under it */
int cli_log_open(const char *path);                  /* from now on cli_say / cli_detail also append to this file (0 ok) */
void cli_log_close(void);
const char *cli_explain(pk_status s);                /* plain words for a status */
void cli_report_status(const char *what, pk_status s, const pk_error *e);
int cli_home(const cli_opts *o, char *out, size_t cap);
/* The unit key remembered by the last eeprom-read (or --unit); 0 if none. */
int cli_unit_remembered(const cli_opts *o, char unit[80]);
int cli_units_with_log(const cli_opts *o, char first[80]);   /* unit folders holding an eeprom.log under the root */
/* Refines the USB-identity model from the stored current image of the remembered unit. Returns the refined model or NULL; why
 * is a plain-words reason when NULL. */
const pk_model *cli_refine_from_store(const cli_opts *o, const pk_model *usb_model, char unit_out[80], char *why, size_t whycap);
const char *cli_model_tag(const pk_model *m);
int cli_cmd_load(cli_opts *o);
int cli_cmd_film(cli_opts *o, const char *sub);
/* A move that the MAIN thread ends with pk_film_stop after stop_after_ms (0 = until Ctrl-C); the mover itself runs with max_ms 300000 (S-R23 I-2). */
pk_status cli_move_for(cli_session *s, pk_film_dir dir, unsigned stop_after_ms, int speed);
/* Starts the same move without waiting (hw1 dx, unplug-watch); cli_move_finish joins it. */
typedef struct cli_mover cli_mover;
cli_mover *cli_move_begin(cli_session *s, pk_film_dir dir, unsigned ms, int speed);
cli_mover *cli_move_begin_register(cli_session *s, pk_film_dir dir, unsigned ms, unsigned reg);   /* speed register as is */
pk_status cli_eject(cli_session *s);
bool cli_move_done(cli_mover *m);
pk_status cli_move_finish(cli_mover *m);

/* hw1.c */
int cli_cmd_hw1(cli_opts *o, int npos, const char **pos);

/* cmd_decode.c */
int cli_cmd_decode(cli_opts *o, int npos, const char **pos);

/* hw2e.c */
int cli_cmd_hw2e(cli_opts *o, int npos, const char **pos);

#ifndef NDEBUG
/* fake.c: a simulated Plus. Returns a heap-allocated RAW transport; the caller passes it to the guard. */
pk_status cli_fake_open(const cli_opts *o, pk_transport **raw);
#endif
#endif
