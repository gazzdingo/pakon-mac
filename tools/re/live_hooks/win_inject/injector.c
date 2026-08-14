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
 * USAGE
 * -----
 *     injector.exe <PSI.exe | pid> <full path to hookdll.dll>
 *
 * Exits 0 on a confirmed-successful LoadLibraryA in the target (remote
 * thread's exit code, i.e. the returned HMODULE, is nonzero), nonzero
 * otherwise, with a plain-English reason printed to stdout.
 */

#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>

static DWORD FindProcessIdByName(const char *name) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return 0;

    PROCESSENTRY32 pe;
    pe.dwSize = sizeof(pe);
    DWORD found = 0;
    int matches = 0;

    if (Process32First(snap, &pe)) {
        do {
            if (lstrcmpiA(pe.szExeFile, name) == 0) {
                matches++;
                found = pe.th32ProcessID;
            }
        } while (Process32Next(snap, &pe));
    }
    CloseHandle(snap);

    if (matches > 1) {
        printf("Multiple processes named '%s' are running -- pass a "
               "numeric PID instead to disambiguate.\n", name);
        return 0;
    }
    return found;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        printf(
            "Usage: injector.exe <PSI.exe | pid> <full path to hookdll.dll>\n"
            "\n"
            "  Injects hookdll.dll into an already-running target process\n"
            "  via classic OpenProcess/VirtualAllocEx/WriteProcessMemory/\n"
            "  CreateRemoteThread(LoadLibraryA). Run this AFTER PSI is\n"
            "  already running (see ../README.md for the full sequence).\n"
        );
        return 2;
    }

    const char *targetArg = argv[1];
    const char *dllPath = argv[2];

    DWORD pid = 0;
    {
        char *end;
        DWORD asNumber = strtoul(targetArg, &end, 10);
        if (*end == '\0' && asNumber != 0) {
            pid = asNumber;
        } else {
            pid = FindProcessIdByName(targetArg);
        }
    }
    if (pid == 0) {
        printf("Could not find a running process matching '%s'. Make sure "
               "PSI is already running (Task Manager, or `tasklist` from a "
               "cmd prompt, should show it) before running this.\n", targetArg);
        return 1;
    }
    printf("Target PID: %lu\n", pid);

    /* Resolve dllPath to an absolute path -- CreateRemoteThread's
     * LoadLibraryA call runs with the TARGET process's current directory,
     * not ours, so a relative path here would very likely fail to
     * resolve inside the target. */
    char fullDllPath[MAX_PATH];
    DWORD fullLen = GetFullPathNameA(dllPath, MAX_PATH, fullDllPath, NULL);
    if (fullLen == 0 || fullLen >= MAX_PATH) {
        printf("Could not resolve full path for '%s'.\n", dllPath);
        return 1;
    }
    DWORD attrs = GetFileAttributesA(fullDllPath);
    if (attrs == INVALID_FILE_ATTRIBUTES) {
        printf("'%s' does not exist or is not accessible.\n", fullDllPath);
        return 1;
    }
    printf("DLL path (resolved): %s\n", fullDllPath);

    HANDLE hProcess = OpenProcess(
        PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION |
        PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ,
        FALSE, pid);
    if (hProcess == NULL) {
        printf("OpenProcess failed (error %lu). Common cause: not running "
               "as the same user / not enough privilege, or the process "
               "is protected. Try running injector.exe as Administrator.\n",
               GetLastError());
        return 1;
    }

    size_t pathBytes = lstrlenA(fullDllPath) + 1;
    LPVOID remoteMem = VirtualAllocEx(hProcess, NULL, pathBytes,
                                       MEM_COMMIT | MEM_RESERVE,
                                       PAGE_READWRITE);
    if (remoteMem == NULL) {
        printf("VirtualAllocEx failed (error %lu).\n", GetLastError());
        CloseHandle(hProcess);
        return 1;
    }

    SIZE_T written = 0;
    BOOL wroteOk = WriteProcessMemory(hProcess, remoteMem, fullDllPath,
                                       pathBytes, &written);
    if (!wroteOk || written != pathBytes) {
        printf("WriteProcessMemory failed (error %lu).\n", GetLastError());
        VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return 1;
    }

    HMODULE hKernel32 = GetModuleHandleA("kernel32.dll");
    FARPROC pLoadLibraryA = GetProcAddress(hKernel32, "LoadLibraryA");
    if (pLoadLibraryA == NULL) {
        printf("Could not resolve kernel32!LoadLibraryA locally (this "
               "should never fail).\n");
        VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return 1;
    }

    HANDLE hThread = CreateRemoteThread(
        hProcess, NULL, 0,
        (LPTHREAD_START_ROUTINE)(void *)pLoadLibraryA, remoteMem, 0, NULL);
    if (hThread == NULL) {
        printf("CreateRemoteThread failed (error %lu).\n", GetLastError());
        VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return 1;
    }

    printf("Remote thread created, waiting for LoadLibraryA to return...\n");
    WaitForSingleObject(hThread, INFINITE);

    DWORD exitCode = 0;
    GetExitCodeThread(hThread, &exitCode);

    CloseHandle(hThread);
    VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
    CloseHandle(hProcess);

    if (exitCode == 0) {
        printf(
            "LoadLibraryA returned NULL in the target process -- the DLL "
            "did NOT load. Common causes: wrong architecture (hookdll.dll "
            "must be 32-bit, matching PSI.exe -- confirmed 32-bit PE32 for "
            "these vendor DLLs, docs/70 line 105), a missing dependency "
            "next to hookdll.dll, or hookdll.dll's own DllMain returning "
            "FALSE. Nothing on the real scanner was touched by this "
            "failure -- it never got far enough to install any hook.\n");
        return 1;
    }

    printf(
        "Success: hookdll.dll loaded in the target process at 0x%08lx.\n"
        "It will now try to install its hooks on a background thread and "
        "start writing a JSONL log next to hookdll.dll (or at "
        "HOOKDLL_LOG_PATH). Go trigger a real scan in PSI's own UI now.\n",
        exitCode);
    return 0;
}
