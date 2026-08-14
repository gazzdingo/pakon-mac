/*
 * hookdll.c -- the injected payload DLL.
 *
 * Frida-free, pure Win32, targets Windows XP (x86) directly: this project's
 * real target VM. See ../README.md "Does this run on Windows XP" for why
 * this exists alongside agent.js/host.py (short version: modern Frida needs
 * Python 3.5+, which requires Windows Vista+; this file needs nothing but
 * kernel32.dll, present on every NT since 3.1 -- verified by build.sh's
 * objdump check on every build, not assumed. See minicrt.h for why even
 * the C runtime itself is avoided: this project's mingw-w64 toolchain
 * defaults to the Universal CRT, which doesn't exist on XP either).
 *
 * TECHNIQUE: one-byte INT3 (0xCC) software breakpoints + a Vectored
 * Exception Handler, the same mechanism every from-scratch Windows debugger
 * uses -- NOT an inline jmp-trampoline hook. This was a deliberate choice:
 * a jmp-trampoline hook overwrites 5+ bytes and must know real x86
 * instruction boundaries to safely relocate the bytes it stole (needs a
 * length disassembler); getting that wrong corrupts the target's code and
 * would corrupt a REAL scan of REAL film through REAL hardware. A 1-byte
 * INT3 patch has no such failure mode: it always overwrites exactly one
 * byte, which this file always restores before letting the real
 * instruction execute (via a single-step, then a conditional re-arm). This
 * is strictly less likely to crash the target than an alternative that
 * requires a disassembler.
 *
 * On x86 Windows, EXCEPTION_BREAKPOINT's reported ExceptionAddress AND
 * ContextRecord->Eip both already equal the INT3 byte's own address (the
 * kernel's trap handler backs Eip up by 1 for you) -- this file relies on
 * that well-established behaviour and does NOT adjust Eip itself.
 *
 * ENTRY + EXIT: entry breakpoints are permanent (installed once, for the
 * life of the process). Exit is tracked the classic debugger way: at
 * entry, before anything else, the return address sitting at [esp] (valid
 * because our breakpoint fires on the function's very first byte, i.e.
 * before any prologue touches esp) is pushed onto a per-thread pending-call
 * stack (TLS) and a temporary breakpoint is armed there too (shared/
 * refcounted across threads and re-entrant calls, since two different
 * calls can share one return address). When that fires, the top of the
 * calling thread's TLS stack is popped to recover which call it belongs to
 * (LIFO -- correct as long as calls on one thread properly nest, which
 * ordinary function calls always do), EAX is logged as the return value,
 * and the temporary breakpoint is disarmed once nothing else is still
 * waiting to return through it.
 *
 * KNOWN LIMITATION, stated plainly: there is a small race window, on the
 * order of a few instructions, during the "restore original byte / single-
 * step / re-arm" sequence on one thread, where a DIFFERENT thread executing
 * the exact same address will simply run the real instruction unhooked
 * (not logged) instead of hitting the breakpoint, since the shared code
 * page is briefly unpatched. This is a known, disclosed limitation of
 * software breakpoints in a multithreaded target (true of every debugger
 * using this technique, not specific to this file) -- see ../README.md.
 * It affects at most one call per hit, does not corrupt anything, and does
 * not apply at all to single-threaded call patterns.
 *
 * Every VA in common.h is documented assuming the owning DLL loads at
 * 0x10000000; this file always rebases against wherever THIS process
 * actually put it (module_base + (va - 0x10000000)) -- see common.h.
 */

#include <windows.h>
#include "common.h"
#include "minicrt.h"

/* ------------------------------------------------------------------ */
/* Global state                                                        */
/* ------------------------------------------------------------------ */

typedef struct {
    const HookDef *def;
    BYTE *addr;          /* runtime address, entry point */
    BYTE originalByte;
    int installed;
} EntryHook;

static EntryHook g_entry[NUM_HOOKS];

#define MAX_RETURN_SLOTS 64
typedef struct {
    BYTE *addr;
    BYTE originalByte;
    int refcount;
    int inUse;
} ReturnSlot;

static ReturnSlot g_retSlots[MAX_RETURN_SLOTS];
static CRITICAL_SECTION g_retCS;

#define MAX_CALL_DEPTH 64
typedef struct {
    BYTE *retAddr;
    LONG callId;
    LONG frameId;
    const HookDef *def;
} CallFrame;

typedef struct {
    CallFrame frames[MAX_CALL_DEPTH];
    int top; /* next free slot */
} ThreadCallStack;

static DWORD g_tlsCallStack = TLS_OUT_OF_INDEXES;

typedef struct {
    BYTE *addr;
    int rearm;
    int valid;
} PendingStep;
static DWORD g_tlsPendingStep = TLS_OUT_OF_INDEXES;

static volatile LONG g_callCounter = 0;
static volatile LONG g_frameCounter = 0;

static HANDLE g_logFile = NULL;
static CRITICAL_SECTION g_logCS;

static PVOID g_vehHandle = NULL;
static HMODULE g_thisModule = NULL;

/* One shared line buffer per call, protected by g_logCS -- avoids a heap
   alloc on every single hook hit. Sized generously: 24 stack slots + 7
   register previews, each up to ~64-byte hex + 32-entry i16 array. */
#define LOGLINE_CAP 65536
static char g_logLineBuf[LOGLINE_CAP];

/* ------------------------------------------------------------------ */
/* Logging helpers                                                     */
/* ------------------------------------------------------------------ */

#define PREVIEW_BYTES 64

static void sb_put_pointer_preview(StrBuf *sb, const void *ptr) {
    if (ptr == NULL || IsBadReadPtr(ptr, PREVIEW_BYTES)) {
        sb_puts(sb, "null");
        return;
    }
    const unsigned char *p = (const unsigned char *)ptr;
    sb_puts(sb, "{\"ptr\":\"0x");
    sb_put_hex8(sb, (unsigned long)(ULONG_PTR)ptr);
    sb_puts(sb, "\",\"hex\":\"");
    for (int i = 0; i < PREVIEW_BYTES; i++) {
        char h[2];
        mc_u8_to_hex2(p[i], h);
        sb_putc(sb, h[0]); sb_putc(sb, h[1]);
    }
    sb_puts(sb, "\",\"i16\":[");
    const short *sp = (const short *)p;
    int n16 = PREVIEW_BYTES / 2;
    for (int i = 0; i < n16; i++) {
        if (i) sb_putc(sb, ',');
        sb_put_i32(sb, (long)sp[i]);
    }
    sb_puts(sb, "],\"known_constant_hits\":[");
    int first = 1;
    for (int i = 0; i < n16; i++) {
        for (int k = 0; k < NUM_KNOWN_CONSTS; k++) {
            if (sp[i] == g_knownConsts[k].value) {
                if (!first) sb_putc(sb, ',');
                first = 0;
                sb_puts(sb, "{\"index\":");
                sb_put_i32(sb, i);
                sb_puts(sb, ",\"value\":");
                sb_put_i32(sb, (long)sp[i]);
                sb_puts(sb, ",\"meaning\":");
                sb_put_json_str(sb, g_knownConsts[k].meaning);
                sb_putc(sb, '}');
            }
        }
    }
    sb_puts(sb, "]}");
}

static void sb_put_stack_preview(StrBuf *sb, DWORD esp, int count) {
    sb_putc(sb, '[');
    BYTE *p = (BYTE *)(ULONG_PTR)esp;
    for (int i = 0; i < count; i++) {
        if (i) sb_putc(sb, ',');
        sb_puts(sb, "{\"offset\":");
        sb_put_i32(sb, i * 4);
        sb_putc(sb, ',');
        if (!IsBadReadPtr(p, 4)) {
            DWORD v = *(DWORD *)p;
            sb_puts(sb, "\"u32\":");
            sb_put_u32(sb, v);
            sb_puts(sb, ",\"preview\":");
            sb_put_pointer_preview(sb, (const void *)(ULONG_PTR)v);
        } else {
            sb_puts(sb, "\"u32\":null,\"preview\":null");
        }
        sb_putc(sb, '}');
        p += 4;
    }
    sb_putc(sb, ']');
}

static void sb_put_regs(StrBuf *sb, const CONTEXT *ctx) {
    static const char *names[] = { "eax","ebx","ecx","edx","esi","edi","ebp","esp","eip" };
    DWORD vals[] = { ctx->Eax, ctx->Ebx, ctx->Ecx, ctx->Edx, ctx->Esi, ctx->Edi, ctx->Ebp, ctx->Esp, ctx->Eip };
    sb_putc(sb, '{');
    for (int i = 0; i < 9; i++) {
        if (i) sb_putc(sb, ',');
        sb_putc(sb, '"'); sb_puts(sb, names[i]); sb_puts(sb, "\":\"0x");
        sb_put_hex8(sb, vals[i]);
        sb_putc(sb, '"');
    }
    sb_putc(sb, '}');
}

static void log_write_line(StrBuf *sb) {
    sb_putc(sb, '\n');
    EnterCriticalSection(&g_logCS);
    mc_write(g_logFile, sb->buf, sb->len);
    LeaveCriticalSection(&g_logCS);
}

static void log_status(const char *msg) {
    char buf[2048];
    StrBuf sb;
    sb_init(&sb, buf, sizeof(buf));
    sb_puts(&sb, "{\"kind\":\"status\",\"message\":");
    sb_put_json_str(&sb, msg);
    sb_putc(&sb, '}');
    log_write_line(&sb);
}

static void log_call_event(const HookDef *def, BYTE *rtAddr, const char *event,
                            LONG callId, LONG frameId, const CONTEXT *ctx,
                            int haveRetval, DWORD retval) {
    StrBuf sb;
    sb_init(&sb, g_logLineBuf, LOGLINE_CAP);

    sb_puts(&sb, "{\"kind\":\"call\",\"event\":\""); sb_puts(&sb, event);
    sb_puts(&sb, "\",\"call_id\":"); sb_put_i32(&sb, callId);
    sb_puts(&sb, ",\"frame_id\":"); sb_put_i32(&sb, frameId);
    sb_puts(&sb, ",\"tid\":"); sb_put_u32(&sb, GetCurrentThreadId());
    sb_puts(&sb, ",\"module\":"); sb_put_json_str(&sb, def->dll);
    sb_puts(&sb, ",\"hook_id\":"); sb_put_json_str(&sb, def->id);
    sb_puts(&sb, ",\"va_documented\":\"0x"); sb_put_hex8(&sb, def->va);
    sb_puts(&sb, "\",\"rt_address\":\"0x"); sb_put_hex8(&sb, (unsigned long)(ULONG_PTR)rtAddr);
    sb_puts(&sb, "\",\"desc\":"); sb_put_json_str(&sb, def->desc);
    sb_puts(&sb, ",\"cite\":"); sb_put_json_str(&sb, def->cite);
    sb_puts(&sb, ",\"approximate_address\":"); sb_puts(&sb, def->approximate ? "true" : "false");
    if (haveRetval) {
        sb_puts(&sb, ",\"retval\":\"0x"); sb_put_hex8(&sb, retval); sb_puts(&sb, "\"");
    }
    sb_puts(&sb, ",\"regs\":"); sb_put_regs(&sb, ctx);
    sb_puts(&sb, ",\"stack\":"); sb_put_stack_preview(&sb, ctx->Esp, 24);
    sb_puts(&sb, ",\"pointer_scan\":{");
    static const char *regNames[] = { "eax","ebx","ecx","edx","esi","edi","ebp" };
    DWORD regVals[] = { ctx->Eax, ctx->Ebx, ctx->Ecx, ctx->Edx, ctx->Esi, ctx->Edi, ctx->Ebp };
    for (int i = 0; i < 7; i++) {
        if (i) sb_putc(&sb, ',');
        sb_puts(&sb, "\"reg_"); sb_puts(&sb, regNames[i]); sb_puts(&sb, "\":");
        sb_put_pointer_preview(&sb, (const void *)(ULONG_PTR)regVals[i]);
    }
    sb_puts(&sb, "}}");
    log_write_line(&sb);
}

/* ------------------------------------------------------------------ */
/* Return-address breakpoint bookkeeping                               */
/* ------------------------------------------------------------------ */

static void return_hook_acquire(BYTE *retAddr) {
    EnterCriticalSection(&g_retCS);
    for (int i = 0; i < MAX_RETURN_SLOTS; i++) {
        if (g_retSlots[i].inUse && g_retSlots[i].addr == retAddr) {
            g_retSlots[i].refcount++;
            LeaveCriticalSection(&g_retCS);
            return;
        }
    }
    for (int i = 0; i < MAX_RETURN_SLOTS; i++) {
        if (!g_retSlots[i].inUse) {
            if (IsBadReadPtr(retAddr, 1)) { LeaveCriticalSection(&g_retCS); return; }
            DWORD oldProt;
            VirtualProtect(retAddr, 1, PAGE_EXECUTE_READWRITE, &oldProt);
            g_retSlots[i].originalByte = *retAddr;
            *retAddr = 0xCC;
            VirtualProtect(retAddr, 1, oldProt, &oldProt);
            g_retSlots[i].addr = retAddr;
            g_retSlots[i].refcount = 1;
            g_retSlots[i].inUse = 1;
            LeaveCriticalSection(&g_retCS);
            return;
        }
    }
    LeaveCriticalSection(&g_retCS);
    log_status("return-hook table full -- exit tracking dropped for one call");
}

static int return_hook_release(BYTE *addr, BYTE *outOriginalByte, int *outShouldRearm) {
    EnterCriticalSection(&g_retCS);
    for (int i = 0; i < MAX_RETURN_SLOTS; i++) {
        if (g_retSlots[i].inUse && g_retSlots[i].addr == addr) {
            *outOriginalByte = g_retSlots[i].originalByte;
            g_retSlots[i].refcount--;
            if (g_retSlots[i].refcount <= 0) {
                g_retSlots[i].inUse = 0;
                *outShouldRearm = 0;
            } else {
                *outShouldRearm = 1;
            }
            LeaveCriticalSection(&g_retCS);
            return 1;
        }
    }
    LeaveCriticalSection(&g_retCS);
    return 0;
}

static ThreadCallStack *get_call_stack(void) {
    ThreadCallStack *s = (ThreadCallStack *)TlsGetValue(g_tlsCallStack);
    if (s == NULL) {
        s = (ThreadCallStack *)mc_alloc(sizeof(ThreadCallStack));
        TlsSetValue(g_tlsCallStack, s);
    }
    return s;
}

static PendingStep *get_pending_step(void) {
    PendingStep *s = (PendingStep *)TlsGetValue(g_tlsPendingStep);
    if (s == NULL) {
        s = (PendingStep *)mc_alloc(sizeof(PendingStep));
        TlsSetValue(g_tlsPendingStep, s);
    }
    return s;
}

/* ------------------------------------------------------------------ */
/* Vectored exception handler                                          */
/* ------------------------------------------------------------------ */

static LONG CALLBACK VectoredHandler(PEXCEPTION_POINTERS ep) {
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    CONTEXT *ctx = ep->ContextRecord;
    BYTE *addr = (BYTE *)ep->ExceptionRecord->ExceptionAddress;

    if (code == EXCEPTION_BREAKPOINT) {
        for (int i = 0; i < NUM_HOOKS; i++) {
            if (g_entry[i].installed && g_entry[i].addr == addr) {
                LONG callId = InterlockedIncrement(&g_callCounter);
                LONG frameId;
                if (g_entry[i].def->frame_boundary) {
                    frameId = InterlockedIncrement(&g_frameCounter);
                } else {
                    frameId = g_frameCounter;
                }

                log_call_event(g_entry[i].def, addr, "enter", callId, frameId, ctx, 0, 0);

                BYTE *retAddr = *(BYTE **)(ULONG_PTR)ctx->Esp;
                if (!IsBadReadPtr(retAddr, 1)) {
                    ThreadCallStack *cs = get_call_stack();
                    if (cs != NULL && cs->top < MAX_CALL_DEPTH) {
                        cs->frames[cs->top].retAddr = retAddr;
                        cs->frames[cs->top].callId = callId;
                        cs->frames[cs->top].frameId = frameId;
                        cs->frames[cs->top].def = g_entry[i].def;
                        cs->top++;
                        return_hook_acquire(retAddr);
                    } else {
                        log_status("call-depth stack full or TLS alloc failed -- exit event dropped for one call");
                    }
                }

                DWORD oldProt;
                VirtualProtect(addr, 1, PAGE_EXECUTE_READWRITE, &oldProt);
                *addr = g_entry[i].originalByte;
                VirtualProtect(addr, 1, oldProt, &oldProt);
                PendingStep *ps = get_pending_step();
                if (ps != NULL) {
                    ps->addr = addr;
                    ps->rearm = 1;
                    ps->valid = 1;
                }
                ctx->EFlags |= 0x100; /* TF */
                return EXCEPTION_CONTINUE_EXECUTION;
            }
        }

        BYTE origByte;
        int shouldRearm;
        if (return_hook_release(addr, &origByte, &shouldRearm)) {
            ThreadCallStack *cs = get_call_stack();
            if (cs != NULL && cs->top > 0) {
                cs->top--;
                CallFrame *fr = &cs->frames[cs->top];
                log_call_event(fr->def, addr, "leave", fr->callId, fr->frameId, ctx, 1, ctx->Eax);
            } else {
                log_status("return breakpoint fired with empty call stack -- logged without call_id correlation");
            }

            DWORD oldProt;
            VirtualProtect(addr, 1, PAGE_EXECUTE_READWRITE, &oldProt);
            *addr = origByte;
            VirtualProtect(addr, 1, oldProt, &oldProt);
            PendingStep *ps = get_pending_step();
            if (ps != NULL) {
                ps->addr = addr;
                ps->rearm = shouldRearm;
                ps->valid = 1;
            }
            ctx->EFlags |= 0x100;
            return EXCEPTION_CONTINUE_EXECUTION;
        }

        return EXCEPTION_CONTINUE_SEARCH;
    }

    if (code == EXCEPTION_SINGLE_STEP) {
        PendingStep *ps = get_pending_step();
        if (ps != NULL && ps->valid) {
            ps->valid = 0;
            if (ps->rearm) {
                DWORD oldProt;
                VirtualProtect(ps->addr, 1, PAGE_EXECUTE_READWRITE, &oldProt);
                *ps->addr = 0xCC;
                VirtualProtect(ps->addr, 1, oldProt, &oldProt);
            }
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        return EXCEPTION_CONTINUE_SEARCH;
    }

    return EXCEPTION_CONTINUE_SEARCH;
}

/* ------------------------------------------------------------------ */
/* Hook install (with retry -- target DLLs may not be loaded yet)      */
/* ------------------------------------------------------------------ */

static DWORD WINAPI InitThread(LPVOID unused) {
    (void)unused;

    char logPath[MAX_PATH];
    GetModuleFileNameA(g_thisModule, logPath, MAX_PATH);
    char *slash = mc_strrchr(logPath, '\\');
    if (slash) slash[1] = 0;
    mc_strcat_n(logPath, "pakon_hooks_pid", MAX_PATH);
    char pidBuf[16];
    int pidLen = mc_u32_to_dec(GetCurrentProcessId(), pidBuf);
    pidBuf[pidLen] = 0;
    mc_strcat_n(logPath, pidBuf, MAX_PATH);
    mc_strcat_n(logPath, ".jsonl", MAX_PATH);

    InitializeCriticalSection(&g_logCS);
    InitializeCriticalSection(&g_retCS);
    g_tlsCallStack = TlsAlloc();
    g_tlsPendingStep = TlsAlloc();

    g_logFile = mc_open_append(logPath);
    if (g_logFile == INVALID_HANDLE_VALUE) {
        return 1; /* nowhere to log to -- nothing more we can safely do */
    }

    /* Self-test hooks (currently just selftest_gettickcount) only install
       if a marker file sits next to the DLL -- GetTickCount is called so
       often that leaving it hooked during a real scan would flood the
       log for no diagnostic value. Create/delete this file yourself; see
       README.md "self-test before the real thing". */
    char selftestFlagPath[MAX_PATH];
    GetModuleFileNameA(g_thisModule, selftestFlagPath, MAX_PATH);
    slash = mc_strrchr(selftestFlagPath, '\\');
    if (slash) slash[1] = 0;
    mc_strcat_n(selftestFlagPath, "selftest.flag", MAX_PATH);
    int selftestEnabled = (GetFileAttributesA(selftestFlagPath) != INVALID_FILE_ATTRIBUTES);
    if (selftestEnabled) {
        log_status("selftest.flag found -- self-test hook(s) will be installed too");
    }

    log_status("hookdll attached, installing hooks");

    g_vehHandle = AddVectoredExceptionHandler(1, VectoredHandler);
    if (!g_vehHandle) {
        log_status("AddVectoredExceptionHandler failed -- cannot install any hooks");
        return 1;
    }

    int pending = NUM_HOOKS;
    int installedOk = 0;
    const int maxAttempts = 240; /* 240 * 500ms = 120s */
    for (int attempt = 0; attempt < maxAttempts && pending > 0; attempt++) {
        pending = 0;
        for (int i = 0; i < NUM_HOOKS; i++) {
            if (g_entry[i].installed) continue;
            if (g_hookDefs[i].resolve_by_export && !selftestEnabled) continue; /* opt-in only */
            HMODULE base = GetModuleHandleA(g_hookDefs[i].dll);
            if (base == NULL) { pending++; continue; }
            BYTE *rt;
            if (g_hookDefs[i].resolve_by_export) {
                rt = (BYTE *)GetProcAddress(base, g_hookDefs[i].export_name);
                if (rt == NULL) {
                    char msg[256];
                    StrBuf sb; sb_init(&sb, msg, sizeof(msg));
                    sb_puts(&sb, "hook_failed id="); sb_puts(&sb, g_hookDefs[i].id);
                    sb_puts(&sb, " -- GetProcAddress could not find ");
                    sb_puts(&sb, g_hookDefs[i].export_name);
                    log_status(msg);
                    continue;
                }
            } else {
                rt = (BYTE *)base + (g_hookDefs[i].va - ASSUMED_BASE);
            }
            if (IsBadReadPtr(rt, 1)) {
                char msg[256];
                StrBuf sb; sb_init(&sb, msg, sizeof(msg));
                sb_puts(&sb, "hook_failed id="); sb_puts(&sb, g_hookDefs[i].id);
                sb_puts(&sb, " -- resolved address not readable");
                log_status(msg);
                continue;
            }
            DWORD oldProt;
            if (!VirtualProtect(rt, 1, PAGE_EXECUTE_READWRITE, &oldProt)) {
                char msg[256];
                StrBuf sb; sb_init(&sb, msg, sizeof(msg));
                sb_puts(&sb, "hook_failed id="); sb_puts(&sb, g_hookDefs[i].id);
                sb_puts(&sb, " -- VirtualProtect failed");
                log_status(msg);
                continue;
            }
            g_entry[i].def = &g_hookDefs[i];
            g_entry[i].addr = rt;
            g_entry[i].originalByte = *rt;
            *rt = 0xCC;
            VirtualProtect(rt, 1, oldProt, &oldProt);
            g_entry[i].installed = 1;
            installedOk++;

            char msg[256];
            StrBuf sb; sb_init(&sb, msg, sizeof(msg));
            sb_puts(&sb, "hook_installed id="); sb_puts(&sb, g_hookDefs[i].id);
            sb_puts(&sb, " module="); sb_puts(&sb, g_hookDefs[i].dll);
            sb_puts(&sb, " rt=0x"); sb_put_hex8(&sb, (unsigned long)(ULONG_PTR)rt);
            log_status(msg);
        }
        if (pending > 0) Sleep(500);
    }

    char summary[256];
    StrBuf sb; sb_init(&sb, summary, sizeof(summary));
    sb_puts(&sb, "hook install pass complete: ");
    sb_put_i32(&sb, installedOk);
    sb_puts(&sb, "/");
    sb_put_i32(&sb, NUM_HOOKS);
    sb_puts(&sb, " installed, ");
    sb_put_i32(&sb, pending);
    sb_puts(&sb, " still waiting on their module");
    log_status(summary);

    return 0;
}

/* ------------------------------------------------------------------ */
/* Entry point.                                                        */
/*                                                                      */
/* Linked with -nostartfiles (see build.sh) -- this function IS the raw */
/* PE entry point (-Wl,-e,_DllMain@12), not wrapped by any CRT DLL      */
/* startup. Its signature/calling convention must exactly match what    */
/* the Windows loader itself invokes for DLL_PROCESS_ATTACH/DETACH,     */
/* which is precisely the standard DllMain signature -- so no adapter   */
/* is needed, this just IS it.                                          */
/* ------------------------------------------------------------------ */

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD reason, LPVOID reserved) {
    (void)reserved;
    switch (reason) {
    case DLL_PROCESS_ATTACH:
        g_thisModule = hinstDLL;
        DisableThreadLibraryCalls(hinstDLL);
        /* Never do real work directly here (loader lock) -- spawn a
           thread and return immediately. */
        CreateThread(NULL, 0, InitThread, NULL, 0, NULL);
        break;
    case DLL_PROCESS_DETACH:
        if (g_vehHandle) RemoveVectoredExceptionHandler(g_vehHandle);
        for (int i = 0; i < NUM_HOOKS; i++) {
            if (g_entry[i].installed) {
                DWORD oldProt;
                VirtualProtect(g_entry[i].addr, 1, PAGE_EXECUTE_READWRITE, &oldProt);
                *g_entry[i].addr = g_entry[i].originalByte;
                VirtualProtect(g_entry[i].addr, 1, oldProt, &oldProt);
            }
        }
        if (g_logFile) CloseHandle(g_logFile);
        break;
    }
    return TRUE;
}
