/*
 * injector.c -- loads hookdll.dll into a running target process by the
 * classic OpenProcess + VirtualAllocEx + WriteProcessMemory +
 * CreateRemoteThread(LoadLibraryA) technique.
 *
 * WHY THIS CLASSIC TECHNIQUE, AND WHY IT'S FINE ON XP SPECIFICALLY
 * ------------------------------------------------------------------
 * This exact injection method has one well-known fragility on modern
 * Windows: ASLR means kernel32.dll (and therefore LoadLibraryA's address)
 * is NOT guaranteed to load at the same base address in the injector's
 * own process as in the target process, so "look up LoadLibraryA's
 * address locally and pass it to CreateRemoteThread in the OTHER
 * process" can resolve to the wrong address. Windows XP has NO ASLR at
 * all (introduced in Vista) -- kernel32.dll loads at the exact same base
 * address in every process on a given XP machine, every time, until
 * reboot. So this classic technique is not just "probably fine", it's
 * the textbook-correct approach for this specific target OS -- no need
 * for the extra defenses (manual PE mapping, remapping kernel32's export
 * table into the target, etc.) that would matter on a modern Windows
 * target. docs/68-handover.md confirms this project's target is
 * genuinely "32-bit Windows XP-only" (line 10).
 *
 * BUILD NOTE: compiled with `-nostartfiles`, linked with `-Wl,-e,_MyMain`
 * -- no CRT startup, no `argc`/`argv` provided by a CRT wrapper. The
 * process's raw command line is parsed by hand (mincrt.h's mc_get_argn,
 * built on GetCommandLineA) and every exit path calls ExitProcess()
 * itself, since there is no CRT `main`-return-to-exit-code translation
 * without it. See mincrt.h's header comment for why this toolchain needs
 * this to produce a binary that will actually start on Windows XP.
 *
 * USAGE
 * -----
 *     injector.exe <PSI.exe | pid> <full path to hookdll.dll>
 *
 * Exits 0 on a confirmed-successful LoadLibraryA in the target (remote
 * thread's exit code, i.e. the returned HMODULE, is nonzero), nonzero
 * otherwise, with a plain-English reason printed to the console.
 */

#include <windows.h>
#include <tlhelp32.h>
#include "mincrt.h"

static void Say(const char *s) { mc_console_write(s); }

static void SayLine(const char *s) {
    mc_console_write(s);
    mc_console_write("\r\n");
}

static void SayU32Line(const char *prefix, unsigned long v, const char *suffix) {
    char buf[16];
    StrBuf sb;
    Say(prefix);
    sb_init(&sb, buf, sizeof(buf));
    sb_put_u32_dec(&sb, v);
    Say(buf);
    SayLine(suffix ? suffix : "");
}

static void SayHex32Line(const char *prefix, unsigned long v, const char *suffix) {
    char buf[10];
    StrBuf sb;
    Say(prefix);
    sb_init(&sb, buf, sizeof(buf));
    sb_put_hex8(&sb, v);
    Say(buf);
    SayLine(suffix ? suffix : "");
}

static DWORD FindProcessIdByName(const char *name) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    PROCESSENTRY32 pe;
    DWORD found = 0;
    int matches = 0;

    if (snap == INVALID_HANDLE_VALUE) return 0;

    pe.dwSize = sizeof(pe);
    if (Process32First(snap, &pe)) {
        do {
            if (mc_streq_ci(pe.szExeFile, name)) {
                matches++;
                found = pe.th32ProcessID;
            }
        } while (Process32Next(snap, &pe));
    }
    CloseHandle(snap);

    if (matches > 1) {
        SayLine("Multiple processes with that name are running -- pass a numeric PID instead to disambiguate.");
        return 0;
    }
    return found;
}

/* Custom entry point (see build.sh: -Wl,-e,_MyMain). Every path out of
 * this function calls ExitProcess itself -- there is no CRT to return
 * to. */
void MyMain(void) {
    char arg1[MAX_PATH], arg2[MAX_PATH];
    DWORD pid = 0;
    char fullDllPath[MAX_PATH];
    DWORD fullLen;
    DWORD attrs;
    HANDLE hProcess;
    SIZE_T pathBytes;
    LPVOID remoteMem;
    SIZE_T written;
    BOOL wroteOk;
    HMODULE hKernel32;
    FARPROC pLoadLibraryA;
    HANDLE hThread;
    DWORD exitCode;

    if (!mc_get_argn(1, arg1, sizeof(arg1)) || !mc_get_argn(2, arg2, sizeof(arg2))) {
        SayLine("Usage: injector.exe <PSI.exe | pid> <full path to hookdll.dll>");
        SayLine("");
        SayLine("  Injects hookdll.dll into an already-running target process via");
        SayLine("  classic OpenProcess/VirtualAllocEx/WriteProcessMemory/");
        SayLine("  CreateRemoteThread(LoadLibraryA). Run this AFTER PSI is already");
        SayLine("  running (see ../README.md for the full sequence).");
        ExitProcess(2);
    }

    if (mc_is_all_digits(arg1)) {
        pid = mc_atoul(arg1);
    } else {
        pid = FindProcessIdByName(arg1);
    }
    if (pid == 0) {
        Say("Could not find a running process matching '");
        Say(arg1);
        SayLine("'. Make sure PSI is already running (Task Manager, or `tasklist`");
        SayLine("from a cmd prompt, should show it) before running this.");
        ExitProcess(1);
    }
    SayU32Line("Target PID: ", pid, "");

    /* Resolve to an absolute path -- CreateRemoteThread's LoadLibraryA
     * call runs with the TARGET process's current directory, not ours,
     * so a relative path here would very likely fail to resolve inside
     * the target. */
    fullLen = GetFullPathNameA(arg2, MAX_PATH, fullDllPath, NULL);
    if (fullLen == 0 || fullLen >= MAX_PATH) {
        Say("Could not resolve full path for '"); Say(arg2); SayLine("'.");
        ExitProcess(1);
    }
    attrs = GetFileAttributesA(fullDllPath);
    if (attrs == INVALID_FILE_ATTRIBUTES) {
        Say("'"); Say(fullDllPath); SayLine("' does not exist or is not accessible.");
        ExitProcess(1);
    }
    Say("DLL path (resolved): "); SayLine(fullDllPath);

    hProcess = OpenProcess(
        PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION |
        PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ,
        FALSE, pid);
    if (hProcess == NULL) {
        SayU32Line("OpenProcess failed (error ", GetLastError(),
                    "). Common cause: not running as the same user / not enough");
        SayLine("privilege, or the process is protected. Try running injector.exe as Administrator.");
        ExitProcess(1);
    }

    pathBytes = mc_strlen(fullDllPath) + 1;
    remoteMem = VirtualAllocEx(hProcess, NULL, pathBytes,
                                MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (remoteMem == NULL) {
        SayU32Line("VirtualAllocEx failed (error ", GetLastError(), ").");
        CloseHandle(hProcess);
        ExitProcess(1);
    }

    written = 0;
    wroteOk = WriteProcessMemory(hProcess, remoteMem, fullDllPath, pathBytes, &written);
    if (!wroteOk || written != pathBytes) {
        SayU32Line("WriteProcessMemory failed (error ", GetLastError(), ").");
        VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        ExitProcess(1);
    }

    hKernel32 = GetModuleHandleA("kernel32.dll");
    pLoadLibraryA = GetProcAddress(hKernel32, "LoadLibraryA");
    if (pLoadLibraryA == NULL) {
        SayLine("Could not resolve kernel32!LoadLibraryA locally (this should never fail).");
        VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        ExitProcess(1);
    }

    hThread = CreateRemoteThread(
        hProcess, NULL, 0,
        (LPTHREAD_START_ROUTINE)(void *)pLoadLibraryA, remoteMem, 0, NULL);
    if (hThread == NULL) {
        SayU32Line("CreateRemoteThread failed (error ", GetLastError(), ").");
        VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        ExitProcess(1);
    }

    SayLine("Remote thread created, waiting for LoadLibraryA to return...");
    WaitForSingleObject(hThread, INFINITE);

    exitCode = 0;
    GetExitCodeThread(hThread, &exitCode);

    CloseHandle(hThread);
    VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
    CloseHandle(hProcess);

    if (exitCode == 0) {
        SayLine("LoadLibraryA returned NULL in the target process -- the DLL did NOT load.");
        SayLine("Common causes: wrong architecture (hookdll.dll must be 32-bit, matching");
        SayLine("PSI.exe -- confirmed 32-bit PE32 for these vendor DLLs, docs/70 line 105),");
        SayLine("a missing dependency next to hookdll.dll, or hookdll.dll's own DllMain");
        SayLine("returning FALSE. Nothing on the real scanner was touched by this failure");
        SayLine("-- it never got far enough to install any hook.");
        ExitProcess(1);
    }

    SayHex32Line("Success: hookdll.dll loaded in the target process at 0x", exitCode, ".");
    SayLine("It will now try to install its hooks on a background thread and start");
    SayLine("writing a JSONL log next to hookdll.dll (or at HOOKDLL_LOG_PATH). Go");
    SayLine("trigger a real scan in PSI's own UI now.");
    ExitProcess(0);
}
