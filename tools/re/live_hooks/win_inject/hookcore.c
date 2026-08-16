/*
 * hookcore.c -- engine implementation: config loading, logging, the
 * MinHook install loop, and the two C entry points called from
 * hookstub.S (HookEntryC / LogExitC). See hookcore.h for the full design
 * rationale (why entry+exit is done via return-address swap rather than
 * typed MinHook detours).
 *
 * XP compatibility note: this file uses ONLY kernel32.dll APIs (via
 * mincrt.h for everything string/formatting-shaped that would normally
 * be CRT or user32 -- see that header's own comment for exactly why: this
 * project's mingw-w64 toolchain has no way to produce a genuine
 * legacy-msvcrt-linked binary, only Universal-CRT-linked ones, and UCRT
 * does not exist on Windows XP). CRITICAL_SECTION, TlsAlloc/TlsGetValue/
 * TlsSetValue, GetModuleHandleA, GetModuleFileNameA, GetTickCount,
 * GetCurrentThreadId, IsBadReadPtr, CreateFileA/WriteFile have all been
 * present since Windows NT 3.1 / Win95 -- nothing here needs anything
 * newer than what shipped with XP RTM.
 */

#include "hookcore.h"
#include "mincrt.h"
#include "../vendor/minhook/include/MinHook.h"

HookEngine g_engine;

/* ---------------------------------------------------------------------
 * Compile-time cross-check that the C struct layout hookstub.S assumes
 * (see that file's header) actually matches what this compiler produces.
 * If this ever fails to compile, the asm offsets MUST be re-derived --
 * do not "fix" this assert by changing the numbers without re-checking
 * hookstub.S.
 * --------------------------------------------------------------------- */
typedef char HookRegs_offset_check_hookIndex
    [(int)__builtin_offsetof(HookRegs, hookIndex) == HOOKREGS_OFFSET_HOOKINDEX ? 1 : -1];
typedef char HookRegs_offset_check_retAddr
    [(int)__builtin_offsetof(HookRegs, retAddr) == HOOKREGS_OFFSET_RETADDR ? 1 : -1];
typedef char HookRegs_size_check
    [(int)sizeof(HookRegs) == HOOKREGS_OFFSET_ARGS ? 1 : -1];

/* ---------------------------------------------------------------------
 * Per-thread shadow stack for the return-address-swap exit technique.
 * Fixed depth -- generous for anything these 23 hooks plausibly do
 * (no evidence of deep recursion in any of them; docs/62/65/66/74 never
 * describe recursive calls among these stages). If the depth is ever
 * exceeded, HookEntryC declines to swap (falls back to entry-only for
 * that specific call) rather than overflow -- see HookEntryC below.
 * --------------------------------------------------------------------- */
#define SHADOW_STACK_DEPTH 64

/* How many raw stack dwords past the args pointer HookEntryC logs on
 * entry -- same spirit as agent.js's STACK_DWORDS_TO_LOG. */
#define STACK_DWORDS_LOGGED 16

typedef struct ShadowFrame {
    DWORD hookIndex;
    DWORD callId;
    void *realRetAddr;
    DWORD entryTick;
} ShadowFrame;

typedef struct ShadowStack {
    int         top; /* next free slot, 0..SHADOW_STACK_DEPTH */
    ShadowFrame frames[SHADOW_STACK_DEPTH];
} ShadowStack;

/* ---------------------------------------------------------------------
 * General runtime guard against the exact corruption mechanism found
 * 2026-08-15: `sba_set_shifts_12`, `icc_effect_op_ctor`, `tla_baddscene`,
 * `tla_colneg_planar_scan`, and `tla_colneg_mmx_kernel` were all found
 * (via a fresh r2 `af`+`axt` cross-reference pass against the verified
 * vendor DLLs -- see hookcore_real_table.c's citations and this session's
 * own writeup) to NOT be independently call-reachable function entries --
 * they are internal branch/fallthrough targets inside a DIFFERENT, larger
 * function. Those five are now disabled by default (`notCallReachable`,
 * see hookcore.h), but that is a per-address fix, and this table was
 * carried over verbatim from agent.js without ever re-checking THIS
 * specific precondition for every entry -- there is no reason to assume
 * every remaining hook (or every hook added in the future) has been
 * checked this thoroughly. This function is the GENERAL fix: it validates,
 * at the moment a call actually happens, that the DWORD HookEntryC is
 * about to trust as "the real return address" and unconditionally
 * overwrite with `OnReturnThunk` actually looks like a real code address
 * (committed, executable memory) before the swap is performed. A hooked
 * address reached via anything other than a genuine `call` (fallthrough,
 * an internal jmp/jcc) will have essentially arbitrary data sitting in
 * that stack slot -- a pointer, a float, a small integer -- which very
 * rarely also happens to satisfy "committed + executable", so this check
 * catches exactly the failure mode that (most likely) explains this
 * harness's repeated "stops mid-loop under load, no shutdown message"
 * failures: the engine corrupting a stack slot that was never really a
 * return address in the first place. Cost: one VirtualQuery syscall per
 * exit-hooked call, same order of magnitude as the IsBadReadPtr check
 * already on this same hot path -- a real, non-zero cost, accepted
 * because the alternative (skip the check) is committing to overwrite
 * live memory whose true meaning we cannot otherwise confirm. */
static BOOL LooksLikeCodeAddress(void *addr) {
    MEMORY_BASIC_INFORMATION mbi;
    DWORD execMask = PAGE_EXECUTE | PAGE_EXECUTE_READ |
                      PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY;
    if (addr == NULL) return FALSE;
    if (VirtualQuery(addr, &mbi, sizeof(mbi)) != sizeof(mbi)) return FALSE;
    if (mbi.State != MEM_COMMIT) return FALSE;
    return (mbi.Protect & execMask) != 0;
}

static ShadowStack *GetShadowStack(HookEngine *eng) {
    ShadowStack *ss = (ShadowStack *)TlsGetValue(eng->tlsShadowStack);
    if (ss == NULL) {
        ss = (ShadowStack *)mc_alloc(sizeof(ShadowStack));
        if (ss != NULL) {
            TlsSetValue(eng->tlsShadowStack, ss);
        }
    }
    return ss;
}

/* ---------------------------------------------------------------------
 * Logging -- plain JSON-lines, hand-formatted via mincrt.h's StrBuf (no
 * JSON library dependency, schema is fixed/flat). Mirrors agent.js's
 * field names loosely (hook_id, call_id, event, regs, retval) so existing
 * analysis habits from the Frida sessions carry over directly.
 * --------------------------------------------------------------------- */

/* How many hot-path (per-call) lines to let accumulate in the OS file
 * cache before an explicit FlushFileBuffers -- see the header comment
 * above LogLine for why this exists and why it's safe. */
#define HOTPATH_FLUSH_EVERY_N_LINES 200

/* forceFlush: TRUE for low-frequency events (status/hook_installed/
 * hook_failed -- a handful of lines total, worth an immediate durable
 * write for install-time diagnosis). FALSE for the hot per-call entry/exit
 * path (HookEntryC/LogExitC): a real, measured problem was found here --
 * an earlier version of this function called FlushFileBuffers() on EVERY
 * line while holding eng->logLock, meaning every single hooked call, on
 * every thread, serialized behind a synchronous disk-flush syscall inside
 * a global lock. For a hook on a demonstrated per-pixel/per-scanline hot
 * path (e.g. tlb_polypixel -- see hookcore_real_table.c), called from
 * multiple threads only tens of ticks apart, that is real, avoidable
 * latency and cross-thread serialization injected into a live scan by
 * this tooling itself -- exactly the kind of self-inflicted timing
 * perturbation that could destabilize a vendor pipeline with any
 * real-time producer/consumer assumption between hardware data delivery
 * and per-pixel software processing, independent of anything about the
 * hooked function itself. FlushFileBuffers only protects against losing
 * the last few lines if the *operating system* goes down before the OS's
 * own lazy-writer flushes its page cache to disk; it does NOT protect
 * against PSI.exe (the hooked *process*) crashing or hanging -- the OS
 * page cache survives a process crash/hang untouched and is written back
 * on its own schedule regardless of what this DLL does. So skipping the
 * per-line flush costs nothing in the one failure mode (PSI.exe going
 * down) this harness actually exists to capture, while removing the most
 * expensive syscall from the hottest path. A periodic flush every
 * HOTPATH_FLUSH_EVERY_N_LINES still runs (outside any single call's
 * critical-section hold beyond the write itself) so a long session still
 * gets bounded, non-zero durability against the OS-crash case too, and
 * HookCore_Shutdown still flushes unconditionally on a clean exit. */
static void LogLine(HookEngine *eng, const char *line, BOOL forceFlush) {
    DWORD written;
    BOOL doFlush;
    if (eng->logFile == NULL || eng->logFile == INVALID_HANDLE_VALUE) return;
    EnterCriticalSection(&eng->logLock);
    WriteFile(eng->logFile, line, (DWORD)mc_strlen(line), &written, NULL);
    WriteFile(eng->logFile, "\r\n", 2, &written, NULL);
    doFlush = forceFlush;
    if (!doFlush) {
        eng->unflushedLines++;
        if (eng->unflushedLines >= HOTPATH_FLUSH_EVERY_N_LINES) {
            eng->unflushedLines = 0;
            doFlush = TRUE;
        }
    } else {
        eng->unflushedLines = 0;
    }
    if (doFlush) FlushFileBuffers(eng->logFile);
    LeaveCriticalSection(&eng->logLock);
}

void HookCore_LogStatus(HookEngine *eng, const char *msg) {
    char line[1024];
    StrBuf sb;
    sb_init(&sb, line, sizeof(line));
    sb_puts(&sb, "{\"kind\":\"status\",\"tid\":");
    sb_put_u32_dec(&sb, GetCurrentThreadId());
    sb_puts(&sb, ",\"tick\":");
    sb_put_u32_dec(&sb, GetTickCount());
    sb_puts(&sb, ",\"message\":");
    sb_put_json_str(&sb, msg);
    sb_puts(&sb, "}");
    LogLine(eng, line, TRUE); /* status messages are rare -- flush immediately */
}

static void LogHookInstalled(HookEngine *eng, int i, BOOL ok, const char *err) {
    char line[1024];
    StrBuf sb;
    HookDef *d = &eng->defs[i];
    HookRuntime *r = &eng->rt[i];
    sb_init(&sb, line, sizeof(line));
    if (ok) {
        sb_puts(&sb, "{\"kind\":\"hook_installed\",\"hook_id\":");
        sb_put_json_str(&sb, d->id);
        sb_puts(&sb, ",\"module\":");
        sb_put_json_str(&sb, d->dll);
        sb_puts(&sb, ",\"va_documented\":\"0x");
        sb_put_hex8(&sb, d->va);
        sb_puts(&sb, "\",\"rt_address\":");
        sb_put_hex8_quoted(&sb, (unsigned long)(DWORD_PTR)r->target);
        sb_puts(&sb, ",\"exit_enabled\":");
        sb_puts(&sb, r->exitEnabled ? "true" : "false");
        sb_puts(&sb, ",\"tick\":");
        sb_put_u32_dec(&sb, GetTickCount());
        sb_puts(&sb, "}");
    } else {
        sb_puts(&sb, "{\"kind\":\"hook_failed\",\"hook_id\":");
        sb_put_json_str(&sb, d->id);
        sb_puts(&sb, ",\"module\":");
        sb_put_json_str(&sb, d->dll);
        sb_puts(&sb, ",\"va_documented\":\"0x");
        sb_put_hex8(&sb, d->va);
        sb_puts(&sb, "\",\"error\":");
        sb_put_json_str(&sb, err ? err : "unknown");
        sb_puts(&sb, ",\"tick\":");
        sb_put_u32_dec(&sb, GetTickCount());
        sb_puts(&sb, "}");
    }
    LogLine(eng, line, TRUE); /* install-time events are rare -- flush immediately */
}

/* ---------------------------------------------------------------------
 * Config: "<configDir>\hooks.cfg", optional. Lines: `# comment`,
 * `EXIT=on|off` (global default for exit-hooking), `<id>=on|off`
 * (per-hook enable/disable, overrides the approximate-address default),
 * `<id>.exit=on|off` (per-hook exit override). Deliberately tiny/naive
 * parser -- this file is meant to be hand-edited on the XP box between
 * runs without needing a rebuild.
 * --------------------------------------------------------------------- */
void HookCore_LoadConfig(HookEngine *eng, const char *configDir) {
    char path[MAX_PATH];
    int i;
    HANDLE f;
    DWORD size;
    char *buf;

    mc_strcpy_n(path, configDir, sizeof(path));
    {
        int n = mc_strlen(path);
        if (n < (int)sizeof(path) - 11) {
            path[n] = '\\';
            mc_strcpy_n(path + n + 1, "hooks.cfg", sizeof(path) - n - 1);
        }
    }

    for (i = 0; i < eng->count; i++) {
        eng->rt[i].enabled =
            (eng->defs[i].approximate || eng->defs[i].hotPathDisabled ||
             eng->defs[i].notCallReachable) ? 0 : 1;
        eng->rt[i].exitEnabled = eng->defs[i].wantExitDefault;
    }

    f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL,
                     OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        HookCore_LogStatus(eng, "no hooks.cfg found next to the DLL -- using built-in defaults (approximate-address and hot-path-disabled-by-default hooks off, others on, exit per wantExitDefault)");
        return;
    }

    size = GetFileSize(f, NULL);
    buf = (char *)mc_alloc(size + 1);
    if (buf != NULL) {
        DWORD readBytes = 0;
        char *line;
        ReadFile(f, buf, size, &readBytes, NULL);
        buf[readBytes] = '\0';

        line = buf;
        while (line != NULL && *line != '\0') {
            char *nl = line;
            char saved;
            while (*nl != '\0' && *nl != '\n' && *nl != '\r') nl++;
            saved = *nl;
            *nl = '\0';

            /* trim leading whitespace */
            while (*line == ' ' || *line == '\t') line++;

            if (*line != '\0' && *line != '#') {
                char *eq = line;
                while (*eq != '\0' && *eq != '=') eq++;
                if (*eq == '=') {
                    char *key = line;
                    const char *val;
                    BOOL on;
                    *eq = '\0';
                    val = eq + 1;
                    on = mc_streq_ci(val, "on") || mc_streq_ci(val, "1");

                    if (mc_streq_ci(key, "EXIT")) {
                        for (i = 0; i < eng->count; i++) eng->rt[i].exitEnabled = on;
                    } else {
                        /* find "<id>" or "<id>.exit" */
                        char *dot = mc_strchr(key, '.');
                        BOOL isExitKey = (dot != NULL);
                        if (isExitKey) *dot = '\0';
                        for (i = 0; i < eng->count; i++) {
                            if (mc_streq_ci(eng->defs[i].id, key)) {
                                if (isExitKey) eng->rt[i].exitEnabled = on;
                                else eng->rt[i].enabled = on;
                                break;
                            }
                        }
                    }
                }
            }

            if (saved == '\0') break;
            line = nl + 1;
        }
        mc_free(buf);
    }
    CloseHandle(f);
    HookCore_LogStatus(eng, "hooks.cfg loaded");
}

BOOL HookCore_Init(HookEngine *eng, const char *configDir) {
    char path[MAX_PATH];
    char envBuf[MAX_PATH];
    BOOL haveEnv;

    InitializeCriticalSection(&eng->logLock);
    eng->tlsShadowStack = TlsAlloc();
    eng->callCounter = 0;
    eng->unflushedLines = 0;

    haveEnv = GetEnvironmentVariableA("HOOKDLL_LOG_PATH", envBuf, MAX_PATH) > 0;

    if (haveEnv) {
        mc_strcpy_n(path, envBuf, sizeof(path));
    } else {
        SYSTEMTIME st;
        StrBuf sb;
        GetLocalTime(&st);
        sb_init(&sb, path, sizeof(path));
        sb_puts(&sb, configDir);
        sb_puts(&sb, "\\live_hooks_");
        sb_put_u32_dec_padded(&sb, st.wYear, 4);
        sb_put_u32_dec_padded(&sb, st.wMonth, 2);
        sb_put_u32_dec_padded(&sb, st.wDay, 2);
        sb_putc(&sb, '-');
        sb_put_u32_dec_padded(&sb, st.wHour, 2);
        sb_put_u32_dec_padded(&sb, st.wMinute, 2);
        sb_put_u32_dec_padded(&sb, st.wSecond, 2);
        sb_puts(&sb, ".jsonl");
    }

    eng->logFile = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL,
                                CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (eng->logFile == INVALID_HANDLE_VALUE) {
        eng->logFile = NULL;
        return FALSE;
    }

    HookCore_LoadConfig(eng, configDir);

    {
        char msg[512];
        StrBuf sb;
        sb_init(&sb, msg, sizeof(msg));
        sb_puts(&sb, "hookcore initialized, ");
        sb_put_u32_dec(&sb, (unsigned long)eng->count);
        sb_puts(&sb, " hook(s) defined, logging to this file");
        HookCore_LogStatus(eng, msg);
    }

    if (MH_Initialize() != MH_OK) {
        HookCore_LogStatus(eng, "MH_Initialize failed");
        return FALSE;
    }
    return TRUE;
}

int HookCore_InstallPass(HookEngine *eng) {
    int installedNow = 0;
    int i;
    for (i = 0; i < eng->count; i++) {
        HookDef *d = &eng->defs[i];
        HookRuntime *r = &eng->rt[i];
        MH_STATUS st;
        if (!r->enabled || r->installed) continue;

        if (d->dll == NULL) {
            /* selftest.c only: `va` is a literal in-process function
             * address (cast from a real local function pointer), not a
             * documented VA to rebase against a named module. The real
             * hookcore_real_table.c never leaves dll NULL. */
            r->target = (void *)(DWORD_PTR)d->va;
        } else {
            HMODULE base = GetModuleHandleA(d->dll);
            DWORD_PTR rva;
            if (base == NULL) continue; /* not loaded yet, try again later */
            rva = (DWORD_PTR)d->va - 0x10000000u;
            r->target = (void *)((DWORD_PTR)base + rva);
        }

        st = MH_CreateHook(r->target, d->entryThunk, &r->trampoline);
        if (st != MH_OK) {
            LogHookInstalled(eng, i, FALSE, MH_StatusToString(st));
            continue;
        }
        st = MH_EnableHook(r->target);
        if (st != MH_OK) {
            LogHookInstalled(eng, i, FALSE, MH_StatusToString(st));
            MH_RemoveHook(r->target);
            continue;
        }
        r->installed = TRUE;
        installedNow++;
        LogHookInstalled(eng, i, TRUE, NULL);
    }
    return installedNow;
}

void HookCore_Shutdown(HookEngine *eng) {
    HookCore_LogStatus(eng, "shutting down: disabling all hooks");
    MH_DisableHook(MH_ALL_HOOKS);
    MH_Uninitialize();
    if (eng->logFile != NULL) {
        FlushFileBuffers(eng->logFile);
        CloseHandle(eng->logFile);
        eng->logFile = NULL;
    }
    DeleteCriticalSection(&eng->logLock);
}

/* ---------------------------------------------------------------------
 * docs/74 SS47's own opt-in "extra buffer dump" feature -- see hookcore.h's
 * ExtraDumpSpec comment for the motivation/design. Called once per "enter"
 * event, after the normal call-enter line has already been logged, so a
 * bug in here can never suppress the baseline capture this whole harness
 * exists for. Emits ZERO OR MORE separate `{"kind":"buffer_dump",...}`
 * JSONL lines, one per matching g_extraDumps[] row, each independently
 * IsBadReadPtr-guarded -- one bad pointer in one row logs
 * `"readable":false` for that row only, never aborts the others.
 * --------------------------------------------------------------------- */
static void LogExtraDumps(HookEngine *eng, HookDef *d, DWORD callId, DWORD *sp) {
    const ExtraDumpSpec *spec;
    /* HOOKCORE_EXTRA_DUMP_MAX_BYTES*2 hex chars + JSON field overhead;
     * sb_putc's own bounds check makes a too-small buffer truncate safely
     * rather than overflow, but this is sized generously so truncation
     * should never actually happen for any row in g_extraDumps[]. */
    char dumpLine[HOOKCORE_EXTRA_DUMP_MAX_BYTES * 2 + 256];
    StrBuf sb;

    for (spec = g_extraDumps; spec->hookId != NULL; spec++) {
        DWORD numBytes;
        void *srcPtr;
        BOOL readable;

        if (!mc_streq_ci(spec->hookId, d->id)) continue;
        /* Defensive: g_extraDumps[] rows are hand-written constants, but
         * a future added row with a bad stackIndex should skip cleanly
         * rather than read outside the STACK_DWORDS_LOGGED dwords the
         * caller already validated. */
        if (spec->stackIndex < 0 || spec->stackIndex >= STACK_DWORDS_LOGGED) continue;

        numBytes = spec->numBytes;
        if (numBytes > HOOKCORE_EXTRA_DUMP_MAX_BYTES) numBytes = HOOKCORE_EXTRA_DUMP_MAX_BYTES;

        srcPtr = NULL;
        readable = FALSE;
        if (spec->kind == EXTRA_DUMP_STACK_PTR) {
            srcPtr = (void *)(DWORD_PTR)sp[spec->stackIndex];
            readable = !IsBadReadPtr(srcPtr, numBytes);
        } else { /* EXTRA_DUMP_DEREF_PTR: base = sp[idx], real ptr = *(base + off) */
            void *base = (void *)(DWORD_PTR)sp[spec->stackIndex];
            if (!IsBadReadPtr((BYTE *)base + spec->derefOffset, sizeof(void *))) {
                srcPtr = *(void **)((BYTE *)base + spec->derefOffset);
                readable = !IsBadReadPtr(srcPtr, numBytes);
            }
        }

        sb_init(&sb, dumpLine, sizeof(dumpLine));
        sb_puts(&sb, "{\"kind\":\"buffer_dump\",\"hook_id\":");
        sb_put_json_str(&sb, d->id);
        sb_puts(&sb, ",\"call_id\":");
        sb_put_i32_dec(&sb, (long)callId);
        sb_puts(&sb, ",\"label\":");
        sb_put_json_str(&sb, spec->label);
        sb_puts(&sb, ",\"addr\":");
        sb_put_hex8_quoted(&sb, (unsigned long)(DWORD_PTR)srcPtr);
        sb_puts(&sb, ",\"len\":");
        sb_put_u32_dec(&sb, numBytes);
        sb_puts(&sb, ",\"readable\":");
        sb_puts(&sb, readable ? "true" : "false");
        sb_puts(&sb, ",\"hex\":");
        if (readable) {
            sb_putc(&sb, '"');
            sb_put_hex_bytes(&sb, (const unsigned char *)srcPtr, (int)numBytes);
            sb_putc(&sb, '"');
        } else {
            sb_puts(&sb, "null");
        }
        sb_puts(&sb, "}");
        LogLine(eng, dumpLine, FALSE); /* same hot-path flush policy as the enter/leave lines */
    }
}

/* ---------------------------------------------------------------------
 * Called from hookstub.S's SharedEntryHandler. See hookcore.h for the
 * exact contract.
 * --------------------------------------------------------------------- */
void *HookEntryC(DWORD hookIndex, HookRegs *regs, void *realRetAddr,
                  void *argsPtr, void **outSwapAddr) {
    HookEngine *eng = &g_engine;
    HookDef *d;
    HookRuntime *r;
    LONG callId;
    char stackBuf[STACK_DWORDS_LOGGED * 13 + 16];
    StrBuf stackSb;
    DWORD *sp;
    BOOL spReadable;
    char line[2048];
    StrBuf sb;

    *outSwapAddr = NULL;

    if (hookIndex >= (DWORD)eng->count || !eng->rt[hookIndex].installed) {
        /* Should never happen -- every entry thunk that can actually run
         * corresponds to an installed hook. Logged loudly rather than
         * silently falling through, since if this ever fires it means
         * something is structurally wrong (e.g. table/thunk index
         * mismatch) and needs investigation before trusting any capture. */
        char msg[256];
        StrBuf msgSb;
        sb_init(&msgSb, msg, sizeof(msg));
        sb_puts(&msgSb, "HookEntryC: hookIndex ");
        sb_put_u32_dec(&msgSb, hookIndex);
        sb_puts(&msgSb, " out of range or not installed -- BUG, investigate before trusting this session");
        HookCore_LogStatus(eng, msg);
        return NULL;
    }

    d = &eng->defs[hookIndex];
    r = &eng->rt[hookIndex];
    callId = InterlockedIncrement(&eng->callCounter);

    /* First STACK_DWORDS_LOGGED stack dwords above the args pointer --
     * same spirit as agent.js's STACK_DWORDS_TO_LOG, a raw dump rather
     * than a decoded argument list (the calling convention/arg count is
     * not known). IsBadReadPtr (not __try/__except -- neither the
     * freestanding build nor i686-w64-mingw32-gcc's normal mode supports
     * MSVC SEH __try blocks) gives the same "don't crash on a bad
     * pointer" safety agent.js's tryReadBytes() had via Frida. */
    sb_init(&stackSb, stackBuf, sizeof(stackBuf));
    sp = (DWORD *)argsPtr;
    spReadable = !IsBadReadPtr(sp, STACK_DWORDS_LOGGED * sizeof(DWORD));
    if (spReadable) {
        int i;
        for (i = 0; i < STACK_DWORDS_LOGGED; i++) {
            if (i > 0) sb_putc(&stackSb, ',');
            sb_put_hex8_quoted(&stackSb, sp[i]);
        }
    } else {
        sb_puts(&stackSb, "\"unreadable\"");
    }

    sb_init(&sb, line, sizeof(line));
    sb_puts(&sb, "{\"kind\":\"call\",\"event\":\"enter\",\"hook_id\":");
    sb_put_json_str(&sb, d->id);
    sb_puts(&sb, ",\"call_id\":");
    sb_put_i32_dec(&sb, callId);
    sb_puts(&sb, ",\"tid\":");
    sb_put_u32_dec(&sb, GetCurrentThreadId());
    sb_puts(&sb, ",\"tick\":");
    sb_put_u32_dec(&sb, GetTickCount());
    sb_puts(&sb, ",\"module\":");
    sb_put_json_str(&sb, d->dll);
    sb_puts(&sb, ",\"va_documented\":\"0x");
    sb_put_hex8(&sb, d->va);
    sb_puts(&sb, "\",\"eax\":"); sb_put_hex8_quoted(&sb, regs->eax);
    sb_puts(&sb, ",\"ebx\":");   sb_put_hex8_quoted(&sb, regs->ebx);
    sb_puts(&sb, ",\"ecx\":");   sb_put_hex8_quoted(&sb, regs->ecx);
    sb_puts(&sb, ",\"edx\":");   sb_put_hex8_quoted(&sb, regs->edx);
    sb_puts(&sb, ",\"esi\":");   sb_put_hex8_quoted(&sb, regs->esi);
    sb_puts(&sb, ",\"edi\":");   sb_put_hex8_quoted(&sb, regs->edi);
    sb_puts(&sb, ",\"ebp\":");   sb_put_hex8_quoted(&sb, regs->ebp_orig);
    sb_puts(&sb, ",\"eflags\":"); sb_put_hex8_quoted(&sb, regs->eflags);
    sb_puts(&sb, ",\"retaddr\":"); sb_put_hex8_quoted(&sb, (unsigned long)(DWORD_PTR)realRetAddr);
    sb_puts(&sb, ",\"stack_dwords\":[");
    sb_puts(&sb, stackBuf);
    sb_puts(&sb, "]}");
    LogLine(eng, line, FALSE); /* hot path -- see LogLine's header comment */

    /* docs/74 SS47 extension -- only ever does anything for hook_ids that
     * appear in g_extraDumps[] (currently just area_image_apply_lut), a
     * plain linear scan/compare against a handful of static rows, so this
     * is a no-op cost for every other one of the 25 hooks. Requires the
     * SAME sp readability already established above -- never dereferences
     * sp[] on a pointer this function has already decided not to trust. */
    if (spReadable) {
        LogExtraDumps(eng, d, (DWORD)callId, sp);
    }

    if (r->exitEnabled) {
        if (!LooksLikeCodeAddress(realRetAddr)) {
            /* See LooksLikeCodeAddress's own header comment. realRetAddr
             * does not look like a real code address, meaning this call
             * almost certainly did not arrive via a genuine `call`
             * instruction -- committing the return-address swap here would
             * overwrite live data belonging to whatever function actually
             * put this value on the stack, exactly the corruption mechanism
             * found 2026-08-15 for several now-disabled hook_ids. Falling
             * back to entry-only logging for this call is always safe;
             * this is loud (not silent) because it means either a
             * not-yet-audited hook has the same problem, or something
             * genuinely unexpected happened for a hook believed to be a
             * real function entry -- both worth investigating. */
            char msg[256];
            StrBuf msgSb;
            sb_init(&msgSb, msg, sizeof(msg));
            sb_puts(&msgSb, "realRetAddr does not look like a real code address for hook_id=");
            sb_puts(&msgSb, d->id);
            sb_puts(&msgSb, " call_id=");
            sb_put_i32_dec(&msgSb, callId);
            sb_puts(&msgSb, " retaddr=0x");
            sb_put_hex8(&msgSb, (unsigned long)(DWORD_PTR)realRetAddr);
            sb_puts(&msgSb, " -- this call almost certainly was NOT reached via a real `call` instruction; declining the return-address swap (would corrupt live stack data) and falling back to entry-only for this call. This hook_id likely needs `notCallReachable` treatment -- see hookcore.h/README.");
            HookCore_LogStatus(eng, msg);
        } else {
            ShadowStack *ss = GetShadowStack(eng);
            if (ss != NULL && ss->top < SHADOW_STACK_DEPTH) {
                ShadowFrame *fr = &ss->frames[ss->top++];
                fr->hookIndex = hookIndex;
                fr->callId = (DWORD)callId;
                fr->realRetAddr = realRetAddr;
                fr->entryTick = GetTickCount();
                *outSwapAddr = (void *)&OnReturnThunk;
            } else {
                char msg[256];
                StrBuf msgSb;
                sb_init(&msgSb, msg, sizeof(msg));
                sb_puts(&msgSb, "shadow stack full or unavailable on tid ");
                sb_put_u32_dec(&msgSb, GetCurrentThreadId());
                sb_puts(&msgSb, " for hook_id=");
                sb_puts(&msgSb, d->id);
                sb_puts(&msgSb, " call_id=");
                sb_put_i32_dec(&msgSb, callId);
                sb_puts(&msgSb, " -- falling back to entry-only for this call");
                HookCore_LogStatus(eng, msg);
            }
        }
    }

    return r->trampoline;
}

void *LogExitC(DWORD eaxRet, DWORD edxRet) {
    HookEngine *eng = &g_engine;
    ShadowStack *ss = GetShadowStack(eng);
    ShadowFrame *fr;
    HookDef *d;
    char line[512];
    StrBuf sb;

    if (ss == NULL || ss->top <= 0) {
        HookCore_LogStatus(eng, "LogExitC: shadow stack empty on exit -- this should not happen, an entry/exit pair is unbalanced; treating as fatal for this call, returning NULL (WILL CRASH if reached from asm without a null-check)");
        return NULL;
    }
    fr = &ss->frames[--ss->top];
    d = (fr->hookIndex < (DWORD)eng->count) ? &eng->defs[fr->hookIndex] : NULL;

    sb_init(&sb, line, sizeof(line));
    sb_puts(&sb, "{\"kind\":\"call\",\"event\":\"leave\",\"hook_id\":");
    sb_put_json_str(&sb, d ? d->id : "?");
    sb_puts(&sb, ",\"call_id\":");
    sb_put_u32_dec(&sb, fr->callId);
    sb_puts(&sb, ",\"tid\":");
    sb_put_u32_dec(&sb, GetCurrentThreadId());
    sb_puts(&sb, ",\"tick\":");
    sb_put_u32_dec(&sb, GetTickCount());
    sb_puts(&sb, ",\"duration_ticks\":");
    sb_put_u32_dec(&sb, GetTickCount() - fr->entryTick);
    sb_puts(&sb, ",\"eax\":"); sb_put_hex8_quoted(&sb, eaxRet);
    sb_puts(&sb, ",\"edx\":"); sb_put_hex8_quoted(&sb, edxRet);
    sb_puts(&sb, "}");
    LogLine(eng, line, FALSE); /* hot path -- see LogLine's header comment */

    return fr->realRetAddr;
}
