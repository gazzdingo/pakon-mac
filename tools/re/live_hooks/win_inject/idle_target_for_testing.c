/*
 * idle_target_for_testing.c -- NOT part of the shipped tooling. A tiny
 * do-nothing process used only here, on the dev machine, to prove
 * injector.exe's OpenProcess/VirtualAllocEx/WriteProcessMemory/
 * CreateRemoteThread(LoadLibraryA) sequence actually works under Wine
 * against a real SEPARATE process, before trusting it against the real
 * PSI.exe on the real XP box. Not copied to the XP box, not referenced
 * by README.md's real usage instructions.
 */
#include <windows.h>
#include <stdio.h>

int main(void) {
    printf("idle target running, pid=%lu\n", GetCurrentProcessId());
    fflush(stdout);
    Sleep(30000);
    return 0;
}
