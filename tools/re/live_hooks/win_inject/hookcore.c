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

static void LogLine(HookEngine *eng, const char *line) {
    DWORD written;
    if (eng->logFile == NULL || eng->logFile == INVALID_HANDLE_VALUE) return;
    EnterCriticalSection(&eng->logLock);
    WriteFile(eng->logFile, line, (DWORD)mc_strlen(line), &written, NULL);
    WriteFile(eng->logFile, "\r\n", 2, &written, NULL);
    FlushFileBuffers(eng->logFile);
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
    LogLine(eng, line);
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
    LogLine(eng, line);
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
        eng->rt[i].enabled = eng->defs[i].approximate ? 0 : 1;
        eng->rt[i].exitEnabled = eng->defs[i].wantExitDefault;
    }

    f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL,
                     OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        HookCore_LogStatus(eng, "no hooks.cfg found next to the DLL -- using built-in defaults (approximate-address hooks off, others on, exit per wantExitDefault)");
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
    if (!IsBadReadPtr(sp, STACK_DWORDS_LOGGED * sizeof(DWORD))) {
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
    LogLine(eng, line);

    if (r->exitEnabled) {
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
    LogLine(eng, line);

    return fr->realRetAddr;
}
