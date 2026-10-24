#define _POSIX_C_SOURCE 200809L
/* Argument parsing for the minimal pakon (Task 10). Global flags may appear before or after the command words. */
#include <stdlib.h>
#include <string.h>
#include "cli.h"

void cli_usage(FILE *f) {
    fputs(
        "pakon: Pakon F-135 scanner tool (hardware session HW-1 build)\n"
        "\n"
        "  pakon detect                         list attached Pakon scanners and say whether they are loaded\n"
        "  pakon vendor import <folder>         copy the Kodak driver files into the vendor store\n"
        "  pakon load [--image 2004]            load the firmware into an unloaded scanner (Kodak's own sequence)\n"
        "  pakon decode <roll.raw> -o <folder> [--colour] [--film P/G] [--home DIR]\n"
        "                                       linear 16-bit TIFF per frame + frames.json; --colour also writes finished colour pictures\n"
        "  pakon film advance|reverse|stop|eject [--seconds N] [--speed N]\n"
        "  pakon hw1 <step>                     the HW-1 steps, run in this order:\n"
        "      eeprom-read [--confirm-reread]   read the calibration chip once (read only), save it, show which copies are intact\n"
        "      eeprom-scanner-type              show the scanner type from the saved copy (no scanner access)\n"
        "      ping                             ping the boards at the addresses of the identified model\n"
        "      motor                            forward 2 s, stop, reverse 2 s, stop (scanner empty)\n"
        "      leds                             step through the status and film LEDs\n"
        "      lamp [--no-keepalive]            lamp warm-up, health, keep-alive (or the idle-timeout test)\n"
        "      dx [--seconds N] [--speed N] [--no-lamp]\n"
        "                                       run a strip through the DX reader and show what it reads\n"
        "      unplug-watch                     run the motor and watch for the cable being pulled\n"
        "      replay <trace> [--register]      replay a recorded trace against this code (must come out identical)\n"
        "\n"
        "Global flags:\n"
        "  --trace DIR      record every transfer to a new trace directory (use corpus/traces/<name>.ptrace)\n"
        "  --replay DIR     run the command against a recorded trace instead of the scanner\n"
        "  --no-leds        do not drive the status or film LEDs\n"
        "  --no-keepalive   (hw1 lamp) send nothing to the light board while the lamp is on\n"
        "  --home DIR       where the vendor store and the saved calibration image live (default $PAKON_HOME or ~/Library/Application Support/PakonMac)\n"
        "  --unit KEY       use this unit key instead of the remembered one\n"
        "  --image 2004     (pakon load only) DIAGNOSTIC, off by default: load the 2004 Pakon7.hex instead of the 2006 one PSI loads.\n"
        "                   Only for a controlled second retry, when the default load failed with clean read-backs and Claude says so.\n"
        "  --model plus|f135  only if the calibration chip has no readable scanner type and Claude tells you to\n"
#ifndef NDEBUG
        "\n"
        "Developer flags (debug builds only; a release build rejects them):\n"
        "  --fake           use a simulated scanner behind the real write guard (hw1 and film only)\n"
        "  --fake-damage M  bit mask of calibration copies the fake damages (1 = CalWiz A, 2 = B, 4 = Adjust A, 8 = Adjust B; default 1)\n"
        "  --fake-unplug N  the fake scanner disappears after N packets\n"
#endif
        "\nExit codes: 0 ok, 1 the operation failed, 2 usage, 130 stopped with Ctrl-C.\n", f);
}

static int need(int argc, char **argv, int i) {
    if (i + 1 >= argc) { fprintf(stderr, "pakon: %s needs a value\n", argv[i]); return 0; }
    return 1;
}

int cli_parse(int argc, char **argv, cli_opts *o, const char **pos, int cap, int *npos) {
    memset(o, 0, sizeof *o);
#ifndef NDEBUG
    o->fake_damage = 1;
#endif
    *npos = 0;
    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        if (!strcmp(a, "--trace")) { if (!need(argc, argv, i)) return 2; o->trace = argv[++i]; }
        else if (!strcmp(a, "--replay")) { if (!need(argc, argv, i)) return 2; o->replay = argv[++i]; o->fast = true; }
        else if (!strcmp(a, "--home")) { if (!need(argc, argv, i)) return 2; o->home = argv[++i]; }
        else if (!strcmp(a, "--unit")) { if (!need(argc, argv, i)) return 2; o->unit = argv[++i]; }
        else if (!strcmp(a, "--model")) { if (!need(argc, argv, i)) return 2; o->model = argv[++i]; }
        else if (!strcmp(a, "--speed") || !strcmp(a, "--seconds")) {
            if (!need(argc, argv, i)) return 2;
            char *end = NULL;
            long v = strtol(argv[i + 1], &end, 10);
            if (!end || *end || v < 0 || v > 100000) { fprintf(stderr, "pakon: %s needs a number\n", a); return 2; }
            if (a[2] == 's' && a[3] == 'p') o->speed = (int)v; else o->seconds = (unsigned)v;
            i++;
        }
        else if (!strcmp(a, "--image")) {
            if (!need(argc, argv, i)) return 2;
            if (strcmp(argv[i + 1], "2004") != 0) { fprintf(stderr, "pakon: --image accepts only 2004 (the default is the 2006 image)\n"); return 2; }
            o->image = 2004; i++;
        }
        else if (!strcmp(a, "--no-leds")) o->no_leds = true;
        else if (!strcmp(a, "--no-keepalive")) o->no_keepalive = true;
        else if (!strcmp(a, "--confirm-reread")) o->confirm_reread = true;
        else if (!strcmp(a, "--no-lamp")) o->no_lamp = true;
        else if (!strcmp(a, "--ir")) o->ir = true;
        else if (!strcmp(a, "--colour") || !strcmp(a, "--color")) o->colour = true;
        else if (!strcmp(a, "--ice")) o->ice = true;
        else if (!strcmp(a, "--film")) { if (!need(argc, argv, i)) return 2; o->film = argv[++i]; }
        else if (!strcmp(a, "--out") || !strcmp(a, "-o")) { if (!need(argc, argv, i)) return 2; o->out = argv[++i]; }
        else if (!strcmp(a, "--base") || !strcmp(a, "--strips")) {
            if (!need(argc, argv, i)) return 2;
            char *end = NULL;
            long v = strtol(argv[i + 1], &end, 10);
            if (!end || *end || v < 0 || v > 16) { fprintf(stderr, "pakon: %s needs a number\n", a); return 2; }
            if (a[2] == 'b') o->base = (int)v; else o->strips = (int)v;
            i++;
        }
        else if (!strcmp(a, "--register")) o->do_register = true;
#ifndef NDEBUG
        else if (!strcmp(a, "--fake")) { o->fake = true; o->fast = true; }
        else if (!strcmp(a, "--fake-damage") || !strcmp(a, "--fake-unplug")) {
            if (!need(argc, argv, i)) return 2;
            char *end = NULL;
            long v = strtol(argv[i + 1], &end, 0);
            if (!end || *end || v < 0 || v > 100000) { fprintf(stderr, "pakon: %s needs a number\n", a); return 2; }
            if (a[7] == 'd') o->fake_damage = (unsigned)v; else o->fake_unplug = (int)v;
            i++;
        }
#endif
        else if (!strcmp(a, "-h") || !strcmp(a, "--help")) { cli_usage(stdout); exit(0); }
        else if (a[0] == '-' && a[1] == '-') { fprintf(stderr, "pakon: unknown flag %s (try pakon --help)\n", a); return 2; }
        else if (*npos < cap) pos[(*npos)++] = a;
        else { fprintf(stderr, "pakon: too many arguments\n"); return 2; }
    }
    return 0;
}
