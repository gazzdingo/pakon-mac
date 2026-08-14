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
 */

#include "hookcore.h"
#include "../vendor/minhook/include/MinHook.h"

static char g_dllDir[MAX_PATH];
static HMODULE g_hInst;
static HANDLE g_workerThread;
static volatile LONG g_shuttingDown = 0;

static int CountEnabled(HookEngine *eng);

static void GetOwnDirectory(HMODULE hInst, char *out, size_t outSize) {
    char path[MAX_PATH];
    DWORD n = GetModuleFileNameA(hInst, path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        lstrcpyA(out, ".");
        return;
    }
    char *lastSlash = NULL;
    char *p = path;
    while (*p != '\0') {
        if (*p == '\\' || *p == '/') lastSlash = p;
        p++;
    }
    if (lastSlash != NULL) {
        *lastSlash = '\0';
        lstrcpynA(out, path, (int)outSize);
    } else {
        lstrcpyA(out, ".");
    }
}

static DWORD WINAPI WorkerThread(LPVOID param) {
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
        wsprintfA(msg, "hookdll.dll attached, %d hooks defined (PakonIMAu.dll/TLA.dll/TLB.dll targets) -- see hooks.cfg next to this DLL to enable/disable individual hooks without a rebuild", g_engine.count);
        HookCore_LogStatus(&g_engine, msg);
    }

    /* Same spirit as agent.js's installHooks() retry loop: try
     * immediately, then poll every 500ms for up to 60s for any hook
     * whose DLL hasn't loaded into this process yet. */
    int totalInstalled = HookCore_InstallPass(&g_engine);
    int attempts = 0;
    while (totalInstalled < CountEnabled(&g_engine) && attempts < 120 &&
           !g_shuttingDown) {
        Sleep(500);
        totalInstalled += HookCore_InstallPass(&g_engine);
        attempts++;
    }

    {
        char msg[256];
        wsprintfA(msg, "install pass complete: %d/%d enabled hook(s) installed after %d attempt(s)",
                  totalInstalled, CountEnabled(&g_engine), attempts);
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
        g_hInst = hinstDLL;
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
