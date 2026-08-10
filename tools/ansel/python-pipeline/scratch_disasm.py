import sys
import struct
from pathlib import Path
from capstone import *
import pefile

DLL_PATH = "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll"
IMAGE_BASE = 0x10000000

def main():
    if not Path(DLL_PATH).is_file():
        print("DLL not found")
        return 1
        
    pe = pefile.PE(DLL_PATH)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    
    def disasm_func(name, va, size=0x200):
        rva = va - IMAGE_BASE
        data = pe.get_memory_mapped_image()[rva:rva+size]
        print(f"--- {name} @ {hex(va)} ---")
        for i in md.disasm(data, va):
            print(f"0x{i.address:x}:\t{i.mnemonic}\t{i.op_str}")
            if i.mnemonic == 'ret':
                break
        print()

    disasm_func("analyzePass1", 0x10123980, 0x400)
    disasm_func("analyzePass2", 0x10123cc0, 0x400)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
