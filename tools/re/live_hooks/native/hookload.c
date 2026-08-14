/*
 * hookload.c -- standalone injector. Run this, pick the target process
 * (e.g. pakon.exe / PSI.exe -- whatever your PSI executable is actually
 * named), and it loads hookdll.dll into it via the classic
 * LoadLibraryA-through-CreateRemoteThread technique. No Python, no Frida,
 * no build step at runtime -- just this .exe and hookdll.dll sitting next
 * to it.
 *
 * Built with NO C runtime at all (see minicrt.h / build.sh) -- imports
 * nothing but KERNEL32.dll, verified by build.sh on every build, so
 * there's no "which CRT does this actually need" question hanging over
 * whether it runs on the real target (Windows XP, 32-bit -- docs/68).
 *
 * Usage:
 *   hookload.exe                 interactive picker over all running processes
 *   hookload.exe pakon           match any running process whose name
 *                                 contains "pakon" (case-insensitive)
 *   hookload.exe 4212            attach directly to PID 4212
 *
 * See ../README.md for the full walkthrough and for why this exists
 * alongside the Frida-based path (short version: this targets genuine
 * 32-bit Windows XP directly, which current Frida/Python cannot).
 */

#include <windows.h>
#include <tlhelp32.h>
#include "minicrt.h"

#define MAX_PROCS 1024
#define MAX_NAME 260

typedef struct {
    DWORD pid;
    char name[MAX_NAME];
} ProcInfo;

static HANDLE g_stdout;
static HANDLE g_stdin;

static void out(const char *s) {
    DWORD written;
    WriteFile(g_stdout, s, (DWORD)mc_strlen(s), &written, NULL);
}

static void out_u32(unsigned long v) {
    char tmp[16];
    int n = mc_u32_to_dec(v, tmp);
    tmp[n] = 0;
    out(tmp);
}

/* Right-pads a PID into a 7-char field for the process table. */
static void out_pid_padded(unsigned long v) {
    char tmp[16];
    int n = mc_u32_to_dec(v, tmp);
    out(tmp);
    for (int i = n; i < 8; i++) out(" ");
}

static int read_line(char *buf, int cap) {
    DWORD read;
    int i = 0;
    char c;
    while (i < cap - 1) {
        if (!ReadFile(g_stdin, &c, 1, &read, NULL) || read == 0) break;
        if (c == '\n') break;
        if (c == '\r') continue;
        buf[i++] = c;
    }
    buf[i] = 0;
    return i;
}

static int enumerate_processes(ProcInfo *out_arr, int maxCount) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return -1;
    PROCESSENTRY32 pe;
    pe.dwSize = sizeof(pe);
    int n = 0;
    if (Process32First(snap, &pe)) {
        do {
            if (n >= maxCount) break;
            out_arr[n].pid = pe.th32ProcessID;
            mc_strcpy_n(out_arr[n].name, pe.szExeFile, MAX_NAME);
            n++;
        } while (Process32Next(snap, &pe));
    }
    CloseHandle(snap);
    return n;
}

static void print_list(ProcInfo *procs, int n) {
    out("\n  PID     Process\n  ------  --------------------------------\n");
    for (int i = 0; i < n; i++) {
        out("  ");
        out_pid_padded(procs[i].pid);
        out(procs[i].name);
        out("\n");
    }
    out("\n");
}

/* Same as print_list but over an index set into a larger array -- avoids
   copying a (potentially large, MAX_PROCS-sized) ProcInfo array. */
static void print_list_indexed(ProcInfo *procs, const int *idx, int count) {
    out("\n  PID     Process\n  ------  --------------------------------\n");
    for (int i = 0; i < count; i++) {
        out("  ");
        out_pid_padded(procs[idx[i]].pid);
        out(procs[idx[i]].name);
        out("\n");
    }
    out("\n");
}

static int resolve_target(const char *arg, ProcInfo *procs, int n, DWORD *outPid, char *outName) {
    char line[256];
    if (arg == NULL) {
        print_list(procs, n);
        out("Enter a PID, or part of a process name (e.g. \"pakon\" or \"psi\"): ");
        if (read_line(line, sizeof(line)) <= 0) return 0;
        arg = line;
    }

    if (mc_is_all_digits(arg)) {
        unsigned long pid = mc_atoul(arg);
        for (int i = 0; i < n; i++) {
            if (procs[i].pid == pid) {
                *outPid = pid;
                mc_strcpy_n(outName, procs[i].name, MAX_NAME);
                return 1;
            }
        }
        out("No running process with that PID.\n");
        return 0;
    }

    int matchIdx[MAX_PROCS];
    int matchCount = 0;
    for (int i = 0; i < n; i++) {
        if (mc_contains_ci(procs[i].name, arg)) matchIdx[matchCount++] = i;
    }
    if (matchCount == 1) {
        *outPid = procs[matchIdx[0]].pid;
        mc_strcpy_n(outName, procs[matchIdx[0]].name, MAX_NAME);
        return 1;
    } else if (matchCount == 0) {
        out("No running process name contains that text.\n");
        return 0;
    } else {
        out("That matches multiple running processes:\n");
        print_list_indexed(procs, matchIdx, matchCount);
        out("Re-run with the exact PID from the list above.\n");
        return 0;
    }
}

void MyMain(void) {
    g_stdout = GetStdHandle(STD_OUTPUT_HANDLE);
    g_stdin = GetStdHandle(STD_INPUT_HANDLE);

    out("hookload -- native (Frida-free) Pakon pipeline hook injector\n");
    out("Uses INT3/VEH breakpoints, one-byte patches only, per-thread safe.\n");
    out("See tools/re/live_hooks/README.md for the full hook list and citations.\n");

    /* Heap-allocated, not a ~270KB stack array -- this program is linked
       -nostartfiles with a hand-written entry point (see build.sh), so
       there's no CRT-provided __chkstk-safe huge-frame handling to lean
       on; keep every stack frame small and put anything large on the
       heap instead. */
    ProcInfo *procs = (ProcInfo *)mc_alloc(sizeof(ProcInfo) * MAX_PROCS);
    if (!procs) {
        out("Out of memory.\n");
        ExitProcess(1);
    }
    int n = enumerate_processes(procs, MAX_PROCS);
    if (n < 0) {
        out("CreateToolhelp32Snapshot failed.\n");
        ExitProcess(1);
    }

    char argBuf[256];
    const char *arg = mc_get_arg1(argBuf, sizeof(argBuf)) ? argBuf : NULL;

    DWORD pid = 0;
    char name[MAX_NAME];
    name[0] = 0; /* NOT "= {0}" -- GCC lowers a whole-array initializer to
                    an implicit memset() call, which this toolchain
                    resolves through api-ms-win-crt-string-l1-1-0.dll (not
                    present on XP); resolve_target() always fills this
                    properly before it's read, so a single NUL is enough. */
    if (!resolve_target(arg, procs, n, &pid, name)) {
        ExitProcess(1);
    }
    out("Target: "); out(name); out(" (PID "); out_u32(pid); out(")\n");

    /* hookdll.dll must sit next to this exe. */
    char dllPath[MAX_PATH];
    GetModuleFileNameA(NULL, dllPath, MAX_PATH);
    char *slash = mc_strrchr(dllPath, '\\');
    if (slash) slash[1] = 0;
    mc_strcat_n(dllPath, "hookdll.dll", MAX_PATH);

    DWORD attrs = GetFileAttributesA(dllPath);
    if (attrs == INVALID_FILE_ATTRIBUTES) {
        out("Cannot find "); out(dllPath); out(" -- it must be in the same directory as this exe.\n");
        ExitProcess(1);
    }

    HANDLE hProc = OpenProcess(PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION |
                                PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ,
                                FALSE, pid);
    if (!hProc) {
        out("OpenProcess failed -- try running this as the same user as the target, or as Administrator.\n");
        ExitProcess(1);
    }

    int pathLen = mc_strlen(dllPath) + 1;
    LPVOID remoteBuf = VirtualAllocEx(hProc, NULL, (SIZE_T)pathLen, MEM_COMMIT, PAGE_READWRITE);
    if (!remoteBuf) {
        out("VirtualAllocEx failed.\n");
        CloseHandle(hProc);
        ExitProcess(1);
    }
    if (!WriteProcessMemory(hProc, remoteBuf, dllPath, (SIZE_T)pathLen, NULL)) {
        out("WriteProcessMemory failed.\n");
        VirtualFreeEx(hProc, remoteBuf, 0, MEM_RELEASE);
        CloseHandle(hProc);
        ExitProcess(1);
    }

    HMODULE hKernel32 = GetModuleHandleA("kernel32.dll");
    FARPROC pLoadLibraryA = GetProcAddress(hKernel32, "LoadLibraryA");

    DWORD remoteTid = 0;
    HANDLE hRemoteThread = CreateRemoteThread(
        hProc, NULL, 0, (LPTHREAD_START_ROUTINE)pLoadLibraryA, remoteBuf, 0, &remoteTid);
    if (!hRemoteThread) {
        out("CreateRemoteThread failed.\n");
        VirtualFreeEx(hProc, remoteBuf, 0, MEM_RELEASE);
        CloseHandle(hProc);
        ExitProcess(1);
    }

    out("Injecting "); out(dllPath); out(" into PID "); out_u32(pid); out("...\n");
    DWORD waitResult = WaitForSingleObject(hRemoteThread, 15000);
    DWORD exitCode = 0;
    GetExitCodeThread(hRemoteThread, &exitCode);
    VirtualFreeEx(hProc, remoteBuf, 0, MEM_RELEASE);
    CloseHandle(hRemoteThread);
    CloseHandle(hProc);

    if (waitResult != WAIT_OBJECT_0) {
        out("Remote LoadLibraryA thread did not finish within 15s.\n");
        ExitProcess(1);
    }
    if (exitCode == 0) {
        out("LoadLibraryA returned NULL in the remote process -- injection failed.\n");
        out("Check that hookdll.dll is 32-bit, matching the target process.\n");
        ExitProcess(1);
    }

    out("\nInjected OK.\n");
    out("hookdll.dll is now waiting (up to 120s) for PakonIMAu.dll / TLA.dll / TLB.dll to be\n");
    out("loaded if they aren't already, then installing its hooks.\n\n");

    char logDir[MAX_PATH];
    GetModuleFileNameA(NULL, logDir, MAX_PATH);
    slash = mc_strrchr(logDir, '\\');
    if (slash) slash[1] = 0;
    out("Log file: "); out(logDir); out("pakon_hooks_pid"); out_u32(pid); out(".jsonl\n");
    out("Tail it (or open in a text editor) while you trigger a real scan in the target's own UI.\n");

    ExitProcess(0);
}
