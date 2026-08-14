/*
 * hookdll.c -- the DLL injected into a real, running PSI.exe on the
 * Windows XP box. Hooks all 23 documented real addresses from
 * `hookcore_real_table.c` (a verbatim transcription of `../agent.js`'s
 * HOOKS array -- see check_table_sync.py) using the shared MinHook +
 * generic entry/exit engine in hookcore.c/hookstub.S.
 *
 * See ../README.md for the full picture. In short, on the XP box:
 *
 *     injector.exe PSI.exe hookdll.dll
 *
 * while PSI is running, then trigger a real scan. A JSONL log appears
 * next to hookdll.dll (or at HOOKDLL_LOG_PATH if that env var is set).
 *
 * WHY THE INSTALL LOOP RUNS ON A WORKER THREAD, NOT IN DllMain DIRECTLY
 * ------------------------------------------------------------------
 * DllMain runs under the loader lock. TLA.dll/TLB.dll may not be loaded
 * yet at the moment we're injected (mirrors agent.js's own 60s retry
 * loop for exactly this reason) -- blocking/sleeping in DllMain to wait
 * for them risks deadlocking the target process's loader. Standard,
 * correct practice: do only the absolute minimum in DllMain itself
 * (register the thread, note the DLL's own directory for config/log
 * paths) and do everything else -- MH_Initialize, the install-and-retry
 * loop, logging -- on a freshly spawned worker thread instead.
 *
 * BUILD NOTE: this is compiled with `-nostartfiles` and linked with
 * `-Wl,-e,_DllMain@12` (see build.sh) -- the CRT startup object is
 * dropped entirely, and the OS loader calls `DllMain` directly as this
 * DLL's actual entry point (its real stdcall/3-arg signature, decorated
 * `_DllMain@12` under i686 mingw's name-mangling, is exactly what the
 * loader itself invokes, so no CRT adapter is needed). See mincrt.h's
 * header comment for why this project's mingw-w64 toolchain needs this
 * to produce a binary that will actually start on Windows XP at all.
 */

#include "hookcore.h"
#include "mincrt.h"
#include "../vendor/minhook/include/MinHook.h"

static char g_dllDir[MAX_PATH];
static HANDLE g_workerThread;
static volatile LONG g_shuttingDown = 0;

static int CountEnabled(HookEngine *eng);

static void GetOwnDirectory(HMODULE hInst, char *out, int outSize) {
    char path[MAX_PATH];
    DWORD n = GetModuleFileNameA(hInst, path, MAX_PATH);
    char *lastSlash = NULL;
    char *p;
    if (n == 0 || n >= MAX_PATH) {
        mc_strcpy_n(out, ".", outSize);
        return;
    }
    for (p = path; *p != '\0'; p++) {
        if (*p == '\\' || *p == '/') lastSlash = p;
    }
    if (lastSlash != NULL) {
        *lastSlash = '\0';
        mc_strcpy_n(out, path, outSize);
    } else {
        mc_strcpy_n(out, ".", outSize);
    }
}

static DWORD WINAPI WorkerThread(LPVOID param) {
    int totalInstalled, attempts;
    (void)param;

    /* Table must be built BEFORE Init: HookCore_Init's config loading
     * walks eng->defs[0..eng->count) to apply per-hook defaults/overrides,
     * so the table needs to already be populated. */
    HookCore_BuildRealTable(&g_engine);

    if (!HookCore_Init(&g_engine, g_dllDir)) {
        return 1;
    }

    {
        char msg[256];
        StrBuf sb;
        sb_init(&sb, msg, sizeof(msg));
        sb_puts(&sb, "hookdll.dll attached, ");
        sb_put_u32_dec(&sb, (unsigned long)g_engine.count);
        sb_puts(&sb, " hooks defined (PakonIMAu.dll/TLA.dll/TLB.dll targets) -- see hooks.cfg next to this DLL to enable/disable individual hooks without a rebuild");
        HookCore_LogStatus(&g_engine, msg);
    }

    /* Same spirit as agent.js's installHooks() retry loop: try
     * immediately, then poll every 500ms for up to 60s for any hook
     * whose DLL hasn't loaded into this process yet. */
    totalInstalled = HookCore_InstallPass(&g_engine);
    attempts = 0;
    while (totalInstalled < CountEnabled(&g_engine) && attempts < 120 &&
           !g_shuttingDown) {
        Sleep(500);
        totalInstalled += HookCore_InstallPass(&g_engine);
        attempts++;
    }

    {
        char msg[256];
        StrBuf sb;
        sb_init(&sb, msg, sizeof(msg));
        sb_puts(&sb, "install pass complete: ");
        sb_put_u32_dec(&sb, (unsigned long)totalInstalled);
        sb_puts(&sb, "/");
        sb_put_u32_dec(&sb, (unsigned long)CountEnabled(&g_engine));
        sb_puts(&sb, " enabled hook(s) installed after ");
        sb_put_u32_dec(&sb, (unsigned long)attempts);
        sb_puts(&sb, " attempt(s)");
        HookCore_LogStatus(&g_engine, msg);
    }

    return 0;
}

static int CountEnabled(HookEngine *eng) {
    int i, n = 0;
    for (i = 0; i < eng->count; i++) if (eng->rt[i].enabled) n++;
    return n;
}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    (void)lpvReserved;
    switch (fdwReason) {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(hinstDLL);
        GetOwnDirectory(hinstDLL, g_dllDir, sizeof(g_dllDir));
        g_workerThread = CreateThread(NULL, 0, WorkerThread, NULL, 0, NULL);
        break;
    case DLL_PROCESS_DETACH:
        InterlockedExchange(&g_shuttingDown, 1);
        if (g_workerThread != NULL) {
            /* Best-effort: give the worker a moment, but don't block
             * process exit indefinitely on it. */
            WaitForSingleObject(g_workerThread, 2000);
            CloseHandle(g_workerThread);
        }
        HookCore_Shutdown(&g_engine);
        break;
    default:
        break;
    }
    return TRUE;
}
