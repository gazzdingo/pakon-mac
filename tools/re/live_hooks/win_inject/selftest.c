/*
 * selftest.c -- dynamic proof that the shared generic entry/exit hooking
 * engine (hookcore.c + hookstub.S, MinHook underneath) is actually
 * transparent and calling-convention-agnostic, run under Wine on the dev
 * machine (see ../README.md "Cross-compiling and self-testing from a
 * Mac"). This is NOT a test against the real vendor DLLs (those only
 * exist on the real XP box) -- it's a test against four small synthetic
 * target functions, one per relevant x86 Windows calling convention
 * (cdecl, stdcall, thiscall, fastcall), proving the mechanism itself
 * (register/stack preservation, the return-address-swap exit technique,
 * per-thread shadow-stack correctness under real recursion and real
 * concurrency) before ever trusting it against irreplaceable hardware.
 *
 * PASS/FAIL is printed to stdout and the process exit code (0 = all
 * passed). Every test computes its OWN expected result independently of
 * the hooked call, both BEFORE hooking (a baseline) and AFTER hooking,
 * and requires the hooked call to still return the byte-identical value
 * -- proving the hook changed nothing observable about the call.
 */

#include "hookcore.h"
#include "../vendor/minhook/include/MinHook.h"
#include <stdio.h>

/* ---- test targets, one per calling convention ---------------------- */

static int __cdecl TestCdecl(int a, int b, int depth) {
    int acc = a * 3 + b * 5;
    if (depth > 0) {
        acc += TestCdecl(a + 1, b + 1, depth - 1); /* recursion: exercises
                                                        nested shadow-stack
                                                        frames on ONE hook */
    }
    return acc;
}

static int __stdcall TestStdcall(int a, int b) {
    return a - b * 2;
}

/* first arg forced into ECX (MSVC thiscall convention) */
__attribute__((thiscall))
static int TestThiscall(void *self, int x) {
    int base = (int)(DWORD_PTR)self;
    return (base & 0xffff) + x * 7;
}

/* first two int args forced into ECX/EDX (MSVC fastcall convention) */
__attribute__((fastcall))
static int TestFastcall(int a, int b, int c) {
    return a * a + b - c;
}

/* docs/74 SS47's opt-in extra-buffer-dump feature (hookcore.h's
 * ExtraDumpSpec) is only ever populated for real hook_ids in
 * hookcore_real_table.c -- selftest.exe does NOT link that file (it uses
 * this file's own synthetic 4-hook table instead, see BuildSelftestTable
 * below), so this translation unit needs its own definition of the
 * `extern const ExtraDumpSpec g_extraDumps[]` hookcore.c references. A
 * sentinel-only (empty) table is the correct thing here, not a copy of
 * the real rows: none of test_cdecl/test_stdcall/test_thiscall/
 * test_fastcall are real hook_ids, so LogExtraDumps would find no match
 * for them either way -- this also exercises (under the same Wine
 * concurrency stress every other part of this harness runs through) the
 * "scan the table, find nothing, do nothing" path safely. */
const ExtraDumpSpec g_extraDumps[] = {
    { NULL, NULL, EXTRA_DUMP_STACK_PTR, 0, 0, 0 }, /* sentinel */
};

/* ---- synthetic table builder ---------------------------------------- */

static void BuildSelftestTable(HookEngine *eng) {
    static const HookDef defs[4] = {
        { NULL, 0, "test_cdecl",    "synthetic cdecl target",    "selftest.c", 0, 1, 0, 0, NULL },
        { NULL, 0, "test_stdcall",  "synthetic stdcall target",  "selftest.c", 0, 1, 0, 0, NULL },
        { NULL, 0, "test_thiscall", "synthetic thiscall target", "selftest.c", 0, 1, 0, 0, NULL },
        { NULL, 0, "test_fastcall", "synthetic fastcall target", "selftest.c", 0, 1, 0, 0, NULL },
    };
    void *thunks[4] = { (void *)&Thunk_00, (void *)&Thunk_01,
                         (void *)&Thunk_02, (void *)&Thunk_03 };
    DWORD vas[4] = {
        (DWORD)(DWORD_PTR)&TestCdecl,
        (DWORD)(DWORD_PTR)&TestStdcall,
        (DWORD)(DWORD_PTR)&TestThiscall,
        (DWORD)(DWORD_PTR)&TestFastcall,
    };

    int i;
    eng->count = 4;
    for (i = 0; i < 4; i++) {
        eng->defs[i] = defs[i];
        eng->defs[i].va = vas[i];
        eng->defs[i].entryThunk = thunks[i];
    }
}

/* ---- driver ----------------------------------------------------------- */

static int TestCdecl_ref(int a, int b, int depth);
static int TestStdcall_ref(int a, int b);
static int TestThiscall_ref(void *self, int x);
static int TestFastcall_ref(int a, int b, int c);

static int g_failures = 0;

static void Check(const char *name, int expected, int actual) {
    if (expected == actual) {
        printf("  PASS  %-28s expected=%d actual=%d\n", name, expected, actual);
    } else {
        printf("  FAIL  %-28s expected=%d actual=%d  <-- MISMATCH\n", name, expected, actual);
        g_failures++;
    }
}

/* ---------------------------------------------------------------------
 * EXTREME concurrency stress (added 2026-08-15, investigating the
 * "stops mid-loop under real load, no shutdown message" failures seen on
 * the real XP box even after the FlushFileBuffers fix). The ORIGINAL
 * concurrency test above (one extra thread, 50 iterations) proved the
 * mechanism works under SOME concurrency, but real per-pixel/per-block
 * vendor hot paths are called far more densely, from more worker threads,
 * than that. This section specifically targets the question raised while
 * investigating: does the TLS-based per-thread shadow stack actually
 * guarantee correctness when the SAME hooked function is entered from
 * MANY different threads, some of which have NOT yet returned, at once --
 * or is there a shared, non-TLS piece of state (the global callCounter,
 * the shared SharedEntryHandler/OnReturnThunk codepath itself, MinHook's
 * own trampoline) that could be raced?
 *
 * Design: STRESS_THREAD_COUNT threads are all created BEFORE any of them
 * is allowed to call the hooked function, then held at a manual-reset
 * event (g_stressStartGate) so they all pile up waiting simultaneously;
 * releasing the gate lets every thread begin hammering the SAME hook
 * (test_fastcall) genuinely at once, rather than the earlier test's
 * naturally-staggered thread startup. Each thread computes its own
 * expected value independently (same "reference implementation, not the
 * hooked call itself" discipline as every other check in this file) using
 * inputs that are unique per-thread-per-iteration (so a value mismatch
 * can only mean real cross-call corruption, never coincidentally-equal
 * inputs masking a bug). On top of per-call correctness, this also checks
 * the engine's shared, non-TLS `callCounter` (protected only by
 * InterlockedIncrement, not the log lock) ends up EXACTLY right after
 * every thread joins -- a lost or duplicated increment would be direct,
 * unambiguous evidence of a race in that shared piece of state.
 */
#define STRESS_THREAD_COUNT      8
#define STRESS_ITERS_PER_THREAD  4000

static volatile LONG g_stressFailures = 0;
static HANDLE g_stressStartGate;

static DWORD WINAPI StressThreadProc(LPVOID param) {
    int tid = (int)(DWORD_PTR)param;
    int i;
    WaitForSingleObject(g_stressStartGate, INFINITE); /* pile up, then all go at once */
    for (i = 0; i < STRESS_ITERS_PER_THREAD; i++) {
        /* Unique-per-thread-per-iteration inputs -- a corrupted register
         * or stack slot from ANOTHER thread's concurrent call would very
         * likely produce a value that doesn't match THIS thread's own
         * independently-computed expectation. */
        int a = tid * 1000000 + i;
        int b = (tid * 37 + i) & 0xfff;
        int c = tid;
        int expected = TestFastcall_ref(a, b, c);
        int actual = TestFastcall(a, b, c);
        if (expected != actual) {
            InterlockedIncrement((LONG *)&g_stressFailures);
        }
    }
    return 0;
}

static void RunExtremeConcurrencyStress(HookEngine *eng) {
    HANDLE threads[STRESS_THREAD_COUNT];
    LONG callsBefore, callsAfter, actualNewCalls, expectedCalls;
    int t;

    printf("\n-- EXTREME concurrency stress: %d threads x %d iters/thread, "
           "SAME hook (test_fastcall), all released simultaneously --\n",
           STRESS_THREAD_COUNT, STRESS_ITERS_PER_THREAD);

    callsBefore = eng->callCounter;
    g_stressStartGate = CreateEvent(NULL, TRUE, FALSE, NULL); /* manual-reset, initially non-signaled */

    for (t = 0; t < STRESS_THREAD_COUNT; t++) {
        threads[t] = CreateThread(NULL, 0, StressThreadProc, (LPVOID)(DWORD_PTR)t, 0, NULL);
    }
    Sleep(100); /* give every thread time to reach WaitForSingleObject on the
                   gate before releasing it -- maximizes genuine simultaneity
                   rather than a staggered start */
    SetEvent(g_stressStartGate);
    WaitForMultipleObjects(STRESS_THREAD_COUNT, threads, TRUE, INFINITE);
    for (t = 0; t < STRESS_THREAD_COUNT; t++) CloseHandle(threads[t]);
    CloseHandle(g_stressStartGate);

    callsAfter = eng->callCounter;
    actualNewCalls = callsAfter - callsBefore;
    expectedCalls = (LONG)(STRESS_THREAD_COUNT * STRESS_ITERS_PER_THREAD);

    if (g_stressFailures != 0) {
        g_failures += (int)g_stressFailures;
        printf("  FAIL  stress test: %ld/%ld concurrent calls returned WRONG "
               "values -- real cross-thread corruption under load\n",
               (long)g_stressFailures, (long)expectedCalls);
    } else {
        printf("  PASS  stress test: all %ld concurrent calls across %d "
               "threads (SAME hook, released simultaneously) returned "
               "correct values\n", (long)expectedCalls, STRESS_THREAD_COUNT);
    }

    if (actualNewCalls != expectedCalls) {
        g_failures++;
        printf("  FAIL  callCounter mismatch: expected exactly %ld new "
               "InterlockedIncrement'd calls, engine recorded %ld -- "
               "evidence of a race in shared (non-TLS) engine state\n",
               (long)expectedCalls, (long)actualNewCalls);
    } else {
        printf("  PASS  callCounter exactly matches expected count (%ld) -- "
               "no lost/duplicated updates to shared engine state under "
               "max concurrency\n", (long)expectedCalls);
    }
}

static DWORD WINAPI SecondThreadProc(LPVOID param) {
    (void)param;
    int i;
    for (i = 0; i < 50; i++) {
        int expected = TestFastcall_ref(1000 + i, 7, 3);
        int actual = TestFastcall(1000 + i, 7, 3);
        if (expected != actual) {
            InterlockedIncrement((LONG *)&g_failures);
            printf("  FAIL  test_fastcall(thread2,i=%d)  expected=%d actual=%d\n",
                   i, expected, actual);
        }
    }
    return 0;
}

/* Reference (unhooked-semantics) copies of each formula, used to compute
 * expected values without relying on the (possibly-hooked) function
 * itself having been correct before hooking -- independent ground truth. */
static int TestCdecl_ref(int a, int b, int depth) {
    int acc = a * 3 + b * 5;
    if (depth > 0) acc += TestCdecl_ref(a + 1, b + 1, depth - 1);
    return acc;
}
static int TestStdcall_ref(int a, int b) { return a - b * 2; }
static int TestThiscall_ref(void *self, int x) {
    int base = (int)(DWORD_PTR)self;
    return (base & 0xffff) + x * 7;
}
static int TestFastcall_ref(int a, int b, int c) { return a * a + b - c; }

int main(void) {
    printf("=== live_hooks/win_inject self-test (run under Wine) ===\n\n");

    printf("-- baseline (unhooked) sanity: functions match their own reference --\n");
    Check("test_cdecl (unhooked)", TestCdecl_ref(2, 3, 3), TestCdecl(2, 3, 3));
    Check("test_stdcall (unhooked)", TestStdcall_ref(10, 4), TestStdcall(10, 4));
    Check("test_thiscall (unhooked)", TestThiscall_ref((void *)0x1234, 9), TestThiscall((void *)0x1234, 9));
    Check("test_fastcall (unhooked)", TestFastcall_ref(6, 2, 5), TestFastcall(6, 2, 5));

    printf("\n-- installing hooks via the real engine (MinHook + hookstub.S) --\n");
    HookEngine *eng = &g_engine;
    /* table before Init -- see hookcore.h HookCore_LoadConfig contract */
    BuildSelftestTable(eng);
    if (!HookCore_Init(eng, ".")) {
        printf("FATAL: HookCore_Init failed\n");
        return 1;
    }
    int installed = HookCore_InstallPass(eng);
    printf("installed %d/%d hooks\n", installed, eng->count);
    if (installed != eng->count) {
        printf("FATAL: not all synthetic hooks installed\n");
        return 1;
    }

    printf("\n-- post-hook: same inputs must produce byte-identical outputs --\n");
    int i;
    for (i = 0; i < 20; i++) {
        int a = i, b = i * 2, c = i + 1;
        Check("test_cdecl", TestCdecl_ref(a, b, 3), TestCdecl(a, b, 3));
        Check("test_stdcall", TestStdcall_ref(a, b), TestStdcall(a, b));
        Check("test_thiscall", TestThiscall_ref((void *)(DWORD_PTR)(a * 111), c),
                                TestThiscall((void *)(DWORD_PTR)(a * 111), c));
        Check("test_fastcall", TestFastcall_ref(a, b, c), TestFastcall(a, b, c));
    }

    printf("\n-- recursion stress on test_cdecl (nested shadow-stack frames, single thread) --\n");
    for (i = 0; i < 10; i++) {
        Check("test_cdecl (deep recursion)", TestCdecl_ref(i, i, 8), TestCdecl(i, i, 8));
    }

    printf("\n-- concurrency: second thread hammering test_fastcall while main thread also calls it --\n");
    HANDLE th = CreateThread(NULL, 0, SecondThreadProc, NULL, 0, NULL);
    for (i = 0; i < 50; i++) {
        Check("test_fastcall (main, concurrent)", TestFastcall_ref(i, 9, 2), TestFastcall(i, 9, 2));
    }
    WaitForSingleObject(th, INFINITE);
    CloseHandle(th);

    RunExtremeConcurrencyStress(eng);

    HookCore_Shutdown(eng);

    printf("\n=== %s (%d failure(s)) ===\n", g_failures == 0 ? "ALL PASS" : "FAILURES", g_failures);
    return g_failures == 0 ? 0 : 1;
}
